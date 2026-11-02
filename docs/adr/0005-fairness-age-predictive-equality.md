# ADR 0005 · Fairness: age groups, predictive equality and reweighing

- Status: accepted
- Date: 2026-10-28

## Context
- A false positive is a genuine customer whose account opening is delayed by a review. If one age group gets more
  false positives, that group carries more friction for the same risk.
- BAF contains `customer_age` (rounded to decades). EDA F4: applicants aged 50+ have about 3x the fraud rate,
  so a model learns age directly and through correlated features.
- Metric (BAF paper protocol): **predictive equality**, the ratio of false-positive rates between applicants aged
  50+ and under 50 at the operating threshold (5% FPR). 1.0 = equal friction.
- Exploration on month 5 (28 Oct, before any test month was scored, gradient boosting, threshold at 5% FPR):

| Candidate | Recall at 5% FPR | FPR <50 | FPR 50+ | FPR ratio |
|---|---|---|---|---|
| all features | 0.537 | 3.7% | 11.2% | 0.33 |
| without customer_age, income, employment_status | 0.528 | 4.2% | 9.1% | 0.46 |
| + reweighing, genuine 50+ weighted 2x | 0.516 | 4.4% | 8.1% | 0.54 |
| + reweighing 4x | 0.510 | 4.6% | 7.1% | 0.65 |
| + reweighing 8x | 0.488 | 4.8% | 6.0% | 0.79 |

## Options considered
1. **Use age as a feature, report the ratio only** — highest recall; applicants 50+ get about 3x the friction.
2. **Drop protected attributes as features** — simple and explainable; the ratio improves but stays below 0.5
   because other features carry age information.
3. **Drop them and reweigh training rows** (Kamiran & Calders, 2012): genuine applicants aged 50+ count more in the
   loss, so the model learns not to push their scores up. Age is used only to set training weights, never at
   scoring time.
4. **Group-specific thresholds** (post-processing, Hardt et al., 2016) — exact equality, but the decision would
   depend on age at scoring time, which is hard to defend for an account-opening decision.

## Decision
Train without protected attributes and choose between reweighing factors 2x and 4x on month 5. The release gate
requires an FPR ratio of at least 0.50 on the test months (one group's FPR at most twice the other's); selection
asks month 5 for 0.60, leaving room for drift.

## Consequences
- Expected cost: about 2–3 points of recall at 5% FPR compared with the all-features model (table above). The
  memo states this trade-off in numbers.
- Age is still processed in training (weights) and in monitoring (FPR by group), so it stays in the warehouse
  under the protected-attribute rules: never sent to the copilot, analysts' reason codes or messages.
- The ratio is monitored monthly once labels arrive; if it falls below 0.50, retraining is triggered.
- Fairness is measured for age only; income and employment status are not audited here (limitation in the
  model card).

## References
- Jesus et al. (2022). Turning the Tables: Biased, Imbalanced, Dynamic Tabular Datasets for ML Evaluation. NeurIPS
  Datasets and Benchmarks. https://arxiv.org/abs/2211.13358
- Hardt, Price & Srebro (2016). Equality of Opportunity in Supervised Learning. https://arxiv.org/abs/1610.02413
- Kamiran & Calders (2012). Data preprocessing techniques for classification without discrimination. Knowledge
  and Information Systems 33(1). https://doi.org/10.1007/s10115-011-0463-8
