"""Local-only business documents and conservative message routing.

Business profile documents are never sent to an external provider by this module.
"""

import io
import re
import unicodedata
import zipfile
from typing import Literal
from urllib.parse import unquote
from xml.etree import ElementTree

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import Field
from pypdf import PdfReader
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DBSession

from .db import get_db
from .models import (
    AuditEvent,
    ExtractionDraft,
    Organization,
    WhatsAppMessage,
    WhatsAppWebhookEvent,
    now,
)
from .schemas import ProductCategory, StrictModel
from .security import Tenant, lock_org, require, scoped, tenant_context

router = APIRouter()
SERVICE_TYPES = {"services", "software", "agency", "salon", "repair"}
BUSINESS_TYPES = Literal[
    "retail",
    "wholesale",
    "services",
    "software",
    "agency",
    "hybrid",
    "online_store",
    "restaurant",
    "salon",
    "repair",
]
CATEGORIES = Literal[
    "business_order", "business_inquiry", "support", "personal", "spam", "needs_review"
]


class BusinessProfileInput(StrictModel):
    primary_category: ProductCategory = "other"
    business_type: BUSINESS_TYPES
    description: str = Field(min_length=20, max_length=3000)
    offerings: str = Field(min_length=3, max_length=3000)
    customers: str = Field(min_length=3, max_length=1500)
    workflow: str = Field(min_length=10, max_length=3000)
    hours: str = Field(min_length=3, max_length=500)
    payments: str = Field(min_length=3, max_length=1500)
    delivery: str = Field(min_length=3, max_length=1500)
    exclusions: str = Field(default="", max_length=1500)
    business_examples: str = Field(default="", max_length=3000)
    personal_examples: str = Field(default="", max_length=3000)
    spam_examples: str = Field(default="", max_length=3000)
    service_area: str = Field(default="", max_length=1500)
    required_details: str = Field(default="", max_length=1500)
    review_triggers: str = Field(default="", max_length=1500)


DASHBOARD_MODULES = Literal["orders", "service_requests", "customers", "catalog"]


class DashboardInput(StrictModel):
    layout: Literal["recommended", "full"] = "recommended"
    modules: list[DASHBOARD_MODULES] | None = Field(default=None, max_length=4)


def dashboard_view(org):
    service = org.business_type in SERVICE_TYPES
    defaults = (
        ["service_requests", "customers", "catalog"]
        if service
        else ["orders", "service_requests", "customers", "catalog"]
        if org.business_type == "hybrid"
        else ["orders", "customers", "catalog"]
    )
    saved = (org.business_profile or {}).get("dashboard", {})
    full = isinstance(saved, dict) and saved.get("layout") == "full"
    if full:
        defaults = ["orders", "service_requests", "customers", "catalog"]
    custom = saved.get("modules") if isinstance(saved, dict) else None
    modules = defaults if custom is None else list(dict.fromkeys(custom))
    return {
        "modules": modules,
        "layout": "full" if full else "recommended",
        "full_business_tools": full,
        "customized": custom is not None,
        "service_business": service,
        "customer_label": "Clients"
        if org.business_type in {"agency", "software"}
        else "Customers",
        "catalog_label": "Menu"
        if org.business_type == "restaurant"
        else "Services"
        if service
        else "Inventory",
        "request_label": "Project requests"
        if org.business_type in {"agency", "software"}
        else "Repair requests"
        if org.business_type == "repair"
        else "Service requests",
    }


@router.get("/api/dashboard-preferences")
def get_dashboard(
    tenant: Tenant = Depends(tenant_context), db: DBSession = Depends(get_db)
):
    return dashboard_view(db.get(Organization, tenant.id))


@router.put("/api/dashboard-preferences")
def save_dashboard(
    body: DashboardInput,
    tenant: Tenant = Depends(tenant_context),
    db: DBSession = Depends(get_db),
):
    require(tenant, "owner", "admin")
    org = lock_org(db, tenant)
    org.business_profile = {
        **(org.business_profile or {}),
        "dashboard": body.model_dump(),
    }
    db.add(
        AuditEvent(
            organization_id=tenant.id,
            actor_id=tenant.user_id,
            action="dashboard.updated",
            entity_id=tenant.id,
        )
    )
    db.commit()
    return dashboard_view(org)


@router.get("/api/dashboard-service-summary")
def service_summary(
    tenant: Tenant = Depends(tenant_context), db: DBSession = Depends(get_db)
):
    status = ExtractionDraft.result["review"]["status"].as_string()
    rows = db.execute(
        select(status, func.count())
        .where(
            ExtractionDraft.organization_id == tenant.id,
            ExtractionDraft.result["kind"].as_string() == "service_request",
        )
        .group_by(status)
    ).all()
    counts = {key or "pending_review": count for key, count in rows}
    return {
        "total": sum(counts.values()),
        "pending_review": counts.get("pending_review", 0),
        "accepted": counts.get("accepted", 0),
        "completed": counts.get("completed", 0),
    }


class CategoryInput(StrictModel):
    category: CATEGORIES


DOCUMENT_FIELDS = {
    "description": "description",
    "what we do": "description",
    "offerings": "offerings",
    "products and services": "offerings",
    "customers": "customers",
    "target clients": "customers",
    "workflow": "workflow",
    "hours": "hours",
    "payments": "payments",
    "delivery": "delivery",
    "exclusions": "exclusions",
    "business examples": "business_examples",
    "personal examples": "personal_examples",
    "spam examples": "spam_examples",
    "service area": "service_area",
    "required details": "required_details",
    "review triggers": "review_triggers",
}


def document_suggestions(content):
    suggestions = {}
    current = None
    for line in content.splitlines():
        heading, separator, value = line.partition(":")
        key = DOCUMENT_FIELDS.get(heading.strip().casefold()) if separator else None
        if key:
            current = key
            suggestions.setdefault(key, [])
            if value.strip():
                suggestions[key].append(value.strip())
        elif current and line.strip():
            suggestions[current].append(line.strip())
    limits = {
        "customers": 1500,
        "hours": 500,
        "payments": 1500,
        "delivery": 1500,
        "exclusions": 1500,
        "service_area": 1500,
        "required_details": 1500,
        "review_triggers": 1500,
    }
    return {
        key: "\n".join(lines)[: limits.get(key, 3000)]
        for key, lines in suggestions.items()
        if lines
    }


def profile_view(org):
    profile = org.business_profile or {}
    return {
        "business_type": org.business_type,
        "profile": profile,
        "document_suggestions": document_suggestions(profile.get("document_text", "")),
        "ready": all(
            profile.get(k)
            for k in (
                "description",
                "offerings",
                "customers",
                "workflow",
                "hours",
                "payments",
                "delivery",
            )
        ),
        "tracks_stock_by_default": org.business_type not in SERVICE_TYPES,
    }


@router.get("/api/business-profile")
def get_profile(
    tenant: Tenant = Depends(tenant_context), db: DBSession = Depends(get_db)
):
    return profile_view(db.get(Organization, tenant.id))


@router.put("/api/business-profile")
def save_profile(
    body: BusinessProfileInput,
    tenant: Tenant = Depends(tenant_context),
    db: DBSession = Depends(get_db),
):
    require(tenant, "owner", "admin")
    org = lock_org(db, tenant)
    previous = org.business_profile or {}
    org.business_type = body.business_type
    org.business_profile = {**previous, **body.model_dump(exclude={"business_type"})}
    db.add(
        AuditEvent(
            organization_id=tenant.id,
            actor_id=tenant.user_id,
            action="business_profile.updated",
            entity_id=tenant.id,
        )
    )
    db.commit()
    return profile_view(org)


@router.get("/api/business-profile/document-template")
def document_template(tenant: Tenant = Depends(tenant_context)):
    return {
        "text": """BUSINESS INTELLIGENCE - ORDERMESH
Description: Explain what your business does.
Offerings: List products/services, aliases and pricing.
Customers: Describe your target clients and their typical needs.
Workflow: Explain inquiry, review, quotation, approval and delivery.
Hours: Opening hours and response times.
Payments: Methods, deposits, cancellation and refund policies.
Delivery: Areas covered or project/service delivery process.
Service area: Regions served or remote service coverage.
Required details: Information your team asks before confirming an order or service.
Review triggers: Topics needing human review, separated by commas.
Exclusions: Unrelated topics, separated by commas.
Business examples:
Paste genuine client messages here, one per line.
Personal examples:
Paste private/unrelated messages here, one per line.
Spam examples:
Paste unwanted promotion/scam messages here, one per line.

Remove these instructions and fill in real details before uploading.
Never include passwords, tokens or private client documents.
"""
    }


@router.post("/api/business-profile/document")
async def upload_document(
    request: Request,
    x_filename: str = Header(...),
    tenant: Tenant = Depends(tenant_context),
    db: DBSession = Depends(get_db),
):
    require(tenant, "owner", "admin")
    filename = unquote(x_filename).replace("\\", "/").split("/")[-1][:160]
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > 2_000_000:
            raise HTTPException(413, "Document must be smaller than 2 MB")
    try:
        if filename.lower().endswith((".txt", ".md")):
            content = bytes(data).decode("utf-8-sig")
        elif filename.lower().endswith(".pdf"):
            reader = PdfReader(io.BytesIO(data), strict=True)
            if reader.is_encrypted or len(reader.pages) > 20:
                raise ValueError("Unsupported PDF")
            content = "\n".join(
                (page.extract_text() or "")[:10000] for page in reader.pages
            )
        elif filename.lower().endswith(".docx"):
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                member = archive.getinfo("word/document.xml")
                if member.file_size > 2_000_000:
                    raise ValueError("Expanded document is too large")
                root = ElementTree.fromstring(archive.read(member))
                content = "\n".join(
                    "".join(paragraph.itertext())
                    for paragraph in root.findall(
                        ".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"
                    )
                )
        else:
            raise HTTPException(
                415, "Upload a TXT, Markdown, text PDF or DOCX document"
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            422,
            "Could not read this document. Use a text PDF, DOCX or UTF-8 text file.",
        ) from exc
    content = content.strip()
    if len(content) < 20 or len(content) > 30000:
        raise HTTPException(
            422,
            "Document must contain 20-30,000 text characters; scanned PDFs need text/OCR first",
        )
    org = lock_org(db, tenant)
    org.business_profile = {
        **(org.business_profile or {}),
        "document_name": filename,
        "document_text": content,
    }
    db.add(
        AuditEvent(
            organization_id=tenant.id,
            actor_id=tenant.user_id,
            action="business_document.uploaded",
            entity_id=tenant.id,
        )
    )
    db.commit()
    return profile_view(org)


class ClassificationPreview(StrictModel):
    text: str = Field(min_length=1, max_length=10000)


@router.post("/api/business-profile/classify-preview")
def preview_classification(
    body: ClassificationPreview,
    tenant: Tenant = Depends(tenant_context),
    db: DBSession = Depends(get_db),
):
    org = db.get(Organization, tenant.id)
    from .models import Product

    products = list(
        db.scalars(
            select(Product).where(
                Product.organization_id == tenant.id, Product.active.is_(True)
            )
        )
    )
    category, reason = classify_message(body.text, products, org.business_profile or {})
    return {"category": category, "reason": reason, "preview": True}


def example_category(source, profile):
    def normalized(value):
        return " ".join(unicodedata.normalize("NFC", value).casefold().split())

    text = normalized(source)
    categories = {
        category
        for key, category in (
            ("business_examples", "business_inquiry"),
            ("personal_examples", "personal"),
            ("spam_examples", "spam"),
        )
        if any(
            normalized(line) == text
            for line in profile.get(key, "").splitlines()
            if line.strip()
        )
    }
    if len(categories) > 1:
        return "needs_review"
    return next(iter(categories), None)


def classify_message(source, products, profile):
    """Local context matching. Never discard messages or send documents externally."""
    text = unicodedata.normalize("NFC", source).casefold()
    if re.search(
        r"\b(lottery winner|claim your prize|guaranteed crypto|verify your otp|send.*otp)\b|உங்கள் பரிசை|otp அனுப்பு|otp යවන්න",
        text,
    ):
        return (
            "spam",
            "Possible unsolicited promotion or credential request; retained for review",
        )
    example = example_category(source, profile)
    if example in {"personal", "spam", "needs_review"}:
        return (
            example,
            "Matches saved business intelligence examples; retained for review",
        )
    triggers = [
        item.strip().casefold()
        for item in profile.get("review_triggers", "").split(",")
        if item.strip()
    ]
    if any(
        re.search(r"(?<!\w)" + re.escape(item) + r"(?!\w)", text) for item in triggers
    ):
        return (
            "needs_review",
            "Matches a business intelligence topic requiring human review",
        )
    if re.search(
        r"புகார்|பணத்தைத் திரும்ப|வேலை செய்யவில்லை|ரத்து|ආපසු|පැමිණිලි|\b(refund|complaint|broken|not working|cancel my|support|bug report)\b",
        text,
    ):
        return "support", "Customer support or cancellation request"
    matches = [
        p
        for p in products
        if any(
            alias
            and unicodedata.normalize("NFC", alias).casefold() in text
            and re.search(
                r"(?<![\w\u0b80-\u0bff\u0d80-\u0dff])"
                + re.escape(unicodedata.normalize("NFC", alias).casefold())
                + r"(?![\w\u0b80-\u0bff\u0d80-\u0dff])",
                text,
            )
            for alias in [p.name, p.sku, *p.aliases]
        )
    ]
    personal_hint = re.search(
        r"பிறந்தநாள்|வீட்டுக்கு வா|பிறந்த நாள்|සුභ උපන්දිනයක්|ගෙදර එන්න|\b(happy birthday|family dinner|come home|love you)\b",
        text,
    )
    if matches and personal_hint:
        return (
            "needs_review",
            "Mixed personal and catalog context; review before extracting an order",
        )
    if matches:
        if re.search(
            r"விலை|எவ்வளவு|இருக்கிறதா|මිල|කීයද|\b(price|cost|available|quote|how much|yesterday|already|paid)\b",
            text,
        ):
            return (
                "business_inquiry",
                "Catalog-related question or existing-order discussion",
            )
        if re.search(r"\d", text):
            return (
                "business_order",
                "Catalog item and quantity detected; human confirmation required",
            )
        return "business_inquiry", "Related to this business catalog"
    if re.search(
        r"பிறந்தநாள்|வீட்டுக்கு வா|பிறந்த நாள்|සුභ උපන්දිනයක්|ගෙදර එන්න|\b(happy birthday|family dinner|come home|love you)\b",
        text,
    ):
        return "personal", "Likely personal message; kept in the inbox"
    if example == "business_inquiry":
        return example, "Matches a saved genuine client example; human review required"
    exclusions = [
        word.strip().casefold()
        for word in profile.get("exclusions", "").split(",")
        if len(word.strip()) >= 4
    ]
    if any(word in text for word in exclusions):
        return (
            "needs_review",
            "Matches the workspace's excluded topics; review manually",
        )
    # Only approved profile fields or positive document sections inform relevance.
    # Negative example sections must never teach the business keyword matcher.
    suggested = document_suggestions(profile.get("document_text", ""))
    document_context = (
        " ".join(
            suggested.get(k, "") for k in ("description", "offerings", "customers")
        )
        if suggested
        else profile.get("document_text", "")
    )
    context = (
        " ".join(
            str(profile.get(k, "")) for k in ("description", "offerings", "customers")
        )
        + " "
        + document_context
    )
    keywords = {
        w
        for w in re.findall(r"[\w\u0b80-\u0bff\u0d80-\u0dff]{4,}", context.casefold())
        if w
        not in {
            "business",
            "customer",
            "customers",
            "about",
            "with",
            "from",
            "your",
            "this",
            "that",
            "have",
            "will",
            "name",
            "contact",
            "details",
            "payment",
            "payments",
            "workflow",
        }
    }
    # Match common English singular/plural offering words without broad substring matches.
    keywords |= {word[:-1] for word in keywords if len(word) > 5 and word.endswith("s")}
    if any(re.search(r"(?<!\w)" + re.escape(w) + r"(?!\w)", text) for w in keywords):
        return "business_inquiry", "Matches the business profile; review the inquiry"
    return (
        "needs_review",
        "No confident business match; a team member should classify this message",
    )


@router.put("/api/inbox/messages/{message_id}/category")
def review_category(
    message_id: str,
    body: CategoryInput,
    tenant: Tenant = Depends(tenant_context),
    db: DBSession = Depends(get_db),
):
    require(tenant, "owner", "admin", "staff")
    message = scoped(db, WhatsAppMessage, tenant, message_id)
    message.category = body.category
    message.category_reason = "Reviewed by a team member"
    message.category_reviewed = True
    message.updated_at = now()
    if (
        body.category in {"business_order", "business_inquiry", "support"}
        and not message.extraction_draft_id
    ):
        event = db.scalar(
            select(WhatsAppWebhookEvent).where(
                WhatsAppWebhookEvent.organization_id == tenant.id,
                WhatsAppWebhookEvent.message_id == message.id,
            )
        )
        if event and event.status != "processing":
            event.status = "queued"
            event.attempts = 0
            event.claimed_at = None
    db.add(
        AuditEvent(
            organization_id=tenant.id,
            actor_id=tenant.user_id,
            action="message.classified",
            entity_id=message.id,
        )
    )
    db.commit()
    return {"category": message.category, "category_reason": message.category_reason}
