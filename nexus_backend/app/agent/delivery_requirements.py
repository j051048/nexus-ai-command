"""User acceptance criteria, separate from evidence and model-generated claims."""

from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Claim = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=2, max_length=300)
]
ModelCode = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
]
Quantity = Annotated[int, Field(strict=True, ge=1, le=10000)]


class RequiredFact(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    topic: str = Field(min_length=2, max_length=160)
    expected_text: str = Field(min_length=2, max_length=300)
    evidence_required: bool = True


class DeliveryRequirements(BaseModel):
    model_config = ConfigDict(extra="forbid")
    required_facts: list[RequiredFact] = Field(default_factory=list, max_length=24)
    forbidden_claims: list[Claim] = Field(default_factory=list, max_length=20)
    budget: Decimal | None = Field(default=None, gt=0, le=1000000000)
    currency: str = Field(default="CNY", pattern=r"^[A-Z]{3}$")
    catalog_quantities: dict[ModelCode, Quantity] = Field(
        default_factory=dict, max_length=40
    )
