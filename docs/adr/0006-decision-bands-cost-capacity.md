# ADR 0006 · Decision bands chosen by cost under review capacity

- Status: proposed
- Date: 2026-10-28

## Context
- The model gives a calibrated fraud probability; operations need one of three actions: approve instantly, send
  to review (analyst check or video verification), or decline.
- A review costs analyst time and some genuine customers abandon; a decline loses a genuine customer for good; an
  approved fraud becomes a mule account. These costs are not in BAF, so they are written assumptions with ranges
  (`configs/business.yaml`).
- The review team can handle about 6% of daily applications (10 analysts x 30 cases, 5,000 applications a day).
  A policy that sends more than that creates a backlog, which in practice means approving unchecked or making
  customers wait.

## Options considered
1. **One threshold at 0.5** — meaningless for a 1% base rate; almost nothing is flagged.
2. **One threshold at 5% FPR (review only)** — matches the model evaluation, but ignores money and capacity and
   never declines even near-certain fraud.
3. **Two thresholds chosen by expected cost, subject to the capacity limit** — the lowest total cost (fraud loss +
   review cost + customer friction) among threshold pairs whose review rate fits the team.
4. **Cost-optimal without a capacity limit** — cheapest on paper, but the review load would not be staffed.

## Decision
Choose `t_review` and `t_decline` on month 5 by minimising expected cost with `review_rate <= max_review_rate`
and at most 1% of applications declined automatically (`max_decline_rate`), apply them unchanged to months 6–7,
and compare with the rule baseline in an offline champion/challenger replay.

The decline guardrail was added after the first replay (28 Oct): with no limit, the base assumptions made the
optimiser decline 4.8% of applications, mostly genuine customers, because a fraud loss is assumed to cost 26 times
a lost customer. That trade-off is too uncertain to automate before a live test measures the decline precision.

## Consequences
- Every result is a scenario under stated assumptions; the sensitivity table shows where the recommendation flips,
  and the memo reports a range, not one saving.
- Decline thresholds depend heavily on `fraud_loss` and `good_decline_cost`; a decline band is used only where the
  expected fraud loss clearly outweighs losing a genuine customer.
- The bands are stored with the model (`models/current/policy.json`) so the API applies exactly what was evaluated.
- Monitor: daily review volume against capacity, decline rate, and the share of genuine applicants held by age
  group.
