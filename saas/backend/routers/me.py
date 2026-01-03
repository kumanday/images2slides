from __future__ import annotations

from fastapi import APIRouter, Depends

from ..schemas import UserOut
from ..services.auth import get_current_user
from ..db.models import User

router = APIRouter()


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user
