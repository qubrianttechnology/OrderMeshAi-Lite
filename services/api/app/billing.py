"""PayHere recurring checkout with independently verified, replay-safe payments."""

import calendar
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qsl, urlsplit
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session as DBSession

from .config import has_real_config, settings
from .db import get_db
from .models import (
    AuditEvent,
    BillingCheckout,
    BillingCheckoutRoute,
    Organization,
    User,
    as_utc,
    now,
)
from .schemas import StrictModel
from .security import Tenant, lock_org, require, subscription_access, tenant_context

router = APIRouter()
PRICE = Decimal("7400.00")


class BillingDetails(StrictModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    phone: str = Field(min_length=8, max_length=30, pattern=r"^\+?[0-9 ()-]+$")
    address: str = Field(min_length=3, max_length=300)
    city: str = Field(min_length=2, max_length=80)
    consent_to_recurring: bool


def payhere_ready():
    return (
        all(
            has_real_config(value)
            for value in (
                settings.payhere_merchant_id,
                settings.payhere_merchant_secret.get_secret_value(),
                settings.payhere_app_id,
                settings.payhere_app_secret.get_secret_value(),
            )
        )
        and urlsplit(settings.payhere_notify_url).scheme == "https"
    )


def _hash(value):
    return hashlib.md5(value.encode(), usedforsecurity=False).hexdigest().upper()


def _merchant_call(path, method="GET", body=None):
    base = (
        "https://sandbox.payhere.lk"
        if settings.payhere_sandbox
        else "https://www.payhere.lk"
    )
    try:
        with httpx.Client(timeout=20) as client:
            token = client.post(
                base + "/merchant/v1/oauth/token",
                auth=(
                    settings.payhere_app_id,
                    settings.payhere_app_secret.get_secret_value(),
                ),
                data={"grant_type": "client_credentials"},
            )
            token.raise_for_status()
            access = token.json()["access_token"]
            response = client.request(
                method,
                base + "/merchant/v1/" + path,
                headers={"Authorization": "Bearer " + access},
                json=body,
            )
            response.raise_for_status()
            data = response.json()
        if data.get("status") != 1:
            raise ValueError("Provider did not confirm the operation")
        return data.get("data")
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(
            503,
            "PayHere verification is unavailable. Payment access will update after a verified notification.",
        ) from exc


def _add_month(value):
    year = value.year + (value.month == 12)
    month = value.month % 12 + 1
    return value.replace(
        year=year, month=month, day=min(value.day, calendar.monthrange(year, month)[1])
    )


@router.get("/api/billing")
def billing_status(
    tenant: Tenant = Depends(tenant_context), db: DBSession = Depends(get_db)
):
    org = db.get(Organization, tenant.id)
    checkout = db.scalar(
        select(BillingCheckout)
        .where(
            BillingCheckout.organization_id == tenant.id,
            BillingCheckout.subscription_id != "",
        )
        .order_by(BillingCheckout.created_at.desc())
    )
    return {
        "plan": "OrderMesh AI Lite",
        "amount_minor": 740000,
        "currency": "LKR",
        "interval": "month",
        "trial_days": 15,
        "trial_ends_at": org.trial_ends_at,
        "paid_until": org.paid_until,
        "status": org.subscription_status if subscription_access(org) else "expired",
        "has_access": subscription_access(org),
        "checkout_available": payhere_ready(),
        "sandbox": settings.payhere_sandbox,
        "can_cancel": bool(
            checkout and checkout.status == "active" and payhere_ready()
        ),
    }


@router.post("/api/billing/checkout")
def start_checkout(
    body: BillingDetails,
    tenant: Tenant = Depends(tenant_context),
    db: DBSession = Depends(get_db),
):
    require(tenant, "owner")
    if not body.consent_to_recurring:
        raise HTTPException(
            422,
            "Authorize the LKR 7,400 monthly recurring subscription before continuing",
        )
    if not payhere_ready():
        raise HTTPException(503, "Subscription payments are not available yet")
    lock_org(db, tenant)
    if db.scalar(
        select(BillingCheckout.id).where(
            BillingCheckout.organization_id == tenant.id,
            BillingCheckout.status == "active",
        )
    ):
        raise HTTPException(409, "A recurring subscription is already active")
    checkout = db.scalar(
        select(BillingCheckout)
        .where(
            BillingCheckout.organization_id == tenant.id,
            BillingCheckout.status == "pending",
            BillingCheckout.created_at > now() - timedelta(minutes=20),
        )
        .order_by(BillingCheckout.created_at.desc())
    )
    if not checkout:
        checkout = BillingCheckout(
            organization_id=tenant.id,
            customer_details=body.model_dump(exclude={"consent_to_recurring"}),
        )
        db.add(checkout)
        db.flush()
        db.add(BillingCheckoutRoute(id=checkout.id, organization_id=tenant.id))
    user = db.get(User, tenant.user_id)
    origin = settings.app_origin.rstrip("/")
    form = {
        "merchant_id": settings.payhere_merchant_id,
        "return_url": origin + "/dashboard?billing=return",
        "cancel_url": origin + "/dashboard?billing=cancelled",
        "notify_url": settings.payhere_notify_url,
        "order_id": checkout.id,
        "items": "OrderMesh AI Lite monthly subscription",
        "currency": "LKR",
        "amount": "7400.00",
        "recurrence": "1 Month",
        "duration": "Forever",
        "email": user.email,
        "country": "Sri Lanka",
        **checkout.customer_details,
    }
    form["hash"] = _hash(
        settings.payhere_merchant_id
        + checkout.id
        + "7400.00LKR"
        + _hash(settings.payhere_merchant_secret.get_secret_value())
    )
    db.add(
        AuditEvent(
            organization_id=tenant.id,
            actor_id=tenant.user_id,
            action="subscription.checkout_started",
            entity_id=checkout.id,
        )
    )
    db.commit()
    return {
        "action": (
            "https://sandbox.payhere.lk"
            if settings.payhere_sandbox
            else "https://www.payhere.lk"
        )
        + "/pay/checkout",
        "fields": form,
    }


@router.post("/api/billing/payhere/notify")
async def payment_notification(request: Request, db: DBSession = Depends(get_db)):
    if not payhere_ready():
        raise HTTPException(503, "Payment verification is not configured")
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 12000:
            raise HTTPException(413, "Notification is too large")
    try:
        pairs = parse_qsl(raw.decode("utf-8"), keep_blank_values=True)
        data = dict(pairs)
        if len(data) != len(pairs):
            raise ValueError("Duplicate parameters")
        expected = _hash(
            data["merchant_id"]
            + data["order_id"]
            + data["payhere_amount"]
            + data["payhere_currency"]
            + data["status_code"]
            + _hash(settings.payhere_merchant_secret.get_secret_value())
        )
        if data[
            "merchant_id"
        ] != settings.payhere_merchant_id or not hmac.compare_digest(
            expected, data.get("md5sig", "").upper()
        ):
            raise HTTPException(403, "Invalid payment signature")
        if (
            data["payhere_currency"] != "LKR"
            or Decimal(data["payhere_amount"]) != PRICE
        ):
            raise HTTPException(422, "Payment amount does not match the subscription")
    except (KeyError, ValueError, InvalidOperation) as exc:
        raise HTTPException(400, "Invalid payment notification") from exc
    route = db.get(BillingCheckoutRoute, data["order_id"])
    if not route:
        raise HTTPException(404, "Checkout not found")
    if db.bind.dialect.name == "postgresql":
        db.execute(
            text("SELECT set_config('app.organization_id',:tenant,true)"),
            {"tenant": route.organization_id},
        )
    org = db.scalar(
        select(Organization)
        .where(Organization.id == route.organization_id)
        .with_for_update()
    )
    checkout = db.scalar(
        select(BillingCheckout)
        .where(
            BillingCheckout.organization_id == route.organization_id,
            BillingCheckout.id == route.id,
        )
        .with_for_update()
    )
    # Never activate from the browser return URL or unsigned notification metadata.
    # Reconcile the gateway's actual successful payments, not its payment_id parameter.
    payments = _merchant_call("payment/search?order_id=" + checkout.id)
    if not isinstance(payments, list) or any(
        not isinstance(payment, dict) for payment in payments
    ):
        raise HTTPException(503, "PayHere returned an invalid payment record")
    seen = set()
    valid_until = []
    for payment in payments or []:
        if (
            str(payment.get("order_id")) != checkout.id
            or payment.get("currency") != "LKR"
        ):
            continue
        try:
            amount = Decimal(str(payment.get("amount")))
        except InvalidOperation:
            continue
        if amount != PRICE or payment.get("status") != "RECEIVED":
            continue
        payment_id = str(payment.get("payment_id", ""))
        if not payment_id or payment_id in seen:
            continue
        try:
            paid = datetime.fromisoformat(payment["date"])
            if paid.tzinfo is None:
                paid = paid.replace(tzinfo=ZoneInfo("Asia/Colombo"))
            paid = paid.astimezone(timezone.utc)
        except (ValueError, KeyError, TypeError):
            raise HTTPException(503, "Payment date could not be verified")
        if paid > now() + timedelta(minutes=10):
            raise HTTPException(503, "Payment date could not be verified")
        valid_until.append(_add_month(paid))
        seen.add(payment_id)
    checkout.entitled_until = max(valid_until) if valid_until else None
    subscription_id = data.get("subscription_id", "")
    if subscription_id and subscription_id.isdigit():
        subscription = _merchant_call("subscription/" + subscription_id)
        if not isinstance(subscription, dict):
            raise HTTPException(503, "PayHere returned an invalid subscription record")
        if str(subscription.get("order_id")) == checkout.id:
            checkout.subscription_id = subscription_id
            checkout.status = (
                "active" if subscription.get("status") == "ACTIVE" else "cancelled"
            )
    checkout.verified_payments = sorted(seen)
    db.flush()
    periods = db.scalars(
        select(BillingCheckout.entitled_until).where(
            BillingCheckout.organization_id == org.id,
            BillingCheckout.entitled_until.is_not(None),
        )
    ).all()
    org.paid_until = max(as_utc(value) for value in periods) if periods else None
    if org.paid_until and as_utc(org.paid_until) > now():
        org.subscription_status = (
            "active" if checkout.status != "cancelled" else "cancelled"
        )
        org.plan = "lite"
    elif org.trial_ends_at and as_utc(org.trial_ends_at) > now():
        org.subscription_status = "trial"
    else:
        org.subscription_status = "past_due"
    db.commit()
    return {"received": True}


@router.post("/api/billing/cancel")
def cancel_subscription(
    tenant: Tenant = Depends(tenant_context), db: DBSession = Depends(get_db)
):
    require(tenant, "owner")
    org = lock_org(db, tenant)
    checkout = db.scalar(
        select(BillingCheckout)
        .where(
            BillingCheckout.organization_id == tenant.id,
            BillingCheckout.status == "active",
            BillingCheckout.subscription_id != "",
        )
        .with_for_update()
    )
    if not checkout:
        raise HTTPException(409, "No active recurring subscription to cancel")
    if not payhere_ready():
        raise HTTPException(503, "Payment management is not available")
    _merchant_call(
        "subscription/cancel",
        "POST",
        {"subscription_id": int(checkout.subscription_id)},
    )
    checkout.status = "cancelled"
    org.subscription_status = "cancelled"
    db.add(
        AuditEvent(
            organization_id=tenant.id,
            actor_id=tenant.user_id,
            action="subscription.cancelled",
            entity_id=checkout.id,
        )
    )
    db.commit()
    return {"status": "cancelled", "paid_until": org.paid_until}
