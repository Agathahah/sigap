# EDA findings (phase 2)

> Format for every finding. Five to eight findings. Each must change a decision later in the project.
> Numbers come from `sql/analysis/*.sql` or `notebooks/01_eda.ipynb` (say which).

### F1 · _title in one sentence_
- **Evidence:** _query/plot + numbers (months 0-4 only, test months stay unseen)_
- **So what:** _what it means for the fraud team / model / policy_
- **Action:** _e.g. "keep the missing flag as a feature", "rule R3 in rules.yaml", "monitor this column's PSI"_

### F2 · ...

## Data quality summary
| Check | Result | Action |
|---|---|---|
| Rows per month vs manifest | | |
| Quarantine rate per month (`make quality`) | | |
| Duplicates on application_id | | |
| Sentinel columns (6) | | |
