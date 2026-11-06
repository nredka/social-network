import pytest
from sqlalchemy import text

from app.database import get_db


def test_get_db_yields_a_working_session_and_closes_it():
    # The suite replaces get_db with a per-test session, so the real one is checked
    # here directly.
    generator = get_db()
    session = next(generator)
    assert session.execute(text("select 1")).scalar() == 1
    assert session.in_transaction()

    generator.close()  # runs the finally block, like FastAPI after the response

    assert not session.in_transaction()


def test_get_db_closes_the_session_even_when_the_handler_raises():
    generator = get_db()
    session = next(generator)
    session.execute(text("select 1"))

    with pytest.raises(RuntimeError):
        generator.throw(RuntimeError("the handler failed"))

    assert not session.in_transaction()
