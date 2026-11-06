from typing import Annotated

from fastapi import Depends, Header, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User

# Shorthand so route signatures read "db: DbSession" instead of repeating Depends.
DbSession = Annotated[Session, Depends(get_db)]

# PostgreSQL "integer" range. A larger id makes the query fail with a database
# error (DataError, a 500) instead of a clean 404/422/401.
MAX_INT4 = 2**31 - 1

# A resource id taken from the URL path, e.g. /users/{user_id}. Out-of-range values
# are rejected with a 422 before they reach the database.
ResourceId = Annotated[int, Path(ge=1, le=MAX_INT4)]


# TODO(milestone-4): TEMPORARY. This trusts a client-supplied X-User-Id header, so
# anyone can act as anyone. Milestone 4 replaces the body of this function with
# JWT verification (and adds login). Keep all "who is the caller" logic in this one
# place so only this dependency changes; routers must not read the header.
def get_current_user(
    db: DbSession,
    x_user_id: Annotated[str | None, Header()] = None,
) -> User:
    if x_user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "X-User-Id header is missing")
    try:
        user_id = int(x_user_id)
    except ValueError:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "X-User-Id must be an integer"
        ) from None
    user = db.get(User, user_id) if 1 <= user_id <= MAX_INT4 else None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown user")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
