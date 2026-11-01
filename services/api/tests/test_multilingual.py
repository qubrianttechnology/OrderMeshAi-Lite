import io
from types import SimpleNamespace

import httpx
from pypdf import PdfReader

from app.ai_provider import OpenAIExtractor
from app.business import classify_message
from app.config import settings
from app.extraction import LocalExtractor, detect_language
from app.invoices import invoice_pdf
from app.service_requests import local_fields

from .test_ai_provider import provider_response
from .test_invoices import sample_invoice


def tamil_catalog():
    return [
        SimpleNamespace(
            id="rice", name="Rice", sku="RICE", unit="bag", aliases=["அரிசி", "සහල්"]
        )
    ]


def test_tamil_and_mixed_messages_require_review_and_respect_alias_boundaries():
    products = tamil_catalog()
    result = LocalExtractor().extract("அரிசி ௨", "ta", products)
    assert result.language == "ta"
    assert result.requires_confirmation
    assert result.items[0].product_id == "rice"
    assert result.items[0].quantity == 2
    assert detect_language("அரிசி and සහල්") == "mixed"
    assert (
        LocalExtractor().extract("அரிசிகள் 2", "ta", products).items[0].product_id
        is None
    )
    assert classify_message("அரிசி 2", products, {})[0] == "business_order"
    assert classify_message("அரிசி விலை எவ்வளவு?", products, {})[0] == "business_inquiry"
    assert classify_message("பிறந்தநாள் வாழ்த்துக்கள்", products, {})[0] == "personal"


def test_tamil_structured_model_retains_source_and_catalog_validation():
    def handler(request):
        assert "Tamil" in request.content.decode()
        response = provider_response(
            {
                "source": "அரிசி 2",
                "product_id": "rice",
                "product_name": "அரிசி",
                "quantity": 2,
                "unit": None,
                "confidence": 0.8,
                "flags": [],
            }
        )
        return httpx.Response(200, json=response)

    result = OpenAIExtractor(
        "test-key", "test-model", httpx.MockTransport(handler)
    ).extract("அரிசி 2", "ta", tamil_catalog())
    assert result.language == "ta"
    assert result.items[0].product_name == "Rice"
    assert result.requires_confirmation


def test_tamil_service_fields_remain_verbatim():
    fields = local_fields(
        "இணையதளம் வேண்டும்; பட்ஜெட் LKR 50000; காலக்கெடு நவம்பர் 30; சந்திப்பு வெள்ளி 2pm"
    )
    assert fields.budget == "பட்ஜெட் LKR 50000"
    assert fields.deadline == "காலக்கெடு நவம்பர் 30"
    assert fields.appointment == "சந்திப்பு வெள்ளி 2pm"
    assert fields.request_type == "project"


def test_mixed_language_invoice_embeds_both_script_fonts(monkeypatch):
    monkeypatch.setattr(settings, "invoice_font_path", "")
    order, lines, org = sample_invoice(
        customer_name="குமார் / කමල්", customer_address="கொழும்பு / කොළඹ"
    )
    lines[0].product_name = "அரிசி / සහල් / Rice"
    pdf = invoice_pdf(order, lines, org)
    reader = PdfReader(io.BytesIO(pdf))
    embedded = [
        font.get_object()
        for font in reader.pages[0]["/Resources"]["/Font"].get_object().values()
        if "/FontFile2" in font.get_object().get("/FontDescriptor", {})
    ]
    assert len(embedded) >= 2
    assert "500.00" in reader.pages[0].extract_text()
