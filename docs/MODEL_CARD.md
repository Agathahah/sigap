# Model card · SIGAP fraud score

| Item | Value |
|---|---|
| Model | _algorithm, version, MLflow run id_ |
| Intended use | Rank account-opening applications for review; NOT an automatic approval of identity |
| Not for | _credit decisions, any decision without a human review band_ |
| Training data | BAF _variant_, months 0-4; validation month 5; test months 6-7 |
| Features | _count; list engineered ones; protected attributes used? (ADR 0005)_ |
| Metrics (test) | TPR@5%FPR, PR-AUC, ROC-AUC, ECE, alert rate _with run id_ |
| Fairness | FPR by age group and ratio _with run id_ |
| Release gate | _passed / failed + reasons_ |
| Explanations | SHAP reason codes, top 3 per application |
| Monitoring | PSI on score and top features monthly; TPR/FPR when labels arrive (+2 months) |
| Limitations | _synthetic data, no amounts, label lag, ..._ |
