from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.permissions import require_role
from app.exceptions import NotFoundException

from app.crud.comment import (
    create_comment,
    get_comments,
    update_comment,
    delete_comment,
)

from app.schemas.comment import (
    CommentCreate,
    CommentUpdate,
    CommentResponse,
)


router = APIRouter(
    prefix="/comments",
    tags=["Comments"],
)


# ============================================================
# CREATE COMMENT
# ============================================================

@router.post(
    "/",
    response_model=CommentResponse,
)
def create(
    comment: CommentCreate,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role(
            "owner",
            "admin",
            "manager",
            "employee",
        )
    ),
):
    try:
        return create_comment(
            db=db,
            comment=comment,
            user_id=current_user.id,
            organization_id=current_user.organization_id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


# ============================================================
# GET COMMENTS FOR TASK
# ============================================================

@router.get(
    "/{task_id}",
    response_model=List[CommentResponse],
)
def get_all(
    task_id: int,
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role(
            "owner",
            "admin",
            "manager",
            "employee",
        )
    ),
):
    return get_comments(
        db=db,
        task_id=task_id,
        organization_id=current_user.organization_id,
        skip=skip,
        limit=limit,
    )


# ============================================================
# UPDATE COMMENT
# ============================================================

@router.put(
    "/{comment_id}",
    response_model=CommentResponse,
)
def update(
    comment_id: int,
    comment: CommentUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role(
            "owner",
            "admin",
            "manager",
            "employee",
        )
    ),
):
    try:
        updated = update_comment(
            db=db,
            comment_id=comment_id,
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            updated_comment=comment,
        )

        if updated is None:
            raise NotFoundException("Comment")

        return updated

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


# ============================================================
# DELETE COMMENT
# ============================================================

@router.delete(
    "/{comment_id}",
    response_model=CommentResponse,
)
def delete(
    comment_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role(
            "owner",
            "admin",
            "manager",
        )
    ),
):
    deleted = delete_comment(
        db=db,
        comment_id=comment_id,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
    )

    if deleted is None:
        raise HTTPException(
            status_code=404,
            detail="Comment not found",
        )

    return deleted