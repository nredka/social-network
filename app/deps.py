from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Path, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Post, User
from app.security import decode_access_token

# Shorthand so route signatures read "db: DbSession" instead of repeating Depends.
DbSession = Annotated[Session, Depends(get_db)]

# PostgreSQL "integer" range. A larger id makes the query fail with a database
# error (DataError, a 500) instead of a clean 404/422/401.
MAX_INT4 = 2**31 - 1

# A resource id taken from the URL path, e.g. /users/{user_id}. Out-of-range values
# are rejected with a 422 before they reach the database.
ResourceId = Annotated[int, Path(ge=1, le=MAX_INT4)]


# Reads the token from "Authorization: Bearer <token>" and makes Swagger show the
# Authorize button. tokenUrl tells Swagger where to send the login form.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def _unauthorized() -> HTTPException:
    # The same answer for every problem (missing, malformed, bad signature, expired,
    # unknown user): the client only needs to know it must log in again.
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], db: DbSession
) -> User:
    """Return the user the bearer token was issued for, or answer 401.

    This is the single place that decides who the caller is: routers only depend on
    CurrentUser and never look at the token themselves.
    """
    try:
        user_id = decode_access_token(token)
    except jwt.InvalidTokenError:
        raise _unauthorized() from None
    # The user may have been deleted after the token was issued.
    user = db.get(User, user_id) if 1 <= user_id <= MAX_INT4 else None
    if user is None:
        raise _unauthorized()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_post_or_404(post_id: ResourceId, db: DbSession) -> Post:
    """Load the post named by {post_id} in the path, or answer 404.

    Any route with a {post_id} path parameter can depend on this, so the lookup and
    the 404 live in one place (posts, comments and likes all reuse it).
    """
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Post not found")
    return post


PostById = Annotated[Post, Depends(get_post_or_404)]
