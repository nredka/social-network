"""Shared pytest setup: a separate test database, migrations, per-test rollback.

The environment is configured BEFORE the application is imported. app.main builds the
cached Settings at import time, so DATABASE_URL has to point at the test database by
then; otherwise the tests would run against the development database.
"""

import os
from collections.abc import Callable, Iterator
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_PASSWORD = "s3cretpass"
TEST_JWT_SECRET_KEY = "test-only-jwt-secret-key-with-at-least-32-characters"


class _DbSettings(BaseSettings):
    """Reads TEST_DATABASE_URL from the environment or from .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    test_database_url: str


def _load_test_database_url() -> str:
    try:
        url = _DbSettings().test_database_url
    except ValidationError:
        pytest.exit(
            "TEST_DATABASE_URL is not set. Create the test database and set the "
            "variable (see README and .env.example).",
            returncode=2,
        )
    database = make_url(url).database or ""
    # Safety guard: never run against a database that is not clearly a test one.
    if not database.endswith("_test"):
        pytest.exit(
            f"Refusing to run: the test database name must end with '_test', got "
            f"{database!r}. The tests would modify data in it.",
            returncode=2,
        )
    return url


TEST_DATABASE_URL = _load_test_database_url()

# Environment variables take priority over .env, so these win over the developer's
# settings. This must run before "import app" below.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["JWT_SECRET_KEY"] = TEST_JWT_SECRET_KEY

from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from alembic import command  # noqa: E402
from app.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Comment, Post, User  # noqa: E402
from app.security import create_access_token, hash_password  # noqa: E402


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    engine = create_engine(TEST_DATABASE_URL)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def migrated_database(engine: Engine) -> None:
    """Apply the Alembic migrations once per session.

    The tests therefore also prove that the migrations build a working schema.
    """
    command.upgrade(Config(str(PROJECT_ROOT / "alembic.ini")), "head")


@pytest.fixture
def db_session(engine: Engine) -> Iterator[Session]:
    """A session whose work is rolled back after the test.

    The session joins an outer transaction through a SAVEPOINT. Our routes call
    commit() and rollback() (the 409 path). With a savepoint, commit() only releases
    it and rollback() only goes back to it, so the outer transaction stays alive and
    is rolled back at the end, leaving the database untouched.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,  # same as the application's SessionLocal
    )
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    """A test client whose requests use the per-test session."""
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def password() -> str:
    """The password every factory-made user has."""
    return TEST_PASSWORD


@pytest.fixture(scope="session")
def password_hash() -> str:
    # argon2 is slow on purpose, so hash once per session and reuse the result.
    # Production hashing is untouched; /auth/login and /auth/register are still
    # exercised with the real thing in test_auth.py.
    return hash_password(TEST_PASSWORD)


@pytest.fixture
def user_factory(
    db_session: Session, password_hash: str
) -> Callable[..., User]:
    def create(
        username: str, email: str | None = None, bio: str | None = None
    ) -> User:
        user = User(
            username=username,
            email=email or f"{username}@example.com",
            password_hash=password_hash,
            bio=bio,
        )
        db_session.add(user)
        db_session.commit()
        return user

    return create


@pytest.fixture
def alice(user_factory: Callable[..., User]) -> User:
    return user_factory("alice")


@pytest.fixture
def bob(user_factory: Callable[..., User]) -> User:
    return user_factory("bobby")


@pytest.fixture
def auth_headers() -> Callable[[User], dict[str, str]]:
    """Build the Authorization header for a user.

    The token is minted directly, which skips argon2 and keeps the suite fast. The
    real /auth/login endpoint is covered by test_auth.py.
    """

    def make(user: User) -> dict[str, str]:
        return {"Authorization": f"Bearer {create_access_token(user.id)}"}

    return make


@pytest.fixture
def post_factory(db_session: Session) -> Callable[..., Post]:
    # created_at is explicit on purpose. PostgreSQL's now() is the start of the
    # TRANSACTION, and a whole test runs in one, so every row would get the same
    # time and ordering tests would prove nothing.
    def create(
        author: User, content: str = "A test post", created_at: datetime | None = None
    ) -> Post:
        post = Post(author_id=author.id, content=content)
        if created_at is not None:
            post.created_at = created_at
        db_session.add(post)
        db_session.commit()
        return post

    return create


@pytest.fixture
def comment_factory(db_session: Session) -> Callable[..., Comment]:
    def create(
        post: Post,
        author: User,
        content: str = "A test comment",
        created_at: datetime | None = None,
    ) -> Comment:
        comment = Comment(post_id=post.id, author_id=author.id, content=content)
        if created_at is not None:
            comment.created_at = created_at
        db_session.add(comment)
        db_session.commit()
        return comment

    return create


@pytest.fixture
def alice_post(post_factory: Callable[..., Post], alice: User) -> Post:
    return post_factory(alice, "Alice's post")
