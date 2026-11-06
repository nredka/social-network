# IT Cluster Social Network

[![CI](https://github.com/nredka/social-network/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/nredka/social-network/actions/workflows/ci.yml)

A social networking backend built with FastAPI and PostgreSQL. This is an academic
project: it is built step by step to practice backend development, databases, Docker
and CI/CD.

**Current status:** project skeleton, the database layer (PostgreSQL schema for users,
posts, comments and likes with Alembic migrations), a REST API on top of it and a CI
pipeline that lints, applies the migrations and runs the tests on every push and pull
request. Users log in and call the API with a JWT bearer token, and only the author can
edit or delete their own posts and comments (see [API](#api)).

**Roadmap**

| Milestone | Topic                                    | Status  |
| --------- | ---------------------------------------- | ------- |
| 1         | Project skeleton and Git workflow        | done    |
| 2         | Database schema and migrations           | done    |
| 7         | CI pipeline (GitHub Actions)             | done    |
| 3         | REST API (users, posts, comments, likes) | done    |
| 4         | Authentication and authorization         | done    |
| 5         | Tests against a real database            | next    |
| 6         | Docker image and Compose for the app     | planned |
| 8         | Docker image build and deploy docs       | planned |

The order of the remaining work is 5 → 6 → 8.

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

Generate a secret for signing access tokens and put it in `.env` as `JWT_SECRET_KEY`
(the placeholder `change-me` is rejected on startup, and so is any key shorter than 32
characters):

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

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

### Authentication

1. **Register** with `POST /auth/register` (the password is stored only as an argon2 hash).
2. **Log in** with `POST /auth/login`. It takes a form (`username` and `password`, as the
   OAuth2 password flow defines); the `username` field accepts the user's **email or
   username**. It returns `{"access_token": "...", "token_type": "bearer"}`.
3. **Send the token** on every request that needs a user:
   `Authorization: Bearer <access_token>`.

Access tokens are JWTs signed with HS256 and valid for 30 minutes
(`ACCESS_TOKEN_EXPIRE_MINUTES`). There are no refresh tokens: after a token expires, log in
again. A token is signed, **not encrypted**, so anyone holding it can read its payload
(`sub`, `iat`, `exp`); it contains nothing sensitive. Because tokens are stateless they
cannot be revoked before they expire.

Security notes:

- A wrong password and an unknown user get the **same** `401` response, and an unknown
  user is still verified against a dummy hash, so neither the body nor the response time
  reveals which accounts exist.
- **Known limitation:** `POST /auth/register` answers `409` with "Email is already
  registered", so registration can still be used to check whether an email has an
  account. Fixing it needs email confirmation (or rate limiting), which this project does
  not have.
- Usernames cannot contain `@`, so login can tell an email from a username.

### Endpoints

| Method and path                  | Auth | Success | Description                                     |
| -------------------------------- | ---- | ------- | ----------------------------------------------- |
| `POST /auth/register`            | no   | 201     | Create an account (409 if email/username taken) |
| `POST /auth/login`               | no   | 200     | Exchange credentials for an access token        |
| `GET /users/me`                  | yes  | 200     | Own profile, including the email                |
| `PATCH /users/me`                | yes  | 200     | Change `username` and/or `bio`                  |
| `GET /users/{id}`                | no   | 200     | Public profile (no email), 404 if missing       |
| `POST /posts`                    | yes  | 201     | Create a post                                   |
| `GET /posts`                     | no   | 200     | Newest first; filter `author_id`; `limit`, `offset` |
| `GET /posts/{id}`                | no   | 200     | One post, 404 if missing                        |
| `PATCH /posts/{id}`              | yes  | 200     | Edit a post (author only, else 403)             |
| `DELETE /posts/{id}`             | yes  | 204     | Delete a post with its comments and likes (author only) |
| `POST /posts/{id}/comments`      | yes  | 201     | Comment on a post                               |
| `GET /posts/{id}/comments`       | no   | 200     | Oldest first; `limit`, `offset`                 |
| `DELETE /comments/{id}`          | yes  | 204     | Delete a comment (its author only, else 403)    |
| `PUT /posts/{id}/like`           | yes  | 204     | Like a post (idempotent)                        |
| `DELETE /posts/{id}/like`        | yes  | 204     | Remove the like (idempotent)                    |

Status codes: `401` missing, invalid, expired or unknown-user token (with
`WWW-Authenticate: Bearer`), `403` you are not the author, `404` post/user/comment not
found, `409` email or username already taken, `422` invalid input (a clear message per
field). When several apply the order is 401, then 404, then 403. Lists accept `limit`
(1-100, default 20) and `offset` (default 0).

### Try it with curl

```bash
# Register two users
curl -X POST localhost:8000/auth/register -H 'Content-Type: application/json' \
  -d '{"email":"alice@example.com","username":"alice","password":"s3cretpass"}'
curl -X POST localhost:8000/auth/register -H 'Content-Type: application/json' \
  -d '{"email":"bob@example.com","username":"bobby","password":"s3cretpass"}'

# Log in (a form, not JSON) and keep the tokens in shell variables
ALICE=$(curl -s -X POST localhost:8000/auth/login \
  -d 'username=alice&password=s3cretpass' | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')
BOB=$(curl -s -X POST localhost:8000/auth/login \
  -d 'username=bob@example.com&password=s3cretpass' | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

# Your own profile
curl localhost:8000/users/me -H "Authorization: Bearer $ALICE"

# Alice writes a post
curl -X POST localhost:8000/posts -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $ALICE" -d '{"content":"Hello from Alice"}'

# Bob comments and likes it (liking twice still leaves a single like)
curl -X POST localhost:8000/posts/1/comments -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $BOB" -d '{"content":"Nice post!"}'
curl -X PUT localhost:8000/posts/1/like -H "Authorization: Bearer $BOB"

# Bob cannot edit Alice's post: 403. Alice can.
curl -X PATCH localhost:8000/posts/1 -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $BOB" -d '{"content":"hacked"}'
curl -X PATCH localhost:8000/posts/1 -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $ALICE" -d '{"content":"edited by Alice"}'

# Read it back (no token needed)
curl localhost:8000/posts
curl localhost:8000/posts/1/comments
```

### Try it in Swagger

Open http://localhost:8000/docs and register a user with `POST /auth/register`. Then
click the **Authorize** button (top right), enter the user's email or username in
`username` and the password in `password`, leave `client_id` and `client_secret` empty
and click **Authorize**, then **Close**. Swagger calls `POST /auth/login` for you and
sends the token with every request: the padlock icons next to the endpoints marked
"yes" in the table are now closed, so **Try it out** works for them. Use **Logout** in
the same dialog to switch to another user.

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
| `JWT_SECRET_KEY`    | none (required)             | Signs access tokens, at least 32 characters |
| `JWT_ALGORITHM`     | `HS256`                     | Token signing algorithm                     |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30`              | Lifetime of an access token                 |

## Project layout

```
app/
├── main.py        # FastAPI app, includes the routers
├── config.py      # Settings loaded from the environment
├── database.py    # Engine, session factory and get_db dependency
├── deps.py        # Shared dependencies (DB session, current user from the JWT)
├── pagination.py  # limit/offset query parameters
├── errors.py      # IntegrityError -> 409 translation
├── security.py    # Password hashing (argon2) and JWT creation/verification
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
