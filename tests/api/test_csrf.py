from fastapi.testclient import TestClient
from muxivo_console.presentation.api import CSRF_COOKIE_NAME, CSRF_HEADER_NAME, create_app


def test_unsafe_requests_require_matching_double_submit_csrf_credentials() -> None:
    client = TestClient(create_app())
    path = "/api/v1/organizations/00000000-0000-0000-0000-000000000000/control-modules"

    missing = client.post(path)
    mismatched = client.post(
        path,
        headers={"Cookie": f"{CSRF_COOKIE_NAME}=cookie-token", CSRF_HEADER_NAME: "other-token"},
    )
    accepted = client.post(
        path,
        headers={"Cookie": f"{CSRF_COOKIE_NAME}=csrf-token", CSRF_HEADER_NAME: "csrf-token"},
    )

    assert missing.status_code == 403
    assert missing.json() == {"detail": "CSRF validation failed"}
    assert mismatched.status_code == 403
    assert accepted.status_code == 405


def test_authentication_bootstrap_routes_are_csrf_exempt() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/auth/email-password/sessions",
        json={"email": "creator@example.com", "password": "a-long-enough-password"},
    )

    assert response.status_code == 503
