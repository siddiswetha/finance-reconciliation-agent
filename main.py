#!/usr/bin/env python3
"""
Finance Reconciliation Agent — synthetic demo, standard library only.

What it does, in plain words:
  1. Loads a synthetic ledger CSV and a synthetic bank CSV.
  2. Matches rows by reference, using the rules in docs/matching-rules.md.
  3. Retrieves the relevant rule/checklist text from docs/ (local RAG:
     plain-text files, keyword scoring — no vector database, no API).
  4. Drafts a plain-English explanation for every exception, citing the
     source rows, using a local deterministic mock LLM client.
  5. STOPS for human confirmation before writing anything.
  6. Only after confirmation, writes an audit JSON with citations,
     assumptions, and the human decision.

No real LLM is called. No data leaves the machine. All data is SYNTHETIC.

Usage:
    python3 main.py                                  # interactive run
    python3 main.py --auto-confirm                   # human confirms via flag
    python3 main.py --ledger data/ledger.csv --bank data/bank.csv \
        --docs docs --output output/audit.json --auto-confirm
    python3 main.py --eval                           # run the eval set

Pluggable LLM interface:
    Implement LLMClient.explain(...) to plug in a real LLM API.
    See docs/prompts.md for the prompt templates. The default client
    (MockLLMClient) is deterministic and rule-based.
"""

import argparse
import csv
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

ASSUMPTIONS = [
    "All data is SYNTHETIC and invented for this demo; no real finance data is used.",
    "The 'reference' field is the primary match key (matching-rules.md Rule 1).",
    "A date difference of 1-2 days with an exact amount is noted, not treated as an error (Rule 4).",
    "An amount mismatch of any size is flagged, never rounded away (Rule 3).",
    "No match is ever guessed from a similar amount or vendor name (Rule 6).",
    "The mock LLM explains only what the rows and rules state; it never invents a reason for a difference.",
]


# ---------------------------------------------------------------- LLM client
class LLMClient:
    """Interface for a language-model client.

    A real implementation would fill the prompt templates in
    docs/prompts.md, call an LLM API, and return the model's text.
    It must NOT change the audit format or skip the human checkpoint.
    """

    def explain(self, exception, retrieved_snippets):
        """Return a plain-English explanation for one exception dict."""
        raise NotImplementedError


class MockLLMClient(LLMClient):
    """Local deterministic mock LLM client (used by default).

    Builds the explanation from the actual row values and the retrieved
    rule text. No API call, no randomness, same input -> same output.
    """

    def explain(self, exception, retrieved_snippets):
        status = exception["status"]
        ledger = exception.get("ledger_row") or {}
        bank = exception.get("bank_row") or {}
        rule = (retrieved_snippets[0]["text"] if retrieved_snippets else
                "See docs/matching-rules.md.")
        # Keep the rule snippet short so the audit file stays readable,
        # cutting at a word boundary so no sentence is cut mid-word.
        rule_flat = " ".join(rule.split())
        rule_short = rule_flat[:220]
        if len(rule_flat) > 220:
            rule_short = rule_short.rsplit(" ", 1)[0] + " ..."

        if status == "amount_mismatch":
            diff = round(float(ledger["amount"]) - float(bank["amount"]), 2)
            return (
                f"Ledger {ledger['ledger_id']} ({ledger['reference']}) records "
                f"${float(ledger['amount']):.2f} on {ledger['date']}, but bank "
                f"{bank['bank_id']} records ${float(bank['amount']):.2f} on "
                f"{bank['date']} — a difference of ${diff:.2f}. "
                f"Rule applied: {rule_short} "
                f"Reason unknown — needs human review. This item is not resolved."
            )
        if status == "date_difference":
            days = exception.get("date_difference_days", 0)
            return (
                f"Ledger {ledger['ledger_id']} ({ledger['reference']}) and bank "
                f"{bank['bank_id']} agree on the amount "
                f"${float(ledger['amount']):.2f}, but the dates differ: ledger "
                f"{ledger['date']}, bank {bank['date']} ({days} day(s) apart). "
                f"Rule applied: {rule_short} "
                f"This is noted, not treated as an error, and still shown for review."
            )
        if status == "missing_in_bank":
            return (
                f"Ledger {ledger['ledger_id']} ({ledger['reference']}) records "
                f"${float(ledger['amount']):.2f} on {ledger['date']} for "
                f"{ledger['vendor']}, but no bank row has that reference. "
                f"Rule applied: {rule_short} "
                f"It may not have cleared yet, or the bank record may be missing. "
                f"Reason unknown — needs human review. This item is not resolved."
            )
        if status == "missing_in_ledger":
            return (
                f"Bank {bank['bank_id']} ({bank['reference']}) records "
                f"${float(bank['amount']):.2f} on {bank['date']} for "
                f"{bank['payee']}, but no ledger row has that reference. "
                f"Rule applied: {rule_short} "
                f"It may be a bank fee, interest, or a payment never entered in "
                f"the ledger. Reason unknown — needs human review. "
                f"This item is not resolved."
            )
        return (
            f"Ledger {ledger.get('ledger_id', '?')} and bank "
            f"{bank.get('bank_id', '?')} match exactly. No action needed."
        )


class RealLLMClient(LLMClient):
    """Stub showing where a real LLM API would plug in. NOT used by default.

    To use it: read the API key from an environment variable at run time
    (never hard-code or commit a key), fill the prompt templates in
    docs/prompts.md, call the provider's API, and return the response
    text. This stub deliberately raises instead of calling anything, so
    a run can never silently pretend a real model was called.
    """

    def __init__(self, api_key_env="LLM_API_KEY"):
        self.api_key_env = api_key_env

    def explain(self, exception, retrieved_snippets):
        raise NotImplementedError(
            "RealLLMClient is a documented stub only. Set up an API key via "
            f"the {self.api_key_env} environment variable and implement the "
            "API call here. The default run uses MockLLMClient instead, and "
            "does not claim a real LLM was called."
        )


# ---------------------------------------------------------------- data loading
def load_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def parse_date(text):
    y, m, d = (int(part) for part in text.strip().split("-"))
    return date(y, m, d)


# ---------------------------------------------------------------- local RAG
def load_docs(docs_dir):
    """Load every .md file under docs_dir as {source, text} chunks."""
    docs = []
    for path in sorted(Path(docs_dir).glob("*.md")):
        text = path.read_text(encoding="utf-8")
        # Split on headings so retrieval returns a focused snippet.
        chunks = re.split(r"\n(?=#{1,3} )", text)
        for chunk in chunks:
            chunk = chunk.strip()
            if chunk:
                docs.append({"source": path.name, "text": chunk})
    return docs


def retrieve(query, docs, top_k=2):
    """Keyword retrieval: score chunks by shared word overlap with query."""
    stopwords = {"the", "a", "an", "and", "or", "of", "to", "in", "on",
                 "for", "is", "are", "by", "with", "no", "not", "it"}
    query_words = {w for w in re.findall(r"[a-z0-9]+", query.lower())
                   if w not in stopwords}
    scored = []
    for doc in docs:
        words = set(re.findall(r"[a-z0-9]+", doc["text"].lower()))
        score = len(query_words & words)
        if score:
            scored.append((score, doc))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [doc for _, doc in scored[:top_k]]


# ---------------------------------------------------------------- matching
def reconcile(ledger_rows, bank_rows):
    """Match ledger rows to bank rows. Returns (items, summary)."""
    bank_by_ref = {row["reference"]: row for row in bank_rows}
    ledger_refs = {row["reference"] for row in ledger_rows}
    items = []

    for ledger in ledger_rows:
        ref = ledger["reference"]
        bank = bank_by_ref.get(ref)
        if bank is None:
            items.append({
                "ledger_id": ledger["ledger_id"],
                "bank_id": None,
                "reference": ref,
                "status": "missing_in_bank",
                "ledger_row": ledger,
                "bank_row": None,
                "amount_difference": None,
                "date_difference_days": None,
            })
            continue
        amount_diff = round(float(ledger["amount"]) - float(bank["amount"]), 2)
        date_diff = abs((parse_date(ledger["date"]) -
                         parse_date(bank["date"])).days)
        if amount_diff != 0:
            status = "amount_mismatch"
        elif date_diff != 0:
            status = "date_difference"
        else:
            status = "matched"
        items.append({
            "ledger_id": ledger["ledger_id"],
            "bank_id": bank["bank_id"],
            "reference": ref,
            "status": status,
            "ledger_row": ledger,
            "bank_row": bank,
            "amount_difference": amount_diff if amount_diff != 0 else 0.0,
            "date_difference_days": date_diff,
        })

    for bank in bank_rows:
        if bank["reference"] not in ledger_refs:
            items.append({
                "ledger_id": None,
                "bank_id": bank["bank_id"],
                "reference": bank["reference"],
                "status": "missing_in_ledger",
                "ledger_row": None,
                "bank_row": bank,
                "amount_difference": None,
                "date_difference_days": None,
            })

    summary = {
        "ledger_rows": len(ledger_rows),
        "bank_rows": len(bank_rows),
        "matched": sum(1 for i in items if i["status"] == "matched"),
        "amount_mismatch": sum(1 for i in items if i["status"] == "amount_mismatch"),
        "date_difference": sum(1 for i in items if i["status"] == "date_difference"),
        "missing_in_bank": sum(1 for i in items if i["status"] == "missing_in_bank"),
        "missing_in_ledger": sum(1 for i in items if i["status"] == "missing_in_ledger"),
        "total_items": len(items),
        "open_exceptions": sum(1 for i in items if i["status"] != "matched"),
    }
    return items, summary


# ---------------------------------------------------------------- run
def run_reconciliation(ledger_path, bank_path, docs_dir, llm=None):
    """Run matching + retrieval + explanations. No file is written here."""
    llm = llm or MockLLMClient()
    ledger_rows = load_csv(ledger_path)
    bank_rows = load_csv(bank_path)
    docs = load_docs(docs_dir)
    items, summary = reconcile(ledger_rows, bank_rows)

    queries = {
        "matched": "exact match reference amount date",
        "amount_mismatch": "amount mismatch reference amounts differ rule",
        "date_difference": "date difference posting date lag rule",
        "missing_in_bank": "missing in bank ledger no bank row",
        "missing_in_ledger": "missing in ledger bank fee interest no ledger row",
    }
    for item in items:
        snippets = retrieve(queries[item["status"]], docs, top_k=2)
        item["retrieved_sources"] = [
            {"source": s["source"], "snippet": s["text"][:300]} for s in snippets
        ]
        item["explanation"] = llm.explain(item, snippets)
    return items, summary


def build_audit(items, summary, human_decision):
    return {
        "project": "finance-reconciliation-agent",
        "data_note": "SYNTHETIC data only — all ledger and bank rows are invented examples. No real finance data, no real company data.",
        "llm_note": "Explanations were drafted by the local deterministic MockLLMClient. No real LLM API was called.",
        "summary": summary,
        "assumptions": ASSUMPTIONS,
        "human_decision": human_decision,
        "items": [
            {
                "ledger_id": item["ledger_id"],
                "bank_id": item["bank_id"],
                "reference": item["reference"],
                "status": item["status"],
                "amount_difference": item["amount_difference"],
                "date_difference_days": item["date_difference_days"],
                "citations": {
                    "ledger_row": item["ledger_row"],
                    "bank_row": item["bank_row"],
                },
                "retrieved_sources": item["retrieved_sources"],
                "explanation": item["explanation"],
            }
            for item in items
        ],
        "open_exceptions": [
            item["reference"] for item in items if item["status"] != "matched"
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Finance Reconciliation Agent (synthetic demo)")
    parser.add_argument("--ledger", default=str(PROJECT_ROOT / "data" / "ledger.csv"))
    parser.add_argument("--bank", default=str(PROJECT_ROOT / "data" / "bank.csv"))
    parser.add_argument("--docs", default=str(PROJECT_ROOT / "docs"))
    parser.add_argument("--output", default=str(PROJECT_ROOT / "output" / "audit.json"))
    parser.add_argument("--auto-confirm", action="store_true",
                        help="Human confirms via this flag (use only when a human has reviewed the summary).")
    parser.add_argument("--eval", action="store_true", help="Run the eval set (see eval.py).")
    args = parser.parse_args(argv)

    if args.eval:
        import eval as eval_module
        return eval_module.main()

    items, summary = run_reconciliation(args.ledger, args.bank, args.docs)

    print("Finance Reconciliation Agent — SYNTHETIC data")
    print(f"Ledger rows: {summary['ledger_rows']}  Bank rows: {summary['bank_rows']}")
    print(f"Matched: {summary['matched']}  Amount mismatches: {summary['amount_mismatch']}  "
          f"Date differences: {summary['date_difference']}")
    print(f"Missing in bank: {summary['missing_in_bank']}  "
          f"Missing in ledger: {summary['missing_in_ledger']}")
    print(f"Open exceptions: {summary['open_exceptions']}")
    print()
    for item in items:
        if item["status"] != "matched":
            print(f"- [{item['status']}] {item['reference']}: {item['explanation']}")
    print()

    # ---- Human-in-the-loop checkpoint: STOP before saving anything. ----
    if args.auto_confirm:
        human_decision = "confirmed (operator passed --auto-confirm after reviewing the summary above)"
    else:
        answer = input("Human checkpoint: review the summary and exceptions above.\n"
                       "Type 'yes' to confirm and save the audit file, anything else to stop: ").strip().lower()
        if answer != "yes":
            print("Stopped by human decision. Nothing was saved.")
            return 2
        human_decision = "confirmed (typed 'yes' at the human checkpoint)"

    audit = build_audit(items, summary, human_decision)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(f"Audit written to {output_path}")
    print(f"Open exceptions still to investigate: {', '.join(audit['open_exceptions'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
