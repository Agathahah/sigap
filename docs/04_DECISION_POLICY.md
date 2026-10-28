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
| t_review | t_decline | review rate | fraud stopped | expected cost / 10k apps |
|---|---|---|---|---|

## Champion (rules) vs challenger (model + bands), months 6-7 replay
_table from reports/policy/champion_challenger_<variant>.csv_

## Sensitivity
| Assumption changed | low | base | high | Does the recommendation change? |
|---|---|---|---|---|
