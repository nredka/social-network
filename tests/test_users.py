import pytest


def test_me_returns_the_own_profile_with_the_email(client, alice, auth_headers):
    response = client.get("/users/me", headers=auth_headers(alice))

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == alice.id
    assert body["username"] == "alice"
    assert body["email"] == "alice@example.com"


def test_me_requires_a_token(client):
    assert client.get("/users/me").status_code == 401


def test_patch_me_changes_the_bio(client, alice, auth_headers):
    response = client.patch(
        "/users/me", json={"bio": "  Hello there  "}, headers=auth_headers(alice)
    )

    assert response.status_code == 200
    assert response.json()["bio"] == "Hello there"
    # The change persisted.
    assert client.get("/users/me", headers=auth_headers(alice)).json()["bio"] == (
        "Hello there"
    )


def test_patch_me_ignores_fields_that_were_not_sent(client, user_factory, auth_headers):
    user = user_factory("carol", bio="original bio")

    # Only the username is sent. The bio must not be overwritten with None.
    response = client.patch(
        "/users/me", json={"username": "caroline"}, headers=auth_headers(user)
    )

    assert response.status_code == 200
    assert response.json()["username"] == "caroline"
    assert response.json()["bio"] == "original bio"


def test_patch_me_can_clear_the_bio_with_null(client, user_factory, auth_headers):
    user = user_factory("carol", bio="original bio")

    response = client.patch("/users/me", json={"bio": None}, headers=auth_headers(user))

    assert response.status_code == 200
    assert response.json()["bio"] is None


def test_patch_me_with_an_empty_body_changes_nothing(client, alice, auth_headers):
    response = client.patch("/users/me", json={}, headers=auth_headers(alice))

    assert response.status_code == 200
    assert response.json()["username"] == "alice"


def test_patch_me_cannot_take_a_username_that_is_used(
    client, alice, bob, auth_headers
):
    response = client.patch(
        "/users/me", json={"username": "bobby"}, headers=auth_headers(alice)
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Username is already taken"}
    # The failed update did not leave alice with a broken session or a changed name.
    assert client.get("/users/me", headers=auth_headers(alice)).json()["username"] == (
        "alice"
    )


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"username": None}, id="username-null"),
        pytest.param({"username": "ab"}, id="username-too-short"),
        pytest.param({"username": "has@sign"}, id="username-with-at-sign"),
        pytest.param({"bio": "x" * 501}, id="bio-too-long"),
        pytest.param({"email": "new@example.com"}, id="email-is-not-editable"),
        pytest.param({"id": 99}, id="id-is-not-editable"),
        pytest.param({"password_hash": "x"}, id="hash-is-not-editable"),
    ],
)
def test_patch_me_rejects_invalid_input(client, alice, auth_headers, payload):
    response = client.patch("/users/me", json=payload, headers=auth_headers(alice))

    assert response.status_code == 422


def test_patch_me_requires_a_token(client):
    assert client.patch("/users/me", json={"bio": "x"}).status_code == 401


def test_public_profile_has_no_email(client, alice):
    response = client.get(f"/users/{alice.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "alice"
    assert "email" not in body
    assert "password" not in response.text.lower()


def test_public_profile_needs_no_token(client, alice):
    assert client.get(f"/users/{alice.id}").status_code == 200


def test_unknown_user_is_404(client):
    response = client.get("/users/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "User not found"}


@pytest.mark.parametrize("user_id", ["0", "-1", "99999999999", "abc"])
def test_a_bad_user_id_is_422_not_a_server_error(client, user_id):
    # 99999999999 exceeds PostgreSQL's integer range and used to cause a 500.
    assert client.get(f"/users/{user_id}").status_code == 422
