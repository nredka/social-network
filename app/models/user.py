from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.post import Post


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "char_length(username) BETWEEN 3 AND 50", name="username_length"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    # Only the hash is stored, never the plain password (hashing comes in Milestone 4).
    password_hash: Mapped[str] = mapped_column(String(255))
    bio: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # passive_deletes lets the database do ON DELETE CASCADE instead of the ORM
    # loading and deleting every child row one by one.
    posts: Mapped[list[Post]] = relationship(
        back_populates="author", cascade="all, delete-orphan", passive_deletes=True
    )
