"""API contract (Pydantic). The API rejects bad input BEFORE it reaches the model.

The request carries one application as the source system sends it (raw BAF columns, minus the label
and month). Sentinel values (-1) are allowed here because that is what the source sends; the API
applies the same cleaning as silver before scoring (same code, not a copy).
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

UnitFloat = Annotated[float, Field(ge=0, le=1)]
Binary = Annotated[int, Field(ge=0, le=1)]


class ApplicationIn(BaseModel):
    """One account-opening application, every field required, unknown fields rejected (HTTP 422).

    Ranges are the data contract's, widened where the source can legitimately send more (velocity, credit score).
    """

    model_config = ConfigDict(extra="forbid")

    income: UnitFloat
    name_email_similarity: UnitFloat
    prev_address_months_count: int = Field(ge=-1)
    current_address_months_count: int = Field(ge=-1)
    customer_age: int = Field(ge=10, le=100)
    days_since_request: float = Field(ge=0)
    intended_balcon_amount: float
    payment_type: Literal["AA", "AB", "AC", "AD", "AE"]
    zip_count_4w: int = Field(ge=0)
    velocity_6h: float
    velocity_24h: float
    velocity_4w: float
    bank_branch_count_8w: int = Field(ge=0)
    date_of_birth_distinct_emails_4w: int = Field(ge=0)
    employment_status: Literal["CA", "CB", "CC", "CD", "CE", "CF", "CG"]
    credit_risk_score: int
    email_is_free: Binary
    housing_status: Literal["BA", "BB", "BC", "BD", "BE", "BF", "BG"]
    phone_home_valid: Binary
    phone_mobile_valid: Binary
    bank_months_count: int = Field(ge=-1)
    has_other_cards: Binary
    proposed_credit_limit: float = Field(ge=0)
    foreign_request: Binary
    source: Literal["INTERNET", "TELEAPP"]
    session_length_in_minutes: float = Field(ge=-1)
    device_os: Literal["windows", "linux", "macintosh", "x11", "other"]
    keep_alive_session: Binary
    device_distinct_emails_8w: int = Field(ge=-1)
    device_fraud_count: int = Field(ge=0)


class ScoreOut(BaseModel):
    """Response of POST /v1/score (the copilot and the dashboard rely on this shape)."""

    application_id: str | None = None
    score: float = Field(ge=0, le=1, description="calibrated fraud probability")
    decision: Literal["approve", "review", "decline"]
    reasons: list[str] = Field(default_factory=list, description="top reason codes, human readable")
    model_version: str
    latency_ms: float


class ModelInfo(BaseModel):
    """Response of GET /v1/model."""

    model_version: str
    candidate: str | None = None
    trained_at: str | None = None
    threshold: float
    t_review: float
    t_decline: float | None
    features: int
    feature_list_sha256: str
    prior_rates_as_of_month: int
    gate_passed: bool | None = None
