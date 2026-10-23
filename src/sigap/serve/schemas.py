"""Phase 7 · API contract (Pydantic). The API rejects bad input BEFORE it reaches the model.

The request carries one application as the source system sends it (raw BAF columns, minus the label
and month). Sentinel values (-1) are allowed here because that is what the source sends; the API
applies the same cleaning as silver before scoring (same code, not a copy).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ApplicationIn(BaseModel):
    """Phase 7 · TODO(Agatha): one account-opening application.

    Required fields (all required, extra fields forbidden -> model_config = ConfigDict(extra="forbid")):
      income: float in [0, 1]                    name_email_similarity: float in [0, 1]
      prev_address_months_count: int >= -1       current_address_months_count: int >= -1
      customer_age: int in [10, 100]             days_since_request: float >= 0
      intended_balcon_amount: float              payment_type: Literal["AA","AB","AC","AD","AE"]
      zip_count_4w: int >= 0                     velocity_6h: float, velocity_24h: float, velocity_4w: float
      bank_branch_count_8w: int >= 0             date_of_birth_distinct_emails_4w: int >= 0
      employment_status: Literal["CA","CB","CC","CD","CE","CF","CG"]
      credit_risk_score: int                     email_is_free: int in [0, 1]
      housing_status: Literal["BA","BB","BC","BD","BE","BF","BG"]
      phone_home_valid: int in [0, 1]            phone_mobile_valid: int in [0, 1]
      bank_months_count: int >= -1               has_other_cards: int in [0, 1]
      proposed_credit_limit: float >= 0          foreign_request: int in [0, 1]
      source: Literal["INTERNET","TELEAPP"]      session_length_in_minutes: float >= -1
      device_os: Literal["windows","linux","macintosh","x11","other"]
      keep_alive_session: int in [0, 1]          device_distinct_emails_8w: int >= -1
      device_fraud_count: int >= 0
    Hint: Field(ge=0, le=1). Check the ranges against your EDA; if real data breaks one, fix the contract
    and write down why.
    Test: tests/test_p7_serve.py::test_schema_*
    """

    model_config = ConfigDict(extra="forbid")
    # TODO(Agatha) phase 7: add every field listed in the docstring, with Field(...) constraints


class ScoreOut(BaseModel):
    """Response of POST /v1/score. Provided (so the copilot and dashboard can rely on it)."""

    application_id: str | None = None
    score: float = Field(ge=0, le=1, description="calibrated fraud probability")
    decision: Literal["approve", "review", "decline"]
    reasons: list[str] = Field(default_factory=list, description="top reason codes, human readable")
    model_version: str
    latency_ms: float
