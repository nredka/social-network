from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

CommentContent = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
]


class CommentCreate(BaseModel):
    """Input: only the text. Post and author come from the URL and the user."""

    model_config = ConfigDict(extra="forbid")

    content: CommentContent


class CommentRead(BaseModel):
    """Output: the fields a client may see."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    post_id: int
    author_id: int
    content: str
    created_at: datetime
