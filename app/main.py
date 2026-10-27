from fastapi import FastAPI

from app.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name, debug=settings.debug)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe: returns 200 as long as the process can serve requests."""
    return {"status": "ok"}
