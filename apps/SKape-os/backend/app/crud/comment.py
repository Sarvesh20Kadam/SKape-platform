from types import SimpleNamespace

from sqlalchemy.orm import Session

from app.crud.activity import log_activity
from app.exceptions import ForbiddenException
from app.models.comment import Comment
from app.models.task import Task
from app.schemas.comment import (
    CommentCreate,
    CommentUpdate,
)


def _persist_with_audit(
    db: Session,
    *,
    action: str,
    entity_id: int,
    user_id: int,
    organization_id: int,
) -> None:
    """
    Flush the pending comment change and the audit row,
    then commit them together.

    A failure rolls both back so a comment mutation cannot
    remain without its audit record, and an audit record
    cannot remain without the mutation.
    """

    try:
        db.flush()

        log_activity(
            db=db,
            action=action,
            entity="comment",
            entity_id=entity_id,
            user_id=user_id,
            organization_id=organization_id,
        )

        db.commit()

    except Exception:
        db.rollback()
        raise


def _snapshot(comment: Comment):
    return SimpleNamespace(
        id=comment.id,
        content=comment.content,
        task_id=comment.task_id,
        user_id=comment.user_id,
        organization_id=comment.organization_id,
        created_at=comment.created_at,
    )


def create_comment(
    db: Session,
    comment: CommentCreate,
    user_id: int,
    organization_id: int,
):
    # -------------------------------------------------
    # Validate task belongs to current organization
    # -------------------------------------------------

    task = (
        db.query(Task)
        .filter(
            Task.id == comment.task_id,
            Task.organization_id == organization_id,
        )
        .first()
    )

    if task is None:
        raise ValueError(
            "Task not found in this organization."
        )

    # -------------------------------------------------
    # Create comment
    # -------------------------------------------------

    db_comment = Comment(
        content=comment.content.strip(),
        task_id=comment.task_id,
        user_id=user_id,
        organization_id=organization_id,
    )

    db.add(db_comment)

    # Flush first so the audit row receives the generated id.
    # The activity insert and the final commit stay in _persist_with_audit,
    # which rolls the comment back if auditing fails.
    try:
        db.flush()
        entity_id = db_comment.id

    except Exception:
        db.rollback()
        raise

    _persist_with_audit(
        db=db,
        action="created",
        entity_id=entity_id,
        user_id=user_id,
        organization_id=organization_id,
    )

    db.refresh(db_comment)

    return db_comment


def get_comments(
    db: Session,
    task_id: int,
    organization_id: int,
    skip: int = 0,
    limit: int = 10,
):
    # -------------------------------------------------
    # Only return comments for a task belonging
    # to the current organization
    # -------------------------------------------------

    task = (
        db.query(Task)
        .filter(
            Task.id == task_id,
            Task.organization_id == organization_id,
        )
        .first()
    )

    if task is None:
        return []

    return (
        db.query(Comment)
        .filter(
            Comment.task_id == task_id,
            Comment.organization_id == organization_id,
        )
        .order_by(Comment.created_at.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def update_comment(
    db: Session,
    comment_id: int,
    organization_id: int,
    user_id: int,
    user_role: str,
    updated_comment: CommentUpdate,
):
    comment = (
        db.query(Comment)
        .filter(
            Comment.id == comment_id,
            Comment.organization_id == organization_id,
        )
        .first()
    )

    if comment is None:
        return None

    # -------------------------------------------------
    # Authorization
    # Owner/Admin can edit any comment in their org.
    # Manager/Employee can edit only their own comment.
    # -------------------------------------------------

    if comment.user_id != user_id and user_role not in {
        "owner",
        "admin",
    }:
        raise ForbiddenException(
            "You can only edit your own comments."
        )

    # -------------------------------------------------
    # Validate content
    # -------------------------------------------------

    content = updated_comment.content.strip()

    if not content:
        raise ValueError(
            "Comment content cannot be empty."
        )

    comment.content = content

    # -------------------------------------------------
    # Audit activity + transaction
    # -------------------------------------------------

    _persist_with_audit(
        db=db,
        action="updated",
        entity_id=comment.id,
        user_id=user_id,
        organization_id=organization_id,
    )

    db.refresh(comment)

    return comment


def delete_comment(
    db: Session,
    comment_id: int,
    organization_id: int,
    user_id: int,
):
    comment = (
        db.query(Comment)
        .filter(
            Comment.id == comment_id,
            Comment.organization_id == organization_id,
        )
        .first()
    )

    if comment is None:
        return None

    # Capture the response before commit expires the deleted row.
    snapshot = _snapshot(comment)
    deleted_comment_id = comment.id

    db.delete(comment)

    _persist_with_audit(
        db=db,
        action="deleted",
        entity_id=deleted_comment_id,
        user_id=user_id,
        organization_id=organization_id,
    )

    return snapshot
