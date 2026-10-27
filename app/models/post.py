from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (
        CheckConstraint(
            "char_length(content) BETWEEN 1 AND 5000", name="content_length"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    author: Mapped[User] = relationship(back_populates="posts")


# Serves "latest posts of one author": filter by author_id, already sorted by
# created_at DESC, so PostgreSQL can read the first N index entries and stop.
Index("ix_posts_author_id_created_at", Post.author_id, Post.created_at.desc())
