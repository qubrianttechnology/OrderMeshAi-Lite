"""Conservative local baseline. No external model or language service is implied."""

import re
import unicodedata
from typing import Protocol

from .schemas import ExtractedLine, ExtractionResult


class TextExtractor(Protocol):
    def extract(self, text: str, language: str, products: list) -> ExtractionResult: ...


class UnsupportedAdapter:
    def __init__(self, name: str):
        self.name = name

    def process(self, *_args, **_kwargs):
        raise NotImplementedError(
            f"{self.name} is not configured or supported in Phase 1"
        )


voice = UnsupportedAdapter("Voice transcription")
whatsapp = UnsupportedAdapter("Official WhatsApp Business API")


def normalize(value):
    return unicodedata.normalize("NFC", value).casefold().strip()


def detect_language(text, requested="auto"):
    languages = []
    if re.search(r"[\u0b80-\u0bff]", text):
        languages.append("ta")
    if re.search(r"[\u0d80-\u0dff]", text):
        languages.append("si")
    if re.search(r"[a-zA-Z]{2,}", text):
        languages.append("en")
    if len(languages) > 1:
        return "mixed"
    return languages[0] if languages else requested if requested != "auto" else "en"


class LocalExtractor:
    def extract(self, text, language, products):
        detected = detect_language(text, language)
        items = []
        for source in filter(str.strip, re.split(r"[\n;]+", text)):
            source = source.strip()
            normalized = normalize(source)
            matches = []
            for product in products:
                for alias in [product.name, product.sku, *product.aliases]:
                    alias = normalize(alias)
                    if (
                        alias
                        and alias in normalized
                        and re.search(
                            r"(?<![\w\u0b80-\u0bff\u0d80-\u0dff])"
                            + re.escape(alias)
                            + r"(?![\w\u0b80-\u0bff\u0d80-\u0dff])",
                            normalized,
                        )
                    ):
                        matches.append((product, alias))
                        break
            flags = []
            product = matches[0][0] if len(matches) == 1 else None
            remainder = normalized
            if product:
                remainder = re.sub(re.escape(matches[0][1]), "", remainder, count=1)
            else:
                flags.append("ambiguous_product" if matches else "unknown_product")
            numbers = re.findall(r"(?<![\w.])[-+]?\d+(?:\.\d+)?(?![\w.])", remainder)
            quantity = (
                int(numbers[0])
                if len(numbers) == 1 and re.fullmatch(r"\d+", numbers[0])
                else None
            )
            if quantity is None or not 1 <= quantity <= 100_000:
                quantity = None
                flags.append("quantity_requires_review")
            # Every free-text interpretation gets human review, even exact catalog matches.
            flags.append("verify_unit_and_intent")
            items.append(
                ExtractedLine(
                    source=source,
                    product_id=product.id if product else None,
                    product_name=product.name if product else None,
                    quantity=quantity,
                    unit=None,
                    confidence=0.85 if product and quantity else 0.2,
                    flags=flags,
                )
            )
        return ExtractionResult(
            language=detected,
            items=items,
            flags=["human_review_required", "heuristic_confidence"],
            delivery_instructions=None,
        )
