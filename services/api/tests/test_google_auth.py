from pydantic import SecretStr
from sqlalchemy import select

from app import main
from app.models import Membership, User


class FakeGoogleResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def configure_google(monkeypatch):
    monkeypatch.setattr(main.settings, "app_origin", "http://localhost:3000")
    monkeypatch.setattr(main.settings, "google_oauth_client_id", "test-client-id")
    monkeypatch.setattr(
        main.settings, "google_oauth_client_secret", SecretStr("test-client-secret")
    )
    monkeypatch.setattr(
        main.settings,
        "google_oauth_redirect_uri",
        "http://localhost:3000/api/auth/google/callback",
    )


def test_google_signup_creates_workspace_and_session(setup, monkeypatch):
    client, factory = setup
    configure_google(monkeypatch)
    started = client.get(
        "/api/auth/google/start?intent=sign-up", follow_redirects=False
    )
    assert started.status_code == 303
    assert started.headers["location"].startswith(main.GOOGLE_OAUTH_AUTHORIZE_URL)
    state = client.cookies.get(main.GOOGLE_OAUTH_STATE_COOKIE).split("|", 1)[0]
    monkeypatch.setattr(
        main.httpx,
        "post",
        lambda *args, **kwargs: FakeGoogleResponse({"access_token": "access-token"}),
    )
    monkeypatch.setattr(
        main.httpx,
        "get",
        lambda *args, **kwargs: FakeGoogleResponse(
            {
                "sub": "google-subject-1",
                "email": "owner@example.com",
                "email_verified": True,
                "name": "Google Owner",
            }
        ),
    )
    callback = client.get(
        "/api/auth/google/callback",
        params={"code": "authorization-code", "state": state},
        follow_redirects=False,
    )
    assert callback.status_code == 303
    assert callback.headers["location"] == "http://localhost:3000/sign-up?google=1"
    completed = client.post(
        "/api/auth/google/complete-registration",
        json={"organization_name": "Google Workspace"},
    )
    assert completed.status_code == 201
    with factory() as db:
        user = db.scalar(select(User).where(User.email == "owner@example.com"))
        assert user.google_subject == "google-subject-1"
        assert db.get(Membership, (user.id, completed.json()["organization_id"]))


def test_google_callback_rejects_state_mismatch(setup, monkeypatch):
    client, _ = setup
    configure_google(monkeypatch)
    client.get("/api/auth/google/start", follow_redirects=False)
    response = client.get(
        "/api/auth/google/callback",
        params={"code": "authorization-code", "state": "wrong-state"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith("oauth_error=invalid_oauth_state")


def test_localhost_google_start_moves_to_https_before_setting_state(setup, monkeypatch):
    client, _ = setup
    configure_google(monkeypatch)
    monkeypatch.setattr(main.settings, "app_origin", "https://secure.example.com")
    response = client.get(
        "/api/auth/google/start?intent=sign-in",
        headers={"X-Forwarded-Host": "localhost:3000"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert (
        response.headers["location"]
        == "https://secure.example.com/api/auth/google/start?intent=sign-in"
    )
    assert main.GOOGLE_OAUTH_STATE_COOKIE not in response.cookies
    response = client.get(
        "/api/auth/google/start?intent=sign-in",
        headers={"X-Forwarded-Host": "secure.example.com"},
        follow_redirects=False,
    )
    assert response.headers["location"].startswith(main.GOOGLE_OAUTH_AUTHORIZE_URL)
    assert main.GOOGLE_OAUTH_STATE_COOKIE in response.cookies
