# IT Cluster Social Network

A social networking backend built with FastAPI and PostgreSQL. This is an academic
project: it is built step by step to practice backend development, databases, Docker
and CI/CD.

**Current status:** project skeleton plus the database layer (PostgreSQL schema for
users, posts, comments and likes with Alembic migrations). The REST API, auth, the
application container and CI are added in later milestones.

## Requirements

- [uv](https://docs.astral.sh/uv/) (installs Python 3.12 and the dependencies)
- [Docker](https://docs.docker.com/get-docker/) with Docker Compose (runs PostgreSQL)
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

Change `POSTGRES_PASSWORD` in `.env` if you like. If you do, update the password in
`DATABASE_URL` as well: the two values must match.

## Database

PostgreSQL 16 runs in a Docker container; its data lives in the named volume `pgdata`,
so it survives container restarts.

```bash
# Start the database and wait until it reports "healthy"
docker compose up -d db
docker compose ps

# Create or update the tables (applies all Alembic migrations)
uv run alembic upgrade head
```

Connect with `psql` inside the container (it reads the credentials from the container
environment):

```bash
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

Useful commands inside `psql`: `\dt` lists tables, `\d users` describes a table,
`\q` quits.

### Migrations

```bash
uv run alembic current                                  # which revision is applied
uv run alembic revision --autogenerate -m "add thing"   # generate a migration
uv run alembic upgrade head                             # apply all migrations
uv run alembic downgrade -1                             # undo the last migration
uv run alembic check                                    # models and database in sync?
```

Always read a generated migration before applying it: autogenerate does not detect
renames (it sees a drop plus an add and would lose data), changes to CHECK
constraints, or data migrations.

### Stop or reset

```bash
docker compose down        # stop the database, keep the data
docker compose down -v     # stop and DELETE all data (removes the volume)
```

### Schema

| Table      | Purpose                                                                       |
| ---------- | ----------------------------------------------------------------------------- |
| `users`    | Accounts. `email` and `username` are unique, `username` is 3-50 characters.  |
| `posts`    | A user's posts, 1-5000 characters. Index on `(author_id, created_at DESC)`.   |
| `comments` | Comments on a post, 1-2000 characters. Index on `post_id`.                    |
| `likes`    | A user's like on a post. Primary key `(user_id, post_id)`: one like per pair. |

Deleting a user or a post deletes everything that depends on it (`ON DELETE CASCADE`).

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

| Variable            | Default                     | Description                                 |
| ------------------- | --------------------------- | ------------------------------------------- |
| `APP_NAME`          | `IT Cluster Social Network` | Title shown in the API docs                 |
| `ENVIRONMENT`       | `development`               | Name of the running environment             |
| `DEBUG`             | `false`                     | Enable FastAPI debug mode                   |
| `DATABASE_URL`      | none (required)             | SQLAlchemy URL, `postgresql+psycopg://...`  |
| `POSTGRES_USER`     | none (required by compose)  | Database user created in the container      |
| `POSTGRES_PASSWORD` | none (required by compose)  | Password of that user                       |
| `POSTGRES_DB`       | none (required by compose)  | Database name created in the container      |

## Project layout

```
app/
├── main.py        # FastAPI app and routes
├── config.py      # Settings loaded from the environment
├── database.py    # Engine, session factory and get_db dependency
├── models/        # SQLAlchemy models: User, Post, Comment, Like
├── schemas/       # Pydantic request/response models (later milestone)
└── routers/       # HTTP endpoints grouped by feature (later milestone)
alembic/           # Migration environment and versions
alembic.ini        # Alembic configuration
docker-compose.yml # PostgreSQL service for local development
scripts/dev.sh     # Start the dev server
tests/             # pytest tests
```

## License

See [LICENSE](LICENSE).
