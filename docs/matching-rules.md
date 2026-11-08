# Matching Rules — Finance Reconciliation Agent

SYNTHETIC RULES ONLY. These rules were written fresh for this project. They
describe how the agent matches a ledger row to a bank row. They are not
copied from any real company policy.

## Rule 1 — Match on reference first

The `reference` field (for example INV-1001) is the primary key. Two rows
with the same reference are treated as the same transaction. Do not match
on vendor name alone, because two different payments can go to the same
vendor in the same week.

## Rule 2 — Exact match

A pair is an exact match when the reference, the amount, and the date are
all identical. Exact matches need no human review beyond the normal
human-in-the-loop confirmation of the whole run.

## Rule 3 — Amount mismatch

If the reference matches but the amounts differ by any amount, flag the
pair as `amount_mismatch`. Do not round the difference away. Record both
amounts and the difference in the audit file. An amount mismatch always
needs a human decision before it is treated as resolved.

## Rule 4 — Date difference

If the reference and amount match but the dates differ, flag the pair as
`date_difference`. A bank posting date can lag the ledger date by a few
days. Record both dates and the number of days between them. A date
difference of 1–2 days is noted, not treated as an error, but it is still
shown to the human reviewer.

## Rule 5 — Missing on one side

- A ledger row with no bank row for its reference is `missing_in_bank`.
  It may be a payment that has not cleared yet, or a missing bank record.
- A bank row with no ledger row for its reference is `missing_in_ledger`.
  It may be a bank fee, interest, or a payment that was never entered in
  the ledger.

Neither case is auto-resolved. Both are listed as exceptions.

## Rule 6 — Never invent a match

If no bank row shares the reference, do not guess a match from a similar
amount or a similar vendor name. Leave the row unmatched and explain why.

## Rule 7 — Every decision cites its rows

Every result in the audit file must cite the ledger row id and, where one
exists, the bank row id it was compared with, plus the rule number above
that decided the outcome.
