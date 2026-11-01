from datetime import timedelta

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import select

from app import meta_signup, whatsapp
from app.config import settings
from app.models import Membership, WhatsAppPhoneNumber, WhatsAppSignupAttempt, now

from .conftest import register
from .test_whatsapp import create_replyable_conversation

APP = "1609244170127322"
WABA = "987654321"
PHONE = "123456789012345"
TOKEN = "private-test-client-token"
SDK_REDIRECT = "https://staticxx.facebook.com/x/connect/xd_arbiter/?version=46#cb=test&domain=dashboard.example.com"


@pytest.fixture
def configured(monkeypatch):
    for key, value in {
        "meta_app_id": APP,
        "meta_embedded_signup_config_id": "1450204687306079",
        "meta_app_secret": SecretStr("test-app-secret"),
        "meta_connection_encryption_key": SecretStr(Fernet.generate_key().decode()),
        "whatsapp_verify_token": SecretStr("test-verify-secret"),
        "whatsapp_graph_api_version": "v26.0",
        "app_origin": "https://dashboard.example.com",
        "whatsapp_public_callback_url": "https://dashboard.example.com/webhooks/whatsapp",
        "ai_provider": "local",
    }.items():
        monkeypatch.setattr(settings, key, value)


def provider(monkeypatch, *, coexistence=True, invalid_app=False, fail_subscribe=False):
    calls = []

    def graph(method, path, token=None, params=None, body=None):
        calls.append((method, path, token, body))
        if path == "oauth/access_token":
            assert body["client_id"] == APP and body["code"] == "single-use-code"
            assert body["redirect_uri"] == SDK_REDIRECT
            return {"access_token": TOKEN}
        if path == "debug_token":
            return {
                "data": {
                    "is_valid": True,
                    "app_id": "other-app" if invalid_app else APP,
                    "expires_at": 0,
                    "scopes": [
                        "whatsapp_business_management",
                        "whatsapp_business_messaging",
                    ],
                    "granular_scopes": [
                        {"scope": "whatsapp_business_management", "target_ids": [WABA]}
                    ],
                }
            }
        assert token == TOKEN
        if path == WABA + "/phone_numbers":
            return {
                "data": [
                    {
                        "id": PHONE,
                        "display_phone_number": "+94770001122",
                        "verified_name": "Client business",
                    }
                ]
            }
        if path == PHONE:
            return {
                "id": PHONE,
                "is_on_biz_app": coexistence,
                "platform_type": "CLOUD_API",
            }
        if path == PHONE + "/register":
            assert body["pin"] == "123456"
            return {"success": True}
        if path == WABA + "/subscribed_apps":
            if fail_subscribe:
                raise HTTPException(502, "Meta subscription failed")
            return {"success": True}
        raise AssertionError(path)

    monkeypatch.setattr(meta_signup, "graph", graph)
    return calls


def begin(client):
    r = client.post("/api/inbox/meta-signup/begin")
    assert r.status_code == 201, r.text
    return r.json()["attempt_id"]


def exchange(client, attempt):
    return client.post(
        "/api/inbox/meta-signup/exchange",
        json={
            "attempt_id": attempt,
            "code": "single-use-code",
            "redirect_uri": SDK_REDIRECT,
        },
    )


def confirm(client, attempt, **extra):
    return client.post(
        "/api/inbox/meta-signup/confirm",
        json={
            "attempt_id": attempt,
            "phone_number_id": PHONE,
            "human_confirmed": True,
            **extra,
        },
    )


def test_coexistence_connection_encrypted_and_sends_with_workspace_token(
    setup, configured, monkeypatch
):
    client, factory = setup
    register(client)
    calls = provider(monkeypatch)
    attempt = begin(client)
    exchanged = exchange(client, attempt)
    assert exchanged.status_code == 200, exchanged.text
    assert TOKEN not in exchanged.text
    assert confirm(client, attempt, human_confirmed=False).status_code == 422
    result = confirm(client, attempt)
    assert result.status_code == 200, result.text
    assert result.json()["connection_kind"] == "coexistence"
    assert not any(path.endswith("/register") for _, path, _, _ in calls)
    with factory() as db:
        phone = db.scalar(select(WhatsAppPhoneNumber))
        assert TOKEN not in phone.access_token_encrypted
        assert meta_signup.decrypt_token(phone.access_token_encrypted) == TOKEN
        row = db.get(WhatsAppSignupAttempt, attempt)
        assert row.status == "completed" and row.token_encrypted == ""
    assert confirm(client, attempt).status_code == 409
    listed = client.get("/api/inbox/phone-numbers")
    assert TOKEN not in listed.text and "access_token_encrypted" not in listed.text
    assert (
        client.get("/api/inbox/integration-status").json()["whatsapp"][
            "cloud_send_configured"
        ]
        is True
    )
    conversation = create_replyable_conversation(client, PHONE)
    monkeypatch.setattr(settings, "whatsapp_test_mode", False)
    monkeypatch.setattr(settings, "whatsapp_access_token", SecretStr(""))
    monkeypatch.setattr(settings, "whatsapp_phone_number_id", "")

    def send(recipient, text, **kw):
        assert kw == {"token_override": TOKEN, "phone_override": PHONE}
        return "wamid.connected.reply"

    monkeypatch.setattr(whatsapp, "_send_meta_text", send)
    reply = client.post(
        "/api/inbox/conversations/" + conversation["id"] + "/reply",
        json={
            "text": "Thanks for your request",
            "client_request_id": "connected-reply-0001",
        },
    )
    assert reply.status_code == 201, reply.text


def test_cloud_registration_requires_pin_and_rejects_unshared_number(
    setup, configured, monkeypatch
):
    client, _ = setup
    register(client)
    calls = provider(monkeypatch, coexistence=False)
    attempt = begin(client)
    assert exchange(client, attempt).status_code == 200
    assert confirm(client, attempt, phone_number_id="999999999").status_code == 403
    assert confirm(client, attempt).status_code == 422
    assert confirm(client, attempt, pin="123456").status_code == 200
    assert any(path == PHONE + "/register" for _, path, _, _ in calls)


def test_attempts_expire_are_one_use_and_bound_to_tenant_and_session(
    setup, configured, monkeypatch
):
    client, factory = setup
    first = register(client)
    provider(monkeypatch)
    attempt = begin(client)
    assert exchange(client, attempt).status_code == 200
    assert exchange(client, attempt).status_code == 409
    register(client, "other")
    assert confirm(client, attempt).status_code == 404
    client.post(
        "/api/auth/login",
        json={"email": "one@example.com", "password": "test-only-password-123"},
    )
    client.headers["X-Organization-ID"] = first["organization_id"]
    assert confirm(client, attempt).status_code == 403
    fresh = begin(client)
    with factory() as db:
        row = db.get(WhatsAppSignupAttempt, fresh)
        row.expires_at = now() - timedelta(seconds=1)
        db.commit()
    assert exchange(client, fresh).status_code == 410


def test_other_app_and_provider_failure_never_activate_phone(
    setup, configured, monkeypatch
):
    client, factory = setup
    register(client)
    provider(monkeypatch, invalid_app=True)
    attempt = begin(client)
    assert exchange(client, attempt).status_code == 403
    with factory() as db:
        assert db.get(WhatsAppSignupAttempt, attempt).token_encrypted == ""
    provider(monkeypatch, fail_subscribe=True)
    attempt = begin(client)
    assert exchange(client, attempt).status_code == 200
    assert confirm(client, attempt).status_code == 502
    assert client.get("/api/inbox/phone-numbers").json() == []
    with factory() as db:
        assert db.get(WhatsAppSignupAttempt, attempt).status == "failed"
        assert db.get(WhatsAppSignupAttempt, attempt).token_encrypted == ""


def test_number_cannot_move_to_another_workspace(setup, configured, monkeypatch):
    client, _ = setup
    register(client)
    provider(monkeypatch)
    attempt = begin(client)
    assert exchange(client, attempt).status_code == 200
    assert confirm(client, attempt).status_code == 200
    register(client, "other")
    second = begin(client)
    assert exchange(client, second).status_code == 200
    assert confirm(client, second).status_code == 409


def test_configuration_and_roles_are_gated_without_exposing_secrets(
    setup, configured, monkeypatch
):
    client, factory = setup
    account = register(client)
    monkeypatch.setattr(settings, "app_origin", "http://localhost:3000")
    info = client.get("/api/inbox/meta-signup/status")
    assert "HTTPS_APP_ORIGIN" in info.json()["missing"]
    assert "test-app-secret" not in info.text
    assert client.post("/api/inbox/meta-signup/begin").status_code == 503
    with factory() as db:
        member = db.scalar(
            select(Membership).where(
                Membership.organization_id == account["organization_id"]
            )
        )
        member.role = "staff"
        db.commit()
    assert client.get("/api/inbox/meta-signup/status").status_code == 403
    assert client.post("/api/inbox/meta-signup/begin").status_code == 403


def test_provider_error_diagnostic_never_exposes_credentials(
    setup, configured, monkeypatch, caplog
):
    import httpx

    original = httpx.Client

    def handle(request):
        return httpx.Response(
            400,
            json={
                "error": {
                    "code": 100,
                    "error_subcode": 36008,
                    "message": "secret-token-and-authorization-code",
                }
            },
        )

    monkeypatch.setattr(
        meta_signup.httpx,
        "Client",
        lambda **kw: original(transport=httpx.MockTransport(handle), **kw),
    )
    with pytest.raises(HTTPException) as caught:
        meta_signup.graph(
            "POST",
            "oauth/access_token",
            body={"client_secret": "private-app-secret", "code": "private-auth-code"},
        )
    assert caught.value.status_code == 422
    assert "authorization_exchange" in caught.value.detail
    assert "36008" in caught.value.detail
    for secret in [
        "secret-token-and-authorization-code",
        "private-app-secret",
        "private-auth-code",
    ]:
        assert secret not in caught.value.detail and secret not in caplog.text


def test_exchange_rejects_untrusted_redirect_before_provider_call(
    setup, configured, monkeypatch
):
    client, _ = setup
    register(client)
    calls = provider(monkeypatch)
    attempt = begin(client)
    response = client.post(
        "/api/inbox/meta-signup/exchange",
        json={
            "attempt_id": attempt,
            "code": "single-use-code",
            "redirect_uri": "https://attacker.example/callback",
        },
    )
    assert response.status_code == 422 and calls == []
    assert exchange(client, attempt).status_code == 200


def test_sdk_asset_hint_is_verified_with_grant_and_requested_number(
    setup, configured, monkeypatch
):
    client, _ = setup
    register(client)
    calls = provider(monkeypatch)
    original_graph = meta_signup.graph

    def without_targets(method, path, token=None, params=None, body=None):
        result = original_graph(method, path, token, params, body)
        if path == "debug_token":
            result["data"]["granular_scopes"] = []
        return result

    monkeypatch.setattr(meta_signup, "graph", without_targets)
    started = client.post(
        "/api/inbox/meta-signup/begin", json={"phone_number": "0770001122"}
    )
    assert started.status_code == 201
    attempt = started.json()["attempt_id"]
    result = client.post(
        "/api/inbox/meta-signup/exchange",
        json={
            "attempt_id": attempt,
            "code": "single-use-code",
            "redirect_uri": SDK_REDIRECT,
            "business_account_id": WABA,
        },
    )
    assert result.status_code == 200, result.text
    assert result.json()["choices"][0]["phone_number_id"] == PHONE
    assert any(
        path == WABA + "/phone_numbers" and token == TOKEN
        for _, path, token, _ in calls
    )


def test_number_entry_cannot_connect_different_shared_number(
    setup, configured, monkeypatch
):
    client, _ = setup
    register(client)
    provider(monkeypatch)
    response = client.post(
        "/api/inbox/meta-signup/begin", json={"phone_number": "+94779999999"}
    )
    attempt = response.json()["attempt_id"]
    assert exchange(client, attempt).status_code == 422


def test_missing_sdk_asset_does_not_guess_or_bypass_meta_permissions(
    setup, configured, monkeypatch
):
    client, _ = setup
    register(client)
    original_graph = provider(monkeypatch)
    handler = meta_signup.graph

    def no_assets(method, path, token=None, params=None, body=None):
        result = handler(method, path, token, params, body)
        if path == "debug_token":
            result["data"]["granular_scopes"] = []
        return result

    monkeypatch.setattr(meta_signup, "graph", no_assets)
    attempt = begin(client)
    assert exchange(client, attempt).status_code == 403
    assert not any(path.endswith("/phone_numbers") for _, path, _, _ in original_graph)


def test_sdk_hint_cannot_bypass_meta_asset_access(setup, configured, monkeypatch):
    client, _ = setup
    register(client)
    provider(monkeypatch)
    handler = meta_signup.graph

    def denied_asset(method, path, token=None, params=None, body=None):
        if path == "555555555/phone_numbers":
            assert token == TOKEN
            raise HTTPException(403, "Account not shared by Meta")
        result = handler(method, path, token, params, body)
        if path == "debug_token":
            result["data"]["granular_scopes"] = []
        return result

    monkeypatch.setattr(meta_signup, "graph", denied_asset)
    attempt = begin(client)
    response = client.post(
        "/api/inbox/meta-signup/exchange",
        json={
            "attempt_id": attempt,
            "code": "single-use-code",
            "redirect_uri": SDK_REDIRECT,
            "business_account_id": "555555555",
        },
    )
    assert response.status_code == 403
    assert confirm(client, attempt).status_code == 409
