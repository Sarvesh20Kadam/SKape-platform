from sqlalchemy.orm import Session
from app.crud.activity import log_activity
from app.models.comment import Comment
from app.schemas.comment import (
    CommentCreate,
    CommentUpdate,
)


def create_comment(
    db: Session,
    comment: CommentCreate,
    user_id: int,
    organization_id: int
):
    db_comment = Comment(
        content=comment.content,
        task_id=comment.task_id,
        user_id=user_id,
        organization_id=organization_id,
    )

    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)

    log_activity(
        db=db,
        action="created",
        entity="comment",
        entity_id=db_comment.id,
        user_id=user_id,
        organization_id=organization_id
    )

    return db_comment


def get_comments(
    db: Session,
    task_id: int,
    organization_id: int,
    skip: int = 0,
    limit: int = 10
):
    return (
        db.query(Comment)
        .filter(
            Comment.task_id == task_id,
            Comment.organization_id == organization_id
        )
        .offset(skip)
        .limit(limit)
        .all()
    )


def update_comment(
    db: Session,
    comment_id: int,
    organization_id: int,
    user_id: int,
    updated_comment: CommentUpdate
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

    comment.content = updated_comment.content

    db.commit()
    db.refresh(comment)

    print("COMMENT UPDATE FUNCTION EXECUTED")

    log_activity(
        db=db,
        action="updated",
        entity="comment",
        entity_id=comment.id,
        user_id=user_id,
        organization_id=organization_id
    )

    return comment


def delete_comment(
    db: Session,
    comment_id: int,
    organization_id: int,
    user_id: int
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

    deleted_comment_id = comment.id

    db.delete(comment)
    db.commit()

    print("COMMENT DELETE FUNCTION EXECUTED")

    log_activity(
        db=db,
        action="deleted",
        entity="comment",
        entity_id=deleted_comment_id,
        user_id=user_id,
        organization_id=organization_id
    )

    return comment