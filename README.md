# IT Cluster Social Network

[![CI](https://github.com/nredka/social-network/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/nredka/social-network/actions/workflows/ci.yml)

A social networking backend built with FastAPI and PostgreSQL. This is an academic
project: it is built step by step to practice backend development, databases, Docker
and CI/CD.

**Current status:** project skeleton, the database layer (PostgreSQL schema for users,
posts, comments and likes with Alembic migrations), a REST API on top of it and a CI
pipeline that lints, applies the migrations and runs the tests on every push and pull
request. Login and real authentication are the next milestone: until then the API
identifies the caller with a temporary `X-User-Id` header (see [API](#api)).

**Roadmap**

| Milestone | Topic                                    | Status  |
| --------- | ---------------------------------------- | ------- |
| 1         | Project skeleton and Git workflow        | done    |
| 2         | Database schema and migrations           | done    |
| 7         | CI pipeline (GitHub Actions)             | done    |
| 3         | REST API (users, posts, comments, likes) | done    |
| 4         | Authentication and authorization         | next    |
| 5         | Tests against a real database            | planned |
| 6         | Docker image and Compose for the app     | planned |
| 8         | Docker image build and deploy docs       | planned |

The order of the remaining work is 4 → 5 → 6 → 8.

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

## API

Start the database (`docker compose up -d db`), apply the migrations
(`uv run alembic upgrade head`) and run the app (`./scripts/dev.sh`).

> **Temporary authentication.** Login and JWT arrive in Milestone 4. Until then,
> endpoints that need a signed-in user read the user id from an `X-User-Id` header.
> This is **not secure** (anyone can send any id) and exists only for development. It
> lives in one dependency, `get_current_user` in `app/deps.py`, which Milestone 4
> replaces. Ownership checks (only the author may edit or delete) come with it, so for
> now any user may change any post or comment.

| Method and path                  | Auth | Success | Description                                   |
| -------------------------------- | ---- | ------- | --------------------------------------------- |
| `POST /auth/register`            | no   | 201     | Create an account (409 if email/username taken) |
| `GET /users/me`                  | yes  | 200     | Own profile, including the email              |
| `PATCH /users/me`                | yes  | 200     | Change `username` and/or `bio`                |
| `GET /users/{id}`                | no   | 200     | Public profile (no email), 404 if missing     |
| `POST /posts`                    | yes  | 201     | Create a post                                 |
| `GET /posts`                     | no   | 200     | Newest first; filter `author_id`; `limit`, `offset` |
| `GET /posts/{id}`                | no   | 200     | One post, 404 if missing                      |
| `PATCH /posts/{id}`              | yes  | 200     | Edit a post                                   |
| `DELETE /posts/{id}`             | yes  | 204     | Delete a post with its comments and likes     |
| `POST /posts/{id}/comments`      | yes  | 201     | Comment on a post                             |
| `GET /posts/{id}/comments`       | no   | 200     | Oldest first; `limit`, `offset`               |
| `DELETE /comments/{id}`          | yes  | 204     | Delete a comment                              |
| `PUT /posts/{id}/like`           | yes  | 204     | Like a post (idempotent)                      |
| `DELETE /posts/{id}/like`        | yes  | 204     | Remove the like (idempotent)                  |

Status codes: `401` missing or unknown `X-User-Id`, `404` post/user/comment not found,
`409` email or username already taken, `422` invalid input (a clear message per field).
Lists accept `limit` (1-100, default 20) and `offset` (default 0).

### Try it with curl

```bash
# Register two users (the response contains the id to use in X-User-Id)
curl -X POST localhost:8000/auth/register -H 'Content-Type: application/json' \
  -d '{"email":"alice@example.com","username":"alice","password":"s3cretpass"}'
curl -X POST localhost:8000/auth/register -H 'Content-Type: application/json' \
  -d '{"email":"bob@example.com","username":"bobby","password":"s3cretpass"}'

# Alice writes a post
curl -X POST localhost:8000/posts -H 'Content-Type: application/json' \
  -H 'X-User-Id: 1' -d '{"content":"Hello from Alice"}'

# Bob comments and likes it (liking twice still leaves a single like)
curl -X POST localhost:8000/posts/1/comments -H 'Content-Type: application/json' \
  -H 'X-User-Id: 2' -d '{"content":"Nice post!"}'
curl -X PUT localhost:8000/posts/1/like -H 'X-User-Id: 2'

# Read it back (no header needed)
curl localhost:8000/posts
curl localhost:8000/posts/1/comments
```

### Try it in Swagger

Open http://localhost:8000/docs. Register users with `POST /auth/register`, then for any
endpoint marked "yes" in the table click **Try it out**, put the user id into the
`x-user-id` field above the request body and click **Execute**. There is no
**Authorize** button yet: the header is a plain field on each endpoint.

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
├── main.py        # FastAPI app, includes the routers
├── config.py      # Settings loaded from the environment
├── database.py    # Engine, session factory and get_db dependency
├── deps.py        # Shared dependencies (DB session, temporary current user)
├── pagination.py  # limit/offset query parameters
├── errors.py      # IntegrityError -> 409 translation
├── security.py    # Password hashing (argon2)
├── models/        # SQLAlchemy models: User, Post, Comment, Like
├── schemas/       # Pydantic input/output models, one file per resource
└── routers/       # HTTP endpoints: auth, users, posts, comments, likes
alembic/           # Migration environment and versions
alembic.ini        # Alembic configuration
docker-compose.yml # PostgreSQL service for local development
scripts/dev.sh     # Start the dev server
tests/             # pytest tests
```

## License

See [LICENSE](LICENSE).
