from datetime import UTC, datetime, timedelta

import pytest

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def at(minutes: int) -> datetime:
    """Distinct creation times: now() is constant inside a test's transaction."""
    return T0 + timedelta(minutes=minutes)


def comments_url(post_id: int) -> str:
    return f"/posts/{post_id}/comments"


# --- create -----------------------------------------------------------------


def test_create_comment_takes_the_author_from_the_token(
    client, bob, alice_post, auth_headers
):
    response = client.post(
        comments_url(alice_post.id),
        json={"content": "  Nice post!  "},
        headers=auth_headers(bob),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["author_id"] == bob.id
    assert body["post_id"] == alice_post.id
    assert body["content"] == "Nice post!"


def test_create_comment_requires_a_token(client, alice_post):
    response = client.post(comments_url(alice_post.id), json={"content": "Hi"})

    assert response.status_code == 401


def test_commenting_on_a_missing_post_is_404(client, alice, auth_headers):
    response = client.post(
        comments_url(999999), json={"content": "Hi"}, headers=auth_headers(alice)
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Post not found"}


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"content": ""}, id="empty"),
        pytest.param({"content": "   "}, id="only-spaces"),
        pytest.param({"content": "x" * 2001}, id="too-long"),
        pytest.param({}, id="missing-content"),
        pytest.param({"content": "Hi", "author_id": 1}, id="author-in-body"),
        pytest.param({"content": "Hi", "post_id": 1}, id="post-in-body"),
    ],
)
def test_create_comment_rejects_invalid_input(
    client, bob, alice_post, auth_headers, payload
):
    response = client.post(
        comments_url(alice_post.id), json=payload, headers=auth_headers(bob)
    )

    assert response.status_code == 422


def test_create_comment_accepts_the_longest_allowed_content(
    client, bob, alice_post, auth_headers
):
    response = client.post(
        comments_url(alice_post.id),
        json={"content": "x" * 2000},
        headers=auth_headers(bob),
    )

    assert response.status_code == 201


# --- list -------------------------------------------------------------------


def test_list_comments_returns_the_oldest_first(
    client, alice, bob, alice_post, comment_factory
):
    comment_factory(alice_post, bob, "second", created_at=at(10))
    comment_factory(alice_post, alice, "first", created_at=at(0))
    comment_factory(alice_post, bob, "third", created_at=at(20))

    response = client.get(comments_url(alice_post.id))

    assert response.status_code == 200
    assert [c["content"] for c in response.json()] == ["first", "second", "third"]


def test_list_comments_breaks_ties_by_id_so_pages_are_stable(
    client, bob, alice_post, comment_factory
):
    first = comment_factory(alice_post, bob, "first", created_at=at(0))
    second = comment_factory(alice_post, bob, "second", created_at=at(0))

    ids = [c["id"] for c in client.get(comments_url(alice_post.id)).json()]

    assert ids == [first.id, second.id]


def test_list_comments_does_not_need_a_token(client, bob, alice_post, comment_factory):
    comment_factory(alice_post, bob, "public")

    response = client.get(comments_url(alice_post.id))

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_list_comments_of_a_post_without_comments_is_an_empty_list(
    client, alice_post
):
    response = client.get(comments_url(alice_post.id))

    assert response.status_code == 200
    assert response.json() == []


def test_list_comments_of_a_missing_post_is_404(client):
    response = client.get(comments_url(999999))

    assert response.status_code == 404


def test_list_comments_paginates_with_limit_and_offset(
    client, bob, alice_post, comment_factory
):
    for minute in range(5):
        comment_factory(alice_post, bob, f"comment {minute}", created_at=at(minute))
    url = comments_url(alice_post.id)

    page1 = client.get(url, params={"limit": 2, "offset": 0}).json()
    page2 = client.get(url, params={"limit": 2, "offset": 2}).json()
    page3 = client.get(url, params={"limit": 2, "offset": 4}).json()

    assert [c["content"] for c in page1] == ["comment 0", "comment 1"]
    assert [c["content"] for c in page2] == ["comment 2", "comment 3"]
    assert [c["content"] for c in page3] == ["comment 4"]


@pytest.mark.parametrize(
    "params",
    [
        pytest.param({"limit": 0}, id="limit-zero"),
        pytest.param({"limit": 101}, id="limit-over-100"),
        pytest.param({"offset": -1}, id="negative-offset"),
    ],
)
def test_list_comments_rejects_bad_query_parameters(client, alice_post, params):
    response = client.get(comments_url(alice_post.id), params=params)

    assert response.status_code == 422


# --- delete -----------------------------------------------------------------


def test_author_can_delete_the_comment(
    client, bob, alice_post, comment_factory, auth_headers
):
    comment = comment_factory(alice_post, bob, "mine")

    response = client.delete(f"/comments/{comment.id}", headers=auth_headers(bob))

    assert response.status_code == 204
    assert response.content == b""
    assert client.get(comments_url(alice_post.id)).json() == []


def test_other_users_cannot_delete_the_comment(
    client, alice, bob, alice_post, post_factory, comment_factory, auth_headers
):
    bobs_post = post_factory(bob, "Bob's post")
    comment = comment_factory(bobs_post, alice, "Alice's comment")
    stranger_headers = auth_headers(bob)

    response = client.delete(f"/comments/{comment.id}", headers=stranger_headers)

    assert response.status_code == 403
    assert response.json() == {"detail": "You can only delete your own comments"}
    assert len(client.get(comments_url(bobs_post.id)).json()) == 1


def test_post_author_cannot_delete_someone_elses_comment_under_their_post(
    client, alice, bob, alice_post, comment_factory, auth_headers
):
    # Ownership is about the comment's author, not the post's author.
    comment = comment_factory(alice_post, bob, "Bob's comment")

    response = client.delete(f"/comments/{comment.id}", headers=auth_headers(alice))

    assert response.status_code == 403
    assert len(client.get(comments_url(alice_post.id)).json()) == 1


def test_delete_comment_requires_a_token(client, bob, alice_post, comment_factory):
    comment = comment_factory(alice_post, bob, "x")

    assert client.delete(f"/comments/{comment.id}").status_code == 401


def test_deleting_a_missing_comment_is_404(client, alice, auth_headers):
    response = client.delete("/comments/999999", headers=auth_headers(alice))

    assert response.status_code == 404
    assert response.json() == {"detail": "Comment not found"}


def test_deleting_a_comment_twice_gives_404_the_second_time(
    client, bob, alice_post, comment_factory, auth_headers
):
    comment = comment_factory(alice_post, bob, "x")
    client.delete(f"/comments/{comment.id}", headers=auth_headers(bob))

    response = client.delete(f"/comments/{comment.id}", headers=auth_headers(bob))

    assert response.status_code == 404
