from datetime import datetime
from typing import Annotated, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    StringConstraints,
    field_validator,
    model_validator,
)

# These limits mirror the CHECK constraints in the database. The schema rejects
# bad input with a clear 422; the database stays the last line of defence.
Username = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=3, max_length=50)
]
# The upper bound matters: argon2 is deliberately slow, so an unbounded password
# would let a client burn CPU with a huge request.
Password = Annotated[str, StringConstraints(min_length=8, max_length=128)]
Bio = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]


class UserCreate(BaseModel):
    """Input for registration. Only these fields are accepted from the client."""

    # extra="forbid" turns unknown fields (e.g. "id", "password_hash") into a 422
    # instead of silently ignoring them.
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    username: Username
    password: Password

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        # Otherwise "Alice@x.com" and "alice@x.com" would be two accounts.
        return value.lower()


class UserUpdate(BaseModel):
    """Input for PATCH /users/me. Every field is optional."""

    model_config = ConfigDict(extra="forbid")

    username: Username | None = None
    bio: Bio | None = None

    @model_validator(mode="after")
    def username_cannot_be_null(self) -> Self:
        # An explicit "username": null would try to write NULL into a NOT NULL
        # column. Omitting the field is fine; setting it to null is not.
        if "username" in self.model_fields_set and self.username is None:
            raise ValueError("username cannot be null")
        return self


class UserPublic(BaseModel):
    """What anyone may see about a user. No email, never the password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    bio: str | None
    created_at: datetime


class UserMe(UserPublic):
    """What a user sees about themselves: the public profile plus the email."""

    email: str
