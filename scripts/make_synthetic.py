"""BAF-shaped synthetic data (same 32 columns and conventions) for CI, tests and the PUBLIC demo. Provided.

NOT a substitute for the real data and NEVER used to report results.
Planted patterns so the pipeline can be tested end to end:
- fraud ~1.1%, higher at age >= 50 (as in the paper, about 2x prevalence)
- fraud linked to high velocity, free e-mail, low name-email similarity, missing previous address,
  non keep-alive sessions, foreign requests
- -1 / negative sentinels as in the real data; a few broken rows for the quarantine
- months 6-7 shifted (velocity up, income down) so drift monitoring has something to detect

Usage:
    python scripts/make_synthetic.py --rows 120000 --out data/raw_synthetic
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

CATEGORICAL = {
    "payment_type": ["AA", "AB", "AC", "AD", "AE"],
    "employment_status": ["CA", "CB", "CC", "CD", "CE", "CF", "CG"],
    "housing_status": ["BA", "BB", "BC", "BD", "BE", "BF", "BG"],
    "source": ["INTERNET", "TELEAPP"],
    "device_os": ["windows", "linux", "macintosh", "x11", "other"],
}
RAW_COLUMNS = (
    "fraud_bool,income,name_email_similarity,prev_address_months_count,current_address_months_count,customer_age,"
    "days_since_request,intended_balcon_amount,payment_type,zip_count_4w,velocity_6h,velocity_24h,velocity_4w,"
    "bank_branch_count_8w,date_of_birth_distinct_emails_4w,employment_status,credit_risk_score,email_is_free,"
    "housing_status,phone_home_valid,phone_mobile_valid,bank_months_count,has_other_cards,proposed_credit_limit,"
    "foreign_request,source,session_length_in_minutes,device_os,keep_alive_session,device_distinct_emails_8w,"
    "device_fraud_count,month"
).split(",")


def make(rows: int, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    month = rng.choice(np.arange(8), rows, p=np.array([10, 11, 12, 13, 13, 13, 14, 14]) / 100)
    late = month >= 6
    age = rng.choice(np.arange(10, 100, 10), rows, p=[0.02, 0.24, 0.27, 0.23, 0.14, 0.07, 0.02, 0.008, 0.002])
    income = np.round(rng.choice(np.arange(1, 10) / 10, rows) - 0.1 * late * (rng.random(rows) < 0.3), 1).clip(0.1, 0.9)
    v6 = rng.gamma(4, 1400, rows) * np.where(late, 1.12, 1.0)
    email_free = (rng.random(rows) < 0.53).astype(int)
    name_sim = rng.beta(2, 2, rows)
    prev_addr = np.where(rng.random(rows) < 0.7, -1, rng.integers(5, 380, rows))
    foreign = (rng.random(rows) < 0.025).astype(int)
    keep_alive = (rng.random(rows) < 0.42).astype(int)
    device_os = rng.choice(CATEGORICAL["device_os"], rows, p=[0.26, 0.33, 0.05, 0.01, 0.35])
    housing = rng.choice(CATEGORICAL["housing_status"], rows, p=[0.17, 0.26, 0.37, 0.03, 0.167, 0.003, 0.0])
    limit = rng.choice([200.0, 500.0, 1000.0, 1500.0, 2000.0], rows, p=[0.4, 0.25, 0.12, 0.13, 0.10])

    logit = (
        -6.45
        + 1.0 * (age >= 50)
        + 0.9 * np.log(v6 / 5600).clip(-2, 2)
        + 1.0 * email_free
        - 2.2 * name_sim
        + 0.8 * (prev_addr == -1)
        + 1.6 * foreign
        - 0.9 * keep_alive
        + 0.9 * (device_os == "windows")
        + 1.0 * (housing == "BA")
        + 0.0009 * limit
    )
    fraud = (rng.random(rows) < 1 / (1 + np.exp(-logit))).astype(int)

    df = pd.DataFrame(
        {
            "fraud_bool": fraud,
            "income": income,
            "name_email_similarity": name_sim,
            "prev_address_months_count": prev_addr,
            "current_address_months_count": np.where(rng.random(rows) < 0.005, -1, rng.integers(0, 400, rows)),
            "customer_age": age,
            "days_since_request": rng.exponential(1.0, rows),
            "intended_balcon_amount": np.where(rng.random(rows) < 0.74, -rng.random(rows) * 2, rng.gamma(2, 20, rows)),
            "payment_type": rng.choice(CATEGORICAL["payment_type"], rows, p=[0.26, 0.37, 0.25, 0.12, 0.0]),
            "zip_count_4w": rng.integers(1, 6000, rows),
            "velocity_6h": v6,
            "velocity_24h": rng.gamma(9, 530, rows) * np.where(late, 1.25, 1.0),
            "velocity_4w": rng.normal(4850, 900, rows).clip(2800, 7000),
            "bank_branch_count_8w": np.where(
                rng.random(rows) < 0.5, rng.integers(0, 30, rows), rng.integers(0, 2400, rows)
            ),
            "date_of_birth_distinct_emails_4w": rng.poisson(9, rows),
            "employment_status": rng.choice(
                CATEGORICAL["employment_status"], rows, p=[0.73, 0.14, 0.04, 0.03, 0.02, 0.04, 0.0]
            ),
            "credit_risk_score": rng.normal(130, 70, rows).round().clip(-170, 390) + 40 * fraud,
            "email_is_free": email_free,
            "housing_status": housing,
            "phone_home_valid": (rng.random(rows) < 0.42).astype(int),
            "phone_mobile_valid": (rng.random(rows) < 0.89).astype(int),
            "bank_months_count": np.where(rng.random(rows) < 0.25, -1, rng.integers(1, 32, rows)),
            "has_other_cards": (rng.random(rows) < 0.22).astype(int),
            "proposed_credit_limit": limit,
            "foreign_request": foreign,
            "source": rng.choice(CATEGORICAL["source"], rows, p=[0.993, 0.007]),
            "session_length_in_minutes": np.where(rng.random(rows) < 0.002, -1, rng.gamma(1.4, 5.5, rows)),
            "device_os": device_os,
            "keep_alive_session": keep_alive,
            "device_distinct_emails_8w": np.where(
                rng.random(rows) < 0.0005, -1, rng.choice([0, 1, 2], rows, p=[0.03, 0.94, 0.03])
            ),
            "device_fraud_count": 0,
            "month": month,
        }
    )[RAW_COLUMNS]
    bad = rng.choice(rows, size=max(rows // 20000, 3), replace=False)
    df.loc[bad[:2], "name_email_similarity"] = 1.7  # outside 0..1 -> quarantine
    df = pd.concat([df, df.iloc[bad[2:]]], ignore_index=True)  # exact duplicates
    return df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=120_000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", type=Path, default=Path("data/raw_synthetic"))
    ap.add_argument("--variant", default="Synthetic")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    df = make(a.rows, a.seed)
    df.to_csv(a.out / f"{a.variant}.csv", index=False)
    print(f"wrote {len(df):,} applications (fraud {df.fraud_bool.mean():.2%}) to {a.out / (a.variant + '.csv')}")


if __name__ == "__main__":
    main()
