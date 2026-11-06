import pytest
from sqlalchemy import func, select

from app.models import Like


def like_count(db_session, post_id: int) -> int:
    return db_session.scalar(
        select(func.count()).select_from(Like).where(Like.post_id == post_id)
    )


def test_liking_a_post_creates_one_like(
    client, db_session, bob, alice_post, auth_headers
):
    response = client.put(f"/posts/{alice_post.id}/like", headers=auth_headers(bob))

    assert response.status_code == 204
    assert response.content == b""
    assert like_count(db_session, alice_post.id) == 1


def test_liking_twice_still_leaves_one_like(
    client, db_session, bob, alice_post, auth_headers
):
    url = f"/posts/{alice_post.id}/like"

    first = client.put(url, headers=auth_headers(bob))
    second = client.put(url, headers=auth_headers(bob))

    # Idempotent: the second PUT is not an error, and it adds nothing.
    assert first.status_code == second.status_code == 204
    assert like_count(db_session, alice_post.id) == 1


def test_different_users_each_get_their_own_like(
    client, db_session, alice, bob, alice_post, auth_headers
):
    url = f"/posts/{alice_post.id}/like"

    client.put(url, headers=auth_headers(alice))  # liking your own post is allowed
    client.put(url, headers=auth_headers(bob))

    assert like_count(db_session, alice_post.id) == 2


def test_unliking_removes_the_like(client, db_session, bob, alice_post, auth_headers):
    url = f"/posts/{alice_post.id}/like"
    client.put(url, headers=auth_headers(bob))

    response = client.delete(url, headers=auth_headers(bob))

    assert response.status_code == 204
    assert like_count(db_session, alice_post.id) == 0


def test_unliking_twice_is_not_an_error(
    client, db_session, bob, alice_post, auth_headers
):
    url = f"/posts/{alice_post.id}/like"
    client.put(url, headers=auth_headers(bob))

    first = client.delete(url, headers=auth_headers(bob))
    second = client.delete(url, headers=auth_headers(bob))

    assert first.status_code == second.status_code == 204
    assert like_count(db_session, alice_post.id) == 0


def test_unliking_a_post_you_never_liked_is_not_an_error(
    client, bob, alice_post, auth_headers
):
    response = client.delete(f"/posts/{alice_post.id}/like", headers=auth_headers(bob))

    assert response.status_code == 204


def test_unliking_only_removes_your_own_like(
    client, db_session, alice, bob, alice_post, auth_headers
):
    url = f"/posts/{alice_post.id}/like"
    client.put(url, headers=auth_headers(alice))
    client.put(url, headers=auth_headers(bob))

    client.delete(url, headers=auth_headers(alice))

    remaining = db_session.scalars(select(Like.user_id)).all()
    assert remaining == [bob.id]


def test_likes_survive_an_edit_of_the_post(
    client, db_session, alice, bob, alice_post, auth_headers
):
    client.put(f"/posts/{alice_post.id}/like", headers=auth_headers(bob))

    client.patch(
        f"/posts/{alice_post.id}",
        json={"content": "edited"},
        headers=auth_headers(alice),
    )

    assert like_count(db_session, alice_post.id) == 1


@pytest.mark.parametrize("method", ["put", "delete"])
def test_liking_or_unliking_a_missing_post_is_404(client, bob, auth_headers, method):
    response = getattr(client, method)("/posts/999999/like", headers=auth_headers(bob))

    assert response.status_code == 404
    assert response.json() == {"detail": "Post not found"}


@pytest.mark.parametrize("method", ["put", "delete"])
def test_liking_or_unliking_requires_a_token(client, alice_post, method):
    response = getattr(client, method)(f"/posts/{alice_post.id}/like")

    assert response.status_code == 401


@pytest.mark.parametrize("method", ["put", "delete"])
def test_a_bad_post_id_is_422_not_a_server_error(client, bob, auth_headers, method):
    response = getattr(client, method)(
        "/posts/99999999999/like", headers=auth_headers(bob)
    )

    assert response.status_code == 422
