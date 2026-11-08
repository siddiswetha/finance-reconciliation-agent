# Finance Reconciliation Agent

A small agentic AI workflow that automates one slice of the Finance
month-end close: reconciling a ledger against bank statements. It
matches rows, flags mismatches, retrieves the relevant close rules from
a local knowledge base, drafts plain-English explanations that cite
their source rows, and **stops for a human to confirm before saving
anything**.

Built from scratch for a portfolio targeting an Associate AI Engineer,
Finance Transformation role. Python standard library only — no external
dependencies, no paid API key, no real model call.

## Synthetic-data note

**All data in this project is SYNTHETIC and invented.** The ledger and
bank CSVs contain made-up vendors, amounts, and references (for example
INV-1001, $1,250.00). There is no real finance data here and no real company
data. The files and the audit output say so explicitly.

## What it is, in plain words

Think of closing the books like checking a shopping list against a
receipt. The ledger is the shopping list — what the company thinks it
paid. The bank statement is the receipt — what actually left the
account. This agent lines the two up, item by item:

- Same reference, same amount, same date → **matched**.
- Same reference, different amount → **amount mismatch** (for example
  ledger $899.00, bank $889.00 — a $10.00 difference).
- Same reference and amount, different date → **date difference**
  (the bank posted it a day or two later).
- In the ledger but not in the bank → **missing in bank**.
- In the bank but not in the ledger → **missing in ledger** (for
  example a $45.00 bank fee).

For every exception it writes a short explanation that names the exact
rows it looked at, so a human can check its work instead of trusting it.

## How it works

1. **Ingest** — `main.py` loads `data/ledger.csv` (14 rows) and
   `data/bank.csv` (14 rows) with Python's `csv` module.
2. **Match** — Rows are matched on `reference` first, then amount and
   date, following the rules in `docs/matching-rules.md`. Nothing is
   ever guessed from a similar amount or vendor name.
3. **Retrieve (local RAG)** — The agent searches the plain-text rule
   files in `docs/` (`close-checklist.md`, `matching-rules.md`) by
   keyword overlap and attaches the most relevant snippets to each
   result. No vector database, no external service.
4. **Explain (pluggable LLM)** — Explanations are drafted through an
   `LLMClient` interface in `main.py`. The default client is
   `MockLLMClient`: a local, deterministic, rule-based client that
   builds the explanation from the real row values and the retrieved
   rule text. Prompt templates live in `docs/prompts.md`. A real LLM
   API would plug into the same interface (`RealLLMClient` is a
   documented stub that raises instead of calling anything) — swapping
   the client does not change the audit format or skip the human check.
   **No real LLM is called in this project, and nothing here claims
   one was.**
5. **Human-in-the-loop checkpoint** — The run prints a summary and
   every exception, then stops. It writes nothing until a human types
   `yes`, or passes `--auto-confirm` after reviewing the summary.
   Answering anything else stops the run and saves nothing.
6. **Audit** — After confirmation it writes `output/audit.json` with
   the summary counts, every item with its ledger/bank row citations,
   the retrieved rule snippets, the assumptions made, the explanations,
   the open exceptions, and the human decision.

## How to run

```bash
cd finance-reconciliation-agent
python3 main.py --auto-confirm        # run end-to-end and write output/audit.json
python3 main.py                       # interactive: type 'yes' at the checkpoint to save
python3 main.py --eval                # run the eval set (same as python3 eval.py)
python3 eval.py                       # run the eval set directly
```

Requirements: Python 3.10+ only. No packages to install, no API key.

## Project layout

```
finance-reconciliation-agent/
├── README.md
├── main.py                  # matching, RAG, mock LLM client, audit writer
├── eval.py                  # eval runner (updates evals/eval-set.csv)
├── .gitignore
├── data/
│   ├── ledger.csv           # synthetic ledger, 14 rows
│   └── bank.csv             # synthetic bank statement, 14 rows
├── docs/
│   ├── close-checklist.md   # month-end close checklist (retrieval source)
│   ├── matching-rules.md    # matching rules (retrieval source)
│   └── prompts.md           # prompt templates + real-LLM plug-in notes
├── evals/
│   ├── eval-set.csv         # 12 test cases with true results recorded
│   └── eval-results.json    # eval summary written by eval.py
└── output/
    └── audit.json           # written only after human confirmation
```

## How this fits Swetha's actual background

Author: Venkata Swetha Siddi. Actual resume: 4+ years in ML and analytics, enterprise networking, and cloud automation, now focused on AI/ML engineering and applied AI. Certified by Anthropic in Claude and the AI Fluency Framework (Claude 101 and AI Fluency Framework & Foundations, June 2026). Skills on that resume include ML evaluation, prompt engineering, Python, SQL, Azure, AWS, Terraform, Ansible, Docker, and Kubernetes. Experience on that resume: Network Engineer, Relic Solutions, Elmont, NY, Oct 2025–Feb 2026; Network Infrastructure Engineer, NWN Carousel, Jan–Jun 2025; System Engineer Intern, InStyle, Houston, Jun–Dec 2024; Data Scientist, Cognizant, Dec 2019–Apr 2022; Associate Engineer, Accenture, Jun 2018–Mar 2019.

How this project complements, and does not repeat, her existing projects: her existing work under github.com/networkwithswetha-alt includes an LLM Fine-Tuning with Eval Harness project and a Document Extraction Pipeline (LLM extraction into Pydantic-validated records, with one validation retry and a deterministic regex fallback). This reconciliation agent is a different step: it does not fine-tune a model and it does not extract documents. It takes already-structured ledger and bank rows, reconciles them, retrieves close rules, explains each exception with source citations, and stops for a human check before saving an audit file. It builds on the same strengths — ML evaluation, prompt engineering, and schema-validated, auditable outputs — applied to a Finance close workflow instead.

## Role skill mapping

| Finance AI Engineer need | How this project shows it |
|---|---|
| Automate Finance close / reconciliation | End-to-end ledger-to-bank matching workflow |
| Outputs explainable, auditable, reconciled | Every item cites ledger + bank rows and the rule applied; full audit JSON |
| Human-in-the-loop checkpoints | Mandatory checkpoint before any file is written; a "no" saves nothing |
| Documented assumptions | Assumptions listed in `main.py`, the README, and every audit file |
| Hands-on LLM APIs / prompt engineering | `LLMClient` interface + prompt templates in `docs/prompts.md`; mock client used by default, real-API plug-in documented |
| RAG | Local retrieval over `docs/` with cited snippets per item |
| Agent frameworks (concepts) | Tool-like steps (ingest → match → retrieve → explain → checkpoint → audit) composed as an agent workflow |
| Working Python | `main.py` + `eval.py`, standard library only, runnable with one command |
| Basic SQL | Matching logic mirrors a SQL-style join on `reference` (see "SQL equivalent" below); CSVs are the demo store |
| Evaluation, tracing, observability | 12-case eval set with a recorded pass bar; audit JSON is the trace |
| Finance / regulated-data care | Synthetic data only, no real data, explicit guardrails (see below) |

### SQL equivalent (for reference)

The core match is the same idea as this join — shown here so the logic
is easy to check, not executed by the project:

```sql
SELECT l.ledger_id, b.bank_id, l.reference,
       l.amount AS ledger_amount, b.amount AS bank_amount,
       l.amount - b.amount AS amount_difference
FROM ledger l
LEFT JOIN bank b ON b.reference = l.reference;
```

## Eval pass bar

**Pass bar: 12/12 tests pass.** The eval set (`evals/eval-set.csv`)
covers exact matches, both amount mismatches ($10.00 and $18.00),
missing rows on each side, both date differences (2 days and 1 day),
the full-run summary counts, both RAG retrieval checks, a grounded-
explanation check, and the human-gate check. `eval.py` runs the tests
against the real code and writes the true result of each test into the
`result` column — nothing is claimed that the run did not show.

## Risks and guardrails

- **A wrong match could hide a real error.** Guardrail: matching is
  by reference only; amount differences of any size are flagged; no
  match is guessed from similar amounts or names.
- **An LLM could invent a reason for a difference.** Guardrail: the
  mock client only states row values and the retrieved rule, and says
  "reason unknown — needs human review" when the reason is not in the
  data. A real model plugged in later must follow the same prompt
  rules in `docs/prompts.md`.
- **Automation could save a bad result.** Guardrail: the human
  checkpoint is mandatory. Nothing is written without confirmation,
  and a rejected run saves nothing.
- **Real finance data could leak.** Guardrail: all data here is
  synthetic and labelled as such. Never point this demo at real
  statements without adding access control, redaction, and a real
  review process first.
- **This is a demo, not production finance software.** It has no
  authentication, no database, and no handling for duplicates, refunds,
  multi-currency, or partial payments. Those are listed as future work,
  not silently assumed.

## Human-in-the-loop

The human reviewer sees the summary counts and every exception in
plain English before anything is saved, confirms with `yes` (or
`--auto-confirm` after reviewing), and their decision is recorded in
the audit file. The agent never treats an exception as resolved on its
own — open exceptions are listed at the end of every run.

## Staged release note

- **Stage 1 (this project):** Local demo on synthetic data, mock LLM,
  human checkpoint, audit JSON. No external calls, no deployment.
- **Stage 2 (next):** Plug in a real LLM API behind the same interface
  (key from an environment variable, never committed), add a small
  SQLite store instead of CSVs, and log every run for observability.
- **Stage 3 (later, with review):** Pilot on a small set of real,
  access-controlled close data with a finance reviewer signing off
  each run, before any wider rollout. No stage skips the human
  checkpoint.
