from collections.abc import Callable

from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import engine
from app.models import User


def test_app_is_wired_to_the_test_database() -> None:
    # If this fails the suite would be writing to the development database.
    assert make_url(get_settings().database_url).database.endswith("_test")
    assert engine.url.database.endswith("_test")


# The next two tests do exactly the same thing. Without per-test rollback the second
# one would fail on the UNIQUE constraints, whichever runs first.
def test_creating_alice_works_the_first_time(
    db_session: Session, user_factory: Callable[..., User]
) -> None:
    assert db_session.scalar(select(func.count()).select_from(User)) == 0
    user_factory("alice")
    assert db_session.scalar(select(func.count()).select_from(User)) == 1


def test_creating_alice_works_the_second_time(
    db_session: Session, user_factory: Callable[..., User]
) -> None:
    assert db_session.scalar(select(func.count()).select_from(User)) == 0
    user_factory("alice")
    assert db_session.scalar(select(func.count()).select_from(User)) == 1


def test_rollback_in_a_route_does_not_lose_the_test_data(
    client, alice: User
) -> None:
    # The 409 path calls db.rollback(). Alice, created before the request, must
    # survive it: this is what the savepoint is for.
    response = client.post(
        "/auth/register",
        json={
            "email": "alice@example.com",
            "username": "someone-else",
            "password": "s3cretpass",
        },
    )

    assert response.status_code == 409
    assert client.get(f"/users/{alice.id}").status_code == 200
