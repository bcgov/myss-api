from fastapi import Depends, HTTPException, status
from app.auth.dependencies import get_current_user
from app.auth.models import UserContext, UserRole


async def require_worker_role(user: UserContext = Depends(get_current_user)) -> UserContext:
    """Require WORKER or ADMIN role with IDIR username."""
    if user.role not in (UserRole.WORKER, UserRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Worker role required")
    if not user.idir_username:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="IDIR authentication required")
    return user


async def require_super_admin(user: UserContext = Depends(require_worker_role)) -> UserContext:
    """Require SUPER_ADMIN role (MYSS_Admins group)."""
    # In production, resolve from IDIR groups in the JWT
    # For now, check that user.role is ADMIN
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super admin role required")
    return user
