from types import SimpleNamespace

import pytest

from app.extraction import LocalExtractor, voice, whatsapp

catalog = [
    SimpleNamespace(id="rice", name="Rice", sku="RICE-1", aliases=["හාල්"]),
    SimpleNamespace(id="sugar", name="Sugar", sku="SUGAR-1", aliases=["සීනි"]),
]


@pytest.mark.parametrize(
    "source,product,quantity",
    [
        ("Rice 12", "rice", 12),
        ("හාල් 5", "rice", 5),
        ("සීනි 8", "sugar", 8),
        ("2 x Sugar", "sugar", 2),
        ("Rice -2", "rice", None),
        ("Rice 1.5", "rice", None),
        ("Rice 2 3", "rice", None),
        ("unknown 4", None, 4),
        ("Rice Sugar 2", None, 2),
    ],
)
def test_conservative_parser(source, product, quantity):
    result = LocalExtractor().extract(source, "auto", catalog)
    assert result.requires_confirmation
    assert result.items[0].product_id == product
    assert result.items[0].quantity == quantity
    assert result.items[0].flags


def test_unsupported_adapters_fail_explicitly():
    with pytest.raises(NotImplementedError):
        voice.process(b"audio")
    with pytest.raises(NotImplementedError):
        whatsapp.process({})
