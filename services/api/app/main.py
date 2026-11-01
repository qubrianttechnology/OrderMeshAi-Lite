import asyncio
import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Literal
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from .account_settings import router as account_settings_router
from .ai_provider import ProviderUnavailable, get_extractor
from .automation import pending_count, queue_order_confirmation
from .automation import router as automation_router
from .billing import payhere_ready
from .billing import router as billing_router
from .business import SERVICE_TYPES, dashboard_view
from .business import router as business_router
from .commerce import router as commerce_router
from .config import settings
from .dashboard_insights import router as dashboard_insights_router
from .db import engine, get_db
from .image_extraction import (
    IMAGE_MIME_TYPES,
    MAX_IMAGE_BYTES,
    ImageError,
    image_flags,
    image_ready,
    read_image,
)
from .inventory import (
    available_at,
    ensure_main,
    move_stock,
    order_totals,
    select_warehouse,
    selling_price,
)
from .invoices import invoice_pdf
from .meta_signup import router as meta_signup_router
from .models import (
    AuditEvent,
    Customer,
    CustomerPayment,
    ExtractionDraft,
    Membership,
    Order,
    OrderLine,
    Organization,
    Product,
    SalesReturn,
    Session,
    StockMovement,
    User,
    WhatsAppMessage,
    as_utc,
)
from .notifications import router as notifications_router
from .schemas import (
    CustomerInput,
    ExtractInput,
    GoogleWorkspaceRegistration,
    Login,
    OrderInput,
    ProductInput,
    Register,
    StockInput,
    Transition,
)
from .security import (
    COOKIE,
    DUMMY_HASH,
    Tenant,
    current_user,
    digest,
    ensure_subscription,
    issue_session,
    lock_org,
    passwords,
    require,
    scoped,
    tenant_context,
)
from .service_requests import extract_service_request, uses_service_workflow
from .service_requests import router as service_request_router
from .voice import voice_ready
from .whatsapp import router as whatsapp_router
from .whatsapp import whatsapp_worker


@asynccontextmanager
async def lifespan(_app):
    if settings.app_env == "production":
        with engine.connect() as connection:
            role = connection.execute(
                text(
                    "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
                )
            ).one()
            if role.rolsuper or role.rolbypassrls:
                raise RuntimeError(
                    "Production database role must not be a superuser or bypass RLS"
                )
            protected = connection.execute(
                text(
                    "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relname IN ('customers','products','extraction_drafts','orders','order_lines','stock_movements','audit_events','customer_whatsapp_contacts','whatsapp_conversations','whatsapp_messages','whatsapp_webhook_events','billing_checkouts','whatsapp_signup_attempts','whatsapp_bot_replies','notification_reads','suppliers','warehouses','warehouse_balances','purchases','customer_payments','expenses','sales_returns','stock_transfers') AND c.relrowsecurity AND c.relforcerowsecurity"
                )
            ).scalar()
            if protected != 23:
                raise RuntimeError(
                    "Required tenant RLS is missing. Apply migrations first."
                )
    with engine.connect() as connection:
        whatsapp_schema_ready = inspect(connection).has_table("whatsapp_webhook_events")
    worker = (
        asyncio.create_task(whatsapp_worker())
        if whatsapp_schema_ready and get_db not in _app.dependency_overrides
        else None
    )
    try:
        yield
    finally:
        if worker:
            worker.cancel()
            try:
                await worker
            except asyncio.CancelledError:
                pass


app = FastAPI(
    title="OrderMesh AI Lite",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.app_env != "production" else None,
    openapi_url="/api/openapi.json" if settings.app_env != "production" else None,
    redoc_url=None,
)
app.include_router(whatsapp_router)
app.include_router(automation_router)
app.include_router(notifications_router)
app.include_router(account_settings_router)
app.include_router(commerce_router)
app.include_router(dashboard_insights_router)
app.include_router(business_router)
app.include_router(billing_router)
app.include_router(service_request_router)
app.include_router(meta_signup_router)
logger = logging.getLogger("ordermesh")
attempts = defaultdict(deque)
rate_lock = Lock()
GOOGLE_OAUTH_STATE_COOKIE = "ordermesh_google_oauth_state"
GOOGLE_OAUTH_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_OAUTH_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


def _oauth_error_redirect(code: str):
    return RedirectResponse(
        f"{settings.app_origin.rstrip('/')}/sign-in?{urlencode({'oauth_error': code})}",
        status_code=303,
    )


def _oauth_state_cookie(state: str, verifier: str, intent: str) -> str:
    return f"{state}|{verifier}|{intent}"


def _read_oauth_state(request: Request, state: str):
    raw = request.cookies.get(GOOGLE_OAUTH_STATE_COOKIE, "")
    parts = raw.split("|", 2)
    if len(parts) != 3 or parts[2] not in {"sign-in", "sign-up"}:
        return None
    cookie_state, verifier, intent = parts
    if not hmac.compare_digest(cookie_state, state):
        return None
    return verifier, intent


def _set_oauth_state_cookie(response: Response, state: str, verifier: str, intent: str):
    response.set_cookie(
        GOOGLE_OAUTH_STATE_COOKIE,
        _oauth_state_cookie(state, verifier, intent),
        max_age=600,
        httponly=True,
        secure=settings.app_env == "production",
        samesite="lax",
        path="/api/auth/google",
    )


def _clear_oauth_state_cookie(response: Response):
    response.delete_cookie(GOOGLE_OAUTH_STATE_COOKIE, path="/api/auth/google")


def _google_authorization_url(state: str, verifier: str) -> str:
    challenge = hashlib.sha256(verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(challenge).rstrip(b"=").decode("ascii")
    query = urlencode(
        {
            "client_id": settings.google_oauth_client_id,
            "redirect_uri": settings.resolved_google_oauth_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "prompt": "select_account",
        }
    )
    return f"{GOOGLE_OAUTH_AUTHORIZE_URL}?{query}"


@app.middleware("http")
async def guards(request: Request, call_next):
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        signed_webhook = request.method == "POST" and request.url.path in (
            "/webhooks/whatsapp",
            "/api/billing/payhere/notify",
        )
        if not signed_webhook and (
            request.headers.get("x-ordermesh") != "1"
            or request.headers.get("origin", settings.app_origin) != settings.app_origin
        ):
            return JSONResponse(
                {"detail": "Invalid request origin or CSRF header"}, status_code=403
            )
        if not signed_webhook and request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse(
                {"detail": "Cross-site requests denied"}, status_code=403
            )
    if request.url.path in ("/api/auth/login", "/api/auth/register"):
        address = request.client.host if request.client else "unknown"
        current = time.monotonic()
        with rate_lock:
            # Bound memory and expire idle clients. A distributed gateway is required at scale.
            for key in list(attempts):
                while attempts[key] and attempts[key][0] < current - 60:
                    attempts[key].popleft()
                if not attempts[key]:
                    del attempts[key]
            bucket = attempts[address]
            if len(bucket) >= 10 or len(attempts) > 10000:
                return JSONResponse(
                    {"detail": "Too many attempts. Try again in a minute."},
                    status_code=429,
                    headers={"Retry-After": "60"},
                )
            bucket.append(current)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(IntegrityError)
async def conflict(_request, _exc):
    return JSONResponse(
        {"detail": "A conflicting record exists. Refresh and try again."},
        status_code=409,
    )


def record(db, tenant, action, entity_id):
    db.add(
        AuditEvent(
            organization_id=tenant.id,
            actor_id=tenant.user_id,
            action=action,
            entity_id=entity_id,
        )
    )


def serialize(obj):
    return {
        c.name: getattr(obj, c.name)
        for c in obj.__table__.columns
        if c.name not in ("request_hash", "idempotency_key", "pos_request_hash")
    }


@app.get("/api/health")
def health(db: DBSession = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.post("/api/auth/register", status_code=201)
def register(body: Register, response: Response, db: DBSession = Depends(get_db)):
    if not settings.allow_registration:
        raise HTTPException(403, "Self-service registration is disabled")
    user = User(
        email=str(body.email).lower(),
        name=body.name,
        password_hash=passwords.hash(body.password),
    )
    org = Organization(name=body.organization_name)
    db.add_all([user, org])
    db.flush()
    ensure_main(db, org.id)
    db.add(Membership(user_id=user.id, organization_id=org.id, role="owner"))
    issue_session(db, user.id, response)
    db.commit()
    return {"id": user.id, "organization_id": org.id}


@app.post("/api/auth/login")
def login(body: Login, response: Response, db: DBSession = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == str(body.email).lower()))
    valid = passwords.verify(body.password, user.password_hash if user else DUMMY_HASH)
    if not user or not valid:
        raise HTTPException(401, "Invalid email or password")
    issue_session(db, user.id, response)
    db.commit()
    return {"id": user.id}


@app.get("/api/auth/google/start")
def google_start(request: Request, intent: Literal["sign-in", "sign-up"] = "sign-in"):
    # A localhost start must first move to the configured HTTPS domain, so the
    # state cookie and callback share a host. Redirect only to fixed app config.
    forwarded_host = (
        request.headers.get("x-forwarded-host", "").split(",")[0].strip().split(":")[0]
    )
    if settings.app_origin.startswith("https://") and forwarded_host in {
        "localhost",
        "127.0.0.1",
    }:
        return RedirectResponse(
            f"{settings.app_origin.rstrip('/')}/api/auth/google/start?intent={intent}",
            status_code=303,
        )
    if not settings.google_oauth_ready:
        return _oauth_error_redirect("google_not_configured")
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    response = RedirectResponse(
        _google_authorization_url(state, verifier), status_code=303
    )
    _set_oauth_state_cookie(response, state, verifier, intent)
    return response


@app.get("/api/auth/google/callback")
def google_callback(
    request: Request,
    code: str = "",
    state: str = "",
    provider_error: str = Query(default="", alias="error"),
    db: DBSession = Depends(get_db),
):
    state_details = _read_oauth_state(request, state)
    if not state_details:
        response = _oauth_error_redirect("invalid_oauth_state")
        _clear_oauth_state_cookie(response)
        return response
    verifier, intent = state_details
    if provider_error or not code:
        response = _oauth_error_redirect("google_cancelled")
        _clear_oauth_state_cookie(response)
        return response
    try:
        token_response = httpx.post(
            GOOGLE_OAUTH_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret.get_secret_value(),
                "redirect_uri": settings.resolved_google_oauth_redirect_uri,
                "grant_type": "authorization_code",
                "code_verifier": verifier,
            },
            timeout=10.0,
        )
        token_response.raise_for_status()
        access_token = token_response.json().get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise ValueError("Google did not return an access token")
        profile_response = httpx.get(
            GOOGLE_OAUTH_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10.0,
        )
        profile_response.raise_for_status()
        profile = profile_response.json()
    except (httpx.HTTPError, TypeError, ValueError):
        logger.warning("Google OAuth callback could not be completed")
        response = _oauth_error_redirect("google_verification_failed")
        _clear_oauth_state_cookie(response)
        return response

    subject = profile.get("sub")
    email = profile.get("email")
    if (
        not isinstance(subject, str)
        or not subject
        or len(subject) > 255
        or not isinstance(email, str)
        or not email
        or len(email) > 254
        or profile.get("email_verified") is not True
    ):
        response = _oauth_error_redirect("google_verification_failed")
        _clear_oauth_state_cookie(response)
        return response
    email = email.casefold()
    user = db.scalar(select(User).where(User.google_subject == subject))
    if user is None:
        user = db.scalar(select(User).where(User.email == email))
        if (
            user
            and user.google_subject
            and not hmac.compare_digest(user.google_subject, subject)
        ):
            response = _oauth_error_redirect("google_account_conflict")
            _clear_oauth_state_cookie(response)
            return response
        if user:
            user.google_subject = subject
        elif intent == "sign-in":
            response = _oauth_error_redirect("google_account_not_found")
            _clear_oauth_state_cookie(response)
            return response
        else:
            display_name = str(profile.get("name") or email.split("@", 1)[0]).strip()
            user = User(
                email=email,
                name=(display_name or "OrderMesh user")[:120],
                password_hash=passwords.hash(secrets.token_urlsafe(48)),
                google_subject=subject,
            )
            db.add(user)
    db.flush()
    has_workspace = (
        db.scalar(
            select(Membership.user_id).where(Membership.user_id == user.id).limit(1)
        )
        is not None
    )
    destination = "/dashboard" if has_workspace else "/sign-up?google=1"
    response = RedirectResponse(f"{settings.app_origin.rstrip('/')}{destination}", 303)
    issue_session(db, user.id, response)
    _clear_oauth_state_cookie(response)
    db.commit()
    return response


@app.post("/api/auth/google/complete-registration", status_code=201)
def complete_google_registration(
    body: GoogleWorkspaceRegistration,
    user: User = Depends(current_user),
    db: DBSession = Depends(get_db),
):
    if not settings.allow_registration:
        raise HTTPException(403, "Self-service registration is disabled")
    if db.scalar(
        select(Membership.user_id).where(Membership.user_id == user.id).limit(1)
    ):
        raise HTTPException(409, "This account already has a workspace")
    organization = Organization(name=body.organization_name)
    db.add(organization)
    db.flush()
    ensure_main(db, organization.id)
    db.add(Membership(user_id=user.id, organization_id=organization.id, role="owner"))
    db.commit()
    return {"id": user.id, "organization_id": organization.id}


@app.post("/api/auth/logout", status_code=204)
def logout(request: Request, response: Response, db: DBSession = Depends(get_db)):
    token = request.cookies.get(COOKIE)
    session = db.get(Session, digest(token)) if token else None
    if session:
        db.delete(session)
    db.commit()
    response.delete_cookie(COOKIE, path="/")


@app.get("/api/auth/me")
def me(user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    memberships = db.execute(
        select(Organization, Membership.role)
        .join(Membership)
        .where(Membership.user_id == user.id)
    ).all()
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "has_photo": bool(user.avatar_data),
        "phone": user.phone,
        "organizations": [
            {**serialize(org), "role": role, "dashboard": dashboard_view(org)}
            for org, role in memberships
        ],
    }


@app.get("/api/customers")
def customers(
    tenant: Tenant = Depends(tenant_context),
    db: DBSession = Depends(get_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    return [
        serialize(x)
        for x in db.scalars(
            select(Customer)
            .where(Customer.organization_id == tenant.id)
            .order_by(Customer.name, Customer.id)
            .offset(offset)
            .limit(limit)
        )
    ]


@app.post("/api/customers", status_code=201)
def create_customer(
    body: CustomerInput,
    tenant: Tenant = Depends(tenant_context),
    db: DBSession = Depends(get_db),
):
    require(tenant, "owner", "admin")
    obj = Customer(organization_id=tenant.id, **body.model_dump())
    db.add(obj)
    db.flush()
    record(db, tenant, "customer.created", obj.id)
    db.commit()
    return serialize(obj)


@app.put("/api/customers/{entity_id}")
def update_customer(
    entity_id: str,
    body: CustomerInput,
    tenant: Tenant = Depends(tenant_context),
    db: DBSession = Depends(get_db),
):
    require(tenant, "owner", "admin")
    lock_org(db, tenant)
    obj = scoped(db, Customer, tenant, entity_id)
    for key, value in body.model_dump(exclude_none=True).items():
        setattr(obj, key, value)
    record(db, tenant, "customer.updated", obj.id)
    db.commit()
    return serialize(obj)


@app.get("/api/products")
def products(
    tenant: Tenant = Depends(tenant_context),
    db: DBSession = Depends(get_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    return [
        serialize(x)
        for x in db.scalars(
            select(Product)
            .where(Product.organization_id == tenant.id)
            .order_by(Product.name, Product.id)
            .offset(offset)
            .limit(limit)
        )
    ]


@app.post("/api/products", status_code=201)
def create_product(
    body: ProductInput,
    tenant: Tenant = Depends(tenant_context),
    db: DBSession = Depends(get_db),
):
    require(tenant, "owner", "admin")
    org = lock_org(db, tenant)
    obj = Product(
        organization_id=tenant.id,
        **body.model_dump(exclude={"track_stock"}),
        track_stock=body.track_stock
        if body.track_stock is not None
        else org.business_type not in SERVICE_TYPES,
    )
    db.add(obj)
    db.flush()
    record(db, tenant, "product.created", obj.id)
    db.commit()
    return serialize(obj)


@app.put("/api/products/{entity_id}")
def update_product(
    entity_id: str,
    body: ProductInput,
    tenant: Tenant = Depends(tenant_context),
    db: DBSession = Depends(get_db),
):
    require(tenant, "owner", "admin")
    lock_org(db, tenant)
    obj = scoped(db, Product, tenant, entity_id)
    for key, value in body.model_dump(exclude_none=True).items():
        setattr(obj, key, value)
    for field in ("cost_minor", "wholesale_price_minor"):
        if field in body.model_fields_set:
            setattr(obj, field, getattr(body, field))
    record(db, tenant, "product.updated", obj.id)
    db.commit()
    return serialize(obj)


@app.post("/api/products/{entity_id}/stock")
def adjust_stock(
    entity_id: str,
    body: StockInput,
    tenant: Tenant = Depends(tenant_context),
    db: DBSession = Depends(get_db),
):
    require(tenant, "owner", "admin")
    lock_org(db, tenant)
    obj = scoped(db, Product, tenant, entity_id)
    if not obj.track_stock:
        raise HTTPException(422, "Services do not use stock adjustments")
    warehouse = select_warehouse(db, tenant, body.warehouse_id)
    move_stock(db, tenant, obj, body.delta, warehouse, body.reason)
    record(db, tenant, "stock.adjusted", obj.id)
    db.commit()
    return serialize(obj)


@app.get("/api/stock-movements")
def movements(
    tenant: Tenant = Depends(tenant_context),
    db: DBSession = Depends(get_db),
    offset: int = Query(0, ge=0),
):
    return [
        serialize(x)
        for x in db.scalars(
            select(StockMovement)
            .where(StockMovement.organization_id == tenant.id)
            .order_by(StockMovement.created_at.desc())
            .offset(offset)
            .limit(100)
        )
    ]


@app.post("/api/extractions", status_code=201)
def extract(
    body: ExtractInput,
    tenant: Tenant = Depends(tenant_context),
    db: DBSession = Depends(get_db),
):
    require(tenant, "owner", "admin", "staff")
    catalog = list(
        db.scalars(
            select(Product).where(
                Product.organization_id == tenant.id, Product.active.is_(True)
            )
        )
    )
    org = db.get(Organization, tenant.id)
    try:
        result = (
            extract_service_request(body.text, org)
            if uses_service_workflow(org, catalog, body.text)
            else get_extractor().extract(body.text, body.language, catalog).model_dump()
        )
    except NotImplementedError as exc:
        raise HTTPException(422, str(exc)) from exc
    except ProviderUnavailable as exc:
        raise HTTPException(502, str(exc)) from exc
    draft = ExtractionDraft(
        organization_id=tenant.id,
        source_text=body.text,
        result=result,
        created_by=tenant.user_id,
    )
    db.add(draft)
    db.flush()
    record(db, tenant, "extraction.created", draft.id)
    db.commit()
    return serialize(draft)


@app.post("/api/extractions/image", status_code=201)
async def extract_order_image(
    request: Request,
    tenant: Tenant = Depends(tenant_context),
    db: DBSession = Depends(get_db),
):
    require(tenant, "owner", "admin", "staff")
    org = db.get(Organization, tenant.id)
    ensure_subscription(org)
    if not image_ready():
        raise HTTPException(503, "Image extraction is not configured")
    mime = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if mime not in IMAGE_MIME_TYPES:
        raise HTTPException(415, "Upload a JPEG, PNG or WebP image")
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > MAX_IMAGE_BYTES:
            raise HTTPException(413, "Order images must be no larger than 8 MB")
    catalog = list(
        db.scalars(
            select(Product).where(
                Product.organization_id == tenant.id, Product.active.is_(True)
            )
        )
    )

    def process():
        readout = read_image(bytes(raw))
        if not readout.text:
            raise ImageError(
                "No readable order text in the image; enter details manually"
            )
        result = (
            extract_service_request(readout.text, org)
            if uses_service_workflow(org, catalog, readout.text)
            else get_extractor().extract(readout.text, "auto", catalog).model_dump()
        )
        return readout.text, image_flags(result, readout.uncertain)

    try:
        source, result = await asyncio.to_thread(process)
    except ImageError as exc:
        raise HTTPException(
            503 if exc.retryable or "credits" in str(exc) else 422, str(exc)
        ) from exc
    except ProviderUnavailable as exc:
        raise HTTPException(
            502, "Image details could not be extracted; retry or enter them manually"
        ) from exc
    draft = ExtractionDraft(
        organization_id=tenant.id,
        source_text=source,
        result=result,
        created_by=tenant.user_id,
    )
    db.add(draft)
    db.flush()
    record(db, tenant, "image_extraction.created", draft.id)
    db.commit()
    return serialize(draft)


@app.get("/api/extractions/{entity_id}")
def get_extraction(
    entity_id: str,
    tenant: Tenant = Depends(tenant_context),
    db: DBSession = Depends(get_db),
):
    return serialize(scoped(db, ExtractionDraft, tenant, entity_id))


def order_result(db, tenant, order):
    lines = db.scalars(
        select(OrderLine).where(
            OrderLine.organization_id == tenant.id, OrderLine.order_id == order.id
        )
    ).all()
    return {**serialize(order), "items": [serialize(x) for x in lines]}


@app.post("/api/orders", status_code=201)
def create_order(
    body: OrderInput,
    idempotency_key: str = Header(..., min_length=8, max_length=80),
    tenant: Tenant = Depends(tenant_context),
    db: DBSession = Depends(get_db),
):
    result = confirm_order(body, idempotency_key, tenant, db)
    db.commit()
    return result


def confirm_order(
    body: OrderInput, idempotency_key: str, tenant: Tenant, db: DBSession
):
    require(tenant, "owner", "admin", "staff")
    org = lock_org(db, tenant)
    request_hash = digest(json.dumps(body.model_dump(), sort_keys=True))
    existing = db.scalar(
        select(Order).where(
            Order.organization_id == tenant.id, Order.idempotency_key == idempotency_key
        )
    )
    if existing:
        if existing.request_hash != request_hash:
            raise HTTPException(409, "Idempotency key was used for a different order")
        return order_result(db, tenant, existing)
    ensure_subscription(org)
    month_start = (
        datetime.now(ZoneInfo("Asia/Colombo"))
        .replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        .astimezone(timezone.utc)
    )
    count = db.scalar(
        select(func.count())
        .select_from(Order)
        .where(Order.organization_id == tenant.id, Order.created_at >= month_start)
    )
    if count >= org.monthly_order_limit:
        raise HTTPException(409, "Monthly order limit reached")
    customer = scoped(db, Customer, tenant, body.customer_id)
    if not customer.active:
        raise HTTPException(422, "Customer is archived")
    if body.draft_id:
        draft = scoped(db, ExtractionDraft, tenant, body.draft_id)
        inbound_request = db.scalar(
            select(WhatsAppMessage.id).where(
                WhatsAppMessage.organization_id == tenant.id,
                WhatsAppMessage.extraction_draft_id == draft.id,
                WhatsAppMessage.direction == "inbound",
            )
        )
        if inbound_request:
            require(tenant, "owner", "admin")
            if draft.result.get("order_review", {}).get("status") == "rejected":
                raise HTTPException(409, "This WhatsApp order request was rejected")
        if draft.result.get("kind") == "service_request":
            raise HTTPException(
                422,
                "Review service requests in the request workflow; create a separate quote/order when agreed",
            )
        if not body.flags_acknowledged:
            raise HTTPException(422, "Acknowledge extraction flags before confirming")
        if db.scalar(
            select(Order.id).where(
                Order.organization_id == tenant.id, Order.draft_id == draft.id
            )
        ):
            raise HTTPException(409, "This extraction has already been confirmed")
    ids = [i.product_id for i in body.items]
    if len(ids) != len(set(ids)):
        raise HTTPException(422, "Combine duplicate product lines before confirming")
    catalog = {
        x.id: x
        for x in db.scalars(
            select(Product)
            .where(Product.organization_id == tenant.id, Product.id.in_(ids))
            .order_by(Product.id)
            .with_for_update()
        )
    }
    warehouse = select_warehouse(db, tenant, body.warehouse_id)
    subtotal = 0
    for item in body.items:
        product = catalog.get(item.product_id)
        if not product or not product.active:
            raise HTTPException(422, "A selected product is unavailable")
        if item.quantity < product.min_order_qty:
            raise HTTPException(
                422,
                f"Minimum order quantity for {product.name} is {product.min_order_qty}",
            )
        if product.track_stock and available_at(db, product, warehouse) < item.quantity:
            raise HTTPException(
                409, f"Insufficient stock for {product.name} in {warehouse.name}"
            )
        subtotal += item.quantity * selling_price(
            product, item.quantity, body.price_mode
        )
    tax, total = order_totals(subtotal, body.discount_minor, body.tax_basis_points)
    if total != body.expected_total_minor:
        raise HTTPException(
            409,
            "Prices changed. Refresh the catalog and review the total before confirming again.",
        )
    order = Order(
        organization_id=tenant.id,
        customer_id=customer.id,
        customer_name=customer.name,
        customer_address=customer.address,
        delivery_instructions=body.delivery_instructions,
        total_minor=total,
        subtotal_minor=subtotal,
        discount_minor=body.discount_minor,
        tax_basis_points=body.tax_basis_points,
        tax_minor=tax,
        price_mode=body.price_mode,
        warehouse_id=warehouse.id,
        source="whatsapp" if body.draft_id and inbound_request else "manual",
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        draft_id=body.draft_id,
        created_by=tenant.user_id,
    )
    db.add(order)
    db.flush()
    for item in body.items:
        product = catalog[item.product_id]
        if product.track_stock:
            move_stock(
                db, tenant, product, -item.quantity, warehouse, f"Order {order.id}"
            )
        db.add(
            OrderLine(
                organization_id=tenant.id,
                order_id=order.id,
                product_id=product.id,
                product_name=product.name,
                track_stock=product.track_stock,
                quantity=item.quantity,
                price_minor=selling_price(product, item.quantity, body.price_mode),
                cost_minor=product.cost_minor,
            )
        )
    record(db, tenant, "order.confirmed", order.id)
    queue_order_confirmation(db, org, order)
    db.flush()
    result = order_result(db, tenant, order)
    return result


@app.get("/api/orders")
def orders(
    tenant: Tenant = Depends(tenant_context),
    db: DBSession = Depends(get_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    return [
        serialize(x)
        for x in db.scalars(
            select(Order)
            .where(Order.organization_id == tenant.id)
            .order_by(Order.created_at.desc(), Order.id)
            .offset(offset)
            .limit(limit)
        )
    ]


@app.get("/api/orders/{entity_id}")
def get_order(
    entity_id: str,
    tenant: Tenant = Depends(tenant_context),
    db: DBSession = Depends(get_db),
):
    return order_result(db, tenant, scoped(db, Order, tenant, entity_id))


@app.patch("/api/orders/{entity_id}")
def transition_order(
    entity_id: str,
    body: Transition,
    tenant: Tenant = Depends(tenant_context),
    db: DBSession = Depends(get_db),
):
    require(tenant, "owner", "admin", "staff")
    lock_org(db, tenant)
    order = scoped(db, Order, tenant, entity_id)
    if order.status == body.status:
        return serialize(order)
    if order.status != "confirmed":
        raise HTTPException(409, "This order is already closed")
    if body.status == "cancelled":
        if db.scalar(
            select(CustomerPayment.id).where(
                CustomerPayment.organization_id == tenant.id,
                CustomerPayment.order_id == order.id,
            )
        ) or db.scalar(
            select(SalesReturn.id).where(
                SalesReturn.organization_id == tenant.id,
                SalesReturn.order_id == order.id,
            )
        ):
            raise HTTPException(
                409,
                "This order has payments or returns; use the return/refund workflow instead",
            )
        warehouse = select_warehouse(db, tenant, order.warehouse_id)
        lines = db.scalars(
            select(OrderLine)
            .where(
                OrderLine.organization_id == tenant.id, OrderLine.order_id == order.id
            )
            .order_by(OrderLine.product_id)
        ).all()
        for line in lines:
            if not line.track_stock:
                continue
            product = scoped(db, Product, tenant, line.product_id)
            move_stock(
                db, tenant, product, line.quantity, warehouse, f"Cancelled {order.id}"
            )
    order.status = body.status
    record(db, tenant, f"order.{body.status}", order.id)
    db.commit()
    return serialize(order)


@app.get("/api/orders/{entity_id}/invoice")
def invoice(
    entity_id: str,
    tenant: Tenant = Depends(tenant_context),
    db: DBSession = Depends(get_db),
):
    order = scoped(db, Order, tenant, entity_id)
    lines = db.scalars(
        select(OrderLine).where(
            OrderLine.organization_id == tenant.id, OrderLine.order_id == order.id
        )
    ).all()
    org = db.scalar(select(Organization).where(Organization.id == tenant.id))
    try:
        data = invoice_pdf(order, lines, org)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return Response(
        data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="invoice-{order.id}.pdf"'
        },
    )


@app.get("/api/analytics")
def analytics(
    tenant: Tenant = Depends(tenant_context), db: DBSession = Depends(get_db)
):
    tenant_orders = select(Order).where(Order.organization_id == tenant.id)
    active = Order.status != "cancelled"
    sales = db.scalar(
        select(func.coalesce(func.sum(Order.total_minor), 0)).where(
            Order.organization_id == tenant.id, active
        )
    )
    order_count = db.scalar(
        select(func.count())
        .select_from(Order)
        .where(Order.organization_id == tenant.id)
    )
    pending = db.scalar(
        select(func.count())
        .select_from(Order)
        .where(Order.organization_id == tenant.id, Order.status == "confirmed")
    )
    low = db.scalar(
        select(func.count())
        .select_from(Product)
        .where(
            Product.organization_id == tenant.id,
            Product.active.is_(True),
            Product.track_stock.is_(True),
            Product.stock <= Product.reorder_level,
        )
    )
    customer_count = db.scalar(
        select(func.count())
        .select_from(Customer)
        .where(Customer.organization_id == tenant.id, Customer.active.is_(True))
    )
    today = datetime.now(ZoneInfo("Asia/Colombo")).date()
    start = datetime.combine(
        today - timedelta(days=6), datetime.min.time(), ZoneInfo("Asia/Colombo")
    ).astimezone(timezone.utc)
    daily = {(today - timedelta(days=i)).isoformat(): 0 for i in reversed(range(7))}
    for order in db.scalars(tenant_orders.where(Order.created_at >= start, active)):
        day = (
            as_utc(order.created_at)
            .astimezone(ZoneInfo("Asia/Colombo"))
            .date()
            .isoformat()
        )
        if day in daily:
            daily[day] += order.total_minor
    return {
        "sales_minor": sales,
        "order_count": order_count,
        "pending_orders": pending,
        "pending_approvals": pending_count(db, tenant.id),
        "low_stock_count": low,
        "customer_count": customer_count,
        "daily_sales": [{"date": d, "total_minor": v} for d, v in daily.items()],
    }


@app.get("/api/audit")
def audit(
    tenant: Tenant = Depends(tenant_context),
    db: DBSession = Depends(get_db),
    offset: int = Query(0, ge=0),
):
    require(tenant, "owner", "admin")
    return [
        serialize(x)
        for x in db.scalars(
            select(AuditEvent)
            .where(AuditEvent.organization_id == tenant.id)
            .order_by(AuditEvent.created_at.desc())
            .offset(offset)
            .limit(100)
        )
    ]


@app.get("/api/integrations")
def integrations(_tenant: Tenant = Depends(tenant_context)):
    return {
        "text": {
            "status": "available",
            "provider": "openai-structured-v1"
            if settings.ai_provider == "openai"
            else "local-rules-v1",
            "languages": ["en", "si", "ta"],
        },
        "llm": {
            "status": "configured"
            if settings.ai_provider == "openai"
            else "not_configured"
        },
        "tamil": {"status": "available"},
        "voice": {
            "status": "configured" if voice_ready() else "not_configured",
            "languages": ["en", "si", "ta"],
            "max_duration_seconds": 180,
            "requires_review": True,
        },
        "images": {
            "status": "configured" if image_ready() else "not_configured",
            "languages": ["en", "si", "ta"],
            "requires_review": True,
        },
        "whatsapp": {"status": "not_configured"},
        "billing": {"status": "configured" if payhere_ready() else "not_configured"},
    }
