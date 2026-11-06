from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import select

from app.deps import MAX_INT4, CurrentUser, DbSession, PostById
from app.models import Post, User
from app.pagination import PageParams
from app.schemas import PostCreate, PostRead, PostUpdate

router = APIRouter(prefix="/posts", tags=["posts"])


@router.post("", response_model=PostRead, status_code=status.HTTP_201_CREATED)
def create_post(payload: PostCreate, current_user: CurrentUser, db: DbSession) -> Post:
    # The author comes from the authenticated user, never from the request body.
    post = Post(author_id=current_user.id, content=payload.content)
    db.add(post)
    db.commit()
    return post


@router.get("", response_model=list[PostRead])
def list_posts(
    db: DbSession,
    page: PageParams,
    author_id: Annotated[int | None, Query(ge=1, le=MAX_INT4)] = None,
) -> list[Post]:
    # id is a tie-breaker: two posts can share created_at, and without a total order
    # the same row could appear on two pages or on none.
    query = select(Post).order_by(Post.created_at.desc(), Post.id.desc())
    if author_id is not None:
        query = query.where(Post.author_id == author_id)
    return list(db.scalars(query.limit(page.limit).offset(page.offset)))


@router.get("/{post_id}", response_model=PostRead)
def read_post(post: PostById) -> Post:
    return post


def _require_author(post: Post, user: User) -> None:
    # 403, not 404: posts are public, so hiding that one exists would protect nothing.
    # By now the post is known to exist (404 came first) and the caller is known
    # (401 came first), so the only question left is "is it yours?".
    if post.author_id != user.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "You can only change your own posts"
        )


# Parameter order matters: FastAPI resolves dependencies in the order they are
# declared. current_user comes first so the error order is 401, then 404, then 403;
# otherwise an anonymous caller could tell which post ids exist from a 404.
@router.patch("/{post_id}", response_model=PostRead)
def update_post(
    payload: PostUpdate, current_user: CurrentUser, post: PostById, db: DbSession
) -> Post:
    _require_author(post, current_user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(post, field, value)
    db.commit()
    return post


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(current_user: CurrentUser, post: PostById, db: DbSession) -> Response:
    _require_author(post, current_user)
    # The database removes the post's comments and likes (ON DELETE CASCADE).
    db.delete(post)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
