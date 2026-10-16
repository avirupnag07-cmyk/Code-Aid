from dataclasses import replace

from fastapi.testclient import TestClient

from app.main import create_app


def test_github_status_is_explicitly_not_configured(client):
    response = client.get("/api/github/status")
    assert response.status_code == 200
    assert response.json() == {
        "provider": "github",
        "configured": False,
        "connected": False,
        "message": "GitHub OAuth is not configured",
    }


def test_github_authorization_requires_configuration(client):
    response = client.get("/api/github/authorize")
    assert response.status_code == 503
    assert response.json()["detail"] == "GitHub OAuth is not configured"


def test_configured_github_authorization_sets_signed_state_and_pkce_cookies(settings):
    configured = replace(
        settings,
        github_client_id="client-id",
        github_client_secret="client-secret",
        github_redirect_uri="http://localhost:8000/api/github/callback",
        oauth_cookie_secret="test-cookie-secret",
    )
    with TestClient(create_app(configured)) as configured_client:
        response = configured_client.get("/api/github/authorize", follow_redirects=False)
        assert response.status_code == 307
        assert "code_challenge=" in response.headers["location"]
        cookies = response.headers.get_list("set-cookie")
        assert any("code_aid_github_state=" in value for value in cookies)
        assert any("code_aid_github_pkce=" in value for value in cookies)
        invalid = configured_client.get("/api/github/callback?code=code&state=wrong")
        assert invalid.status_code == 400
        assert invalid.json()["detail"] == "Invalid GitHub OAuth state"
