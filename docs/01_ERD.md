# ERD · warehouse and operational tables

Matches the DDL in `sql/warehouse/001_schemas.sql` (gold + decision/monitoring tables) and `003_ops.sql`
(review cases and alerts). Loaded by `src/sigap/pipeline/gold.py`.

**Grain of the fact table:** one row per account-opening application.

```mermaid
erDiagram
    DIM_MONTH ||--o{ FACT_APPLICATION : "month_key"
    DIM_CHANNEL ||--o{ FACT_APPLICATION : "channel_key"
    DIM_DEVICE ||--o{ FACT_APPLICATION : "device_key"
    DIM_PROFILE ||--o{ FACT_APPLICATION : "profile_key"
    FACT_APPLICATION ||--o{ DECISION_LOG : "application_id"
    FACT_APPLICATION ||--o| REVIEW_CASE : "application_id"
    REVIEW_CASE ||--o{ REVIEW_DECISION : "case_id"
    DIM_MONTH ||--o{ MONITORING_MONTHLY : "month"

    DIM_MONTH {
        int month_key PK
        smallint month_index UK
        boolean label_complete "month + label lag <= as-of month"
    }
    DIM_CHANNEL {
        int channel_key PK "identity"
        text source UK
        text payment_type UK
    }
    DIM_DEVICE {
        int device_key PK "identity"
        text device_os UK
        smallint keep_alive_session
        smallint email_is_free
    }
    DIM_PROFILE {
        int profile_key PK "identity"
        text age_band "protected: <30 | 30-39 | 40-49 | 50-59 | 60+"
        smallint income_decile "protected: 1..9"
        text employment_status "protected"
        text housing_status
    }
    FACT_APPLICATION {
        text application_id PK "one row per application"
        int month_key FK
        int channel_key FK
        int device_key FK
        int profile_key FK
        float name_email_similarity
        float velocity_6h "also velocity_24h, velocity_4w"
        int credit_risk_score
        float proposed_credit_limit
        int prev_address_months_count "NULL when the source had the sentinel"
        smallint prev_address_months_count_missing "one flag per sentinel column (6)"
        smallint is_fraud "NULL until the label arrives"
    }
    DECISION_LOG {
        bigint id PK
        text application_id FK
        text model_version
        float score
        text decision "approve | review | decline"
        text_array reasons "reason codes, no raw values"
        timestamptz decided_at
    }
    MONITORING_MONTHLY {
        smallint month PK
        text metric PK "psi | alert_rate | review_rate | tpr | fpr"
        text feature PK "'' when not per feature"
        float value
    }
    REVIEW_CASE {
        text case_id PK
        text application_id FK
        date day
        int priority
        text status "assigned | backlog | pending_info | closed_*"
    }
    REVIEW_DECISION {
        bigint decision_id PK
        text case_id FK
        text outcome "confirmed_fraud | legit | need_info"
        text analyst_id
        timestamptz decided_at
    }
    ALERT {
        text alert_key PK "stable id per event"
        text kind "drift | queue_over_capacity | data_incident"
        text severity
        timestamptz acked_at
    }
```

## Design decisions
- **Star schema, not one wide table.** Analysts, the dashboard and the copilot ask the same questions by month,
  channel, device and profile. Dimensions keep those queries short, and protected attributes live in one
  dimension (`dim_profile`) that the copilot's read-only role cannot see.
- **Labels in the fact table, completeness in `dim_month`.** `is_fraud` stays NULL until the label feed delivers
  it; `label_complete` marks months whose labels have all arrived, so a dashboard never reports a fraud rate for
  a month that only looks clean because its labels are missing.
- **Operational schema `ops`.** Decisions, monitoring, alerts and review cases are written by the running
  system, not by the batch pipeline, and are kept apart from the analytical `gold` schema.
- **Analyst decisions are not labels.** `review_decision` records what an analyst concluded for a reviewed case;
  it never overwrites `fact_application.is_fraud`.
- **Decision log without a foreign key.** The API decides before an application reaches the warehouse, so
  `ops.decision_log.application_id` is a logical link to the fact table, not an enforced one.
- **Stable surrogate keys.** Dimension keys are identity columns and new categories are inserted with
  `ON CONFLICT DO NOTHING`, so a key never changes after it is assigned. The fact is upserted on
  `application_id`; the load never truncates, so decisions logged for loaded applications keep their match.
- **Point in time.** The warehouse is built as of the latest month in silver: a label is joined only when
  `available_month <= as_of`. With 8 months and a 2-month lag, months 0–5 are labelled and months 6–7 are not
  yet; re-running after the next drop fills them in.
- **Sentinels as NULL + flag.** The six sentinel columns are NULL in the fact, with a `*_missing` flag beside
  each one (EDA finding F1: the missing pattern itself is a fraud signal).
