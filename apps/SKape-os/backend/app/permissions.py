from fastapi import Depends, HTTPException

from app.dependencies import get_current_user


def require_role(*allowed_roles):
    def checker(current_user=Depends(get_current_user)):
        if current_user.get("role") not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to perform this action."
            )

        return current_user

    return checker