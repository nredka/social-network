import base64
import json
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.config import get_settings
from app.models import User

VALID_REGISTRATION = {
    "email": "carol@example.com",
    "username": "carol",
    "password": "s3cretpass",
}


def make_token(
    user_id: int,
    *,
    secret: str | None = None,
    expires_in: timedelta = timedelta(minutes=5),
) -> str:
    """Build a signed token. Used to craft expired or foreign-signed tokens."""
    now = datetime.now(UTC)
    return jwt.encode(
        {"sub": str(user_id), "iat": now - timedelta(hours=1), "exp": now + expires_in},
        secret or get_settings().jwt_secret_key,
        algorithm="HS256",
    )


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- registration -----------------------------------------------------------


def test_register_creates_the_user(client):
    # Arrange: the payload. Act: register. Assert: status and body.
    response = client.post("/auth/register", json=VALID_REGISTRATION)

    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "carol"
    assert body["email"] == "carol@example.com"
    assert body["bio"] is None
    assert isinstance(body["id"], int)


def test_register_never_returns_the_password_or_its_hash(client):
    response = client.post("/auth/register", json=VALID_REGISTRATION)

    assert "password" not in response.text.lower()
    assert set(response.json()) == {"id", "username", "bio", "created_at", "email"}


def test_register_stores_an_argon2_hash_not_the_password(client, db_session):
    client.post("/auth/register", json=VALID_REGISTRATION)

    user = db_session.query(User).filter_by(username="carol").one()
    assert user.password_hash != "s3cretpass"
    assert user.password_hash.startswith("$argon2id$")


def test_register_normalizes_the_email_to_lowercase(client):
    response = client.post(
        "/auth/register", json={**VALID_REGISTRATION, "email": "Carol@Example.COM"}
    )

    assert response.json()["email"] == "carol@example.com"


def test_register_rejects_a_duplicate_email_in_any_case(client, alice):
    response = client.post(
        "/auth/register",
        json={**VALID_REGISTRATION, "email": "ALICE@example.com"},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Email is already registered"}


def test_register_rejects_a_duplicate_username(client, alice):
    response = client.post(
        "/auth/register", json={**VALID_REGISTRATION, "username": "alice"}
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Username is already taken"}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        pytest.param("email", "not-an-email", id="invalid-email"),
        pytest.param("username", "ab", id="username-too-short"),
        pytest.param("username", "x" * 51, id="username-too-long"),
        pytest.param("username", "bad@name", id="username-with-at-sign"),
        pytest.param("username", "   ", id="username-only-spaces"),
        pytest.param("password", "short", id="password-too-short"),
        pytest.param("password", "x" * 129, id="password-too-long"),
    ],
)
def test_register_rejects_invalid_input(client, field, value):
    response = client.post("/auth/register", json={**VALID_REGISTRATION, field: value})

    assert response.status_code == 422
    assert field in json.dumps(response.json()["detail"])


def test_register_rejects_unknown_fields(client):
    # "id" and "password_hash" must not be settable by the client (mass assignment).
    response = client.post(
        "/auth/register", json={**VALID_REGISTRATION, "password_hash": "x", "id": 99}
    )

    assert response.status_code == 422


# --- login ------------------------------------------------------------------


@pytest.mark.parametrize(
    "identifier",
    ["alice", "alice@example.com", "ALICE@Example.com"],
    ids=["by-username", "by-email", "by-email-any-case"],
)
def test_login_accepts_username_or_email(client, alice, password, identifier):
    response = client.post(
        "/auth/login", data={"username": identifier, "password": password}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    # The token really works.
    me = client.get("/users/me", headers=bearer(body["access_token"]))
    assert me.status_code == 200
    assert me.json()["id"] == alice.id


def test_wrong_password_and_unknown_user_look_identical(client, alice):
    wrong_password = client.post(
        "/auth/login", data={"username": "alice", "password": "wrong-password"}
    )
    unknown_user = client.post(
        "/auth/login", data={"username": "nobody", "password": "wrong-password"}
    )

    # Different bodies would let an attacker find out which accounts exist.
    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json() == unknown_user.json()
    assert wrong_password.headers["www-authenticate"] == "Bearer"
    assert unknown_user.headers["www-authenticate"] == "Bearer"


def test_login_rejects_a_password_longer_than_registration_allows(client, alice):
    response = client.post(
        "/auth/login", data={"username": "alice", "password": "x" * 500}
    )

    assert response.status_code == 401


def test_login_requires_both_fields(client):
    assert client.post("/auth/login", data={"username": "alice"}).status_code == 422


# --- bearer authentication --------------------------------------------------


def test_request_without_a_token_is_rejected(client):
    response = client.get("/users/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_the_old_x_user_id_header_no_longer_works(client, alice):
    response = client.get("/users/me", headers={"X-User-Id": str(alice.id)})

    assert response.status_code == 401


def test_a_valid_token_authenticates(client, alice):
    response = client.get("/users/me", headers=bearer(make_token(alice.id)))

    assert response.status_code == 200
    assert response.json()["username"] == "alice"


def test_a_tampered_token_is_rejected(client, alice):
    header, payload, signature = make_token(alice.id).split(".")
    flipped = ("A" if signature[0] != "A" else "B") + signature[1:]

    response = client.get("/users/me", headers=bearer(f"{header}.{payload}.{flipped}"))

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_a_payload_edited_to_another_user_is_rejected(client, alice, bob):
    header, payload, signature = make_token(alice.id).split(".")
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    claims["sub"] = str(bob.id)
    forged = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()

    response = client.get("/users/me", headers=bearer(f"{header}.{forged}.{signature}"))

    assert response.status_code == 401


def test_an_expired_token_is_rejected(client, alice):
    expired = make_token(alice.id, expires_in=timedelta(minutes=-1))

    response = client.get("/users/me", headers=bearer(expired))

    assert response.status_code == 401


def test_a_token_signed_with_another_secret_is_rejected(client, alice):
    foreign = make_token(alice.id, secret="another-secret-of-more-than-32-characters")

    response = client.get("/users/me", headers=bearer(foreign))

    assert response.status_code == 401


def test_an_unsigned_token_with_alg_none_is_rejected(client, alice):
    def encode(part: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(part).encode()).rstrip(b"=").decode()

    now = int(datetime.now(UTC).timestamp())
    token = ".".join(
        [
            encode({"alg": "none", "typ": "JWT"}),
            encode({"sub": str(alice.id), "iat": now, "exp": now + 3600}),
            "",
        ]
    )

    response = client.get("/users/me", headers=bearer(token))

    assert response.status_code == 401


def test_a_token_without_an_expiry_is_rejected(client, alice):
    no_exp = jwt.encode(
        {"sub": str(alice.id), "iat": datetime.now(UTC)},
        get_settings().jwt_secret_key,
        algorithm="HS256",
    )

    assert client.get("/users/me", headers=bearer(no_exp)).status_code == 401


def test_garbage_and_wrong_scheme_are_rejected(client):
    assert client.get("/users/me", headers=bearer("garbage")).status_code == 401
    basic = {"Authorization": "Basic YWxpY2U6czNjcmV0cGFzcw=="}
    assert client.get("/users/me", headers=basic).status_code == 401


def test_a_token_of_a_deleted_user_is_rejected(client, db_session, alice):
    token = make_token(alice.id)
    db_session.delete(alice)
    db_session.commit()

    assert client.get("/users/me", headers=bearer(token)).status_code == 401
