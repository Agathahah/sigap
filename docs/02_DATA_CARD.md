# Data card · BAF (Bank Account Fraud) suite

| Item | Value |
|---|---|
| Source | Jesus et al. (2022), *Turning the Tables: Biased, Imbalanced, Dynamic Tabular Datasets for ML Evaluation*, NeurIPS Datasets & Benchmarks · Kaggle `sgpjesus/bank-account-fraud-dataset-neurips-2022` |
| Licence | CC BY-NC-SA 4.0 (Kaggle dataset metadata, checked 23 Oct 2026). Non-commercial, share-alike: raw rows are not redistributed in this repository |
| Files used | Base.csv: — rows, sha256 — (from `data/raw/MANIFEST.json`) |
| Generation | Synthetic, feature-engineered applications generated with a CTGAN trained on a real, anonymized bank-account-opening dataset, with differential-privacy noise (paper §3) |
| Period | 8 months (`month` 0–7), no calendar dates |
| Label | `fraud_bool` (renamed `is_fraud`), prevalence — per month |
| Protected attributes | customer_age, income, employment_status |
| Variants | Base and Variant I–V, each with a controlled type of bias (paper §4) |

## Missing values encoded as sentinels
Filled in phase 2 from the data contract and EDA.

| Column | Rule | Share missing | Fraud rate when missing vs. not |
|---|---|---|---|
| prev_address_months_count | `-1` | — | — |
| bank_months_count | `-1` | — | — |

## Simulated production behaviour (this project's choice, not part of BAF)
- Monthly application drops in `data/landing/<variant>/applications/month=MM/`, without the label.
- Labels arrive two months later in `data/landing/<variant>/labels/available_month=MM/`
  (`SIGAP_LABEL_LAG=2`). At the end of month 7, labels are complete for months 0–5 only.

## Known limitations
No money amounts (all costs are assumptions), no timestamps within a month, no device or graph identifiers,
and synthetic generation may smooth rare fraud patterns.
