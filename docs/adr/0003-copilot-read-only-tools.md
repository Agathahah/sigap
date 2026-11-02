# ADR 0003 · Copilot reads data only through fixed, read-only tools (no free-form SQL)

- Status: accepted
- Date: 2026-10-29

## Context
- Analysts ask the same kinds of questions every day: why an application went to review, how a fraud rate moves
  by device or month, whether the model drifted, what POJK 12/2024 or the review SOP says. A copilot can answer
  in seconds what now takes a dashboard and a document search.
- In a bank the copilot must not become a new way to leak or change data. Three failure modes matter: the model
  invents a number; personal data reaches an external model API; text pasted by an analyst (a customer chat, an
  email) carries instructions aimed at the model (indirect prompt injection, Greshake et al. 2023).
- The warehouse holds protected attributes (age band, income decile, employment status, ADR 0005) and labels.

## Options considered
1. **Text-to-SQL** (the model writes SQL against the warehouse): flexible, but any column becomes reachable, a
   prompt injection can turn into a query, and results are hard to audit or test.
2. **Fixed tools with validated parameters** behind a read-only database role: five functions written and
   tested like any other code; the model only chooses a tool and its arguments.
3. **No data access, documents only (RAG):** safe, but cannot answer the most common questions (cases, KPIs).

## Decision
The copilot touches data only through five tools (`query_kpi`, `get_application`, `similar_cases`,
`search_policy`, `monitoring_status`), each a parameterized query with allowlisted arguments, run as the
`sigap_copilot` role that can read only the `copilot` views; the same tools are exposed over MCP.

## Consequences
- **Least privilege in the database, not only in the prompt:** `sigap_copilot` has SELECT on the `copilot`
  schema only, every transaction is read-only and statements stop after 5 s. The views leave out age band,
  income decile and employment status. No tool can approve, decline or edit anything.
- **Every number is checkable:** tools return small JSON with values rounded to 4 decimals; the graph's output
  guard rejects an answer whose numbers appear in no tool output (one retry, then a refusal).
- **Personal data:** the question is masked (e-mail, NIK, phone) before it reaches the model; tools never return
  names, NIK, phone numbers or e-mails because the warehouse does not hold them.
- **Injection:** a pattern match adds a warning to the model's instructions; the real defence is that the model
  has nothing harmful to call. Golden-set cases test both (category `injection`).
- **Harder:** a new kind of question needs a new tool (code, test, review), not just a prompt change. That is
  the intended cost.
- **Monitor:** tool errors per day, refusals for ungrounded numbers, questions stopped by the step limit or the
  daily budget, and the golden-set pass rate per prompt version (ADR 0004).

## References
- Greshake et al. (2023). Not what you've signed up for: compromising real-world LLM-integrated applications with
  indirect prompt injection. https://arxiv.org/pdf/2302.12173
- OWASP Top 10 for LLM Applications 2025 (LLM01 prompt injection, LLM06 excessive agency):
  https://genai.owasp.org/llm-top-10/
- POJK 12/2024 Penerapan Strategi Anti Fraud bagi Lembaga Jasa Keuangan (ojk.go.id)
- Model Context Protocol specification: https://modelcontextprotocol.io/specification
