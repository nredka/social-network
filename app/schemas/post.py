from datetime import datetime
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

# strip_whitespace: a post made only of spaces passes the database CHECK
# (its length is > 0) but is effectively empty, so it is rejected here.
PostContent = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)
]


class PostCreate(BaseModel):
    """Input for POST /posts. The author comes from the current user, not the body."""

    model_config = ConfigDict(extra="forbid")

    content: PostContent


class PostUpdate(BaseModel):
    """Input for PATCH /posts/{id}. Every field is optional."""

    model_config = ConfigDict(extra="forbid")

    content: PostContent | None = None

    @model_validator(mode="after")
    def content_cannot_be_null(self) -> Self:
        if "content" in self.model_fields_set and self.content is None:
            raise ValueError("content cannot be null")
        return self


class PostRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    author_id: int
    content: str
    created_at: datetime
