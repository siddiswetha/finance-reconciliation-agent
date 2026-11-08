#!/usr/bin/env python3
"""Eval runner for the Finance Reconciliation Agent.

Runs the test cases in evals/eval-set.csv against the real code in
main.py, writes the TRUE result of each test back into eval-set.csv
(result column) and into evals/eval-results.json, and prints a summary.

Pass bar for the whole set: 12/12 tests pass.
No result is invented: a test only passes if its check actually passes.
"""

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

import main as agent  # noqa: E402

EVAL_CSV = PROJECT_ROOT / "evals" / "eval-set.csv"
RESULTS_JSON = PROJECT_ROOT / "evals" / "eval-results.json"


def _by_ref(items, ref):
    return [i for i in items if i["reference"] == ref]


def run_tests():
    items, summary = agent.run_reconciliation(
        str(PROJECT_ROOT / "data" / "ledger.csv"),
        str(PROJECT_ROOT / "data" / "bank.csv"),
        str(PROJECT_ROOT / "docs"),
    )
    docs = agent.load_docs(str(PROJECT_ROOT / "docs"))
    results = {}

    results["E01"] = _by_ref(items, "INV-1001")[0]["status"] == "matched"

    m = _by_ref(items, "INV-1003")[0]
    results["E02"] = m["status"] == "amount_mismatch" and m["amount_difference"] == 10.00

    m = _by_ref(items, "INV-1008")[0]
    results["E03"] = m["status"] == "amount_mismatch" and m["amount_difference"] == 18.00

    results["E04"] = _by_ref(items, "INV-1005")[0]["status"] == "missing_in_bank"

    results["E05"] = _by_ref(items, "BANK-FEE-77")[0]["status"] == "missing_in_ledger"

    m = _by_ref(items, "INV-1006")[0]
    results["E06"] = m["status"] == "date_difference" and m["date_difference_days"] == 2

    m = _by_ref(items, "INV-1012")[0]
    results["E07"] = m["status"] == "date_difference" and m["date_difference_days"] == 1

    results["E08"] = (
        summary["matched"] == 8
        and summary["amount_mismatch"] == 2
        and summary["date_difference"] == 2
        and summary["missing_in_bank"] == 2
        and summary["missing_in_ledger"] == 2
        and summary["open_exceptions"] == 8
        and summary["total_items"] == 16
    )

    top = agent.retrieve("amount mismatch reference amounts differ rule", docs, top_k=1)
    results["E09"] = bool(top) and top[0]["source"] == "matching-rules.md"

    top = agent.retrieve("month end close checklist human checkpoint", docs, top_k=1)
    results["E10"] = bool(top) and top[0]["source"] == "close-checklist.md"

    m = _by_ref(items, "INV-1003")[0]
    expl = m["explanation"]
    results["E11"] = ("L003" in expl and "B003" in expl and "10.00" in expl
                      and "needs human review" in expl)

    # E12: human gate — run main.py as a subprocess, answer "no", check nothing is written.
    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / "audit.json"
        proc = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "main.py"),
             "--output", str(out_path)],
            input="no\n", text=True, capture_output=True, cwd=str(PROJECT_ROOT),
        )
        results["E12"] = proc.returncode == 2 and not out_path.exists()

    return results


def main():
    results = run_tests()

    # Write TRUE results back into eval-set.csv (result column).
    with open(EVAL_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        fieldnames = list(rows[0].keys()) if rows else []
    for row in rows:
        row["result"] = "pass" if results.get(row["test_id"]) else "fail"
    with open(EVAL_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    passed = sum(1 for v in results.values() if v)
    total = len(results)
    payload = {
        "pass_bar": "12/12 tests pass",
        "passed": passed,
        "total": total,
        "met_pass_bar": passed == total,
        "results": {k: ("pass" if v else "fail") for k, v in sorted(results.items())},
    }
    RESULTS_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    for test_id in sorted(results):
        print(f"{test_id}: {'pass' if results[test_id] else 'fail'}")
    print(f"\nEval result: {passed}/{total} passed. Pass bar: 12/12. "
          f"{'PASS BAR MET' if passed == total else 'PASS BAR NOT MET'}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
