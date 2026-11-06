from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.models import Comment, Like, Post

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def at(minutes: int) -> datetime:
    """Distinct creation times: now() is constant inside a test's transaction."""
    return T0 + timedelta(minutes=minutes)


# --- create -----------------------------------------------------------------


def test_create_post_takes_the_author_from_the_token(client, alice, auth_headers):
    response = client.post(
        "/posts", json={"content": "  Hello world  "}, headers=auth_headers(alice)
    )

    assert response.status_code == 201
    body = response.json()
    assert body["author_id"] == alice.id
    assert body["content"] == "Hello world"
    assert isinstance(body["id"], int)


def test_create_post_does_not_accept_an_author_in_the_body(
    client, alice, bob, auth_headers
):
    # Otherwise Alice could post as Bob.
    response = client.post(
        "/posts",
        json={"content": "Hi", "author_id": bob.id},
        headers=auth_headers(alice),
    )

    assert response.status_code == 422


def test_create_post_requires_a_token(client):
    assert client.post("/posts", json={"content": "Hi"}).status_code == 401


@pytest.mark.parametrize(
    "content",
    ["", "   ", "x" * 5001],
    ids=["empty", "only-spaces", "too-long"],
)
def test_create_post_rejects_invalid_content(client, alice, auth_headers, content):
    response = client.post(
        "/posts", json={"content": content}, headers=auth_headers(alice)
    )

    assert response.status_code == 422


def test_create_post_accepts_the_longest_allowed_content(client, alice, auth_headers):
    response = client.post(
        "/posts", json={"content": "x" * 5000}, headers=auth_headers(alice)
    )

    assert response.status_code == 201


# --- read and list ----------------------------------------------------------


def test_get_post(client, alice_post):
    response = client.get(f"/posts/{alice_post.id}")

    assert response.status_code == 200
    assert response.json()["content"] == "Alice's post"


def test_get_missing_post_is_404(client):
    response = client.get("/posts/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Post not found"}


def test_list_posts_returns_the_newest_first(client, alice, post_factory):
    post_factory(alice, "oldest", created_at=at(0))
    post_factory(alice, "newest", created_at=at(20))
    post_factory(alice, "middle", created_at=at(10))

    response = client.get("/posts")

    assert [p["content"] for p in response.json()] == ["newest", "middle", "oldest"]


def test_list_posts_breaks_ties_by_id_so_pages_are_stable(
    client, alice, post_factory
):
    # Same created_at: without a tie-breaker the order would be undefined.
    first = post_factory(alice, "first", created_at=at(0))
    second = post_factory(alice, "second", created_at=at(0))

    ids = [p["id"] for p in client.get("/posts").json()]

    assert ids == [second.id, first.id]


def test_list_posts_can_filter_by_author(client, alice, bob, post_factory):
    post_factory(alice, "alice 1", created_at=at(0))
    post_factory(bob, "bob 1", created_at=at(1))
    post_factory(alice, "alice 2", created_at=at(2))

    response = client.get("/posts", params={"author_id": alice.id})

    assert [p["content"] for p in response.json()] == ["alice 2", "alice 1"]


def test_list_posts_for_an_author_without_posts_is_an_empty_list(client, alice):
    response = client.get("/posts", params={"author_id": alice.id})

    assert response.status_code == 200
    assert response.json() == []


def test_list_posts_paginates_with_limit_and_offset(client, alice, post_factory):
    for minute in range(5):
        post_factory(alice, f"post {minute}", created_at=at(minute))

    page1 = client.get("/posts", params={"limit": 2, "offset": 0}).json()
    page2 = client.get("/posts", params={"limit": 2, "offset": 2}).json()
    page3 = client.get("/posts", params={"limit": 2, "offset": 4}).json()

    assert [p["content"] for p in page1] == ["post 4", "post 3"]
    assert [p["content"] for p in page2] == ["post 2", "post 1"]
    assert [p["content"] for p in page3] == ["post 0"]


def test_list_posts_default_page_size_is_20(client, alice, post_factory):
    for minute in range(25):
        post_factory(alice, f"post {minute}", created_at=at(minute))

    assert len(client.get("/posts").json()) == 20


@pytest.mark.parametrize(
    "params",
    [
        pytest.param({"limit": 0}, id="limit-zero"),
        pytest.param({"limit": 101}, id="limit-over-100"),
        pytest.param({"offset": -1}, id="negative-offset"),
        pytest.param({"limit": "abc"}, id="limit-not-a-number"),
        pytest.param({"author_id": 0}, id="author-id-zero"),
        pytest.param({"author_id": 99999999999}, id="author-id-out-of-range"),
    ],
)
def test_list_posts_rejects_bad_query_parameters(client, params):
    assert client.get("/posts", params=params).status_code == 422


def test_list_posts_accepts_the_maximum_limit(client):
    assert client.get("/posts", params={"limit": 100}).status_code == 200


# --- update -----------------------------------------------------------------


def test_author_can_edit_the_post(client, alice, alice_post, auth_headers):
    response = client.patch(
        f"/posts/{alice_post.id}",
        json={"content": "edited"},
        headers=auth_headers(alice),
    )

    assert response.status_code == 200
    assert response.json()["content"] == "edited"
    assert client.get(f"/posts/{alice_post.id}").json()["content"] == "edited"


def test_patch_with_an_empty_body_keeps_the_content(
    client, alice, alice_post, auth_headers
):
    response = client.patch(
        f"/posts/{alice_post.id}", json={}, headers=auth_headers(alice)
    )

    assert response.status_code == 200
    assert response.json()["content"] == "Alice's post"


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"content": None}, id="content-null"),
        pytest.param({"content": ""}, id="content-empty"),
        pytest.param({"content": "x" * 5001}, id="content-too-long"),
        pytest.param({"author_id": 2}, id="author-is-not-editable"),
    ],
)
def test_patch_post_rejects_invalid_input(
    client, alice, alice_post, auth_headers, payload
):
    response = client.patch(
        f"/posts/{alice_post.id}", json=payload, headers=auth_headers(alice)
    )

    assert response.status_code == 422


def test_other_users_cannot_edit_the_post(client, bob, alice_post, auth_headers):
    response = client.patch(
        f"/posts/{alice_post.id}",
        json={"content": "hacked"},
        headers=auth_headers(bob),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "You can only change your own posts"}
    assert client.get(f"/posts/{alice_post.id}").json()["content"] == "Alice's post"


def test_patch_post_requires_a_token(client, alice_post):
    response = client.patch(f"/posts/{alice_post.id}", json={"content": "x"})

    assert response.status_code == 401


def test_patching_a_missing_post_is_404(client, alice, auth_headers):
    response = client.patch(
        "/posts/999999", json={"content": "x"}, headers=auth_headers(alice)
    )

    assert response.status_code == 404


# --- delete -----------------------------------------------------------------


def test_author_can_delete_the_post(client, alice, alice_post, auth_headers):
    response = client.delete(f"/posts/{alice_post.id}", headers=auth_headers(alice))

    assert response.status_code == 204
    assert response.content == b""
    assert client.get(f"/posts/{alice_post.id}").status_code == 404


def test_other_users_cannot_delete_the_post(client, bob, alice_post, auth_headers):
    response = client.delete(f"/posts/{alice_post.id}", headers=auth_headers(bob))

    assert response.status_code == 403
    assert client.get(f"/posts/{alice_post.id}").status_code == 200


def test_delete_post_requires_a_token(client, alice_post):
    assert client.delete(f"/posts/{alice_post.id}").status_code == 401


def test_deleting_a_missing_post_is_404(client, alice, auth_headers):
    response = client.delete("/posts/999999", headers=auth_headers(alice))

    assert response.status_code == 404


def test_deleting_a_post_twice_gives_404_the_second_time(
    client, alice, alice_post, auth_headers
):
    client.delete(f"/posts/{alice_post.id}", headers=auth_headers(alice))

    response = client.delete(f"/posts/{alice_post.id}", headers=auth_headers(alice))

    assert response.status_code == 404


def test_deleting_a_post_removes_its_comments_and_likes(
    client, db_session, alice, bob, alice_post, comment_factory, auth_headers
):
    # Arrange: a comment and a like from Bob on Alice's post.
    comment_factory(alice_post, bob, "nice")
    client.put(f"/posts/{alice_post.id}/like", headers=auth_headers(bob))

    def count(model) -> int:
        return db_session.scalar(select(func.count()).select_from(model))

    assert (count(Post), count(Comment), count(Like)) == (1, 1, 1)

    # Act
    response = client.delete(f"/posts/{alice_post.id}", headers=auth_headers(alice))

    # Assert: the database cascaded the delete.
    assert response.status_code == 204
    assert (count(Post), count(Comment), count(Like)) == (0, 0, 0)
