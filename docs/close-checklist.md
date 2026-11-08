# Month-End Close Checklist — Finance Reconciliation Agent

SYNTHETIC CHECKLIST ONLY. This checklist was written fresh for this
project as the local knowledge base for retrieval. It is not copied from
any real company close process.

## Step 1 — Load both files

Check that the ledger CSV and the bank CSV both loaded, count the rows in
each, and stop if either file is empty or a required column is missing.
Required ledger columns: ledger_id, date, vendor, amount, reference.
Required bank columns: bank_id, date, payee, amount, reference.

## Step 2 — Match every ledger row

For each ledger row, look up its reference in the bank file and apply the
matching rules in docs/matching-rules.md. Count exact matches, amount
mismatches, date differences, and rows missing in the bank.

## Step 3 — Find bank-only rows

List every bank row whose reference appears in no ledger row. These are
`missing_in_ledger` exceptions. Bank fees and interest are common
examples, but do not assume that — list them and let a human decide.

## Step 4 — Draft an explanation for every exception

For each mismatch or missing row, draft one short plain-English
explanation that states the two amounts or dates, the difference, and
the rule that applied. Every explanation must cite the ledger row id
and bank row id it refers to.

## Step 5 — Human checkpoint (mandatory)

Stop before saving anything. Show the summary counts and every exception
to a human reviewer. Do not write the audit file until the human confirms.
If the human rejects the run, save nothing and record the rejection.

## Step 6 — Write the audit file

After confirmation, write one audit JSON file containing: the summary
counts, every matched and unmatched item with its citations, the
assumptions made, the retrieved rule snippets, and the human decision
(confirmed or rejected, and who/when if known).

## Step 7 — Report what is still open

End with a short list of open exceptions — the rows a human still needs
to investigate — so nothing looks finished when it is not.
