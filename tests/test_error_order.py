"""Authentication is checked before anything about the post is revealed.

An anonymous caller must get 401 whether or not the post exists. If the post were
loaded first, a 404 for a missing post and a 401 for an existing one would tell an
anonymous caller which post ids exist.
"""

import pytest

PROTECTED_POST_ENDPOINTS = [
    pytest.param("patch", "/posts/{id}", {"content": "x"}, id="edit-post"),
    pytest.param("delete", "/posts/{id}", None, id="delete-post"),
    pytest.param("post", "/posts/{id}/comments", {"content": "x"}, id="create-comment"),
    pytest.param("put", "/posts/{id}/like", None, id="like"),
    pytest.param("delete", "/posts/{id}/like", None, id="unlike"),
]


@pytest.mark.parametrize(("method", "path", "body"), PROTECTED_POST_ENDPOINTS)
def test_anonymous_request_to_a_missing_post_is_401_not_404(
    client, method, path, body
):
    response = client.request(method.upper(), path.format(id=999999), json=body)

    assert response.status_code == 401


@pytest.mark.parametrize(("method", "path", "body"), PROTECTED_POST_ENDPOINTS)
def test_anonymous_request_to_an_existing_post_is_401(
    client, alice_post, method, path, body
):
    response = client.request(
        method.upper(), path.format(id=alice_post.id), json=body
    )

    assert response.status_code == 401


@pytest.mark.parametrize(("method", "path", "body"), PROTECTED_POST_ENDPOINTS)
def test_authenticated_request_to_a_missing_post_is_404(
    client, bob, auth_headers, method, path, body
):
    # Once the caller is known, a missing post is a plain 404.
    response = client.request(
        method.upper(), path.format(id=999999), json=body, headers=auth_headers(bob)
    )

    assert response.status_code == 404
