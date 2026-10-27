from fastapi import FastAPI

app = FastAPI(title="IT Cluster Social Network")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe: returns 200 as long as the process can serve requests."""
    return {"status": "ok"}
