from pydantic import BaseModel


class Token(BaseModel):
    """Response of a successful login, in the shape the OAuth2 spec defines."""

    access_token: str
    token_type: str = "bearer"
