import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta

from fastapi import Depends, Header, HTTPException, Request, Response
from pwdlib import PasswordHash
from sqlalchemy import select, text
from sqlalchemy.orm import Session as DBSession

from .config import settings
from .db import get_db
from .models import Membership, Organization, Session, User, as_utc, now

passwords = PasswordHash.recommended()
DUMMY_HASH = passwords.hash(secrets.token_urlsafe(32))
COOKIE = "ordermesh_session"


def digest(value: str):
    return hashlib.sha256(value.encode()).hexdigest()


def issue_session(db, user_id, response: Response):
    token = secrets.token_urlsafe(48)
    db.add(
        Session(
            token_hash=digest(token),
            user_id=user_id,
            expires_at=now() + timedelta(hours=settings.session_hours),
        )
    )
    response.set_cookie(
        COOKIE,
        token,
        max_age=settings.session_hours * 3600,
        httponly=True,
        secure=settings.app_env == "production",
        samesite="strict",
        path="/",
    )


def current_user(request: Request, db: DBSession = Depends(get_db)):
    token = request.cookies.get(COOKIE)
    session = db.get(Session, digest(token)) if token else None
    if not session or as_utc(session.expires_at) <= now():
        raise HTTPException(401, "Please sign in")
    user = db.get(User, session.user_id)
    if not user:
        raise HTTPException(401, "Please sign in")
    return user


@dataclass
class Tenant:
    id: str
    user_id: str
    role: str


def tenant_context(
    request: Request,
    x_organization_id: str = Header(...),
    user: User = Depends(current_user),
    db: DBSession = Depends(get_db),
):
    membership = db.get(Membership, (user.id, x_organization_id))
    if not membership:
        raise HTTPException(403, "Organization access denied")
    if db.bind.dialect.name == "postgresql":
        db.execute(
            text("SELECT set_config('app.organization_id', :tenant, true)"),
            {"tenant": membership.organization_id},
        )
    if request.method in (
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
    ) and not request.url.path.startswith(
        (
            "/api/billing",
            "/api/business-profile",
            "/api/inbox/messages",
            "/api/notifications",
        )
    ):
        ensure_subscription(db.get(Organization, membership.organization_id))
    return Tenant(membership.organization_id, user.id, membership.role)


def require(tenant: Tenant, *roles):
    if tenant.role not in roles:
        raise HTTPException(403, "Your role cannot perform this action")


def scoped(db, model, tenant, entity_id):
    obj = db.scalar(
        select(model).where(model.organization_id == tenant.id, model.id == entity_id)
    )
    if obj is None:
        raise HTTPException(404, "Record not found")
    return obj


def lock_org(db, tenant):
    return db.scalar(
        select(Organization).where(Organization.id == tenant.id).with_for_update()
    )


def subscription_access(org):
    current = now()
    if org.subscription_status == "trial":
        return bool(org.trial_ends_at and as_utc(org.trial_ends_at) > current)
    return org.subscription_status in ("active", "cancelled") and bool(
        org.paid_until and as_utc(org.paid_until) > current
    )


def ensure_subscription(org):
    if org.subscription_status not in ("trial", "active", "cancelled"):
        raise HTTPException(403, "Subscription is not active")
    if not subscription_access(org):
        raise HTTPException(
            402,
            "Your trial or paid subscription has ended. Open Settings to renew; existing records remain available.",
        )
