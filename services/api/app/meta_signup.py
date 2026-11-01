"""Meta Embedded Signup: session-bound code exchange and encrypted tenant tokens."""

import logging
import re
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field, SecretStr, field_validator
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import has_real_config, settings
from .db import get_db
from .models import AuditEvent, WhatsAppPhoneNumber, WhatsAppSignupAttempt, as_utc, now
from .schemas import StrictModel
from .security import COOKIE, Tenant, digest, lock_org, require, scoped, tenant_context

logger = logging.getLogger("ordermesh.meta")
router = APIRouter(prefix="/api/inbox/meta-signup")
ID_PATTERN = r"\d{5,128}"


def cipher():
    try:
        return Fernet(
            settings.meta_connection_encryption_key.get_secret_value().encode()
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            503, "WhatsApp credential encryption is not configured"
        ) from exc


def encrypt_token(value):
    return cipher().encrypt(value.encode()).decode()


def decrypt_token(value):
    try:
        return cipher().decrypt(value.encode()).decode()
    except (InvalidToken, UnicodeError) as exc:
        raise HTTPException(
            503,
            "WhatsApp credentials cannot be read; contact the workspace administrator",
        ) from exc


def setup_status():
    missing = []
    for name, value in {
        "META_APP_ID": settings.meta_app_id,
        "META_EMBEDDED_SIGNUP_CONFIG_ID": settings.meta_embedded_signup_config_id,
        "META_APP_SECRET": settings.meta_app_secret.get_secret_value(),
        "WHATSAPP_VERIFY_TOKEN": settings.whatsapp_verify_token.get_secret_value(),
    }.items():
        if not has_real_config(value):
            missing.append(name)
    if not re.fullmatch(r"v\d+\.\d+", settings.whatsapp_graph_api_version):
        missing.append("WHATSAPP_GRAPH_API_VERSION")
    try:
        cipher()
    except HTTPException:
        missing.append("META_CONNECTION_ENCRYPTION_KEY")
    for name, value in [
        ("META_APP_ID", settings.meta_app_id),
        ("META_EMBEDDED_SIGNUP_CONFIG_ID", settings.meta_embedded_signup_config_id),
    ]:
        if name not in missing and not re.fullmatch(ID_PATTERN, value):
            missing.append(name)
    origin = urlparse(settings.app_origin)
    callback = urlparse(settings.whatsapp_public_callback_url)
    if origin.scheme != "https" or not origin.hostname:
        missing.append("HTTPS_APP_ORIGIN")
    if (
        callback.scheme != "https"
        or not callback.hostname
        or callback.path != "/webhooks/whatsapp"
        or callback.query
        or callback.fragment
    ):
        missing.append("WHATSAPP_PUBLIC_CALLBACK_URL")
    return {
        "configured": not missing,
        "missing": missing,
        "app_id": settings.meta_app_id,
        "config_id": settings.meta_embedded_signup_config_id,
        "graph_version": settings.whatsapp_graph_api_version,
        "origin": settings.app_origin,
        "callback_url": settings.whatsapp_public_callback_url,
        "provider_verified": False,
    }


def graph(method, path, token=None, params=None, body=None):
    if not re.fullmatch(r"v\d+\.\d+", settings.whatsapp_graph_api_version):
        raise HTTPException(503, "Set the Meta Graph API version")
    try:
        with httpx.Client(timeout=httpx.Timeout(25, connect=5)) as client:
            response = client.request(
                method,
                "https://graph.facebook.com/"
                + settings.whatsapp_graph_api_version
                + "/"
                + path,
                headers={"Authorization": "Bearer " + token} if token else {},
                params=params,
                data=body,
            )
            response.raise_for_status()
            result = response.json()
        if not isinstance(result, dict) or result.get("error"):
            raise ValueError("Invalid Meta response")
        return result
    except httpx.HTTPStatusError as exc:
        # Never log full URLs, tokens, codes, provider messages or response bodies.
        phase = (
            "authorization_exchange"
            if path == "oauth/access_token"
            else "authorization_validation"
            if path == "debug_token"
            else "phone_discovery"
            if path.endswith("/phone_numbers")
            else "phone_registration"
            if path.endswith("/register")
            else "webhook_subscription"
            if path.endswith("/subscribed_apps")
            else "phone_verification"
        )
        try:
            error = exc.response.json().get("error", {})
            code = error.get("code")
            subcode = error.get("error_subcode")
        except (ValueError, AttributeError):
            code = subcode = None
        code = code if type(code) is int else None
        subcode = subcode if type(subcode) is int else None
        logger.warning(
            "Meta connection failed stage=%s http=%s code=%s subcode=%s",
            phase,
            exc.response.status_code,
            code,
            subcode,
        )
        reference = (
            f"{phase}; HTTP {exc.response.status_code}; code {code}; subcode {subcode}"
        )
        raise HTTPException(
            422 if exc.response.status_code == 400 else 502,
            "Meta could not complete this connection step. Start again; if it repeats, check app permissions. Reference: "
            + reference,
        ) from exc
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        raise HTTPException(
            502,
            "Meta could not complete the connection. Check app permissions and try again.",
        ) from exc


def phone_choices(waba, token):
    if not re.fullmatch(ID_PATTERN, waba):
        raise HTTPException(502, "Meta returned an invalid business account")
    result = []
    after = None
    for _ in range(10):
        params = {"fields": "id,display_phone_number,verified_name", "limit": "100"}
        if after:
            params["after"] = after
        data = graph("GET", waba + "/phone_numbers", token, params=params)
        rows = data.get("data")
        if not isinstance(rows, list):
            raise HTTPException(502, "Meta did not return phone numbers")
        for row in rows:
            if not isinstance(row, dict) or not re.fullmatch(
                ID_PATTERN, str(row.get("id", ""))
            ):
                raise HTTPException(502, "Meta returned an invalid phone number")
            result.append(
                {
                    "phone_number_id": row["id"],
                    "business_account_id": waba,
                    "display_phone_number": str(row.get("display_phone_number", ""))[
                        :40
                    ],
                    "verified_name": str(row.get("verified_name", ""))[:160],
                }
            )
        paging = data.get("paging", {})
        if not paging.get("next"):
            return result
        after = paging.get("cursors", {}).get("after")
        if not isinstance(after, str) or len(after) > 2000:
            break
    raise HTTPException(
        502, "Too many Meta numbers; narrow the shared accounts and reconnect"
    )


def normalize_business_number(value):
    digits = re.sub(r"[\s().-]", "", value).lstrip("+")
    if len(digits) == 10 and digits.startswith("0"):
        digits = "94" + digits[1:]
    if not re.fullmatch(r"[1-9]\d{7,14}", digits):
        raise ValueError("Enter a valid WhatsApp number, for example +94770001122")
    return digits


class BeginInput(StrictModel):
    phone_number: str = Field(min_length=5, max_length=40)


class ExchangeInput(StrictModel):
    attempt_id: str = Field(min_length=36, max_length=36)
    code: SecretStr
    business_account_id: str | None = Field(default=None, pattern=r"^\d{5,128}$")
    redirect_uri: str = Field(min_length=1, max_length=4000)

    @field_validator("redirect_uri")
    @classmethod
    def sdk_redirect_only(cls, value):
        parsed = urlparse(value)
        query = parse_qs(parsed.query, keep_blank_values=True)
        if (
            parsed.scheme != "https"
            or parsed.netloc != "staticxx.facebook.com"
            or parsed.path != "/x/connect/xd_arbiter/"
            or set(query) != {"version"}
            or len(query["version"]) != 1
            or not re.fullmatch(r"\d{1,4}", query["version"][0])
        ):
            raise ValueError("Use the callback URI generated by the official Meta SDK")
        return value

    @field_validator("code")
    @classmethod
    def valid_code(cls, value):
        if not 1 <= len(value.get_secret_value()) <= 4096:
            raise ValueError("Invalid authorization code")
        return value


class ConfirmInput(StrictModel):
    attempt_id: str = Field(min_length=36, max_length=36)
    phone_number_id: str = Field(pattern=r"^\d{5,128}$")
    pin: SecretStr | None = None
    human_confirmed: bool

    @field_validator("human_confirmed", mode="before")
    @classmethod
    def consent(cls, value):
        if value is not True:
            raise ValueError("Confirm the number connection")
        return value


def attempt_for(db, tenant, request, attempt_id):
    row = scoped(db, WhatsAppSignupAttempt, tenant, attempt_id)
    if row.created_by != tenant.user_id or row.session_hash != digest(
        request.cookies.get(COOKIE, "")
    ):
        raise HTTPException(
            403, "Start the WhatsApp connection from this signed-in session"
        )
    if as_utc(row.expires_at) <= now():
        row.token_encrypted = ""
        row.status = "expired"
        db.commit()
        raise HTTPException(410, "Connection expired; start again")
    return row


def claim(db, row, expected, next_status):
    changed = db.execute(
        update(WhatsAppSignupAttempt)
        .where(
            WhatsAppSignupAttempt.id == row.id,
            WhatsAppSignupAttempt.organization_id == row.organization_id,
            WhatsAppSignupAttempt.status == expected,
        )
        .values(status=next_status)
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "This connection step is already used; start again")
    org_id = row.organization_id
    db.commit()
    if db.bind.dialect.name == "postgresql":
        db.execute(
            text("SELECT set_config('app.organization_id', :tenant, true)"),
            {"tenant": org_id},
        )
    db.refresh(row)


@router.get("/status")
def status(tenant: Tenant = Depends(tenant_context)):
    require(tenant, "owner", "admin")
    return setup_status()


@router.post("/begin", status_code=201)
def begin(
    request: Request,
    body: BeginInput | None = None,
    tenant: Tenant = Depends(tenant_context),
    db: Session = Depends(get_db),
):
    require(tenant, "owner", "admin")
    try:
        requested_number = normalize_business_number(body.phone_number) if body else ""
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    config = setup_status()
    if not config["configured"]:
        raise HTTPException(
            503, "WhatsApp setup is incomplete: " + ", ".join(config["missing"])
        )
    lock_org(db, tenant)
    active = db.scalar(
        select(WhatsAppSignupAttempt.id).where(
            WhatsAppSignupAttempt.organization_id == tenant.id,
            WhatsAppSignupAttempt.created_by == tenant.user_id,
            WhatsAppSignupAttempt.status.in_(["exchanging", "connecting"]),
            WhatsAppSignupAttempt.expires_at > now(),
        )
    )
    if active:
        raise HTTPException(
            409, "A Meta connection is being processed; wait before starting again"
        )
    # Invalidate prior attempts and erase abandoned tokens, including expired sessions.
    db.execute(
        update(WhatsAppSignupAttempt)
        .where(
            WhatsAppSignupAttempt.organization_id == tenant.id,
            WhatsAppSignupAttempt.created_by == tenant.user_id,
            WhatsAppSignupAttempt.status != "completed",
        )
        .values(status="cancelled", token_encrypted="")
    )
    row = WhatsAppSignupAttempt(
        organization_id=tenant.id,
        created_by=tenant.user_id,
        session_hash=digest(request.cookies.get(COOKIE, "")),
        expires_at=now() + timedelta(minutes=10),
        choices=[{"requested_number": requested_number}] if requested_number else [],
    )
    db.add(row)
    db.commit()
    return {**config, "attempt_id": row.id, "expires_at": row.expires_at}


@router.post("/exchange")
def exchange(
    body: ExchangeInput,
    request: Request,
    tenant: Tenant = Depends(tenant_context),
    db: Session = Depends(get_db),
):
    require(tenant, "owner", "admin")
    row = attempt_for(db, tenant, request, body.attempt_id)
    claim(db, row, "pending", "exchanging")
    try:
        exchanged = graph(
            "POST",
            "oauth/access_token",
            body={
                "client_id": settings.meta_app_id,
                "client_secret": settings.meta_app_secret.get_secret_value(),
                "code": body.code.get_secret_value(),
                "redirect_uri": body.redirect_uri,
            },
        )
        token = exchanged.get("access_token")
        if not isinstance(token, str) or not token or len(token) > 16000:
            raise HTTPException(502, "Meta did not return a valid connection token")
        info = graph(
            "GET",
            "debug_token",
            settings.meta_app_id + "|" + settings.meta_app_secret.get_secret_value(),
            params={"input_token": token},
        ).get("data", {})
        if (
            info.get("is_valid") is not True
            or str(info.get("app_id")) != settings.meta_app_id
        ):
            raise HTTPException(403, "Meta authorization does not belong to this app")
        if info.get("expires_at") and info["expires_at"] <= int(now().timestamp()):
            raise HTTPException(403, "Meta authorization expired; connect again")
        scopes = set(info.get("scopes", []))
        if not {"whatsapp_business_management", "whatsapp_business_messaging"}.issubset(
            scopes
        ):
            raise HTTPException(
                403, "Grant both WhatsApp management and messaging permissions"
            )
        targets = {
            str(v)
            for scope in info.get("granular_scopes", [])
            if scope.get("scope") == "whatsapp_business_management"
            for v in scope.get("target_ids", [])
        }
        if not targets and body.business_account_id:
            # The SDK FINISH event is only an asset hint. Authority comes from a
            # successful WABA phone_numbers lookup with this validated grant.
            targets = {body.business_account_id}
        elif targets and body.business_account_id:
            if body.business_account_id not in targets:
                raise HTTPException(
                    403,
                    "The selected WhatsApp account was not shared by this authorization",
                )
            targets = {body.business_account_id}
        if not targets or len(targets) > 20:
            logger.warning(
                "Meta authorization valid but no WABA targets or SDK finish asset were available"
            )
            raise HTTPException(
                403,
                "Meta login completed without a WhatsApp account selection. Start again and complete the WhatsApp business/number steps in the Meta popup.",
            )
        choices = [p for waba in sorted(targets) for p in phone_choices(waba, token)]
        requested_number = next(
            (
                p.get("requested_number")
                for p in row.choices
                if p.get("requested_number")
            ),
            "",
        )
        if requested_number:
            verified_choices = []
            for choice in choices:
                try:
                    if (
                        normalize_business_number(choice["display_phone_number"])
                        == requested_number
                    ):
                        verified_choices.append(choice)
                except ValueError:
                    continue
            if not verified_choices:
                raise HTTPException(
                    422,
                    "The number shared in Meta does not match the WhatsApp number you entered. Start again and choose that number in Meta.",
                )
            choices = verified_choices
        if not choices:
            raise HTTPException(
                422,
                "No shared WhatsApp numbers found; finish number onboarding in Meta",
            )
        row.token_encrypted = encrypt_token(token)
        row.choices = choices
        row.status = "ready"
        db.commit()
        return {"attempt_id": row.id, "choices": choices}
    except (HTTPException, TypeError, ValueError, AttributeError) as exc:
        row.status = "failed"
        row.token_encrypted = ""
        db.commit()
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(
            502, "Meta returned invalid authorization details; connect again"
        ) from exc


@router.post("/confirm")
def confirm(
    body: ConfirmInput,
    request: Request,
    tenant: Tenant = Depends(tenant_context),
    db: Session = Depends(get_db),
):
    require(tenant, "owner", "admin")
    row = attempt_for(db, tenant, request, body.attempt_id)
    if row.status != "ready":
        raise HTTPException(409, "Complete Meta authorization before connecting")
    selected = next(
        (p for p in row.choices if p["phone_number_id"] == body.phone_number_id), None
    )
    if not selected:
        raise HTTPException(403, "Choose a phone number verified by Meta")
    lock_org(db, tenant)
    existing = db.scalar(
        select(WhatsAppPhoneNumber).where(
            WhatsAppPhoneNumber.phone_number_id == body.phone_number_id
        )
    )
    if existing and existing.organization_id != tenant.id:
        raise HTTPException(409, "This number is already assigned to another workspace")
    if (
        existing
        and existing.connection_kind == "connecting"
        and as_utc(existing.created_at) > now() - timedelta(minutes=15)
    ):
        raise HTTPException(
            409, "This number is already being connected; wait and try again"
        )
    token = decrypt_token(row.token_encrypted)
    # Revalidate WABA membership immediately before provider mutation.
    current = phone_choices(selected["business_account_id"], token)
    if not any(p["phone_number_id"] == body.phone_number_id for p in current):
        raise HTTPException(403, "This phone number is no longer shared")
    details = graph(
        "GET",
        body.phone_number_id,
        token,
        params={"fields": "id,is_on_biz_app,platform_type"},
    )
    if (
        str(details.get("id")) != body.phone_number_id
        or type(details.get("is_on_biz_app")) is not bool
    ):
        raise HTTPException(
            502, "Could not verify WhatsApp Business App coexistence status"
        )
    coexistence = details["is_on_biz_app"]
    pin = body.pin.get_secret_value() if body.pin else ""
    if not coexistence and not re.fullmatch(r"\d{6}", pin):
        raise HTTPException(
            422, "Enter a six-digit registration PIN for this Cloud API number"
        )
    # Reserve the globally unique phone before making provider-side changes. This
    # prevents two different workspaces racing to register the same number.
    reserved_id = None
    if not existing:
        reservation = WhatsAppPhoneNumber(
            organization_id=tenant.id,
            phone_number_id=body.phone_number_id,
            connected_by=tenant.user_id,
            display_phone_number=selected["display_phone_number"],
            active=False,
            business_account_id=selected["business_account_id"],
            connection_kind="connecting",
        )
        db.add(reservation)
        try:
            db.flush()
            reserved_id = reservation.id
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                409, "This number is being connected to another workspace"
            ) from exc
    claim(db, row, "ready", "connecting")
    try:
        if not coexistence:
            registered = graph(
                "POST",
                body.phone_number_id + "/register",
                token,
                body={"messaging_product": "whatsapp", "pin": pin},
            )
            if registered.get("success") is not True:
                raise HTTPException(502, "Meta did not confirm number registration")
        subscribed = graph(
            "POST", selected["business_account_id"] + "/subscribed_apps", token
        )
        if subscribed.get("success") is not True:
            raise HTTPException(502, "Meta did not confirm webhook subscription")
        lock_org(db, tenant)
        existing = db.scalar(
            select(WhatsAppPhoneNumber).where(
                WhatsAppPhoneNumber.phone_number_id == body.phone_number_id
            )
        )
        if existing and existing.organization_id != tenant.id:
            raise HTTPException(409, "This number was connected to another workspace")
        phone = existing or WhatsAppPhoneNumber(
            organization_id=tenant.id,
            phone_number_id=body.phone_number_id,
            connected_by=tenant.user_id,
        )
        phone.display_phone_number = selected["display_phone_number"]
        phone.business_account_id = selected["business_account_id"]
        phone.access_token_encrypted = encrypt_token(token)
        phone.connection_kind = "coexistence" if coexistence else "cloud_api"
        phone.active = True
        db.add(phone)
        row.status = "completed"
        row.token_encrypted = ""
        db.add(
            AuditEvent(
                organization_id=tenant.id,
                actor_id=tenant.user_id,
                action="whatsapp.connected",
                entity_id=phone.phone_number_id,
            )
        )
        db.commit()
        return {
            "phone_number_id": phone.phone_number_id,
            "display_phone_number": phone.display_phone_number,
            "connection_kind": phone.connection_kind,
            "connected": True,
            "message_delivery_verified": False,
        }
    except (HTTPException, IntegrityError) as exc:
        db.rollback()
        if db.bind.dialect.name == "postgresql":
            db.execute(
                text("SELECT set_config('app.organization_id', :tenant, true)"),
                {"tenant": tenant.id},
            )
        if reserved_id:
            reservation = db.get(WhatsAppPhoneNumber, reserved_id)
            if (
                reservation
                and not reservation.active
                and reservation.organization_id == tenant.id
            ):
                db.delete(reservation)
        row = db.get(WhatsAppSignupAttempt, body.attempt_id)
        if row:
            row.status = "failed"
            row.token_encrypted = ""
            db.commit()
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(
            409, "The number connection changed; connect again"
        ) from exc
