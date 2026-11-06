# IT Cluster Social Network

A REST API for a small social network: FastAPI, PostgreSQL, JWT, Docker and CI/CD.
An academic portfolio project, built milestone by milestone through pull requests.

[![CI](https://github.com/nredka/social-network/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/nredka/social-network/actions/workflows/ci.yml)
[![Docker](https://github.com/nredka/social-network/actions/workflows/docker.yml/badge.svg?branch=main)](https://github.com/nredka/social-network/actions/workflows/docker.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/github/license/nredka/social-network)](LICENSE)

**Status:** all eight planned milestones are done (see the [roadmap](#roadmap)).

## Contents

- [What it does](#what-it-does)
- [Quick start](#quick-start): [Docker only](#a-docker-only) · [published image](#b-the-published-image) · [local development](#c-local-development-with-uv)
- [Try the API](#try-the-api)
- [API overview](#api-overview)
- [Tech stack](#tech-stack)
- [Architecture](#architecture)
- [Configuration](#configuration)
- [Database and migrations](#database-and-migrations)
- [Testing and CI/CD](#testing-and-cicd)
- [Deployment](#deployment)
- [Project layout](#project-layout)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)
- [License](#license)

## What it does

- **Accounts and login.** Register, log in with an email or a username and get a JWT
  access token (valid for 30 minutes). Passwords are stored only as argon2id hashes.
- **Posts, comments and likes.** The full set of REST endpoints. Likes are idempotent:
  liking twice is not an error and never creates a duplicate.
- **Authorization.** Only the author can edit or delete their own posts and comments
  (`403` otherwise). Errors always come in the order 401, 404, 403.
- **Pagination.** `limit` and `offset` on the feed and on comment lists, newest posts
  first, in a stable order.
- **Validation and data integrity.** Clear `422` messages for bad input; PostgreSQL
  constraints, cascading foreign keys and indexes are the last line of defence.
- **Tested.** 155 tests against a real PostgreSQL (the database is not mocked), 100%
  branch coverage, and the migrations are tested up and down.
- **Ships as an image.** CI builds and publishes a multi-architecture (amd64 and arm64)
  image to GitHub Container Registry. There is a Docker Compose setup and a guide for
  running it on your own server.

## Quick start

Pick one of three ways, from the easiest to the most hands-on.

### Prerequisites

| Tool | What for | Notes |
| ---- | -------- | ----- |
| Git | clone the repository | any recent 2.x |
| Docker with Compose v2 | run the stack | `docker compose version` must work. Docker Desktop on macOS and Windows, Docker Engine with the Compose plugin on Linux. Tested with Docker 29. |
| `openssl` | generate random keys | preinstalled on macOS and on most Linux distributions |
| `curl` | call the API in the examples | preinstalled on macOS and Linux |
| [uv](https://docs.astral.sh/uv/) | only for [local development](#c-local-development-with-uv) | installs Python 3.12 itself, so you do not need Python |

The commands are written for macOS (zsh) and Linux (bash); on Windows use WSL 2 (not tested).
All URLs use `127.0.0.1`.

### a) Docker only

You need only Git and Docker. This builds the image, starts PostgreSQL and the API in
containers and creates the tables.

**1. Get the code.**

```bash
git clone https://github.com/nredka/social-network.git
cd social-network
```

**2. Create `.env` and a signing key.** The first command copies the template and never
overwrites an existing `.env`. The second puts a random 64-character key into the new
file. The template's key is a deliberately too-short placeholder: the app refuses to
start with it, so nobody runs with a key that is public in the repository. Run the
second command only for a **new** `.env`, otherwise it replaces your key and signs
everyone out.

```bash
cp -n .env.example .env
sed -i.bak "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$(openssl rand -hex 32)|" .env && rm .env.bak
```

No output means success.

**3. Build and start.** The first build takes about a minute. The API starts only after
the database reports `healthy`.

```bash
docker compose up -d --build
```

Check that both services are `healthy` (this can take a few seconds):

```bash
docker compose ps
```

```text
NAME                   IMAGE                COMMAND                  SERVICE   CREATED          STATUS                    PORTS
social-network-api-1   social-network-api   "uvicorn app.main:ap…"   api       10 minutes ago   Up 10 minutes (healthy)   127.0.0.1:8000->8000/tcp
social-network-db-1    postgres:16          "docker-entrypoint.s…"   db        10 minutes ago   Up 10 minutes (healthy)   127.0.0.1:5432->5432/tcp
```

**4. Create the tables.** Migrations are a separate, explicit step on purpose (see
[How it is wired](#how-it-is-wired)).

```bash
docker compose run --rm api alembic upgrade head
```

```text
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 36602b6e3cb4, create initial schema
```

**5. Check it works.**

```bash
curl http://127.0.0.1:8000/health
```

```text
{"status":"ok"}
```

Open http://127.0.0.1:8000/docs for the interactive API (Swagger UI) or continue with
[Try the API](#try-the-api).

Everyday commands:

```bash
docker compose logs -f api                 # follow the API logs (Ctrl+C stops following)
docker compose up -d --build api           # rebuild and restart the API after a code change
docker compose down                        # stop and remove the containers, KEEP the data
```

> **`docker compose down -v` deletes the database volume, which means all your data.**
> Plain `down` is safe: the data lives in the named volume `pgdata`.

Port 8000 or 5432 already in use? See [Troubleshooting](#troubleshooting).

### b) The published image

Only for trying it out: no clone, no build. CI publishes the image to GitHub Container
Registry, and `compose.prod.yml` runs it. In an empty directory, this downloads the
compose file, writes a `.env` with freshly generated secrets, starts the stack and
creates the tables:

```bash
mkdir social-network-try && cd social-network-try
curl -fsSLO https://raw.githubusercontent.com/nredka/social-network/main/compose.prod.yml
cat > .env <<EOF
POSTGRES_USER=social
POSTGRES_PASSWORD=$(openssl rand -hex 16)
POSTGRES_DB=social_network
JWT_SECRET_KEY=$(openssl rand -hex 32)
EOF
docker compose -f compose.prod.yml up -d
docker compose -f compose.prod.yml run --rm api alembic upgrade head
curl http://127.0.0.1:8000/health
```

The last command prints `{"status":"ok"}`. The first `up` downloads the image
(`ghcr.io/nredka/social-network:latest`, for amd64 or arm64, picked automatically). The
database is not published to your machine here: only the API can reach it. To run it on a
real server, with a pinned version, backups and HTTPS, read [Deployment](#deployment).

### c) Local development with uv

For working on the code: auto-reload, tests and the linter. PostgreSQL still runs in
Docker, and the app runs on your machine.

**1. Get the code and `.env`** (skip what you did in [a)](#a-docker-only)):

```bash
git clone https://github.com/nredka/social-network.git
cd social-network
cp -n .env.example .env
sed -i.bak "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$(openssl rand -hex 32)|" .env && rm .env.bak
```

**2. Install the dependencies.** `uv` reads `.python-version`, downloads Python 3.12 if
you do not have it and creates `.venv`.

```bash
uv sync
```

**3. Start only the database and create the tables.** The `.env` template already points
the app at `localhost:5432`.

```bash
docker compose up -d db
uv run alembic upgrade head
```

**4. Run the API with auto-reload.** Edit a file and the server restarts by itself.

```bash
./scripts/dev.sh
```

```text
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [30422] using WatchFiles
INFO:     Application startup complete.
```

The API is on http://127.0.0.1:8000 (`PORT=8001 ./scripts/dev.sh` uses another port).

**5. Run the tests and the linter** in a second terminal. The tests use a separate
database, which you create once:

```bash
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "CREATE DATABASE social_network_test"'
uv run pytest
uv run ruff check .
```

```text
CREATE DATABASE
...
======================== 155 passed, 1 warning in 1.58s ========================
All checks passed!
```

(The warning is a deprecation notice from the test client library and is harmless.)

You create the test database only once. If you run that first command again,
PostgreSQL answers `ERROR:  database "social_network_test" already exists` and the
command exits with status 1. That is harmless: the database and your data stay as they
are.

## Try the API

The easiest way is the Swagger UI (below). The same flow with `curl`: register, log in,
create a post, comment on it, like it, read the feed. It assumes the API runs on
`127.0.0.1:8000` (use another port in `BASE` if you changed it). The responses are real;
your ids and timestamps will differ.

```bash
BASE=http://127.0.0.1:8000
PASSWORD='demo-password-123'    # a throw-away password for this local demo
```

**1. Register.** A password needs 8 to 128 characters. The response never contains the
password or its hash.

```bash
curl -s -X POST "$BASE/auth/register" -H 'Content-Type: application/json' \
  -d '{"email":"alice@example.com","username":"alice","password":"'"$PASSWORD"'"}'
```

```json
{"id":1,"username":"alice","bio":null,"created_at":"2026-11-06T20:16:59.297360Z","email":"alice@example.com"}
```

**2. Log in and keep the token.** Login takes a form (not JSON), and `username` can be
the username or the email. The server answers `{"access_token":"...","token_type":"bearer"}`;
the `sed` command pulls the token out without needing any other tool. This prints the
first characters of the token:

```bash
TOKEN=$(curl -s -X POST "$BASE/auth/login" -d "username=alice&password=$PASSWORD" \
  | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')
echo "$TOKEN" | cut -c1-24
```

```text
eyJhbGciOiJIUzI1NiIsInR5
```

**3. Who am I?** Send the token in the `Authorization` header.

```bash
curl -s "$BASE/users/me" -H "Authorization: Bearer $TOKEN"
```

```json
{"id":1,"username":"alice","bio":null,"created_at":"2026-11-06T20:16:59.297360Z","email":"alice@example.com"}
```

**4. Create a post.** The author is taken from the token, never from the request body.

```bash
POST=$(curl -s -X POST "$BASE/posts" -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"content":"Hello, world!"}')
echo "$POST"
POST_ID=$(echo "$POST" | sed -n 's/.*"id":\([0-9]*\).*/\1/p')
echo "post id: $POST_ID"
```

```json
{"id":1,"author_id":1,"content":"Hello, world!","created_at":"2026-11-06T20:16:59.389875Z"}
post id: 1
```

**5. Comment on it.**

```bash
curl -s -X POST "$BASE/posts/$POST_ID/comments" -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"content":"First comment"}'
```

```json
{"id":1,"post_id":1,"author_id":1,"content":"First comment","created_at":"2026-11-06T20:16:59.410572Z"}
```

**6. Like it, twice.** A like has no response body, so this prints the HTTP status. The
second like is not an error and does not create a second like.

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X PUT "$BASE/posts/$POST_ID/like" -H "Authorization: Bearer $TOKEN"
curl -s -o /dev/null -w '%{http_code}\n' -X PUT "$BASE/posts/$POST_ID/like" -H "Authorization: Bearer $TOKEN"
```

```text
204
204
```

**7. Read the feed.** Reading needs no token. Posts come newest first; comments oldest first.

```bash
curl -s "$BASE/posts?limit=5"; echo
curl -s "$BASE/posts/$POST_ID/comments"; echo
```

```json
[{"id":1,"author_id":1,"content":"Hello, world!","created_at":"2026-11-06T20:16:59.389875Z"}]
[{"id":1,"post_id":1,"author_id":1,"content":"First comment","created_at":"2026-11-06T20:16:59.410572Z"}]
```

**8. You cannot change someone else's post.** A second user tries to edit Alice's post:

```bash
curl -s -X POST "$BASE/auth/register" -H 'Content-Type: application/json' \
  -d '{"email":"bob@example.com","username":"bob","password":"'"$PASSWORD"'"}' > /dev/null
BOB=$(curl -s -X POST "$BASE/auth/login" -d "username=bob&password=$PASSWORD" \
  | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')
curl -s -w '\nHTTP %{http_code}\n' -X PATCH "$BASE/posts/$POST_ID" -H "Authorization: Bearer $BOB" \
  -H 'Content-Type: application/json' -d '{"content":"hacked"}'
```

```text
{"detail":"You can only change your own posts"}
HTTP 403
```

### Swagger UI

Open http://127.0.0.1:8000/docs, register a user with `POST /auth/register`, then click
the **Authorize** button (top right). Enter the user's email or username in `username` and
the password in `password`, leave `client_id` and `client_secret` empty, click
**Authorize**, then **Close**. Swagger calls `POST /auth/login` for you and sends the
token with every request: the padlocks next to the endpoints that need a user are now
closed, so **Try it out** works for them. **Logout** in the same dialog switches to
another user.

## API overview

Auth means "needs `Authorization: Bearer <token>`". The success code is listed first; the
other codes are the ones you may see. `422` (invalid input) can come from any endpoint
that takes input.

| Method | Path | Auth | What it does | Codes |
| ------ | ---- | ---- | ------------ | ----- |
| `POST` | `/auth/register` | no | Create an account | 201, 409 (email or username taken), 422 |
| `POST` | `/auth/login` | no | Exchange credentials for an access token (form body) | 200, 401, 422 |
| `GET` | `/users/me` | yes | Your profile, including the email | 200, 401 |
| `PATCH` | `/users/me` | yes | Change your `username` and/or `bio` | 200, 401, 409, 422 |
| `GET` | `/users/{user_id}` | no | Public profile (no email) | 200, 404 |
| `POST` | `/posts` | yes | Create a post | 201, 401, 422 |
| `GET` | `/posts` | no | Newest first. Filter `author_id`; `limit` (1-100, default 20), `offset` | 200, 422 |
| `GET` | `/posts/{post_id}` | no | One post | 200, 404 |
| `PATCH` | `/posts/{post_id}` | yes | Edit a post (author only) | 200, 401, 403, 404, 422 |
| `DELETE` | `/posts/{post_id}` | yes | Delete a post with its comments and likes (author only) | 204, 401, 403, 404 |
| `POST` | `/posts/{post_id}/comments` | yes | Comment on a post | 201, 401, 404, 422 |
| `GET` | `/posts/{post_id}/comments` | no | Oldest first; `limit`, `offset` | 200, 404 |
| `DELETE` | `/comments/{comment_id}` | yes | Delete a comment (its author only) | 204, 401, 403, 404 |
| `PUT` | `/posts/{post_id}/like` | yes | Like a post (idempotent) | 204, 401, 404 |
| `DELETE` | `/posts/{post_id}/like` | yes | Remove your like (idempotent) | 204, 401, 404 |
| `GET` | `/health` | no | Liveness check: `{"status":"ok"}` | 200 |

When several errors apply, they come in this order: `401` (who are you?), then `404`
(does it exist?), then `403` (is it yours?). An anonymous caller therefore cannot tell
which post ids exist.

### Authentication and security notes

- **Tokens.** `POST /auth/login` returns a JWT signed with HS256, valid for 30 minutes
  (`ACCESS_TOKEN_EXPIRE_MINUTES`). There are no refresh tokens: after it expires, log in
  again. A token is signed, **not encrypted**, so anyone holding it can read its payload
  (`sub`, `iat`, `exp`); it contains nothing sensitive. Tokens are stateless and cannot
  be revoked before they expire.
- **Same answer for a wrong password and an unknown user.** Both get the same `401`, and
  an unknown user is still checked against a dummy hash, so neither the response body nor
  the response time reveals which accounts exist.
- **Known limitation.** `POST /auth/register` answers `409` with "Email is already
  registered", so registration can still be used to check whether an email has an account.
  Closing that needs email confirmation or rate limiting, which this project does not have.
- **Usernames cannot contain `@`**, so login can tell an email from a username.
- **Inputs are whitelisted.** Request bodies reject unknown fields, so a client cannot set
  fields such as `id` or `password_hash`; responses never contain `password_hash`.

## Tech stack

| Layer | Technology |
| ----- | ---------- |
| Language | Python 3.12 |
| Web framework | FastAPI 0.162 on Uvicorn |
| Validation and settings | Pydantic v2, pydantic-settings |
| Database | PostgreSQL 16 |
| ORM and migrations | SQLAlchemy 2.1 (psycopg 3), Alembic |
| Authentication | PyJWT (HS256), pwdlib with argon2 |
| Tests | pytest, pytest-cov, a real PostgreSQL database |
| Tooling | uv (dependencies), ruff (lint), hadolint (Dockerfile lint) |
| Containers | Docker, Docker Compose |
| CI/CD | GitHub Actions, GitHub Container Registry |

## Architecture

### Runtime

```mermaid
flowchart LR
    client(["Browser, curl or Swagger UI"])
    subgraph net["Docker network 'backend' (private)"]
        api["api<br/>FastAPI + Uvicorn<br/>non-root, healthcheck"]
        db[("db<br/>PostgreSQL 16<br/>volume pgdata")]
        api -->|"SQLAlchemy + psycopg<br/>db:5432"| db
    end
    client -->|"HTTP on 127.0.0.1:8000<br/>JWT bearer token"| api
```

Inside the API every request takes the same path:

```mermaid
flowchart LR
    req["HTTP request"] --> router["routers<br/>auth, users, posts,<br/>comments, likes"]
    router --> schema["Pydantic schemas<br/>validate the input,<br/>shape the output"]
    router --> deps["dependencies<br/>get_db, get_current_user,<br/>PostById, pagination"]
    deps --> models["SQLAlchemy models"]
    models --> pg[("PostgreSQL<br/>constraints and indexes")]
```

### Database schema

```mermaid
erDiagram
    USERS ||--o{ POSTS : writes
    USERS ||--o{ COMMENTS : writes
    USERS ||--o{ LIKES : gives
    POSTS ||--o{ COMMENTS : has
    POSTS ||--o{ LIKES : receives
    USERS {
        int id PK
        string email UK "unique, stored in lower case"
        string username UK "unique, 3 to 50 characters, no @"
        string password_hash "argon2id"
        text bio "optional"
        timestamptz created_at
    }
    POSTS {
        int id PK
        int author_id FK "ON DELETE CASCADE"
        text content "1 to 5000 characters"
        timestamptz created_at
    }
    COMMENTS {
        int id PK
        int post_id FK "ON DELETE CASCADE"
        int author_id FK "ON DELETE CASCADE"
        text content "1 to 2000 characters"
        timestamptz created_at
    }
    LIKES {
        int user_id PK, FK "ON DELETE CASCADE"
        int post_id PK, FK "ON DELETE CASCADE"
        timestamptz created_at
    }
```

- The primary key of `likes` is the pair `(user_id, post_id)`: a user cannot like a post
  twice, and the database enforces it even for concurrent requests.
- Deleting a user or a post deletes everything that depends on it.
- Indexes besides the keys: `posts (author_id, created_at DESC)` for "latest posts of
  one author", `comments (post_id)` and `likes (post_id)`.
- The global feed (`GET /posts` without `author_id`) sorts all posts, which is fine at
  this scale; an index on `posts (created_at DESC)` would be the next step.

### How it is wired

- **`DATABASE_URL`.** Inside a container `localhost` is the container itself, so the API
  reaches the database at the host `db` (Docker's DNS name for that service). Compose
  builds the URL for the `api` service from the `POSTGRES_*` variables, so there is one
  set of credentials to maintain. The `localhost` value in your `.env` is what the app and
  the tests use when they run on the host. The password in `.env` must not contain
  characters that are special in a URL (`@ / : ? #`).
- **Migrations are a separate command** (`docker compose run --rm api alembic upgrade head`).
  Running them automatically when the container starts looks convenient, but several
  replicas would run them at the same time, a failing migration would put the container in
  a restart loop, and its output would be buried in the application logs.
- **Ports.** The API is published on `127.0.0.1` only. In development the database is too,
  for `psql` and for tests run on the host. In production it is not published at all.
- **Image.** A multi-stage build: the build tools stay in the first stage and the final
  image holds only the virtualenv and the app code. It runs as an unprivileged user (UID
  10001), and `.env` is never copied into it (`.dockerignore`); Compose passes the values
  to the running container as environment variables.

## Configuration

Settings are read from environment variables, and in development from `.env`. Copy
`.env.example` to `.env`; the file explains every variable.

| Variable | Default | Meaning |
| -------- | ------- | ------- |
| `JWT_SECRET_KEY` | none, **required** | Signs the access tokens. At least 32 characters; the app refuses to start otherwise. Changing it signs every user out. |
| `DATABASE_URL` | none, **required** | SQLAlchemy URL, `postgresql+psycopg://user:password@host:port/name`. In Compose the `api` container gets its own, built from `POSTGRES_*`. |
| `POSTGRES_USER` | none, required by Compose | Database user created in the `db` container. |
| `POSTGRES_PASSWORD` | none, required by Compose | Password of that user (no `@ / : ? #`). It is only applied when the database is first created. |
| `POSTGRES_DB` | none, required by Compose | Name of the database. |
| `TEST_DATABASE_URL` | none, required by the tests | Database the tests use. Its name must end with `_test`, otherwise the tests refuse to run. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Lifetime of an access token. |
| `JWT_ALGORITHM` | `HS256` | Token signing algorithm. |
| `APP_NAME` | `IT Cluster Social Network` | Title shown in the API docs. |
| `ENVIRONMENT` | `development` | A label for the environment; it does not change behaviour yet. |
| `DEBUG` | `false` | FastAPI debug mode. |
| `API_PORT` | `8000` | Docker Compose only: host port of the API container. |
| `DB_PORT` | `5432` | Docker Compose only (development): host port of the database. If you change it, use the same port in `DATABASE_URL` and `TEST_DATABASE_URL`. |
| `IMAGE_TAG` | `latest` | `compose.prod.yml` only: which published image to run. In production pin a `sha-...` tag. |
| `PORT` | `8000` | `scripts/dev.sh` only, set in the shell: port of the development server. |

## Database and migrations

Connect with `psql` inside the container (it reads the credentials from the container's
environment). Useful commands: `\dt` lists tables, `\d users` describes one, `\q` quits.

```bash
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

Schema changes go through [Alembic](https://alembic.sqlalchemy.org/) migrations. On the
host, with the database running:

```bash
uv run alembic current                                  # which revision is applied
uv run alembic revision --autogenerate -m "add thing"   # generate a migration
uv run alembic upgrade head                             # apply all migrations
uv run alembic downgrade -1                             # undo the last migration
uv run alembic check                                    # do the models and the database agree?
```

Always read a generated migration before applying it: autogenerate does not detect
renames (it sees a drop plus an add and would lose data), changes to `CHECK`
constraints, or data migrations.

## Testing and CI/CD

The tests call the API over HTTP (FastAPI's `TestClient`) against a **real PostgreSQL
database**, not SQLite: the code relies on PostgreSQL features (`ON CONFLICT`, `CHECK`
constraints, `timestamptz`, constraint names). They use a separate database, so your
development data is never touched. Create it and run the suite as shown in step 5 of
[local development](#c-local-development-with-uv). Two more commands:

```bash
uv run pytest tests/test_posts.py -k removes        # one file, filtered by name
uv run pytest --cov=app --cov-report=term-missing   # with a coverage report
```

How it works:

- The tests **refuse to run** unless the database name in `TEST_DATABASE_URL` ends with
  `_test`.
- `tests/conftest.py` points the app at the test database before importing it, applies
  the Alembic migrations once per session (so the tests also prove the migrations work)
  and wraps every test in a transaction that is rolled back, so tests cannot affect each
  other and can run in any order.
- Coverage is measured with branch coverage and the build fails below the `fail_under`
  value in `pyproject.toml` (currently 98%; measured 100%).
- Tests are written as arrange, act, assert, one file per resource (`test_auth.py`,
  `test_users.py`, `test_posts.py`, `test_comments.py`, `test_likes.py`) plus a few for
  cross-cutting behaviour (`test_error_order.py`, `test_isolation.py`, `test_database.py`,
  `test_errors.py`).

**CI** (`.github/workflows/ci.yml`) runs on every pull request and every push to `main`
with two jobs:

- `test`: lint with ruff, apply the migrations to a fresh PostgreSQL service container,
  check that the models match the migrations, check that the migration is reversible
  (downgrade, then upgrade), run the tests with coverage.
- `docker`: lint the `Dockerfile` with hadolint, build the image, and smoke-test it by
  starting the container and waiting for its health check.

`main` is protected: changes arrive only through a pull request and the `test` and
`docker` checks must pass. After a merge, **`docker.yml`** builds the image for
`linux/amd64` and `linux/arm64` and pushes it to GitHub Container Registry as
`ghcr.io/nredka/social-network`, tagged `sha-<short commit>` (immutable, what production
should run) and `latest` (convenient for trying it out).

```mermaid
flowchart LR
    pr["Pull request"] --> ci["CI workflow<br/>test + docker jobs"]
    ci -->|"green checks"| merge["Merge to main"]
    merge --> pub["Docker workflow<br/>build amd64 + arm64"]
    pub --> ghcr[("ghcr.io/nredka/social-network<br/>sha-... and latest")]
    ghcr -->|"docker compose pull"| srv["Your server<br/>compose.prod.yml"]
```

## Deployment

`compose.prod.yml` runs the published image instead of building it. It differs from the
development setup in four ways:

- PostgreSQL is **not published** to the host. Only the API can reach it.
- The API listens on `127.0.0.1`, for a reverse proxy in front of it.
- Container logs are rotated.
- The API container is read-only, has no Linux capabilities and cannot gain privileges.

In production, pin an immutable `sha-...` tag in `IMAGE_TAG`.

The step-by-step guide is in **[docs/deploy.md](docs/deploy.md)**: preparing an Ubuntu
server, getting the files and creating `.env` with strong secrets, starting, updating and
rolling back, backing up and restoring the database, HTTPS with a reverse proxy, and where
the secrets live.

## Project layout

```text
.
├── app/
│   ├── main.py            # FastAPI app: includes the routers, /health
│   ├── config.py          # settings read from environment variables
│   ├── database.py        # engine, session factory, get_db
│   ├── deps.py            # shared dependencies: DB session, current user (JWT), PostById
│   ├── security.py        # argon2 password hashing, JWT creation and verification
│   ├── pagination.py      # limit and offset query parameters
│   ├── errors.py          # translates a unique violation into 409
│   ├── models/            # SQLAlchemy models: user, post, comment, like
│   ├── schemas/           # Pydantic input and output models
│   └── routers/           # auth, users, posts, comments, likes
├── alembic/               # migration environment and versions/
├── alembic.ini
├── tests/                 # pytest suite (conftest.py sets up the test database)
├── scripts/dev.sh         # development server with auto-reload
├── docs/deploy.md         # deploying on a Linux server
├── Dockerfile             # multi-stage image (non-root, no tests or dev tools)
├── .dockerignore          # keeps .env, tests and caches out of the image
├── docker-compose.yml     # development stack: builds the image, db on 127.0.0.1
├── compose.prod.yml       # production stack: published image, db not published
├── .github/workflows/     # ci.yml (lint, tests, image check), docker.yml (publish)
├── .env.example           # template for .env; every variable is explained
├── .gitignore             # keeps .env, .venv and caches out of git
├── pyproject.toml         # dependencies and tool settings
├── uv.lock                # exact versions of every dependency
├── .python-version        # 3.12
└── LICENSE
```

## Troubleshooting

**Docker is not running.** Any `docker` command fails with something like:

```text
failed to connect to the docker API at unix:///.../docker.sock; check if the path is correct and if the daemon is running: dial unix /.../docker.sock: connect: no such file or directory
```

Start Docker Desktop (macOS, Windows) or the service (Linux: `sudo systemctl start docker`)
and try again.

**Port 8000 (or 5432) is already in use.** `docker compose up` fails with:

```text
Error response from daemon: ports are not available: exposing port TCP 127.0.0.1:8000 -> 127.0.0.1:0: listen tcp4 127.0.0.1:8000: bind: address already in use
```

Something else listens on that port (often the dev server from
[local development](#c-local-development-with-uv), or a PostgreSQL of your own on 5432).
Find it with `lsof -nP -iTCP:8000 -sTCP:LISTEN`, stop it, or give the containers other
ports. Put the variables in `.env` (or in front of the command):

```bash
API_PORT=8001 DB_PORT=5433 docker compose up -d
```

The API is then on `http://127.0.0.1:8001`. If you also run the app or the tests **on the
host** with the new `DB_PORT`, point their URLs at it (they use `localhost:5432` by
default):

```bash
sed -i.bak "s|localhost:5432|localhost:5433|" .env && rm .env.bak
```

**The `api` container keeps restarting; its logs say the JWT key is too short.** `docker
compose ps` shows `Restarting (1)` and `docker compose logs api` ends with:

```text
pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings
jwt_secret_key
  String should have at least 32 characters [type=string_too_short, input_value='change-me', input_type=str]
```

`JWT_SECRET_KEY` is still the template's placeholder. Generate a key (step 2 of
[Quick start a)](#a-docker-only)), then `docker compose up -d`.

**Login or any request returns `500` after you changed `POSTGRES_PASSWORD`.** The logs
show:

```text
sqlalchemy.exc.OperationalError: (psycopg.OperationalError) connection failed: connection to server at "172.21.0.2", port 5432 failed: FATAL:  password authentication failed for user "social"
```

PostgreSQL applies `POSTGRES_PASSWORD` only when it first creates the database, so the
existing database still has the old password. Change it inside the database too
(replace `NEW_PASSWORD` with the value now in `.env`), or put the old value back:

```bash
docker compose exec db sh -c "psql -U \"\$POSTGRES_USER\" -d postgres -c \"ALTER USER \\\"\$POSTGRES_USER\\\" PASSWORD 'NEW_PASSWORD'\""
```

**`pytest` fails with `database "social_network_test" does not exist`.** Create the test
database once (step 5 of [local development](#c-local-development-with-uv)). If it says
`Refusing to run: the test database name must end with '_test'`, fix `TEST_DATABASE_URL`
in `.env`: the tests never run against a database whose name does not end in `_test`.

**I copied `.env.example` again and lost my `.env`.** A plain `cp .env.example .env`
overwrites the file. Use `cp -n`, which skips an existing file. (On macOS `cp -n` also
exits with status 1 when it skips, so do not chain it with `&&`.) Restoring a lost key
means a new key: everyone has to log in again.

## Roadmap

All eight milestones are done.

| # | Milestone | Status |
| - | --------- | ------ |
| 1 | Project skeleton and Git workflow | done |
| 2 | Database schema and migrations | done |
| 3 | REST API: users, posts, comments, likes | done |
| 4 | Authentication and authorization | done |
| 5 | Automated tests on a real database | done |
| 6 | Docker image and Docker Compose | done |
| 7 | CI pipeline with GitHub Actions | done |
| 8 | Image publishing to GHCR and a deploy guide | done |

Possible next steps:

- **Refresh tokens and token revocation**, so a stolen token can be cut off before it
  expires.
- **Rate limiting** on login and registration, which also closes the account-enumeration
  gap noted above.
- **HTTPS in the stack**: a Caddy or nginx service in `compose.prod.yml` instead of a
  manual reverse proxy.
- **Follows and a personal feed**, with an index on `posts (created_at DESC)` for the
  global feed.
- **Cursor pagination** for long feeds, and email confirmation of new accounts.

## License

MIT — see [LICENSE](LICENSE).
