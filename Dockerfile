# syntax=docker/dockerfile:1

# Two stages: "builder" installs the dependencies (it needs uv and a cache), and the
# final stage copies only the finished virtualenv and the application code. Build
# tools never reach the image that runs in production, so it is smaller and has less
# for an attacker to use.

# ---- builder ---------------------------------------------------------------------
FROM python:3.12.16-slim-trixie AS builder

# uv comes from its official image, pinned to an exact version (never "latest").
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /bin/uv

# COMPILE_BYTECODE: precompile .pyc files so the app starts faster.
# LINK_MODE=copy: the cache mount and the target are on different file systems, so
#   hard links are impossible; copying silences the warning.
# PYTHON_DOWNLOADS=0: use the Python of this base image, not a downloaded one, so the
#   virtualenv matches the interpreter of the final stage.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Dependencies first, in their own layer. Only pyproject.toml and uv.lock are mounted,
# so this layer is rebuilt only when the dependencies change, not on every code edit.
# --locked: fail if uv.lock is out of date. --no-dev: no pytest, ruff and so on.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --locked --no-dev --no-install-project

# ---- final -----------------------------------------------------------------------
FROM python:3.12.16-slim-trixie AS final

# DONTWRITEBYTECODE: the code is read-only for the app user anyway.
# UNBUFFERED: logs are written straight to stdout, so `docker logs` shows them live.
# PATH: run python, uvicorn and alembic from the virtualenv without activating it.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# An unprivileged user with a fixed UID (the same on every machine, which matters for
# file ownership on mounted volumes). No home directory and no login shell.
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home \
        --shell /usr/sbin/nologin app

WORKDIR /app

# Files stay owned by root and are only readable for the app user: a compromised
# process cannot rewrite the code it is running.
COPY --from=builder /app/.venv /app/.venv
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

# Everything after this line, including the container's main process, runs as "app".
USER 10001:10001

EXPOSE 8000

# python:slim has no curl, so the check uses Python. It fails (non-zero exit) on a
# connection error or any non-2xx answer.
HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=5 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"]

# 0.0.0.0: inside a container, 127.0.0.1 is the container's own loopback, which Docker's
#   port forwarding cannot reach. Binding all interfaces is safe because Compose
#   decides what is published to the host.
# No --reload: that is a development tool (a file watcher plus a supervisor process).
#   Production runs one stable process that handles SIGTERM and shuts down cleanly.
# Exec form (a JSON list): uvicorn is PID 1 and receives the stop signal directly.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
