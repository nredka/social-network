from fastapi import APIRouter, status
from sqlalchemy.exc import IntegrityError

from app.deps import DbSession
from app.errors import to_conflict
from app.models import User
from app.schemas import UserCreate, UserMe
from app.security import hash_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserMe, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: DbSession) -> User:
    # Hash immediately: the plain password never reaches the model or the database.
    user = User(
        email=payload.email,
        username=payload.username,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    # Insert first and let the UNIQUE constraints decide. "Check, then insert" has
    # a race: two concurrent requests can both see the email as free.
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise to_conflict(exc) from exc
    return user
