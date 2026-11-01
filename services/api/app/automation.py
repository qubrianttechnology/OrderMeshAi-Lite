"""Grounded chatbot replies, owner review queue and durable send states."""

import re
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session as DBSession

from .bot_text import wording
from .db import SessionLocal, get_db
from .models import (
    AuditEvent,
    ExtractionDraft,
    Membership,
    Order,
    Organization,
    Product,
    WhatsAppBotReply,
    WhatsAppMessage,
    WhatsAppPhoneNumber,
    now,
)
from .schemas import StrictModel, WhatsAppReplyInput
from .security import (
    Tenant,
    lock_org,
    require,
    scoped,
    subscription_access,
    tenant_context,
)

router = APIRouter()


class BotSettings(StrictModel):
    enabled: bool = False
    answer_business_questions: bool = True


def bot_settings(org):
    raw = (org.business_profile or {}).get("whatsapp_bot", {})
    return BotSettings.model_validate(raw if isinstance(raw, dict) else {}).model_dump()


@router.get("/api/inbox/chatbot-settings")
def get_settings(
    tenant: Tenant = Depends(tenant_context), db: DBSession = Depends(get_db)
):
    require(tenant, "owner", "admin")
    return {
        **bot_settings(db.get(Organization, tenant.id)),
        "owner_approval_required": True,
        "processing_mode": "local",
    }


@router.put("/api/inbox/chatbot-settings")
def save_settings(
    body: BotSettings,
    tenant: Tenant = Depends(tenant_context),
    db: DBSession = Depends(get_db),
):
    require(tenant, "owner", "admin")
    org = lock_org(db, tenant)
    org.business_profile = {
        **(org.business_profile or {}),
        "whatsapp_bot": body.model_dump(),
    }
    db.add(
        AuditEvent(
            organization_id=tenant.id,
            actor_id=tenant.user_id,
            action="whatsapp.chatbot.settings",
            entity_id=org.id,
        )
    )
    db.commit()
    return {**body.model_dump(), "owner_approval_required": True}


def availability(db, organization_id, result):
    items = result.get("items", [])
    ids = [item.get("product_id") for item in items if item.get("product_id")]
    products = {
        p.id: p
        for p in db.scalars(
            select(Product).where(
                Product.organization_id == organization_id,
                Product.id.in_(ids),
                Product.active.is_(True),
            )
        )
    }
    totals = {}
    for item in items:
        pid, qty = item.get("product_id"), item.get("quantity")
        if pid in products and type(qty) is int and 0 < qty <= 100000:
            totals[pid] = totals.get(pid, 0) + qty
    rows = []
    for item in items:
        product = products.get(item.get("product_id"))
        qty = item.get("quantity")
        flags = item.get("flags", [])
        requested_unit = (item.get("unit") or "").casefold().strip()
        # Never turn a request for cartons into pieces, or guess vehicle fitment.
        unit_matches = not requested_unit or requested_unit.rstrip("s") == (
            product.unit.casefold().strip().rstrip("s") if product else ""
        )
        grounded = not any(
            flag in flags
            for flag in (
                "source_not_grounded",
                "unknown_or_foreign_product",
                "quantity_requires_review",
                "unit_not_grounded",
            )
        )
        if (
            not product
            or type(qty) is not int
            or not 0 < qty <= 100000
            or not unit_matches
            or not grounded
        ):
            state = "needs_review"
        elif totals.get(product.id, qty) < getattr(product, "min_order_qty", 1):
            state = "needs_review"
        elif not product.track_stock:
            state = "not_tracked"
        elif product.stock < totals.get(product.id, qty):
            state = "insufficient_stock"
        else:
            state = "available"
        rows.append(
            {
                "product_id": product.id if product else None,
                "product_name": product.name if product else "Unmatched item",
                "quantity": qty,
                "unit": product.unit if product else None,
                "status": state,
            }
        )
    return rows


def availability_reply(rows, source=""):
    words = wording(source)
    lines = [words["received"]]
    for row in rows[:20]:
        label = row["product_name"][:120]
        quantity = (
            f" ({row['quantity']} {row['unit']})"
            if type(row["quantity"]) is int and row["unit"]
            else ""
        )
        lines.append(f"- {label}{quantity}: {words[row['status']]}")
    lines.append(words["pending"])
    return "\n".join(lines)[:4096]


def enqueue(db, source, kind, body, key):
    if source.external_id.startswith("sim_"):
        return
    if not db.scalar(
        select(WhatsAppBotReply.id).where(
            WhatsAppBotReply.organization_id == source.organization_id,
            WhatsAppBotReply.request_key == key,
        )
    ):
        db.add(
            WhatsAppBotReply(
                organization_id=source.organization_id,
                source_message_id=source.id,
                request_key=key,
                kind=kind,
                body=body,
            )
        )


def queue_inbound_reply(db, message, org, draft=None):
    config = bot_settings(org)
    if (
        not config["enabled"]
        or not subscription_access(org)
        or message.category in {"personal", "spam"}
    ):
        return
    if draft and draft.result.get("kind") != "service_request":
        rows = availability(db, org.id, draft.result)
        if rows:
            enqueue(
                db,
                message,
                "availability",
                availability_reply(rows, message.text),
                "availability:" + message.id,
            )
        return
    if not config["answer_business_questions"]:
        return
    source = (message.text or "").casefold().strip()
    words = wording(source)
    if source in {"hi", "hello", "hello!", "hi!", "ආයුබෝවන්", "வணக்கம்"}:
        answer = words["greeting"]
    else:
        topics = [
            (r"\b(hours|open|opening|close)\b|විවෘත|වේලාව|වෙලාව|நேரம்|திறக்கும்", "hours"),
            (
                r"\b(delivery|deliver|shipping|dispatch)\b|බෙදාහැර|ඩිලිවරි|ප්‍රවාහන|விநியோக|டெலிவரி",
                "delivery",
            ),
            (r"\b(payment|payments|deposit|pay)\b|ගෙවී|ගෙවීම|கட்டணம்|பணம்", "payments"),
        ]
        key = next(
            (field for pattern, field in topics if re.search(pattern, source)), None
        )
        answer = str((org.business_profile or {}).get(key, ""))[:1500] if key else ""
        if not answer:
            return
        answer = words["info"] + answer + "\n" + words["terms"]
    enqueue(db, message, "business_info", answer, "business-info:" + message.id)
    return True


def pending_query(organization_id):
    return (
        select(ExtractionDraft, WhatsAppMessage)
        .join(
            WhatsAppMessage, WhatsAppMessage.extraction_draft_id == ExtractionDraft.id
        )
        .where(
            ExtractionDraft.organization_id == organization_id,
            WhatsAppMessage.organization_id == organization_id,
            WhatsAppMessage.direction == "inbound",
            WhatsAppMessage.category.in_(["business_order", "business_inquiry"]),
            func.coalesce(ExtractionDraft.result["kind"].as_string(), "")
            != "service_request",
            func.coalesce(
                ExtractionDraft.result["order_review"]["status"].as_string(), "pending"
            )
            == "pending",
            ~select(Order.id)
            .where(
                Order.organization_id == organization_id,
                Order.draft_id == ExtractionDraft.id,
            )
            .exists(),
        )
    )


def pending_count(db, organization_id):
    return db.scalar(
        select(func.count()).select_from(pending_query(organization_id).subquery())
    )


@router.get("/api/inbox/order-requests")
def order_requests(
    tenant: Tenant = Depends(tenant_context), db: DBSession = Depends(get_db)
):
    rows = db.execute(
        pending_query(tenant.id).order_by(ExtractionDraft.created_at.desc()).limit(100)
    ).all()
    return [
        {
            "draft": {
                "id": draft.id,
                "source_text": draft.source_text,
                "result": draft.result,
            },
            "customer_name": message.customer_name,
            "customer_phone": message.customer_phone,
            "is_simulated": message.external_id.startswith("sim_"),
            "availability": availability(db, tenant.id, draft.result),
            "created_at": draft.created_at,
        }
        for draft, message in rows
    ]


@router.post("/api/inbox/order-requests/{draft_id}/reject")
def reject_request(
    draft_id: str,
    tenant: Tenant = Depends(tenant_context),
    db: DBSession = Depends(get_db),
):
    require(tenant, "owner", "admin")
    org = lock_org(db, tenant)
    draft = scoped(db, ExtractionDraft, tenant, draft_id)
    source = db.scalar(
        select(WhatsAppMessage).where(
            WhatsAppMessage.organization_id == tenant.id,
            WhatsAppMessage.extraction_draft_id == draft.id,
            WhatsAppMessage.direction == "inbound",
        )
    )
    if not source or draft.result.get("kind") == "service_request":
        raise HTTPException(404, "WhatsApp order request not found")
    if db.scalar(
        select(Order.id).where(
            Order.organization_id == tenant.id, Order.draft_id == draft.id
        )
    ):
        raise HTTPException(409, "An approved order cannot be rejected here")
    draft.result = {**draft.result, "order_review": {"status": "rejected"}}
    if bot_settings(org)["enabled"]:
        enqueue(
            db,
            source,
            "rejected",
            wording(source.text)["rejected"],
            "rejected:" + draft.id,
        )
    db.add(
        AuditEvent(
            organization_id=tenant.id,
            actor_id=tenant.user_id,
            action="whatsapp.order.rejected",
            entity_id=draft.id,
        )
    )
    db.commit()
    return {"status": "rejected"}


def queue_order_confirmation(db, org, order):
    if not order.draft_id or not bot_settings(org)["enabled"]:
        return
    source = db.scalar(
        select(WhatsAppMessage).where(
            WhatsAppMessage.organization_id == org.id,
            WhatsAppMessage.extraction_draft_id == order.draft_id,
            WhatsAppMessage.direction == "inbound",
        )
    )
    if source:
        enqueue(
            db,
            source,
            "confirmed",
            wording(source.text)["confirmed"].format(
                reference=order.id, amount=f"{order.total_minor / 100:,.2f}"
            ),
            "confirmed:" + order.id,
        )


@router.get("/api/inbox/chatbot-replies")
def reply_status(
    tenant: Tenant = Depends(tenant_context), db: DBSession = Depends(get_db)
):
    require(tenant, "owner", "admin")
    return [
        {
            "id": row.id,
            "kind": row.kind,
            "status": row.status,
            "last_error": row.last_error,
            "created_at": row.created_at,
        }
        for row in db.scalars(
            select(WhatsAppBotReply)
            .where(WhatsAppBotReply.organization_id == tenant.id)
            .order_by(WhatsAppBotReply.created_at.desc())
            .limit(20)
        )
    ]


@router.post("/api/inbox/chatbot-replies/{reply_id}/retry")
def retry_reply(
    reply_id: str,
    tenant: Tenant = Depends(tenant_context),
    db: DBSession = Depends(get_db),
):
    require(tenant, "owner", "admin")
    row = scoped(db, WhatsAppBotReply, tenant, reply_id)
    if row.status != "blocked":
        raise HTTPException(
            409, "Only a reply blocked before sending can be retried safely"
        )
    row.status = "queued"
    row.last_error = ""
    row.updated_at = now()
    db.commit()
    return {"status": "queued"}


def process_bot_replies_once():
    from .whatsapp import send_reply

    count = 0
    with SessionLocal() as db:
        org_ids = db.scalars(
            select(WhatsAppPhoneNumber.organization_id).distinct()
        ).all()
        for org_id in org_ids:

            def scope():
                if db.bind.dialect.name == "postgresql":
                    db.execute(
                        text("SELECT set_config('app.organization_id', :tenant, true)"),
                        {"tenant": org_id},
                    )

            scope()
            stale = list(
                db.scalars(
                    select(WhatsAppBotReply).where(
                        WhatsAppBotReply.organization_id == org_id,
                        WhatsAppBotReply.status == "sending",
                        WhatsAppBotReply.updated_at < now() - timedelta(minutes=5),
                    )
                )
            )
            for job in stale:
                existing = db.scalar(
                    select(WhatsAppMessage.id).where(
                        WhatsAppMessage.organization_id == org_id,
                        WhatsAppMessage.client_request_id == "bot:" + job.id,
                    )
                )
                job.status = "accepted" if existing else "unknown"
                job.last_error = (
                    ""
                    if existing
                    else "Delivery is unknown; inspect the conversation before sending another reply."
                )
                job.updated_at = now()
            db.commit()
            scope()
            ids = list(
                db.scalars(
                    select(WhatsAppBotReply.id)
                    .where(
                        WhatsAppBotReply.organization_id == org_id,
                        WhatsAppBotReply.status == "queued",
                    )
                    .order_by(WhatsAppBotReply.created_at)
                    .limit(20)
                )
            )
            for job_id in ids:
                scope()
                claimed = db.execute(
                    update(WhatsAppBotReply)
                    .where(
                        WhatsAppBotReply.organization_id == org_id,
                        WhatsAppBotReply.id == job_id,
                        WhatsAppBotReply.status == "queued",
                    )
                    .values(status="sending", updated_at=now())
                )
                if claimed.rowcount != 1:
                    db.rollback()
                    continue
                db.commit()
                scope()
                job = db.get(WhatsAppBotReply, job_id)
                org = db.get(Organization, org_id)
                source = db.get(WhatsAppMessage, job.source_message_id)
                if (
                    not bot_settings(org)["enabled"]
                    or (
                        job.kind == "business_info"
                        and not bot_settings(org)["answer_business_questions"]
                    )
                    or not subscription_access(org)
                    or source.category in {"personal", "spam"}
                ):
                    job.status = "cancelled"
                    job.updated_at = now()
                    db.commit()
                    continue
                phone = db.scalar(
                    select(WhatsAppPhoneNumber).where(
                        WhatsAppPhoneNumber.organization_id == org_id,
                        WhatsAppPhoneNumber.phone_number_id == source.phone_number_id,
                        WhatsAppPhoneNumber.active.is_(True),
                    )
                )
                if not phone:
                    job.status = "blocked"
                    job.last_error = "WhatsApp number is no longer connected"
                    db.commit()
                    continue
                membership = db.get(Membership, (phone.connected_by, org_id))
                if not membership or membership.role not in {"owner", "admin"}:
                    job.status = "blocked"
                    job.last_error = "Reconnect WhatsApp with an owner or admin account"
                    db.commit()
                    continue
                if job.kind == "confirmed":
                    order = db.scalar(
                        select(Order).where(
                            Order.organization_id == org_id,
                            Order.draft_id == source.extraction_draft_id,
                        )
                    )
                    if not order or order.status == "cancelled":
                        job.status = "cancelled"
                        job.updated_at = now()
                        db.commit()
                        continue
                if job.kind == "availability":
                    draft = (
                        db.get(ExtractionDraft, source.extraction_draft_id)
                        if source.extraction_draft_id
                        else None
                    )
                    confirmed = db.scalar(
                        select(Order.id).where(
                            Order.organization_id == org_id,
                            Order.draft_id == source.extraction_draft_id,
                        )
                    )
                    if (
                        not draft
                        or confirmed
                        or draft.result.get("order_review", {}).get("status")
                        == "rejected"
                        or source.category not in {"business_order", "business_inquiry"}
                    ):
                        job.status = "cancelled"
                        db.commit()
                        continue
                    job.body = availability_reply(
                        availability(db, org_id, draft.result), source.text
                    )
                # Persist sending before provider I/O. Unknown outcomes never auto-resend.
                try:
                    send_reply(
                        source.conversation_id,
                        WhatsAppReplyInput(
                            text=job.body, client_request_id="bot:" + job.id
                        ),
                        Tenant(org_id, phone.connected_by, membership.role),
                        db,
                    )
                    scope()
                    job = db.get(WhatsAppBotReply, job_id)
                    job.status = "accepted"
                    job.last_error = ""
                    count += 1
                except HTTPException as exc:
                    db.rollback()
                    scope()
                    job = db.get(WhatsAppBotReply, job_id)
                    job.status = (
                        "blocked"
                        if exc.status_code in {403, 409, 422, 503}
                        else "unknown"
                    )
                    job.last_error = (
                        str(exc.detail)[:240]
                        if job.status == "blocked"
                        else "Provider outcome needs review; automatic resend is disabled."
                    )
                except Exception:
                    db.rollback()
                    scope()
                    job = db.get(WhatsAppBotReply, job_id)
                    job.status = "unknown"
                    job.last_error = "Reply outcome needs manual review; automatic resend is disabled."
                job.updated_at = now()
                db.commit()
    return count
