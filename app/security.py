from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.config import get_settings

# recommended() picks argon2, a deliberately slow, memory-hard algorithm. Each hash
# carries its own random salt and parameters, so equal passwords hash differently.
_password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Return the argon2 hash of a password. The plain text is never stored."""
    return _password_hasher.hash(password)


# Hash of a throwaway password, computed once at import. Login verifies against it
# when the user does not exist, so that case takes as long as a wrong password and
# the response time does not reveal which accounts exist.
DUMMY_PASSWORD_HASH = hash_password("dummy-password-for-timing-equalisation")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Check a password against a stored hash (the comparison is constant-time)."""
    return _password_hasher.verify(plain_password, password_hash)


def create_access_token(user_id: int) -> str:
    """Create a signed, short-lived access token for a user.

    The token is signed, not encrypted: anyone holding it can read the payload, so it
    carries only the subject and timestamps, nothing sensitive.
    """
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        # The JWT spec requires "sub" to be a string.
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


def decode_access_token(token: str) -> int:
    """Verify a token and return the user id it was issued for.

    Raises jwt.InvalidTokenError (or a subclass such as ExpiredSignatureError) when
    the token is malformed, has a bad signature, is expired, or lacks a valid subject.
    """
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        # Pin the accepted algorithms ourselves. The header is chosen by the client, so
        # trusting it would allow "alg": "none" and algorithm confusion attacks.
        algorithms=[settings.jwt_algorithm],
        # Without "require", a token that simply omits "exp" would never expire.
        options={"require": ["exp", "iat", "sub"]},
    )
    try:
        return int(payload["sub"])
    except ValueError:
        raise jwt.InvalidTokenError("subject is not a user id") from None
