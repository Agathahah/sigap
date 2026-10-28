# EDA findings

Training months 0–4 only (675,666 applications, 6,740 frauds, 0.998%). Months 5–7 stay unseen until validation
and test. Every number comes from `sql/analysis/q01`–`q07` (results in `reports/eda/`, 27 Oct 2026).

### F1 · Missing history is a fraud signal, not noise
- **Evidence (q03):** applications with no previous address (`prev_address_months_count = -1`, 69.6% of volume)
  have a fraud rate of 1.31% vs 0.28% when the address is present (4.7×). No intended balance (73.1%): 1.19% vs
  0.48% (2.5×). No previous bank account (25.5%): 1.49% vs 0.83% (1.8×). The opposite holds for an unknown current
  address (0.4% of volume, 0.28× the fraud rate).
- **So what:** replacing these sentinels with an average would erase one of the strongest signals in the data.
- **Action:** silver keeps a `<column>_missing` flag for all six sentinel columns and sets the value to NULL.
  The flags are model features; "no previous address" alone covers 70% of volume, so it is a rule component, not
  a rule.

### F2 · Windows devices carry most of the fraud, steadily
- **Evidence (q02, q05):** Windows is 27.0% of applications but 60.8% of frauds (fraud rate 2.25%, lift 2.25).
  Its 3-month rolling rate stays between 2.10% and 2.50% in every training month; Linux stays below 0.6%.
- **So what:** the signal is stable over time, so it is unlikely to be a one-month artefact.
- **Action:** `device_os` is a feature; Windows is a candidate component of a combined rule; its share is
  monitored for drift (PSI) because a shift in device mix changes the alert volume.

### F3 · One housing status concentrates half of the fraud
- **Evidence (q02):** `housing_status = BA` is 16.3% of applications and 56.1% of frauds (fraud rate 3.42%,
  lift 3.43), the strongest single category in the data.
- **So what:** strong for detection, but housing status can act as a proxy for income or wealth.
- **Action:** use it as a feature and check, in the fairness stage, that false positives do not concentrate in
  one income or age group through it.

### F4 · Customers aged 50+ have about three times the fraud rate
- **Evidence (q06):** in every training month the 50+ group (18–20% of volume) has a fraud rate of 1.96–2.59%,
  against 0.62–0.81% for under-50s.
- **So what:** a model will flag older applicants more often. Some of that is real risk; the question is
  whether genuine older customers pay for it with more reviews and declines.
- **Action:** `customer_age` is a protected attribute. The release gate compares the false-positive rate of 50+
  vs under-50 (predictive equality, ADR 0005); the copilot and messages never receive age.

### F5 · "Many applications in a short time" does not mean fraud here
- **Evidence (q04):** the fraud rate falls from 1.35% in the lowest decile of `velocity_6h` to 0.68% in the
  highest; `velocity_4w` shows no trend (0.71–1.27% across deciles). The lowest decile also contains the slightly
  negative values noted in the data contract.
- **So what:** the intuitive "application burst" rule would raise alerts on the least risky traffic.
- **Action:** no velocity-threshold rule; velocity stays a model feature so the model can learn its non-linear
  shape. The negative `velocity_6h` values are kept (they are in the source) and watched in monitoring.

### F6 · Single broad rules would flood the review team
- **Evidence (q07):** with four candidate rules, 74.9% of applications hit at least one rule. Applications hitting
  none hold only 5.0% of frauds (0.20%). Hitting two or more: 12.0% of volume, 33.7% of frauds, fraud rate
  2.58% (two rules) and 7.27% (three or more).
- **So what:** "any rule fires → review" is far beyond any realistic review capacity; combinations are where
  precision lives.
- **Action:** the rule baseline is built from combinations and tuned against capacity in the rules stage; the
  model has to beat that baseline, not zero.

### F7 · High lift on a tiny segment catches little fraud
- **Evidence (q02):** `source = TELEAPP` has lift 1.44 but is 0.75% of volume and 1.1% of frauds.
  `payment_type = AC` has a lower lift (1.52) but is 25.4% of volume and 38.7% of frauds.
- **So what:** lift alone is a misleading way to pick rules.
- **Action:** rules are ranked by fraud share caught per alert raised, not by lift.

## Data quality summary
| Check | Result | Action |
|---|---|---|
| Rows per month vs manifest | 1,000,000 landed = 1,000,000 in the manifest = 1,000,000 labels | none |
| Quarantine rate per month (`make quality`) | 0% in all 8 months | contract stays as the guard for future drops |
| Duplicates on application_id | none (ids are unique by construction, `test_application_id_deterministic_and_unique`) | none |
| Sentinel columns | six, confirmed in q03 | NULL + `_missing` flag in silver |
| Constant column | `device_fraud_count` is 0 in every row | excluded from features |
| Fraud rate trend | 0.88–1.14% in training, 1.18% validation, 1.34–1.47% test | expect a harder test period; monitor drift |
