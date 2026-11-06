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
    data: CommentCreate, current_user: CurrentUser, post: PostById, db: DbSession
) -> Comment:
    # current_user is declared before post so authentication (401) is checked before
    # the post is loaded (404); dependencies are resolved in signature order.
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
    comment = db.get(Comment, comment_id)
    if comment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Comment not found")
    # Compare with the comment's author, not the post's: a comment has two foreign
    # keys, and owning the post does not make someone the author of its comments.
    # The order is 401 (current_user), 404 (above), then 403 (here).
    if comment.author_id != current_user.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "You can only delete your own comments"
        )
    db.delete(comment)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
