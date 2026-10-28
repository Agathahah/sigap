# Memo to Head of Fraud · SIGAP recommendation

Bank Nusa Digital (fictional) · 28 October 2026 · offline replay on BAF Base months 6–7 (205,011 applications).
Money figures rest on written assumptions (`configs/business.yaml`) and are scenarios, not measured savings.

**Recommendation:** run the model-based policy as a challenger on 10% of account-opening traffic for four weeks,
with reviews for the riskiest 6% of applications and automatic declines capped at 1%, and keep today's rules on the
other 90%.

**Why:**
- **More fraud stopped with fewer reviews.** In the replay the challenger stops 44.6% of fraudulent applications
  against 31.9% for the rules, while reviewing 6.05% of applications instead of 8.23%
  (`reports/policy/champion_challenger_base.csv`). At the same review volume as the rules, the model finds 59% of
  fraud against 45% (`reports/model/base_metrics.json`, MLflow run `train-20261028-0433`).
- **It fits the team.** The rules need about 14 analysts for the 300-a-day review queue; the challenger needs 11,
  one more than today's 10, because volumes after the training period were slightly higher.
- **Less friction for genuine customers, more evenly spread.** The challenger holds 5.6% of genuine applicants under
  50 and 9.4% of those aged 50+; the rules hold 6.3% and 15.0%. 62 genuine applicants in 10,000 would be declined
  automatically; without the 1% cap it would be 413, which is why the cap is part of the recommendation.

**What it costs / saves (under stated assumptions):** Rp 43–431 million per 10,000 applications less than the rules,
Rp 216.5 million in the base case (about Rp 108 million a day at 5,000 applications a day). The range comes from
moving each assumption to its low and high value; the model is cheaper in every case
(`reports/policy/sensitivity_base.csv`). The widest uncertainty is the loss per fraudulent account.

**Risks and how we watch them:**
- **Drift:** fraud patterns and volumes move (month 6–7 fraud rate 1.40% vs 1.00% in training). Monthly PSI on the
  score and top features; thresholds re-checked against capacity every month.
- **Late labels:** fraud is confirmed about two months later, so recall and false-positive rates are only known
  with that delay; analyst outcomes give an early, partial signal for reviewed cases.
- **Fairness by age:** the false-positive rate for genuine applicants aged 50+ is 1.7 times that of younger
  applicants (ratio 0.58, release limit 0.50); reported monthly and a retraining trigger if it falls below 0.50.
- **Model or service failure:** if the scoring service is down or the model fails its monthly checks, traffic
  falls back to the current rules.

**What I need from you:**
1. Approval for a 10% challenger split for four weeks, with the decline cap at 1%.
2. One additional analyst (or overtime) for the review queue during the test, and agreement that analysts record
   an outcome for every reviewed case.
3. A loss figure per confirmed mule account from Finance, to replace the public proxy used here.
