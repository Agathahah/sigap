# Interview story · SIGAP

## Two-minute version
At an Indonesian digital bank every account-opening application has to be decided in seconds, and fraudsters open
accounts with stolen or synthetic identities to use them as mule accounts. Rules alone catch too little and send
too many genuine customers to manual review. I built SIGAP to decide approve, review or decline on the BAF dataset,
1 million applications over 8 months, treated the way a bank would: monthly data drops, fraud labels that arrive
two months late, and a review team that can only check 6% of applications a day.

I started with a rules baseline, then trained a calibrated XGBoost model with a fairness gate by age. Instead of a
single threshold I chose approve/review/decline bands by expected cost under the review capacity. In a replay of
the last two months the model stops 45% of fraud against 32% for the rules while reviewing fewer applications.
I capped automatic declines at 1% after seeing that the pure cost optimum would decline mostly genuine customers.

Then I built what the fraud team needs around it: a scoring API, monthly drift and late-label monitoring, alerts
and review cases sent to analysts through n8n with decisions written back through an API, and a read-only analyst
copilot in LangGraph whose answers must be grounded in tool outputs, evaluated on a golden set and compared between
Claude and a local open-weight model.

## Stories (situation, what I did, result, what I learned)

1. **Labels arrive late.** Fraud is confirmed about two months after the application, so a random split would
   leak the future. I split by month, fixed the threshold on month 5 and tested on months 6–7, and built prior
   fraud rates only from labels known at t−2. Recall on the later months was 0.521, close to validation, and the
   test months were genuinely harder (fraud rate 1.40% vs 1.00% in training).
2. **The optimiser wanted to decline 4.8% of applicants.** With the base cost assumptions, minimising cost declined
   413 genuine applicants per 10,000. I added a 1% decline cap as a business guardrail and showed the trade-off
   in the memo: 62 genuine declines per 10,000 and still Rp 216.5 million cheaper than the rules per 10,000
   applications, in every sensitivity case.
3. **Fairness has a price, and I stated it.** The model trained on all features had an FPR ratio of 0.32 between
   applicants aged 50+ and younger ones. Reweighing (Kamiran and Calders) raised it to 0.58 on test at a cost of
   1.9 points of validation recall. In the monthly replay the ratio drifted down to 0.56, so it is monitored, not
   assumed solved.
4. **"Sent" is not "delivered".** WhatsApp alerts from the Meta test number were accepted by the API, so n8n
   acknowledged them, but the status webhook showed error 130497 (cross-border restriction for Indonesian users).
   Twelve alerts were marked handled that nobody had seen. I added a channel switch with e-mail as default, a
   runbook step to reopen alerts, and wrote that production should acknowledge on the delivered status.
5. **The evaluation caught a bug in my own guardrail.** The copilot retries once when an answer has numbers that
   no tool returned. In the golden-set run, five answers passed the graph's check but failed the evaluation's,
   because the retry message quoted the invented numbers and was counted as a source. I fixed it and added a
   regression test. Prompt v2 then passed 24 of 24 cases against 17 for v1 (McNemar p = 0.016).
6. **API or local model.** On the same golden set Claude Haiku 5.5 passed 24/24 and Hermes 3 8B on my laptop
   12/24, with p95 latency 6.7 s vs 31 s. The guardrails held with the weaker model, so its failures cost
   usefulness, not safety. At about 900 questions a day the API costs around USD 14 a month, so the decision
   turns on data residency (UU PDP) and vendor review, not on token cost.

## Questions I expect
- **Why not deep learning?** Tabular data at 1% prevalence, a need for calibrated probabilities and per-case
  reasons, and a logistic regression that was already close (month-5 recall 0.512 vs 0.518): gradient
  boosting is the defensible choice, and most of the gain came from the decision policy, not the algorithm.
- **How do you know the money figures?** I do not; they are scenarios from written assumptions with public
  reference points, and the recommendation holds across each assumption's low and high value.
- **What would you do with two more weeks?** Graph features (devices and e-mails shared across applications),
  a live challenger on 10% of traffic, and a stronger local model or a tool-routing step for small models,
  measured on new held-out cases.
