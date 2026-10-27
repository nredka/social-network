# IT Cluster Social Network

A social networking backend built with FastAPI and PostgreSQL. This is an academic
project: it is built step by step to practice backend development, databases, Docker
and CI/CD.

**Current status:** project skeleton only (a FastAPI app with a `/health` endpoint,
settings, tests and tooling). Users, posts, comments, likes, auth, Docker and CI are
added in later milestones.

## Requirements

- [uv](https://docs.astral.sh/uv/) (installs Python 3.12 and the dependencies)
- Git

You do not need to install Python 3.12 yourself: `uv` downloads it on first use.

## Setup

```bash
git clone git@github.com:nredka/social-network.git
cd social-network

# Create .venv with Python 3.12 and install the exact versions from uv.lock
uv sync

# Create your local settings (the real .env is never committed)
cp .env.example .env
```

## Run the app

```bash
./scripts/dev.sh
```

The server starts on http://127.0.0.1:8000 with auto-reload. Set `PORT` to use another
port, e.g. `PORT=8080 ./scripts/dev.sh`.

Check that it works:

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

Interactive API docs are available at http://localhost:8000/docs.

## Test and lint

```bash
uv run pytest
uv run ruff check .
```

## Configuration

Settings are read from environment variables (and from `.env` if present). See
`.env.example` for the available variables.

| Variable      | Default                     | Description                     |
| ------------- | --------------------------- | ------------------------------- |
| `APP_NAME`    | `IT Cluster Social Network` | Title shown in the API docs     |
| `ENVIRONMENT` | `development`               | Name of the running environment |
| `DEBUG`       | `false`                     | Enable FastAPI debug mode       |

## Project layout

```
app/
├── main.py        # FastAPI app and routes
├── config.py      # Settings loaded from the environment
├── models/        # Database tables (later milestone)
├── schemas/       # Pydantic request/response models (later milestone)
└── routers/       # HTTP endpoints grouped by feature (later milestone)
scripts/dev.sh     # Start the dev server
tests/             # pytest tests
```

## License

See [LICENSE](LICENSE).
