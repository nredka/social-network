from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.deps import CurrentUser, DbSession, ResourceId
from app.errors import to_conflict
from app.models import User
from app.schemas import UserMe, UserPublic, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


# "/me" must be declared before "/{user_id}". FastAPI matches routes in order, so
# otherwise "me" would be treated as a user id and rejected as not an integer.
@router.get("/me", response_model=UserMe)
def read_me(current_user: CurrentUser) -> User:
    return current_user


@router.patch("/me", response_model=UserMe)
def update_me(payload: UserUpdate, current_user: CurrentUser, db: DbSession) -> User:
    # exclude_unset: only fields the client actually sent. Otherwise a missing
    # field would default to None and overwrite the stored value.
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(current_user, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise to_conflict(exc) from exc
    return current_user


@router.get("/{user_id}", response_model=UserPublic)
def read_user(user_id: ResourceId, db: DbSession) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user
