"""Reason codes: why was THIS application sent to review?

An analyst cannot act on "score 0.83". They can act on "requested the top credit limit; device used with several
e-mail addresses". Reason codes are the features with the largest positive SHAP contribution for one application.
Protected attributes are never shown as a reason (they are not sent to analysts, the copilot or messages).
"""

from __future__ import annotations

PROTECTED = ("customer_age", "income", "employment_status")

LABELS = {
    "proposed_credit_limit": "requested credit limit is high for a new account",
    "credit_risk_score": "internal risk score is high",
    "device_os__windows": "device type with a high fraud rate",
    "housing_status__BA": "housing status with a high fraud rate",
    "prev_address_months_count_missing": "no previous address on record",
    "prev_address_months_count": "short time at previous address",
    "current_address_months_count": "time at current address",
    "keep_alive_session": "session not kept alive",
    "device_distinct_emails_8w": "device used with several e-mail addresses",
    "name_email_similarity": "e-mail address does not match the applicant's name",
    "email_is_free": "free e-mail provider",
    "has_other_cards": "no other cards with the bank",
    "phone_home_valid": "home phone not valid",
    "phone_mobile_valid": "mobile phone not valid",
    "bank_months_count_missing": "no previous bank account",
    "intended_balcon_amount_missing": "no intended initial balance",
    "date_of_birth_distinct_emails_4w": "e-mail addresses seen with the same date of birth",
    "prior_rate_device_os": "device type with a high recent fraud rate",
    "prior_rate_payment_type": "payment type with a high recent fraud rate",
    "velocity_ratio": "application volume in the last 6 hours vs normal",
    "foreign_request": "request from abroad",
    "source__TELEAPP": "application through the phone channel",
    "days_since_request": "days between request and application",
    "zip_count_4w": "applications from the same postcode in 4 weeks",
    "velocity_6h": "application volume in the last 6 hours",
    "velocity_24h": "application volume in the last 24 hours",
    "velocity_4w": "application volume in the last 4 weeks",
    "bank_branch_count_8w": "applications at the same branch in 8 weeks",
    "intended_balcon_amount": "intended initial balance",
    "bank_months_count": "age of previous bank account",
    "session_length_in_minutes": "session length",
    "session_length_in_minutes_missing": "session length not recorded",
    "current_address_months_count_missing": "time at current address unknown",
    "device_distinct_emails_8w_missing": "device e-mail history not recorded",
}


def readable(feature: str) -> str:
    """Text for a feature without an explicit label: one-hot `col__value` -> "col = value"."""
    if feature in LABELS:
        return LABELS[feature]
    if "__" in feature:
        col, value = feature.split("__", 1)
        return f"{col.replace('_', ' ')} = {value}"
    return feature.replace("_", " ")


def top_reasons(contributions: dict[str, float], labels: dict[str, str] | None = None, k: int = 3) -> list[str]:
    """The k features that pushed the score up the most (positive values only; ties by feature name)."""
    labels = labels or {}
    positive = [(f, v) for f, v in contributions.items() if v > 0]
    positive.sort(key=lambda fv: (-fv[1], fv[0]))
    return [labels.get(f, f) for f, _ in positive[:k]]


def analyst_reasons(contributions: dict[str, float], k: int = 3) -> list[str]:
    """Reason codes for analysts and messages: protected attributes (and their one-hot columns) removed."""
    allowed = {f: v for f, v in contributions.items() if not f.startswith(PROTECTED)}
    return [readable(f) for f in top_reasons(allowed, None, k)]
