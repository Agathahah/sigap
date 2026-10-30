# Policy corpus for the copilot (phase 9)

| File | What | Licence / status |
|---|---|---|
| `POJK-12-2024-strategi-anti-fraud.pdf` | POJK 12/2024 Penerapan Strategi Anti Fraud bagi Lembaga Jasa Keuangan | public regulation, `make docs-download`, or a browser download from the [regulation page](https://ojk.go.id/id/regulasi/Pages/Penerapan-Strategi-Anti-Fraud-Bagi-Lembaga-Jasa-Keuangan.aspx) when the site rejects scripts (not committed) |
| `sop_review_pembukaan_rekening.md` | review SOP of the fictional Bank Nusa Digital | fictional, written for this project |

`make rag-index` chunks every `.pdf` and `.md` here (except this README), embeds the chunks locally with
`intfloat/multilingual-e5-small` and stores them in `copilot.policy_chunks`. Nothing confidential from any
employer goes here.
