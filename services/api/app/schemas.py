from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Register(StrictModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    name: str = Field(min_length=1, max_length=120)
    organization_name: str = Field(min_length=1, max_length=120)


class Login(StrictModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class GoogleWorkspaceRegistration(StrictModel):
    organization_name: str = Field(min_length=1, max_length=120)


class CustomerInput(StrictModel):
    credit_limit_minor: int = Field(default=0, ge=0, le=2_000_000_000, strict=True)
    payment_terms_days: int = Field(default=0, ge=0, le=365, strict=True)
    price_group: Literal["retail", "wholesale"] = "retail"
    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(default="", max_length=30)
    address: str = Field(default="", max_length=500)
    active: bool = True


ProductCategory = Literal[
    "electronics",
    "fashion",
    "beauty",
    "grocery",
    "household",
    "packaging",
    "stationery",
    "hardware",
    "vehicle_parts",
    "other",
]


class ProductInput(StrictModel):
    barcode: str = Field(default="", max_length=80, pattern=r"^[A-Za-z0-9._-]*$")
    cost_minor: int | None = Field(default=None, ge=0, le=100_000_000, strict=True)
    wholesale_price_minor: int | None = Field(
        default=None, ge=0, le=100_000_000, strict=True
    )
    wholesale_min_qty: int = Field(default=1, ge=1, le=100000, strict=True)
    min_order_qty: int = Field(default=1, ge=1, le=100000, strict=True)
    category: ProductCategory = "other"
    track_stock: bool | None = None
    sku: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=120)
    aliases: list[Annotated[str, Field(min_length=1, max_length=120)]] = Field(
        default_factory=list, max_length=20
    )
    unit: str = Field(default="units", min_length=1, max_length=30)
    price_minor: int = Field(ge=0, le=100_000_000, strict=True)
    reorder_level: int = Field(default=10, ge=0, le=1_000_000, strict=True)
    active: bool = True


class StockInput(StrictModel):
    warehouse_id: str | None = Field(default=None, max_length=36)
    delta: int = Field(ge=-1_000_000, le=1_000_000, strict=True)
    reason: str = Field(min_length=3, max_length=200)


class OrderItem(StrictModel):
    product_id: str = Field(min_length=1, max_length=36)
    quantity: int = Field(gt=0, le=100_000, strict=True)


class OrderInput(StrictModel):
    warehouse_id: str | None = Field(default=None, max_length=36)
    price_mode: Literal["retail", "wholesale"] = "retail"
    discount_minor: int = Field(default=0, ge=0, le=2_000_000_000, strict=True)
    tax_basis_points: int = Field(default=0, ge=0, le=10000, strict=True)
    customer_id: str = Field(min_length=1, max_length=36)
    items: list[OrderItem] = Field(min_length=1, max_length=100)
    delivery_instructions: str = Field(default="", max_length=500)
    human_confirmed: Literal[True]
    expected_total_minor: int = Field(ge=0, le=2_000_000_000, strict=True)
    flags_acknowledged: bool = False
    draft_id: str | None = Field(default=None, max_length=36)

    @field_validator("human_confirmed", mode="before")
    @classmethod
    def explicit_confirmation(cls, value):
        if value is not True:
            raise ValueError("Explicit human confirmation is required")
        return value


class Transition(StrictModel):
    status: Literal["fulfilled", "cancelled"]


class ExtractInput(StrictModel):
    text: str = Field(min_length=1, max_length=10000)
    language: Literal["auto", "en", "si", "ta"] = "auto"


class WhatsAppPhoneNumberInput(StrictModel):
    phone_number_id: str = Field(min_length=5, max_length=128, pattern=r"^\d+$")
    display_phone_number: str = Field(min_length=5, max_length=40)
    business_account_id: str = Field(default="", max_length=128)


class WhatsAppSimulatorInput(StrictModel):
    phone_number_id: str = Field(min_length=5, max_length=128, pattern=r"^\d+$")
    customer_phone: str = Field(min_length=5, max_length=40, pattern=r"^\+?\d+$")
    customer_name: str = Field(default="Test customer", max_length=120)
    text: str = Field(min_length=1, max_length=10000)


class WhatsAppReplyInput(StrictModel):
    text: str = Field(min_length=1, max_length=4096)
    client_request_id: str = Field(min_length=16, max_length=80)


class WhatsAppConversationCustomerInput(StrictModel):
    customer_id: str = Field(min_length=1, max_length=36)


class ExtractedLine(StrictModel):
    source: str
    product_id: str | None
    product_name: str | None
    quantity: int | None
    unit: str | None
    confidence: float = Field(ge=0, le=1)
    flags: list[str]


class ExtractionResult(StrictModel):
    provider: Literal["local-rules-v1", "openai-structured-v1"] = "local-rules-v1"
    language: str
    items: list[ExtractedLine]
    flags: list[str]
    delivery_instructions: str | None
    requires_confirmation: Literal[True] = True
