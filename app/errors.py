from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

UNIQUE_VIOLATION = "23505"

# Keyed by constraint name. The names are deterministic thanks to the MetaData
# naming convention, so we can tell the client exactly what is taken.
_UNIQUE_MESSAGES = {
    "uq_users_email": "Email is already registered",
    "uq_users_username": "Username is already taken",
}


def to_conflict(exc: IntegrityError) -> HTTPException:
    """Translate a unique violation into a 409 response.

    Any other integrity error (a CHECK or foreign key failure) means a bug in our
    code, not a client mistake, so it is re-raised and ends up as a 500.
    """
    if getattr(exc.orig, "sqlstate", None) != UNIQUE_VIOLATION:
        raise exc
    constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
    detail = _UNIQUE_MESSAGES.get(constraint, "Resource already exists")
    return HTTPException(status.HTTP_409_CONFLICT, detail)
