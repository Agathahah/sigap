# ERD · warehouse (gold) and operational tables

> Phase 0 draft, phase 3 final. Grain first: what is ONE row of the fact table?

```mermaid
erDiagram
    %% TODO(Agatha): draw fact_application, dim_month, dim_channel, dim_device, dim_profile,
    %% decision_log, monitoring_monthly, policy_chunks. Mark PK/FK and the grain of each table.
```

## Design decisions
- _Why a star schema and not one wide table? (who queries it, which questions get simpler)_
- _Where do labels live, and how does `label_complete` in dim_month protect dashboards from reading
  an incomplete fraud rate for the last two months?_
- _Which table does the copilot's read-only role see? Which columns are excluded (protected attributes)?_
