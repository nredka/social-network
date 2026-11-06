from fastapi import FastAPI

from app.config import get_settings
from app.routers import auth, comments, likes, posts, users

settings = get_settings()

app = FastAPI(title=settings.app_name, debug=settings.debug)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(posts.router)
app.include_router(comments.router)
app.include_router(likes.router)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe: returns 200 as long as the process can serve requests."""
    return {"status": "ok"}
