# PRD · SIGAP

> Write this BEFORE any code (phase 0). One to two pages. Replace every prompt in _italics_.

## 1. Problem
_Who loses what today? A fictional Indonesian digital bank opens accounts online. Fraudsters open accounts
with stolen or synthetic identities (mule accounts). Describe the cost of fraud AND the cost of blocking
genuine customers._

## 2. Users and decisions
| User | Decision they make | What they need from SIGAP |
|---|---|---|
| Fraud analyst | _review a flagged application_ | _score, reasons, similar past cases, policy references_ |
| Head of fraud / risk | _set thresholds and review capacity_ | _cost vs capacity trade-off, monthly KPIs_ |
| Product / growth | _approval rate and onboarding friction_ | _approval rate, review rate, time to decision_ |

## 3. Success metrics
| Metric | Definition | Target | Why this target |
|---|---|---|---|
| Fraud caught at 5% FPR | TPR on test months 6-7 | _≥ ..._ | _BAF paper protocol_ |
| Review rate | share of applications sent to review | _≤ capacity_ | _analysts x reviews/day_ |
| Expected cost per 10k applications | phase 6 cost model | _lower than rule baseline_ | |
| FPR ratio by age (≥50 vs <50) | predictive equality | _≥ ..._ | _ADR 0005_ |
| API latency | p95 for one application | _< 100 ms_ | _instant account opening_ |
| Copilot golden-set pass rate | phase 9 | _≥ ..._ | |

## 4. Scope
- In: _..._
- Out (and why): _real-time streaming, device fingerprinting, graph features ... say what a v2 would add_

## 5. Constraints and risks
_Label lag (fraud confirmed weeks later), class imbalance (~1%), dataset licence, protected attributes,
synthetic-but-realistic data (BAF is privacy-preserving, generated from real data)._

## 6. Milestones
| Phase | Deliverable | Date |
|---|---|---|
| 0-2 | PRD, ERD, data card, EDA findings | |
| 3-4 | warehouse in Postgres, rule baseline, features | |
| 5-6 | model + gate, decision policy, business memo | |
| 7-8 | API in Docker, CI, monitoring replay, dashboard | |
| 9-10 | copilot + eval, README, model card, story | |
