# PRD · SIGAP (Sistem Identifikasi Gejala Anomali Pengajuan)

## 1. Problem
Bank Nusa Digital (a fictional Indonesian digital bank) opens savings accounts entirely through its app.
Fraudsters use stolen or synthetic identities to open accounts that are later used as mule accounts to move
the proceeds of scams. Every application has to be decided within seconds.

Fraud is a two-sided cost:
- **Fraud let through**: losses passed through mule accounts, investigation effort, reputational damage and the
  anti-fraud obligations of POJK 12/2024.
- **Genuine customers stopped**: a manual review adds friction and drop-off; a wrong decline loses a customer
  whose acquisition has already been paid for.

The bank currently relies on hand-written rules. SIGAP replaces "rules only" with a measured decision policy:
approve, send to review, or decline, chosen by expected cost within the review team's capacity.

## 2. Users and decisions
| User | Decision they make | What they need from SIGAP |
|---|---|---|
| Fraud analyst | Approve or reject an application in the review queue | Score, top reasons, similar past cases, policy references, a clear queue |
| Head of fraud / risk | Set thresholds and review capacity | Cost vs. capacity trade-off, monthly KPIs, drift and data-incident alerts |
| Product / growth | Accept onboarding friction | Approval rate, review rate, time to decision |
| Data science on duty | Retrain or roll back the model | Drift (PSI), late-label performance, release-gate results |

## 3. Success metrics
| Metric | Definition | Target | Why this target |
|---|---|---|---|
| Fraud caught at 5% FPR | TPR on test months 6–7 at the threshold fixed on month 5 | ≥ 0.40 | Evaluation protocol of the BAF paper; release gate in `configs/gate.yaml` |
| Precision–recall | PR-AUC on test months | ≥ 0.10 | Fraud prevalence is ~1%; a random model scores ~0.01 |
| Review rate | Share of applications sent to review | ≤ review capacity | Analysts × reviews per analyst per day (`configs/business.yaml`) |
| Expected cost per 10k applications | Decision-policy cost model | Lower than the rule baseline | The model must beat today's process, not zero |
| Age fairness | FPR ratio, customers ≥ 50 vs. < 50 (predictive equality) | ≥ 0.80 (proposed) | Friction should not fall disproportionately on one age group; final value in ADR 0005 |
| Scoring latency | p95 for one application | < 100 ms | Account opening is instant |
| Duplicate alerts | Same event sent to analysts more than once | 0 | Alert fatigue makes a team ignore real incidents |
| Copilot quality | Golden-set pass rate; injection cases followed | ≥ 0.80; 0 followed | Analysts must be able to trust every number it states |

Targets are fixed before test results are seen and are never lowered afterwards.

## 4. Scope
**In:** monthly batch ingestion with late labels, data contract and quarantine, Spark pipeline into a Postgres
star schema, rule baseline, gradient-boosted model with calibration, reason codes and an age-fairness check,
cost-based decision bands under review capacity, champion–challenger replay, scoring API, drift monitoring,
alerting and review-case workflow for analysts (WhatsApp), and a read-only analyst copilot.

**Out (v2 candidates):** real-time streaming, device fingerprinting and graph features (shared devices and
e-mails), live A/B traffic split, a managed cloud ML platform.

## 5. Constraints and risks
- **Late labels:** fraud is confirmed about two months after the application; the most recent months always
  look cleaner than they are.
- **Class imbalance:** ~1% fraud; accuracy is meaningless.
- **Dataset:** BAF is synthetic data generated from a real bank's applications (CC BY-NC-SA 4.0). Raw rows are not
  redistributed; the public demo uses BAF-shaped synthetic data.
- **No money amounts:** all costs are written assumptions with a sensitivity range.
- **Protected attributes:** customer_age, income and employment_status are never sent to the copilot or to
  messaging channels.
- **Selective labels:** analyst decisions exist only for reviewed applications and are not used as training labels
  on their own.

## 6. Milestones
| Phase | Deliverable | Date |
|---|---|---|
| 0–2 | PRD, ERD, data card, EDA findings | 22–28 Oct 2026 |
| 3–5 | Warehouse, rule baseline, features, model and release gate | 29 Oct – 5 Nov |
| 6–8b | Decision policy and memo, API in Docker, monitoring replay, analyst alerts | 5–11 Nov |
| 9–10 | Copilot and evaluation, model comparison, README and model card | 12–19 Nov |
