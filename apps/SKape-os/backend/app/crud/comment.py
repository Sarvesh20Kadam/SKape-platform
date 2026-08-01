from sqlalchemy.orm import Session

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

    return db_comment


def get_comments(
    db: Session,
    task_id: int,
    organization_id: int
):
    return (
        db.query(Comment)
        .filter(
            Comment.task_id == task_id,
            Comment.organization_id == organization_id,
        )
        .all()
    )


def update_comment(
    db: Session,
    comment_id: int,
    content: str,
    organization_id: int
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

    comment.content = content

    db.commit()
    db.refresh(comment)

    return comment


def delete_comment(
    db: Session,
    comment_id: int,
    organization_id: int
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

    db.delete(comment)
    db.commit()

    return comment