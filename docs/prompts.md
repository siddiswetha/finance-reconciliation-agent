# Prompt Templates — Finance Reconciliation Agent

These are the prompt templates the agent sends to the language-model
client. The default client is a local deterministic mock (see main.py),
so no real model is called and no data leaves the machine. A real LLM
API would plug into the `LLMClient` interface in main.py using these
same templates.

## Template 1 — Explain one exception

```
You are a careful finance assistant. Explain this reconciliation
exception in plain English, in 2–3 sentences.

Ledger row: {ledger_row}
Bank row: {bank_row_or_none}
Matching rule applied: {rule_text}
Retrieved checklist snippet: {retrieved_snippet}

Rules for your answer:
- State both amounts and both dates when they exist.
- State the exact difference (amount difference in dollars, or days).
- Cite the ledger id and bank id.
- Do not invent a reason for the difference. If the reason is unknown,
  say "reason unknown — needs human review".
- Do not say the item is resolved.
```

## Template 2 — Summarise the run

```
You are a careful finance assistant. Summarise this reconciliation run
in plain English.

Summary counts: {summary_counts}
Open exceptions: {exception_count}
Assumptions: {assumptions}

Rules for your answer:
- List how many rows matched, mismatched, and were missing on each side.
- List the open exceptions by id only, with no extra commentary.
- Say clearly that a human must confirm before anything is saved.
```

## How the mock client uses these templates

The mock client in main.py does not call any API. It fills Template 1
with the real row values and the retrieved rule text, and returns a
deterministic explanation built from those values. That keeps the output
reproducible and auditable, and it shows exactly what prompt a real
model would receive.

## Plugging in a real LLM API

Implement the `LLMClient` interface in main.py (method
`explain(exception, retrieved_snippets) -> str`). Read the API key from
an environment variable at run time — never hard-code a key, never
commit one — send the filled Template 1 or 2, and return the model's
text unchanged. Keep the human checkpoint and the audit file exactly
as they are; swapping the client must not change the audit format.
