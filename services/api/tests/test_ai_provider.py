import json
from types import SimpleNamespace

import httpx
import pytest

from app.ai_provider import FallbackExtractor, OpenAIExtractor, ProviderUnavailable
from app.extraction import LocalExtractor

catalog = [
    SimpleNamespace(id="rice", name="Rice", sku="RICE", unit="bags", aliases=["හාල්"])
]


def provider_response(item):
    return {
        "status": "completed",
        "output": [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": json.dumps(
                            {
                                "language": "en",
                                "items": [item],
                                "flags": [],
                                "delivery_instructions": None,
                            }
                        ),
                    }
                ],
            }
        ],
    }


def test_structured_request_and_foreign_ids_are_revalidated():
    def handler(request):
        body = json.loads(request.content)
        assert request.headers["Authorization"] == "Bearer test-key"
        assert body["store"] is False
        assert body["text"]["format"]["strict"] is True
        assert body["text"]["format"]["schema"]["additionalProperties"] is False
        assert "password" not in body["input"]
        return httpx.Response(
            200,
            json=provider_response(
                {
                    "source": "Rice 2",
                    "product_id": "other-tenant-product",
                    "product_name": "Fake",
                    "quantity": 2,
                    "unit": None,
                    "confidence": 0.99,
                    "flags": [],
                }
            ),
        )

    result = OpenAIExtractor(
        "test-key", "configured-model", httpx.MockTransport(handler)
    ).extract("Rice 2", "auto", catalog)
    assert result.items[0].product_id is None and result.items[0].confidence == 0
    assert result.requires_confirmation


@pytest.mark.parametrize(
    "response",
    [
        {"status": "incomplete", "output": []},
        {
            "status": "completed",
            "output": [{"content": [{"type": "refusal", "refusal": "No"}]}],
        },
        provider_response(
            {
                "source": "Rice 2",
                "product_id": "rice",
                "product_name": "Rice",
                "quantity": 2,
                "unit": None,
                "confidence": 2,
                "flags": [],
            }
        ),
    ],
)
def test_invalid_refused_incomplete_model_output_fails_closed(response):
    extractor = OpenAIExtractor(
        "test-key",
        "configured-model",
        httpx.MockTransport(lambda _: httpx.Response(200, json=response)),
    )
    with pytest.raises(ProviderUnavailable):
        extractor.extract("Rice 2", "auto", catalog)


def test_provider_http_failure_has_safe_message():
    api_key = "fake-openai-test-key"
    extractor = OpenAIExtractor(
        api_key,
        "configured-model",
        httpx.MockTransport(
            lambda request: (
                httpx.Response(
                    401,
                    json={
                        "error": {
                            "message": "private provider details",
                            "credential": api_key,
                        }
                    },
                )
                if request.headers["Authorization"] == f"Bearer {api_key}"
                else httpx.Response(401)
            )
        ),
    )
    with pytest.raises(ProviderUnavailable) as exc:
        extractor.extract("Rice 2", "auto", catalog)
    assert "private provider details" not in str(exc.value)
    assert api_key not in str(exc.value)


def test_missing_openai_key_fails_without_request_and_uses_local_fallback():
    called = False

    def handler(_request):
        nonlocal called
        called = True
        raise AssertionError("A missing credential must not initiate a request")

    unconfigured = OpenAIExtractor("", "configured-model", httpx.MockTransport(handler))
    with pytest.raises(ProviderUnavailable) as error:
        unconfigured.extract("Rice 2", "auto", catalog)
    assert "OPENAI_API_KEY" in str(error.value)
    assert not called

    result = FallbackExtractor(unconfigured, LocalExtractor()).extract(
        "Rice 2", "auto", catalog
    )
    assert result.items[0].product_id == "rice"
    assert "ai_provider_fallback" in result.flags


def test_grounded_delivery_details_and_fallback_draft():
    source = "Rice 2 bags, deliver to Borella"

    def handler(_):
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [
                    {
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(
                                    {
                                        "language": "en",
                                        "items": [
                                            {
                                                "source": "Rice 2 bags",
                                                "product_id": "rice",
                                                "product_name": "Rice",
                                                "quantity": 2,
                                                "unit": "bags",
                                                "confidence": 0.8,
                                                "flags": [],
                                            }
                                        ],
                                        "flags": [],
                                        "delivery_instructions": "deliver to Borella",
                                    }
                                ),
                            }
                        ]
                    }
                ],
            },
        )

    result = OpenAIExtractor(
        "test-key",
        "configured-model",
        httpx.MockTransport(handler),
    ).extract(source, "auto", catalog)
    assert result.items[0].unit == "bags"
    assert result.delivery_instructions == "deliver to Borella"

    class FailingExtractor:
        def extract(self, *_args):
            raise ProviderUnavailable("safe provider failure")

    # A provider failure must remain a reviewable local draft, never an order.
    fallback = FallbackExtractor(FailingExtractor(), LocalExtractor())
    fallback_result = fallback.extract("Rice 2", "auto", catalog)
    assert fallback_result.items[0].product_id == "rice"
    assert fallback_result.requires_confirmation
    assert "ai_provider_fallback" in fallback_result.flags
