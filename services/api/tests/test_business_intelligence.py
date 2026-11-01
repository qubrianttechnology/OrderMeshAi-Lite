import io
from types import SimpleNamespace

from reportlab.pdfgen.canvas import Canvas
from sqlalchemy import func, select

from app.business import classify_message, document_suggestions
from app.models import ExtractionDraft, WhatsAppMessage

from .conftest import catalog, register
from .test_business_billing import profile_data
from .test_whatsapp import connect_phone


def test_business_intelligence_examples_are_tenant_scoped_and_preview_is_read_only(
    setup,
):
    client, factory = setup
    first = register(client)
    data = {
        **profile_data(),
        "business_examples": "Can you redesign our portal?",
        "personal_examples": "Bring the album tonight",
        "spam_examples": "Unwanted galaxy investment offer",
        "review_triggers": "urgent legal dispute",
    }
    assert client.put("/api/business-profile", json=data).status_code == 200
    for source, category in [
        ("Can you redesign our portal?", "business_inquiry"),
        (" Bring  the album tonight ", "personal"),
        ("Unwanted galaxy investment offer", "spam"),
        ("Please help with an urgent legal dispute", "needs_review"),
    ]:
        result = client.post(
            "/api/business-profile/classify-preview", json={"text": source}
        )
        assert result.status_code == 200
        assert result.json()["category"] == category
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(ExtractionDraft)) == 0
        assert db.scalar(select(func.count()).select_from(WhatsAppMessage)) == 0
    register(client, "other-intelligence")
    assert (
        client.post(
            "/api/business-profile/classify-preview",
            json={"text": "Bring the album tonight"},
        ).json()["category"]
        == "needs_review"
    )
    assert (
        client.post(
            "/api/business-profile/classify-preview",
            headers={"X-Organization-ID": first["organization_id"]},
            json={"text": "hello"},
        ).status_code
        == 403
    )


def test_personal_examples_block_catalog_order_drafts_in_the_real_worker_path(setup):
    client, _ = setup
    register(client)
    catalog(client)
    assert (
        client.put(
            "/api/business-profile",
            json={**profile_data("retail"), "personal_examples": "Rice 2"},
        ).status_code
        == 200
    )
    connect_phone(client)
    result = client.post(
        "/api/inbox/simulator",
        json={
            "phone_number_id": "123456789012345",
            "customer_phone": "+94770001122",
            "text": "Rice 2",
        },
    )
    assert result.status_code == 201
    conversation = client.get("/api/inbox/conversations").json()[0]
    message = client.get(
        "/api/inbox/conversations/" + conversation["id"] + "/messages"
    ).json()[0]
    assert message["category"] == "personal"
    assert message["extraction_draft_id"] is None


def test_mixed_messages_conflicting_examples_and_dangerous_whitelists_are_reviewed():
    products = [SimpleNamespace(name="Rice", sku="RICE", aliases=[])]
    assert (
        classify_message("Rice 2 - happy birthday", products, {})[0] == "needs_review"
    )
    assert (
        classify_message(
            "same message",
            [],
            {"business_examples": "same message", "spam_examples": "same message"},
        )[0]
        == "needs_review"
    )
    assert (
        classify_message("send your otp", [], {"business_examples": "send your otp"})[0]
        == "spam"
    )


def test_pdf_sections_offer_reviewable_fields_without_promoting_negative_keywords(
    setup,
):
    client, _ = setup
    register(client)
    output = io.BytesIO()
    canvas = Canvas(output)
    for index, line in enumerate(
        [
            "Description: We sell fresh bakery products to local shops.",
            "Offerings: Bread and cakes",
            "Customers: Cafes and grocery shops",
            "Business examples:",
            "Could you bake a custom cake?",
            "Personal examples:",
            "Meet at the park tonight",
            "Spam examples:",
            "Cryptogalaxy promotional offer",
        ]
    ):
        canvas.drawString(40, 800 - index * 24, line)
    canvas.save()
    response = client.post(
        "/api/business-profile/document",
        content=output.getvalue(),
        headers={"X-Filename": "bakery.pdf", "Content-Type": "application/pdf"},
    )
    assert response.status_code == 200
    value = response.json()
    assert value["document_suggestions"]["customers"] == "Cafes and grocery shops"
    assert (
        value["document_suggestions"]["spam_examples"]
        == "Cryptogalaxy promotional offer"
    )
    assert not value["profile"].get(
        "spam_examples"
    )  # Saving the profile applies suggestions.
    assert (
        client.post(
            "/api/business-profile/classify-preview", json={"text": "Cryptogalaxy"}
        ).json()["category"]
        == "needs_review"
    )
    saved = client.put(
        "/api/business-profile",
        json={**profile_data("retail"), **value["document_suggestions"]},
    )
    assert saved.status_code == 200
    assert (
        client.post(
            "/api/business-profile/classify-preview",
            json={"text": "Meet at the park tonight"},
        ).json()["category"]
        == "personal"
    )


def test_suggestions_bound_optional_fields_and_preserve_multiline_examples():
    suggested = document_suggestions(
        "Required details: "
        + "x" * 2000
        + "\nPersonal examples:\nhello friend\ncome for dinner"
    )
    assert len(suggested["required_details"]) == 1500
    assert suggested["personal_examples"] == "hello friend\ncome for dinner"
