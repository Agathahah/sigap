# ADR 0002 · Temporal split, label lag and a threshold fixed at 5% FPR

- Status: proposed
- Date: 2026-10-28

## Context
- The model scores applications as they arrive; fraud is confirmed about two months later. Any evaluation that
  mixes months, or uses labels that would not have existed at scoring time, overstates performance.
- BAF has 8 months with a rising fraud rate (0.87–1.14% in months 0–4, 1.18% in month 5, 1.34–1.47% in 6–7):
  the test period is harder than the training period, which is what production looks like.
- The operations team feels the false-positive rate (genuine customers sent to review), not AUC.

## Options considered
1. **Random train/test split** — standard in tutorials; leaks future patterns into training and hides drift.
2. **Temporal split: train 0–4, validation 5, test 6–7** — mirrors deployment; one month to choose and calibrate,
   two unseen months to measure once.
3. **Rolling-origin backtest (retrain every month)** — the most realistic; several times the compute and harder to
   explain in one table. Kept as a later extension.
4. **Threshold by maximising F1 or Youden's J on test** — tunes on the data used to report results.

## Decision
Split by month (train 0–4, validation 5, test 6–7), build point-in-time features with a 2-month label lag, and set
the decision threshold at 5% FPR on month 5, applied unchanged to months 6–7.

## Consequences
- Month 5 is used three times (early stopping, calibration, threshold); months 6–7 are scored once, after the
  release gate limits were written.
- The test FPR can move away from 5% when the score distribution shifts; the gate caps it (max 6%) and the
  monthly PSI on the score watches it.
- Labels of months 6–7 arrive at months 8–9: the test is a backtest of that future, stated in the model card.
- The 5% FPR point follows the BAF paper protocol (Jesus et al., 2022), so results are comparable with it.
