# Data card · BAF (Bank Account Fraud) suite

| Item | Value |
|---|---|
| Source | Jesus et al. (2022), *Turning the Tables: Biased, Imbalanced, Dynamic Tabular Datasets for ML Evaluation*, NeurIPS Datasets & Benchmarks · Kaggle `sgpjesus/bank-account-fraud-dataset-neurips-2022` |
| Licence | CC BY-NC-SA 4.0 (Kaggle dataset metadata, checked 23 Oct 2026). Non-commercial, share-alike: raw rows are not redistributed in this repository |
| Files used | Base.csv: 1,000,000 rows, 213.4 MB, sha256 `7bf10a37ce07…` (`data/raw/MANIFEST.json`, 23 Oct 2026) |
| Generation | Synthetic, feature-engineered applications generated with a CTGAN trained on a real, anonymized bank-account-opening dataset, with differential-privacy noise (paper §3) |
| Period | 8 months (`month` 0–7), no calendar dates |
| Label | `fraud_bool` (renamed `is_fraud`): 11,029 frauds, 1.10% overall; see the table below |
| Protected attributes | customer_age, income, employment_status |
| Variants | Base and Variant I–V, each with a controlled type of bias (paper §4) |

## Volume and fraud by month
| Month | Applications | Frauds | Fraud rate | Role |
|---|---|---|---|---|
| 0 | 132,440 | 1,500 | 1.13% | train |
| 1 | 127,620 | 1,198 | 0.94% | train |
| 2 | 136,979 | 1,198 | 0.87% | train |
| 3 | 150,936 | 1,392 | 0.92% | train |
| 4 | 127,691 | 1,452 | 1.14% | train |
| 5 | 119,323 | 1,411 | 1.18% | validation |
| 6 | 108,168 | 1,450 | 1.34% | test |
| 7 | 96,843 | 1,428 | 1.47% | test |

Volume falls and the fraud rate rises in the later months, so the test months are harder than the training
months: a model tuned on months 0-4 will meet a different mix in months 6-7.

## Missing values encoded as sentinels
Six columns, listed in `configs/data_contract.yaml`. Shares and fraud rates come from `sql/analysis/q03` on months 0-4.

| Column | Rule | Share missing | Fraud rate when missing vs. not |
|---|---|---|---|
| prev_address_months_count | `-1` | 69.55% | 1.31% vs 0.28% (4.7×) |
| current_address_months_count | `-1` | 0.42% | 0.28% vs 1.00% (0.3×) |
| intended_balcon_amount | `< 0` | 73.08% | 1.19% vs 0.48% (2.5×) |
| bank_months_count | `-1` | 25.50% | 1.49% vs 0.83% (1.8×) |
| session_length_in_minutes | `-1` | 0.19% | 0.78% vs 1.00% (0.8×) |
| device_distinct_emails_8w | `-1` | 0.04% | 1.09% vs 1.00% (1.1×) |

`device_fraud_count` is 0 in every row of the Base file and carries no information.

## Simulated production behaviour (this project's choice, not part of BAF)
- Monthly application drops in `data/landing/<variant>/applications/month=MM/`, without the label.
- Labels arrive two months later in `data/landing/<variant>/labels/available_month=MM/`
  (`SIGAP_LABEL_LAG=2`). At the end of month 7, labels are complete for months 0–5 only.

## Known limitations
No money amounts (all costs are assumptions), no timestamps within a month, no device or graph identifiers,
and synthetic generation may smooth rare fraud patterns.
