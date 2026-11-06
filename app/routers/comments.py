from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from app.deps import CurrentUser, DbSession, PostById, ResourceId
from app.models import Comment
from app.pagination import PageParams
from app.schemas import CommentCreate, CommentRead

# No prefix: the routes live under /posts/... and /comments/...
router = APIRouter(tags=["comments"])


@router.post(
    "/posts/{post_id}/comments",
    response_model=CommentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_comment(
    data: CommentCreate, post: PostById, current_user: CurrentUser, db: DbSession
) -> Comment:
    comment = Comment(post_id=post.id, author_id=current_user.id, content=data.content)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


@router.get("/posts/{post_id}/comments", response_model=list[CommentRead])
def list_comments(post: PostById, page: PageParams, db: DbSession) -> list[Comment]:
    stmt = (
        select(Comment)
        .where(Comment.post_id == post.id)
        .order_by(Comment.created_at.asc(), Comment.id.asc())
        .limit(page.limit)
        .offset(page.offset)
    )
    return list(db.scalars(stmt))


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(
    comment_id: ResourceId, current_user: CurrentUser, db: DbSession
) -> Response:
    # TODO(milestone-4): only the author may delete a comment (403 otherwise).
    comment = db.get(Comment, comment_id)
    if comment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Comment not found")
    db.delete(comment)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
