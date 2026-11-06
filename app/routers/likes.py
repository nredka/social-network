from fastapi import APIRouter, Response, status
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert

from app.deps import CurrentUser, DbSession, PostById
from app.models import Like

router = APIRouter(prefix="/posts", tags=["likes"])


@router.put("/{post_id}/like", status_code=status.HTTP_204_NO_CONTENT)
def like_post(post: PostById, current_user: CurrentUser, db: DbSession) -> Response:
    """Like a post. Idempotent: liking an already liked post is not an error."""
    # One atomic statement. If the (user_id, post_id) primary key already exists
    # PostgreSQL does nothing, so there is no race and no IntegrityError to catch.
    db.execute(
        insert(Like)
        .values(user_id=current_user.id, post_id=post.id)
        .on_conflict_do_nothing()
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{post_id}/like", status_code=status.HTTP_204_NO_CONTENT)
def unlike_post(post: PostById, current_user: CurrentUser, db: DbSession) -> Response:
    """Remove the like. Idempotent: removing a missing like is not an error."""
    db.execute(
        delete(Like).where(Like.user_id == current_user.id, Like.post_id == post.id)
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
