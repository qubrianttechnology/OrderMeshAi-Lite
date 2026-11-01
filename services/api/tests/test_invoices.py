from datetime import datetime, timezone
from io import BytesIO
from types import SimpleNamespace

import pytest
from pypdf import PdfReader

from app.config import settings
from app.invoices import invoice_pdf


def sample_invoice(**changes):
    order = SimpleNamespace(
        id="sinhala-test",
        customer_name="කමල් පෙරේරා",
        customer_address="අංක 12, කොළඹ\nශ්‍රී ලංකාව",
        delivery_instructions="හෙට උදේ ගෙන එන්න",
        created_at=datetime(2026, 10, 28, tzinfo=timezone.utc),
        status="confirmed",
        total_minor=50000,
    )
    for key, value in changes.items():
        setattr(order, key, value)
    lines = [SimpleNamespace(product_name="සුදු සහල්", quantity=2, price_minor=25000)]
    return order, lines, SimpleNamespace(name="සිංහල වෙළඳසැල")


def test_bundled_sinhala_invoice_has_embedded_font_and_correct_total(monkeypatch):
    monkeypatch.setattr(settings, "invoice_font_path", "")
    pdf = invoice_pdf(*sample_invoice())
    reader = PdfReader(BytesIO(pdf))
    assert len(reader.pages) == 1
    text = reader.pages[0].extract_text()
    assert "500.00" in text
    assert "INVOICE" in text
    fonts = reader.pages[0]["/Resources"]["/Font"].get_object().values()
    assert any(
        "/FontFile2" in font.get_object().get("/FontDescriptor", {})
        for font in fonts
    )
    assert any("/ToUnicode" in font.get_object() for font in fonts)


def test_long_multiline_sinhala_invoice_wraps_across_pages(monkeypatch):
    monkeypatch.setattr(settings, "invoice_font_path", "")
    order, lines, org = sample_invoice()
    lines[0].product_name = "සුදු සහල් " * 12
    lines = lines * 35
    order.total_minor = 50000 * len(lines)
    reader = PdfReader(BytesIO(invoice_pdf(order, lines, org)))
    assert len(reader.pages) > 1
    assert "17,500.00" in reader.pages[-1].extract_text()


def test_delivery_instructions_are_checked_for_missing_glyphs(monkeypatch):
    monkeypatch.setattr(settings, "invoice_font_path", "")
    with pytest.raises(ValueError, match="does not support all characters"):
        invoice_pdf(*sample_invoice(delivery_instructions="Deliver \U0001f600"))


def test_invalid_custom_font_fails_explicitly(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "invoice_font_path", str(tmp_path / "missing.ttf"))
    with pytest.raises(ValueError, match="font is unavailable"):
        invoice_pdf(*sample_invoice())
