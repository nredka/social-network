from pwdlib import PasswordHash

# recommended() picks argon2, a deliberately slow, memory-hard algorithm. Each hash
# carries its own random salt and parameters, so equal passwords hash differently.
_password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Return the argon2 hash of a password. The plain text is never stored."""
    return _password_hasher.hash(password)
