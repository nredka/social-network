from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.deps import DbSession
from app.errors import to_conflict
from app.models import User
from app.schemas import Token, UserCreate, UserMe
from app.schemas.user import MAX_PASSWORD_LENGTH
from app.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    hash_password,
    verify_password,
)

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


def _invalid_credentials() -> HTTPException:
    # One response for "no such user" and "wrong password": different messages would
    # let an attacker find out which emails and usernames are registered.
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Incorrect username or password",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("/login", response_model=Token)
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession
) -> Token:
    # The OAuth2 password flow fixes the field names to "username" and "password",
    # which is what Swagger's Authorize button sends. We accept an email or a username
    # in the "username" field; a "@" tells them apart (usernames cannot contain one).
    identifier = form.username.strip()
    if "@" in identifier:
        condition = User.email == identifier.lower()
    else:
        condition = User.username == identifier
    user = db.scalars(select(User).where(condition)).one_or_none()

    # A password longer than registration allows cannot be right. Reject it without
    # hashing, so a huge request cannot make argon2 burn CPU.
    if len(form.password) > MAX_PASSWORD_LENGTH:
        raise _invalid_credentials()

    if user is None:
        # Timing: verify against a dummy hash anyway. Skipping the slow argon2 step
        # would make unknown users answer much faster than known ones.
        verify_password(form.password, DUMMY_PASSWORD_HASH)
        raise _invalid_credentials()
    if not verify_password(form.password, user.password_hash):
        raise _invalid_credentials()

    return Token(access_token=create_access_token(user.id))
