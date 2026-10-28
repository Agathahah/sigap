-- Decisions written by the scoring API. Run: make db-sql F=sql/checks/p7_decisions.sql

\echo '== decisions per model version and band =='
SELECT model_version, decision, count(*) AS n, round(avg(score)::numeric, 4) AS avg_score
FROM ops.decision_log
GROUP BY 1, 2
ORDER BY 1, 2;

\echo '== last 5 decisions (no personal fields are stored) =='
SELECT id, application_id, decision, round(score::numeric, 4) AS score, reasons, decided_at
FROM ops.decision_log
ORDER BY id DESC
LIMIT 5;
