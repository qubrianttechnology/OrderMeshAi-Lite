"""Exercise only the explicitly isolated demo, with synthetic AI context."""

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/api"))
from app.ai_provider import OpenAIExtractor, ProviderUnavailable
from app.business import classify_message
from app.config import settings
from app.db import SessionLocal
from app.extraction import LocalExtractor
from app.models import Order, Organization, Product, WhatsAppPhoneNumber
from sqlalchemy import select


def main():
    info = json.loads((ROOT / ".local/demo-access.json").read_text(encoding="utf-8"))
    orgid = info["organization_id"]
    with SessionLocal() as db:
        org = db.get(Organization, orgid)
        assert (
            org.name == "OrderMesh Demo Wholesale"
            and org.business_profile.get("demo_workspace") == "true"
        )
        assert not db.scalar(
            select(WhatsAppPhoneNumber.id).where(
                WhatsAppPhoneNumber.organization_id == orgid
            )
        )
        # Correct the synthetic questionnaire field names without touching another workspace.
        profile = {
            **org.business_profile,
            "customers": "Retail shops and wholesale trade buyers. Synthetic demo only.",
            "workflow": "Review incoming orders, check stock and prices, owner approval, invoice, payment and delivery.",
            "personal_examples": "Happy birthday! Come home for family dinner.",
            "business_examples": "Please quote wholesale trade supplies.",
        }
        org.business_profile = profile
        db.commit()
        products = list(
            db.scalars(
                select(Product).where(
                    Product.organization_id == orgid, Product.active.is_(True)
                )
            )
        )
        catalog = {p.sku: p for p in products}
        already = (
            db.scalar(
                select(Order.id).where(
                    Order.organization_id == orgid,
                    Order.idempotency_key == "demo-readiness-sale-v1",
                )
            )
            is not None
        )
    result = {
        "workspace": org.name,
        "catalog_products": len(products),
        "synthetic_only": True,
        "whatsapp_connected": False,
        "checks": {},
        "local_extraction": [],
    }
    cases = [
        (
            "English",
            "Rice 1kg 2; Sugar 1kg 1; Milk Powder 1",
            [("DEMO-RICE", 2), ("DEMO-SUGAR", 1), ("DEMO-MILK", 1)],
        ),
        ("Sinhala", "කිරිපිටි 2", [("DEMO-MILK", 2)]),
        ("Tamil", "பால்மா 3", [("DEMO-MILK", 3)]),
        ("SKU search", "DEMO-3000 4", [("DEMO-3000", 4)]),
    ]
    for label, source, expected in cases:
        start = time.perf_counter()
        draft = LocalExtractor().extract(source, "auto", products)
        found = [
            (next((p.sku for p in products if p.id == x.product_id), None), x.quantity)
            for x in draft.items
        ]
        passed = found == expected and draft.requires_confirmation
        result["local_extraction"].append(
            {
                "language": label,
                "passed": passed,
                "elapsed_ms": round((time.perf_counter() - start) * 1000, 2),
                "provider": draft.provider,
                "requires_confirmation": draft.requires_confirmation,
            }
        )
        assert passed, (label, found)
    categories = [
        ("Rice 1kg 2", "business_order"),
        ("Happy birthday! Come home for family dinner.", "personal"),
        ("Claim your prize now", "spam"),
        ("Need refund for broken item", "support"),
    ]
    result["checks"]["message_filters"] = all(
        classify_message(s, products, profile)[0] == category
        for s, category in categories
    )
    assert result["checks"]["message_filters"]
    h = {"X-OrderMesh": "1", "X-Organization-ID": orgid}
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=45) as client:
        assert client.get("/api/health").status_code == 200
        assert (
            client.post(
                "/api/auth/login",
                json={"email": info["email"], "password": info["password"]},
                headers={"X-OrderMesh": "1"},
            ).status_code
            == 200
        )
        customer = client.get("/api/customers", headers=h).json()[0]
        items = [
            {"product_id": catalog[sku].id, "quantity": q}
            for sku, q in [("DEMO-RICE", 2), ("DEMO-SUGAR", 1), ("DEMO-MILK", 1)]
        ]
        quote = client.post(
            "/api/commerce/quote", headers=h, json={"items": items}
        ).json()
        assert quote["total_minor"] == 193000
        body = {
            "customer_id": customer["id"],
            "items": items,
            "human_confirmed": True,
            "expected_total_minor": 193000,
            "paid_minor": 193000,
            "payment_method": "cash",
        }
        before = client.get("/api/products?limit=500", headers=h).json()
        before_stock = {p["id"]: p["stock"] for p in before}
        sale = client.post(
            "/api/commerce/sales",
            headers={**h, "Idempotency-Key": "demo-readiness-sale-v1"},
            json=body,
        )
        assert sale.status_code == 201, sale.status_code
        oid = sale.json()["id"]
        replay = client.post(
            "/api/commerce/sales",
            headers={**h, "Idempotency-Key": "demo-readiness-sale-v1"},
            json=body,
        )
        assert replay.json()["id"] == oid
        # Read directly after pagination, ensuring catalog size does not hide the products checked.
        with SessionLocal() as db:
            for item in items:
                p = db.get(Product, item["product_id"])
                if not already and p.id in before_stock:
                    assert p.stock == before_stock[p.id] - item["quantity"]
        receipt = client.get(f"/api/commerce/orders/{oid}/receipt", headers=h)
        assert receipt.status_code == 200 and receipt.content.startswith(b"%PDF")
        (ROOT / ".local/demo-payment-record.pdf").write_bytes(receipt.content)
        day = datetime.now(ZoneInfo("Asia/Colombo")).date()
        report = client.get(f"/api/commerce/reports?start={day}&end={day}", headers=h)
        assert report.status_code == 200
        result["checks"].update(
            {
                "server_quote_1930_LKR": True,
                "sale_payment_and_stock": True,
                "repeat_save_no_second_stock_deduction": True,
                "payment_record_pdf": True,
                "financial_report": True,
            }
        )
        result["sale_id"] = oid
        result["financial_report"] = report.json()
        alert_product = catalog["DEMO-3000"]
        with SessionLocal() as db:
            quantity = db.get(Product, alert_product.id).stock
        if quantity > 5:
            changed = client.post(
                f"/api/products/{alert_product.id}/stock",
                headers=h,
                json={
                    "delta": 5 - quantity,
                    "reason": "Synthetic demo low-stock alert test",
                },
            )
            assert changed.status_code == 200
        feed = client.get("/api/notifications", headers=h).json()
        assert any(x["title"] == "Low stock" for x in feed["items"])
        result["checks"]["low_stock_notification"] = True
    result["live_model"] = {"tested": False, "reason": "OpenAI not configured"}
    if settings.ai_provider == "openai" and settings.openai_api_key.get_secret_value():
        # Only synthetic sample catalog entries and synthetic sentences are sent; no customer data.
        source = "Rice 1kg 2\nකිරිපිටි 1\nபால்மா 3"
        try:
            answer = OpenAIExtractor(
                settings.openai_api_key.get_secret_value(), settings.openai_model
            ).extract(source, "auto", products)
            found = [
                (
                    next((p.sku for p in products if p.id == x.product_id), None),
                    x.quantity,
                )
                for x in answer.items
            ]
            passed = sorted(found) == sorted(
                [("DEMO-RICE", 2), ("DEMO-MILK", 1), ("DEMO-MILK", 3)]
            )
            result["live_model"] = {
                "tested": True,
                "passed": passed,
                "model": settings.openai_model,
                "provider": answer.provider,
                "requires_confirmation": answer.requires_confirmation,
                "source": "synthetic English, Sinhala and Tamil order only",
            }
        except ProviderUnavailable:
            result["live_model"] = {
                "tested": True,
                "passed": False,
                "reason": "Provider unavailable or response failed validation; no provider error body stored.",
            }
    result["completed_at"] = datetime.now(ZoneInfo("Asia/Colombo")).isoformat()
    (ROOT / ".local/demo-readiness-results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
