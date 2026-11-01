"""Actionable, tenant-scoped alerts with per-user acknowledgement."""

import hashlib

from fastapi import APIRouter, Depends
from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DBSession

from .automation import pending_query
from .db import get_db
from .models import (
    ExtractionDraft,
    NotificationRead,
    Order,
    Organization,
    Product,
    StockMovement,
    WhatsAppBotReply,
    WhatsAppConversation,
    WhatsAppMessage,
    WhatsAppWebhookEvent,
    as_utc,
    now,
)
from .schemas import StrictModel
from .security import Tenant, subscription_access, tenant_context

router = APIRouter()


def workspace_alerts(db, tenant):
    items = []
    stock_times = dict(
        db.execute(
            select(StockMovement.product_id, func.max(StockMovement.created_at))
            .where(StockMovement.organization_id == tenant.id)
            .group_by(StockMovement.product_id)
        ).all()
    )
    inbound_times = dict(
        db.execute(
            select(WhatsAppMessage.conversation_id, func.max(WhatsAppMessage.sent_at))
            .where(
                WhatsAppMessage.organization_id == tenant.id,
                WhatsAppMessage.direction == "inbound",
            )
            .group_by(WhatsAppMessage.conversation_id)
        ).all()
    )

    def add(key, title, detail, target, severity="info", created_at=None):
        items.append(
            {
                "id": hashlib.sha256(key.encode()).hexdigest(),
                "title": title,
                "detail": detail,
                "target": target,
                "severity": severity,
                "created_at": as_utc(created_at or now()).isoformat(),
            }
        )

    for draft, message in db.execute(pending_query(tenant.id)):
        add(
            "approval:" + draft.id,
            "WhatsApp order needs approval",
            message.customer_name or message.customer_phone,
            "Orders",
            "warning",
            draft.created_at,
        )
    for draft in db.scalars(
        select(ExtractionDraft).where(
            ExtractionDraft.organization_id == tenant.id,
            ExtractionDraft.result["kind"].as_string() == "service_request",
            func.coalesce(
                ExtractionDraft.result["review"]["status"].as_string(), "pending_review"
            )
            == "pending_review",
        )
    ):
        add(
            "service:" + draft.id,
            "Service request needs review",
            draft.source_text[:180],
            "Service requests",
            "warning",
            draft.created_at,
        )
    for product in db.scalars(
        select(Product).where(
            Product.organization_id == tenant.id,
            Product.active.is_(True),
            Product.track_stock.is_(True),
            Product.stock <= Product.reorder_level,
        )
    ):
        add(
            f"stock:{product.id}:{product.stock}:{product.reorder_level}:{stock_times.get(product.id)}",
            "Out of stock" if product.stock == 0 else "Low stock",
            f"{product.name}: {product.stock} {product.unit}; reorder level {product.reorder_level}",
            "Inventory",
            "error" if product.stock == 0 else "warning",
            stock_times.get(product.id),
        )
    for conversation in db.scalars(
        select(WhatsAppConversation).where(
            WhatsAppConversation.organization_id == tenant.id,
            WhatsAppConversation.unread_count > 0,
        )
    ):
        add(
            f"inbox:{conversation.id}:{inbound_times.get(conversation.id)}",
            "New WhatsApp message",
            f"{conversation.customer_name or conversation.customer_phone}: {conversation.unread_count} unread",
            "WhatsApp inbox",
            created_at=conversation.last_message_at,
        )
    if tenant.role in {"owner", "admin"}:
        for job in db.scalars(
            select(WhatsAppBotReply)
            .where(
                WhatsAppBotReply.organization_id == tenant.id,
                WhatsAppBotReply.status.in_(["blocked", "unknown"]),
            )
            .order_by(WhatsAppBotReply.updated_at.desc())
            .limit(100)
        ):
            add(
                f"reply:{job.id}:{job.status}:{job.updated_at.isoformat()}",
                "WhatsApp reply needs attention",
                job.last_error or job.status,
                "Settings",
                "error",
                job.updated_at,
            )
        for event in db.scalars(
            select(WhatsAppWebhookEvent)
            .where(
                WhatsAppWebhookEvent.organization_id == tenant.id,
                WhatsAppWebhookEvent.status == "failed",
            )
            .limit(100)
        ):
            add(
                f"extraction:{event.id}:{event.attempts}",
                "Message processing failed",
                "Open the inbox to review or retry this message.",
                "WhatsApp inbox",
                "error",
                event.created_at,
            )
    if tenant.role in {"owner", "admin", "staff"}:
        from datetime import datetime

        from .commerce import COL, balances

        amounts = balances(db, tenant)
        today = datetime.now(COL).date()
        for order in db.scalars(
            select(Order).where(
                Order.organization_id == tenant.id, Order.status != "cancelled"
            )
        ):
            due = amounts.get(order.id, 0)
            if order.due_date and order.due_date < today and due:
                add(
                    f"overdue:{order.id}:{due}:{order.due_date}",
                    "Customer payment overdue",
                    f"{order.customer_name}: LKR {due / 100:,.2f} due since {order.due_date}",
                    "Operations",
                    "warning",
                    order.posted_at,
                )
            if order.delivery_status == "failed":
                add(
                    f"delivery:{order.id}:{order.delivery_reference}",
                    "Delivery needs attention",
                    order.customer_name,
                    "Operations",
                    "error",
                    order.created_at,
                )
        for message in db.scalars(
            select(WhatsAppMessage)
            .where(
                WhatsAppMessage.organization_id == tenant.id,
                WhatsAppMessage.direction == "outbound",
                WhatsAppMessage.delivery_status == "failed",
            )
            .limit(100)
        ):
            add(
                f"outbound:{message.id}:{message.status_updated_at}",
                "WhatsApp message failed",
                "Open the inbox to review the delivery failure.",
                "WhatsApp inbox",
                "error",
                message.status_updated_at or message.created_at,
            )
    org = db.get(Organization, tenant.id)
    if not subscription_access(org):
        add(
            "subscription:" + str(org.paid_until or org.trial_ends_at),
            "Subscription needs attention",
            "Renew access in Settings; existing records remain available.",
            "Settings",
            "error",
        )
    priority = {"error": 0, "warning": 1, "info": 2}
    items.sort(key=lambda x: (priority[x["severity"]], x["id"]))
    return items


class ReadInput(StrictModel):
    keys: list[str] = Field(default_factory=list, max_length=200)
    all: bool = False


@router.get("/api/notifications")
def notifications(
    tenant: Tenant = Depends(tenant_context), db: DBSession = Depends(get_db)
):
    items = workspace_alerts(db, tenant)
    read = set(
        db.scalars(
            select(NotificationRead.event_key).where(
                NotificationRead.organization_id == tenant.id,
                NotificationRead.user_id == tenant.user_id,
            )
        )
    )
    for item in items:
        item["read"] = item["id"] in read
    items.sort(key=lambda item: item["read"])
    return {
        "items": items[:200],
        "unread_count": sum(not item["read"] for item in items),
        "total": len(items),
    }


@router.post("/api/notifications/read")
def mark_read(
    body: ReadInput,
    tenant: Tenant = Depends(tenant_context),
    db: DBSession = Depends(get_db),
):
    candidates = {item["id"] for item in workspace_alerts(db, tenant)}
    keys = candidates if body.all else candidates.intersection(body.keys)
    existing = set(
        db.scalars(
            select(NotificationRead.event_key).where(
                NotificationRead.organization_id == tenant.id,
                NotificationRead.user_id == tenant.user_id,
            )
        )
    )
    if db.bind.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    remaining = list(keys - existing)
    marked = 0
    for offset in range(0, len(remaining), 200):
        values = [
            {"organization_id": tenant.id, "user_id": tenant.user_id, "event_key": key}
            for key in remaining[offset : offset + 200]
        ]
        result = db.execute(
            insert(NotificationRead)
            .values(values)
            .on_conflict_do_nothing(
                index_elements=["organization_id", "user_id", "event_key"]
            )
        )
        marked += result.rowcount
    db.commit()
    return {"marked_read": marked}
