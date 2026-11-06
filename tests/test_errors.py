import pytest
from sqlalchemy.exc import IntegrityError

from app.errors import to_conflict


class _DriverError(Exception):
    """Stands in for the database driver's exception."""

    def __init__(self, sqlstate: str, constraint: str | None = None) -> None:
        self.sqlstate = sqlstate
        self.diag = type("Diag", (), {"constraint_name": constraint})()


def test_a_unique_violation_becomes_a_409_naming_the_field():
    exc = IntegrityError("INSERT", {}, _DriverError("23505", "uq_users_email"))

    result = to_conflict(exc)

    assert result.status_code == 409
    assert result.detail == "Email is already registered"


def test_an_unknown_unique_constraint_still_gives_a_409():
    exc = IntegrityError("INSERT", {}, _DriverError("23505", "uq_something_new"))

    result = to_conflict(exc)

    assert result.status_code == 409
    assert result.detail == "Resource already exists"


def test_other_integrity_errors_are_not_hidden_as_a_409():
    # A CHECK violation (23514) means a bug in our code, not a client mistake.
    exc = IntegrityError("INSERT", {}, _DriverError("23514"))

    with pytest.raises(IntegrityError):
        to_conflict(exc)
