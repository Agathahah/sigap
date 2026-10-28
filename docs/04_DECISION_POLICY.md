# Decision policy (phase 4 rules + phase 6 bands)

## Rule baseline log
Measured on training months 0-4 (675,666 applications, fraud 1.00%); month 5 is checked once per version.
Alerts = share of applications flagged by any rule.

| Date | Change in rules.yaml | Alerts | Hit rate | Recall | Note |
|---|---|---|---|---|---|
| 2026-10-28 | v0: template rules `device_seen_with_fraud`, `application_burst` | 0% / 0.21% | – / 0.43% | 0% / 0.1% | both retired: `device_fraud_count` is always 0; the burst rule flags traffic that is less risky than average (EDA F5) |
| 2026-10-28 | v1: five rules from EDA F1–F3 and F6 (combinations, no protected attributes) | 8.76% | 5.40% | 47.4% | month 5: 7.86% alerts, 6.80% hit rate, 45.2% recall; `ba_windows_no_history` alone gives 33.9% recall at 5.11% alerts |

## Cost assumptions (from configs/business.yaml)
All values are assumptions for the fictional Bank Nusa Digital (IDR), written 28 Oct 2026 before the replay.

| Assumption | Value | Reasoning / reference |
|---|---|---|
| Applications per day | 5,000 | Bank Jago added 2.9 million customers in 2025, about 7,900 a day ([Kontan, 12 Mar 2026](https://keuangan.kontan.co.id/news/bank-jago-catat-jumlah-nasabah-mencapai-182-juta-pada-2025)); a mid-size digital bank at ~60% of that |
| Review capacity | 300 a day = 6% | 10 analysts x 30 cases (about 14 minutes each, 7 productive hours) |
| Fraud loss per fraudulent account | Rp 13 million (3–25 million) | IASC (OJK): Rp 9 trillion reported losses across 681,890 reported accounts, Nov 2024–Dec 2025 ([Investortrust, 9 Jan 2026](https://investortrust.id/financial/90898/ojk-terima-411055-laporan-penipuan-transaksi-keuangan-kerugian-capai-rp-9-triliun)) |
| Review cost | Rp 20,000 (10–50 thousand) | Rp 10 million gross pay x 1.4 loaded / 147 hours ≈ Rp 1,600 a minute x 10 minutes + tooling; Jakarta minimum wage 2026 ≈ Rp 5.73 million as floor |
| Review catch rate | 70% (50–90%) | No public figure; document check plus call-back or video step |
| Genuine customer declined | Rp 500,000 (250,000–1.5 million) | Digital-bank acquisition cost in emerging markets US$15–50 (Quinlan & Associates via [Selular.id, 10 Aug 2023](https://selular.id/2023/08/4-alasan-mengapa-bank-digital-sulit-meraih-laba/)) plus margin |
| Genuine customer reviewed | Rp 50,000 (25–150 thousand) | 10% assumed to abandon x Rp 500,000; 68% of European consumers abandoned a financial application in a year ([Signicat, 2022](https://www.signicat.com/press-releases/the-battle-to-onboard-2022)) |

## Chosen policy
Bands chosen on month 5 by expected cost, with review capacity 6% and at most 1% automatic declines
(`reports/policy/base_policy.json`, model `base-20261028-0433-b4e83b`).

| t_review | t_decline | review rate | decline rate | fraud stopped | expected cost / 10k apps |
|---|---|---|---|---|---|
| 0.0125 | 0.0604 | 5.75% (month 5) · 6.05% (months 6–7) | 0.75% · 0.87% | 44.1% · 44.6% | Rp 1,081.5 million (months 6–7) |

Calibrated score 0.0125 means about 1.3% fraud probability: roughly the top 6% of applications go to review;
0.0604 (about 6%, four times the months 6–7 fraud rate) is declined.

## Champion (rules) vs challenger (model + bands), months 6-7 replay
205,011 applications, fraud 1.40%. Offline replay, not live traffic (`reports/policy/champion_challenger_base.csv`).

| Arm | Review | Decline | Genuine declined / 10k | Fraud stopped | Cost / 10k apps | Saving / day vs rules | Analysts needed |
|---|---|---|---|---|---|---|---|
| Rules (champion) | 8.23% | 0% | 0 | 31.9% | Rp 1,297.9 million | – | 14 |
| **Model + bands (challenger)** | 6.05% | 0.87% | 62 | 44.6% | Rp 1,081.5 million | Rp 108.2 million | 11 |
| Model, no decline limit | 6.24% | 4.80% | 413 | 60.8% | Rp 964.6 million | Rp 166.7 million | 11 |
| Approve all | 0% | 0% | 0 | 0% | Rp 1,825.0 million | −Rp 263.5 million | 0 |

Genuine applicants held (review or decline): rules 6.29% under 50 vs 14.99% aged 50+ (ratio 0.42); challenger
5.61% vs 9.40% (ratio 0.60). Both arms exceed the 300-review capacity on months 6–7 (rules by 37%, the challenger by
1%, because the score distribution shifted after month 5).

## Sensitivity
Thresholds re-chosen on month 5 for each value, replayed on months 6–7. Saving = rules cost − challenger cost per
10,000 applications; base case Rp 216.5 million (`reports/policy/sensitivity_base.csv`).

| Assumption changed | low | base | high | Does the recommendation change? |
|---|---|---|---|---|
| Fraud loss per account (Rp 3 / 13 / 25 million) | Rp 43.3 m | Rp 216.5 m | Rp 431.3 m | No |
| Review catch rate (50 / 70 / 90%) | Rp 244.4 m | Rp 216.5 m | Rp 189.8 m | No |
| Genuine customer declined (Rp 0.25 / 0.5 / 1.5 million) | Rp 232.0 m | Rp 216.5 m | Rp 161.6 m | No |
| Genuine customer reviewed (Rp 25 / 50 / 150 thousand) | Rp 211.3 m | Rp 216.5 m | Rp 237.2 m | No |
| Review cost (Rp 10 / 20 / 50 thousand) | Rp 214.3 m | Rp 216.5 m | Rp 223.0 m | No |
| Review capacity (4 / 6 / 8%) | Rp 122.0 m | Rp 216.5 m | Rp 281.8 m | No |
| Automatic decline limit (0 / 1 / 3%) | Rp 109.0 m | Rp 216.5 m | Rp 319.8 m | No; at 3% the bank declines 250 genuine applicants per 10k |

The model is cheaper than the rules in every case. What the assumptions do change is the size of the decline band:
it is the least certain part of the policy and is capped until a live test measures its precision.
