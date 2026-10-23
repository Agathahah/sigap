# Data card · BAF (Bank Account Fraud) suite

| Item | Value |
|---|---|
| Source | Jesus et al. (2022), NeurIPS Datasets & Benchmarks · Kaggle `sgpjesus/bank-account-fraud-dataset-neurips-2022` |
| Licence | _copy from `make data-licence` output and the Kaggle page; date checked_ |
| Files used | _from data/raw/MANIFEST.json: name, rows, sha256 (first 12 chars)_ |
| Generation | _privacy-preserving synthetic data generated from a real bank's applications (read the paper §3)_ |
| Period | 8 months (month 0-7), no calendar dates |
| Label | `fraud_bool` (renamed `is_fraud`), prevalence _..._ per month |
| Protected attributes | customer_age, income, employment_status |
| Variants | Base, Variant I-V (each with a controlled bias; summarize from the paper) |

## Sentinels (missing data encoded as -1 / negative)
| Column | Rule | Share missing | Fraud rate when missing vs not |
|---|---|---|---|
| _..._ | | | |

## Simulated production behaviour (this project's choice, not part of BAF)
- Monthly drops in `data/landing/applications/month=XX/`
- Labels arrive `LABEL_LAG_MONTHS` = 2 months later in `data/landing/labels/available_month=XX/`

## Known limitations
_No amounts (so money is an assumption), no timestamps within a month, no device/graph identifiers,
synthetic generation may smooth rare patterns._
