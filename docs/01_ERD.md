# ERD · warehouse and operational tables

Draft (phase 0). The final version follows the DDL in `sql/warehouse/`.

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
        int month_index
        boolean label_complete "false for the last 2 months (labels not arrived)"
    }
    DIM_CHANNEL {
        int channel_key PK
        text source
        text payment_type
    }
    DIM_DEVICE {
        int device_key PK
        text device_os
        smallint keep_alive_session
        smallint email_is_free
    }
    DIM_PROFILE {
        int profile_key PK
        text age_band "protected"
        int income_decile "protected"
        text employment_status "protected"
        text housing_status
    }
    FACT_APPLICATION {
        text application_id PK "one row per application"
        int month_key FK
        int channel_key FK
        int device_key FK
        int profile_key FK
        float velocity_6h
        float name_email_similarity
        smallint is_fraud "NULL until the label arrives"
    }
    DECISION_LOG {
        bigint id PK
        text application_id FK
        text model_version
        float score
        text decision "approve | review | decline"
        text reasons
        timestamptz decided_at
    }
    MONITORING_MONTHLY {
        int month PK
        text metric PK
        text feature PK
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
