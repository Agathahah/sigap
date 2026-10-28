# Model card · SIGAP fraud score

| Item | Value |
|---|---|
| Model | XGBoost (hist, depth 6, learning rate 0.05, early stopping on month-5 PR-AUC) with Platt (sigmoid) calibration on month 5. Candidate `xgb_reweighed_4`, version `base-20261028-0433-b4e83b`, registered as `sigap-base` v1 with alias `champion` (MLflow experiment `sigap-base`) |
| Intended use | Rank account-opening applications so that the riskiest go to a human review or verification step |
| Not for | Credit decisions; declining an applicant without the review band; any use outside account opening |
| Training data | BAF Base (Jesus et al., 2022), months 0–4 (675,666 applications, fraud 1.00%); validation month 5 (119,323, 1.18%); test months 6–7 (205,011, 1.40%). Data manifest sha256 starts `6e721c44cb27` |
| Features | 50: 22 numeric, 6 missing-value flags, 19 one-hot categories, `velocity_ratio`, point-in-time `prior_rate` for payment type and device OS. Protected attributes (`customer_age`, `income`, `employment_status`) are **not** model inputs; age is used only for training weights and fairness measurement (ADR 0005) |
| Threshold | Calibrated score ≥ 0.0133 = 5% FPR on month 5, applied unchanged to months 6–7 (ADR 0002) |
| Metrics (test, months 6–7) | Recall at the threshold 0.521; FPR 0.053; precision 0.123; alert rate 5.9%; PR-AUC 0.175; ROC-AUC 0.882; ECE 0.0034 |
| Compared with | Logistic regression baseline: month-5 recall 0.512 at 5% FPR, PR-AUC 0.156. Rule baseline (5 rules): at the rules' month-5 alert rate of 7.86% the rules catch 45.2% of fraud; the model catches 59.1% (month 5) and 59.0% (months 6–7) |
| Fairness | FPR aged 50+ vs under 50 at the threshold: 8.1% vs 4.7% on test, ratio 0.58 (month 5: 0.65). The all-features model had a month-5 ratio of 0.32. Cost of the mitigation: month-5 recall 0.518 vs 0.537 for the all-features model |
| Release gate | Passed: test recall ≥ 0.40, PR-AUC ≥ 0.10, FPR ratio by age ≥ 0.50, FPR ≤ 0.06, ECE ≤ 0.05, score PSI test vs train ≤ 0.25 (0.054) |
| Explanations | Reason codes from per-application SHAP contributions (XGBoost TreeSHAP), top 3 positive, protected attributes never shown. Largest mean contributions on test: housing status BA, home phone validity, Windows device, session keep-alive, name–e-mail similarity |
| Monitoring | Monthly PSI on the score and top features; recall, FPR and the age FPR ratio when labels arrive (+2 months) |
| Limitations | BAF is synthetic data derived from a real bank, with no money amounts; one variant (Base) only; month 5 is used for early stopping, calibration and the threshold; fairness is audited for age only (not income or employment); housing status BA is the strongest signal and may act as a wealth proxy; results come from an offline backtest, not live traffic |

Sources: `reports/model/base_metrics.json`, `reports/model/base_candidates.csv`, `reports/model/base_shap_importance.csv`,
MLflow parent run `train-20261028-0433`.
