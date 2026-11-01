import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    false,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def uid():
    return str(uuid.uuid4())


def now():
    return datetime.now(timezone.utc)


def as_utc(value):
    return (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )


class User(Base):
    phone: Mapped[str] = mapped_column(String(40), default="", server_default="")
    avatar_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    avatar_mime: Mapped[str] = mapped_column(String(40), default="", server_default="")
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(Text)
    google_subject: Mapped[str | None] = mapped_column(
        String(255), unique=True, index=True, nullable=True
    )


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(120))
    plan: Mapped[str] = mapped_column(String(32), default="starter")
    subscription_status: Mapped[str] = mapped_column(String(32), default="trial")
    monthly_order_limit: Mapped[int] = mapped_column(Integer, default=500)
    business_type: Mapped[str] = mapped_column(String(32), default="wholesale")
    business_profile: Mapped[dict] = mapped_column(JSON, default=dict)
    trial_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=now
    )
    trial_ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=lambda: now() + timedelta(days=15)
    )
    paid_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Membership(Base):
    __tablename__ = "memberships"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(16))
    __table_args__ = (CheckConstraint("role IN ('owner','admin','staff','viewer')"),)


class Session(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TenantMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )


class Customer(TenantMixin, Base):
    __tablename__ = "customers"
    credit_limit_minor: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    payment_terms_days: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    price_group: Mapped[str] = mapped_column(
        String(16), default="retail", server_default="retail"
    )
    walk_in: Mapped[bool] = mapped_column(default=False, server_default=false())
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(30), default="")
    address: Mapped[str] = mapped_column(String(500), default="")
    active: Mapped[bool] = mapped_column(default=True)
    __table_args__ = (UniqueConstraint("organization_id", "id"),)


class CustomerWhatsAppContact(TenantMixin, Base):
    """A deliberate, tenant-owned WhatsApp identity for a customer.

    The value is stored as international digits without a leading ``+``.  It is
    intentionally separate from the general customer phone field: a free-form
    office phone must never silently identify a WhatsApp sender.
    """

    __tablename__ = "customer_whatsapp_contacts"
    customer_id: Mapped[str] = mapped_column(String(36))
    phone: Mapped[str] = mapped_column(String(15))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        UniqueConstraint("organization_id", "phone"),
        ForeignKeyConstraint(
            ["organization_id", "customer_id"],
            ["customers.organization_id", "customers.id"],
        ),
    )


class Product(TenantMixin, Base):
    category: Mapped[str] = mapped_column(
        String(32), default="other", server_default="other"
    )
    __tablename__ = "products"
    barcode: Mapped[str] = mapped_column(String(80), default="", server_default="")
    cost_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    wholesale_price_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    wholesale_min_qty: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1"
    )
    min_order_qty: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    sku: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(120))
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    unit: Mapped[str] = mapped_column(String(30), default="units")
    price_minor: Mapped[int] = mapped_column(Integer)
    track_stock: Mapped[bool] = mapped_column(default=True)
    stock: Mapped[int] = mapped_column(Integer, default=0)
    reorder_level: Mapped[int] = mapped_column(Integer, default=10)
    active: Mapped[bool] = mapped_column(default=True)
    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        UniqueConstraint("organization_id", "sku"),
        Index(
            "uq_product_barcode",
            "organization_id",
            "barcode",
            unique=True,
            sqlite_where=text("barcode <> ''"),
            postgresql_where=text("barcode <> ''"),
        ),
        CheckConstraint("stock >= 0"),
        CheckConstraint("price_minor >= 0"),
        CheckConstraint("reorder_level >= 0"),
    )


class ExtractionDraft(TenantMixin, Base):
    __tablename__ = "extraction_drafts"
    source_text: Mapped[str] = mapped_column(Text)
    result: Mapped[dict] = mapped_column(JSON)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("organization_id", "id"),)


class Order(TenantMixin, Base):
    __tablename__ = "orders"
    source: Mapped[str] = mapped_column(
        String(20), default="manual", server_default="manual"
    )
    warehouse_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    subtotal_minor: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    discount_minor: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    tax_basis_points: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    tax_minor: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    price_mode: Mapped[str] = mapped_column(
        String(16), default="retail", server_default="retail"
    )
    financial_posted: Mapped[bool] = mapped_column(
        default=False, server_default=false()
    )
    posted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    pos_request_hash: Mapped[str] = mapped_column(
        String(64), default="", server_default=""
    )
    assigned_to: Mapped[str | None] = mapped_column(String(36), nullable=True)
    delivery_status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default="pending"
    )
    delivery_reference: Mapped[str] = mapped_column(
        String(160), default="", server_default=""
    )
    customer_id: Mapped[str] = mapped_column(String(36))
    customer_name: Mapped[str] = mapped_column(String(120))
    customer_address: Mapped[str] = mapped_column(String(500))
    delivery_instructions: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(20), default="confirmed")
    total_minor: Mapped[int] = mapped_column(Integer)
    idempotency_key: Mapped[str] = mapped_column(String(80))
    request_hash: Mapped[str] = mapped_column(String(64))
    draft_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, index=True
    )
    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        UniqueConstraint("organization_id", "idempotency_key"),
        UniqueConstraint("organization_id", "draft_id"),
        CheckConstraint("total_minor >= 0"),
        CheckConstraint("status IN ('confirmed','fulfilled','cancelled')"),
        ForeignKeyConstraint(
            ["organization_id", "customer_id"],
            ["customers.organization_id", "customers.id"],
        ),
        ForeignKeyConstraint(
            ["organization_id", "draft_id"],
            ["extraction_drafts.organization_id", "extraction_drafts.id"],
        ),
    )


class OrderLine(TenantMixin, Base):
    track_stock: Mapped[bool] = mapped_column(default=True)
    __tablename__ = "order_lines"
    cost_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    order_id: Mapped[str] = mapped_column(String(36))
    product_id: Mapped[str] = mapped_column(String(36))
    product_name: Mapped[str] = mapped_column(String(120))
    quantity: Mapped[int] = mapped_column(Integer)
    price_minor: Mapped[int] = mapped_column(Integer)
    __table_args__ = (
        CheckConstraint("quantity > 0"),
        CheckConstraint("price_minor >= 0"),
        ForeignKeyConstraint(
            ["organization_id", "order_id"], ["orders.organization_id", "orders.id"]
        ),
        ForeignKeyConstraint(
            ["organization_id", "product_id"],
            ["products.organization_id", "products.id"],
        ),
    )


class StockMovement(TenantMixin, Base):
    __tablename__ = "stock_movements"
    warehouse_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    product_id: Mapped[str] = mapped_column(String(36))
    delta: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(200))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "product_id"],
            ["products.organization_id", "products.id"],
        ),
    )


class AuditEvent(TenantMixin, Base):
    __tablename__ = "audit_events"
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class WhatsAppPhoneNumber(Base):
    __tablename__ = "whatsapp_phone_numbers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    phone_number_id: Mapped[str] = mapped_column(String(128), unique=True)
    display_phone_number: Mapped[str] = mapped_column(String(40))
    access_token_encrypted: Mapped[str] = mapped_column(Text, default="")
    connection_kind: Mapped[str] = mapped_column(String(24), default="manual")
    business_account_id: Mapped[str] = mapped_column(String(128), default="")
    connected_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("organization_id", "phone_number_id"),)


class WhatsAppConversation(TenantMixin, Base):
    archived: Mapped[bool] = mapped_column(default=False, server_default=false())
    pinned: Mapped[bool] = mapped_column(default=False, server_default=false())
    __tablename__ = "whatsapp_conversations"
    phone_number_id: Mapped[str] = mapped_column(String(128))
    customer_phone: Mapped[str] = mapped_column(String(40))
    customer_name: Mapped[str] = mapped_column(String(120), default="")
    customer_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    customer_match_source: Mapped[str] = mapped_column(String(24), default="unmatched")
    last_message_preview: Mapped[str] = mapped_column(String(500), default="")
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    unread_count: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "phone_number_id"],
            [
                "whatsapp_phone_numbers.organization_id",
                "whatsapp_phone_numbers.phone_number_id",
            ],
        ),
        ForeignKeyConstraint(
            ["organization_id", "customer_id"],
            ["customers.organization_id", "customers.id"],
        ),
        UniqueConstraint("organization_id", "id"),
        UniqueConstraint("organization_id", "phone_number_id", "customer_phone"),
        CheckConstraint("unread_count >= 0"),
        CheckConstraint(
            "customer_match_source IN ('unmatched','customer_phone','whatsapp_contact','manual')"
        ),
    )


class WhatsAppMessage(TenantMixin, Base):
    category: Mapped[str] = mapped_column(String(32), default="unclassified")
    category_reason: Mapped[str] = mapped_column(String(240), default="")
    category_reviewed: Mapped[bool] = mapped_column(default=False)
    __tablename__ = "whatsapp_messages"
    conversation_id: Mapped[str] = mapped_column(String(36))
    phone_number_id: Mapped[str] = mapped_column(String(128))
    external_id: Mapped[str] = mapped_column(String(256), unique=True)
    direction: Mapped[str] = mapped_column(String(12), default="inbound")
    message_type: Mapped[str] = mapped_column(String(20))
    media_caption: Mapped[str] = mapped_column(
        String(1024), default="", server_default=""
    )
    media_uncertain: Mapped[bool] = mapped_column(default=False, server_default=false())
    media_id: Mapped[str] = mapped_column(String(128), default="", server_default="")
    media_mime_type: Mapped[str] = mapped_column(
        String(100), default="", server_default=""
    )
    media_sha256: Mapped[str] = mapped_column(String(64), default="", server_default="")
    transcription_status: Mapped[str] = mapped_column(
        String(20), default="", server_default=""
    )
    transcription_error: Mapped[str] = mapped_column(
        String(240), default="", server_default=""
    )
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_phone: Mapped[str] = mapped_column(String(40))
    customer_name: Mapped[str] = mapped_column(String(120), default="")
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    extraction_draft_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    delivery_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    delivery_error_code: Mapped[str] = mapped_column(String(40), default="")
    delivery_error_message: Mapped[str] = mapped_column(String(500), default="")
    client_request_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "conversation_id"],
            [
                "whatsapp_conversations.organization_id",
                "whatsapp_conversations.id",
            ],
        ),
        ForeignKeyConstraint(
            ["organization_id", "phone_number_id"],
            [
                "whatsapp_phone_numbers.organization_id",
                "whatsapp_phone_numbers.phone_number_id",
            ],
        ),
        ForeignKeyConstraint(
            ["organization_id", "extraction_draft_id"],
            ["extraction_drafts.organization_id", "extraction_drafts.id"],
        ),
        CheckConstraint("direction IN ('inbound','outbound')"),
        UniqueConstraint("organization_id", "id"),
        UniqueConstraint(
            "organization_id",
            "client_request_id",
            name="uq_whatsapp_messages_org_client_request",
        ),
    )


class WhatsAppWebhookEvent(TenantMixin, Base):
    __tablename__ = "whatsapp_webhook_events"
    external_id: Mapped[str] = mapped_column(String(256), unique=True)
    message_id: Mapped[str] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(16), default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "message_id"],
            ["whatsapp_messages.organization_id", "whatsapp_messages.id"],
        ),
        CheckConstraint("status IN ('queued','processing','processed','failed')"),
        CheckConstraint("attempts >= 0"),
        Index("ix_whatsapp_webhook_queue", "status", "created_at"),
    )


class BillingCheckoutRoute(Base):
    """Private callback routing only; no customer data or payment credentials."""

    __tablename__ = "billing_checkout_routes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"))


class BillingCheckout(TenantMixin, Base):
    __tablename__ = "billing_checkouts"
    entitled_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    customer_details: Mapped[dict] = mapped_column(JSON, default=dict)
    subscription_id: Mapped[str] = mapped_column(String(80), default="")
    status: Mapped[str] = mapped_column(String(24), default="pending")
    verified_payments: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class WhatsAppSignupAttempt(TenantMixin, Base):
    __tablename__ = "whatsapp_signup_attempts"
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    session_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), default="pending")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    token_encrypted: Mapped[str] = mapped_column(Text, default="")
    choices: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class WhatsAppBotReply(TenantMixin, Base):
    __tablename__ = "whatsapp_bot_replies"
    source_message_id: Mapped[str] = mapped_column(String(36))
    request_key: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(24))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="queued")
    last_error: Mapped[str] = mapped_column(String(240), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint("organization_id", "request_key"),
        ForeignKeyConstraint(
            ["organization_id", "source_message_id"],
            ["whatsapp_messages.organization_id", "whatsapp_messages.id"],
        ),
        CheckConstraint(
            "status IN ('queued','sending','accepted','blocked','unknown','cancelled')"
        ),
    )


class NotificationRead(TenantMixin, Base):
    __tablename__ = "notification_reads"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    event_key: Mapped[str] = mapped_column(String(64))
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("organization_id", "user_id", "event_key"),)


class Supplier(TenantMixin, Base):
    __tablename__ = "suppliers"
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(40), default="")
    address: Mapped[str] = mapped_column(String(500), default="")
    active: Mapped[bool] = mapped_column(default=True)
    __table_args__ = (UniqueConstraint("organization_id", "id"),)


class Warehouse(TenantMixin, Base):
    __tablename__ = "warehouses"
    name: Mapped[str] = mapped_column(String(120))
    code: Mapped[str] = mapped_column(String(32))
    active: Mapped[bool] = mapped_column(default=True)
    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        UniqueConstraint("organization_id", "code"),
    )


class WarehouseBalance(TenantMixin, Base):
    __tablename__ = "warehouse_balances"
    warehouse_id: Mapped[str] = mapped_column(String(36))
    product_id: Mapped[str] = mapped_column(String(36))
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (
        UniqueConstraint("organization_id", "warehouse_id", "product_id"),
        CheckConstraint("quantity >= 0"),
        ForeignKeyConstraint(
            ["organization_id", "warehouse_id"],
            ["warehouses.organization_id", "warehouses.id"],
        ),
        ForeignKeyConstraint(
            ["organization_id", "product_id"],
            ["products.organization_id", "products.id"],
        ),
    )


class Purchase(TenantMixin, Base):
    __tablename__ = "purchases"
    supplier_id: Mapped[str] = mapped_column(String(36))
    warehouse_id: Mapped[str] = mapped_column(String(36))
    reference: Mapped[str] = mapped_column(String(100), default="")
    status: Mapped[str] = mapped_column(String(20), default="draft")
    lines: Mapped[list] = mapped_column(JSON)
    total_minor: Mapped[int] = mapped_column(Integer)
    idempotency_key: Mapped[str] = mapped_column(String(80))
    request_hash: Mapped[str] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        UniqueConstraint("organization_id", "idempotency_key"),
        CheckConstraint("status IN ('draft','received','cancelled')"),
        CheckConstraint("total_minor >= 0"),
        ForeignKeyConstraint(
            ["organization_id", "supplier_id"],
            ["suppliers.organization_id", "suppliers.id"],
        ),
        ForeignKeyConstraint(
            ["organization_id", "warehouse_id"],
            ["warehouses.organization_id", "warehouses.id"],
        ),
    )


class CustomerPayment(TenantMixin, Base):
    __tablename__ = "customer_payments"
    order_id: Mapped[str] = mapped_column(String(36))
    customer_id: Mapped[str] = mapped_column(String(36))
    amount_minor: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(16), default="payment")
    method: Mapped[str] = mapped_column(String(20))
    reference: Mapped[str] = mapped_column(String(120), default="")
    idempotency_key: Mapped[str] = mapped_column(String(80))
    request_hash: Mapped[str] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key"),
        CheckConstraint("amount_minor > 0"),
        CheckConstraint("kind IN ('payment','refund')"),
        ForeignKeyConstraint(
            ["organization_id", "order_id"], ["orders.organization_id", "orders.id"]
        ),
        ForeignKeyConstraint(
            ["organization_id", "customer_id"],
            ["customers.organization_id", "customers.id"],
        ),
    )


class Expense(TenantMixin, Base):
    __tablename__ = "expenses"
    category: Mapped[str] = mapped_column(String(60))
    description: Mapped[str] = mapped_column(String(500))
    amount_minor: Mapped[int] = mapped_column(Integer)
    paid_on: Mapped[date] = mapped_column(Date)
    reference: Mapped[str] = mapped_column(String(120), default="")
    voided: Mapped[bool] = mapped_column(default=False)
    idempotency_key: Mapped[str] = mapped_column(String(80))
    request_hash: Mapped[str] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key"),
        CheckConstraint("amount_minor > 0"),
    )


class SalesReturn(TenantMixin, Base):
    __tablename__ = "sales_returns"
    order_id: Mapped[str] = mapped_column(String(36))
    warehouse_id: Mapped[str] = mapped_column(String(36))
    lines: Mapped[list] = mapped_column(JSON)
    tax_minor: Mapped[int] = mapped_column(Integer, default=0)
    total_minor: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(500))
    idempotency_key: Mapped[str] = mapped_column(String(80))
    request_hash: Mapped[str] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key"),
        CheckConstraint("total_minor >= 0"),
        ForeignKeyConstraint(
            ["organization_id", "order_id"], ["orders.organization_id", "orders.id"]
        ),
        ForeignKeyConstraint(
            ["organization_id", "warehouse_id"],
            ["warehouses.organization_id", "warehouses.id"],
        ),
    )


class StockTransfer(TenantMixin, Base):
    __tablename__ = "stock_transfers"
    product_id: Mapped[str] = mapped_column(String(36))
    from_warehouse_id: Mapped[str] = mapped_column(String(36))
    to_warehouse_id: Mapped[str] = mapped_column(String(36))
    quantity: Mapped[int] = mapped_column(Integer)
    idempotency_key: Mapped[str] = mapped_column(String(80))
    request_hash: Mapped[str] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key"),
        CheckConstraint("quantity > 0"),
        ForeignKeyConstraint(
            ["organization_id", "product_id"],
            ["products.organization_id", "products.id"],
        ),
        ForeignKeyConstraint(
            ["organization_id", "from_warehouse_id"],
            ["warehouses.organization_id", "warehouses.id"],
        ),
        ForeignKeyConstraint(
            ["organization_id", "to_warehouse_id"],
            ["warehouses.organization_id", "warehouses.id"],
        ),
    )
