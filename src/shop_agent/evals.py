"""Score agent results (outbox/results.json) against expectations (evals/cases.json).

A tool group like "search_products|get_product" matches any of the names.
tools_ok: at least one successful call from each group.
tools_not_ok: no successful call from any group.
"""

import argparse
import json
import re
import sys
from pathlib import Path


def _norm(text: str) -> str:
    """Lowercase and collapse every kind of space (models emit NBSP, narrow NBSP...) to a plain one."""
    return re.sub(r"\s+", " ", text.replace("\u202f", " ").replace("\u00a0", " ")).lower()


def _ok_calls(result: dict) -> set[str]:
    return {a["tool"] for a in result["actions"] if not a["is_error"]}


def check(case: dict, result: dict | None) -> list[tuple[str, bool, str]]:
    if result is None:
        return [("result present", False, "agent produced no result for this email")]

    checks = []
    if "category" in case:
        checks.append(("category", result["category"] in case["category"],
                       f"got {result['category']}, want {'/'.join(case['category'])}"))
    if "needs_human" in case:
        checks.append(("needs_human", result["needs_human"] == case["needs_human"],
                       f"got {result['needs_human']}, want {case['needs_human']}"))

    ok = _ok_calls(result)
    for group in case.get("tools_ok", []):
        names = set(group.split("|"))
        checks.append((f"called {group}", bool(ok & names), f"successful calls: {sorted(ok) or 'none'}"))
    for group in case.get("tools_not_ok", []):
        names = set(group.split("|"))
        hit = ok & names
        checks.append((f"did not call {group}", not hit, f"called {sorted(hit)}"))

    reply = _norm(result["reply"])
    for text in case.get("reply_includes", []):
        checks.append((f"reply has '{text}'", _norm(text) in reply, "missing"))
    for text in case.get("reply_excludes", []):
        checks.append((f"reply avoids '{text}'", _norm(text) not in reply, "present"))

    checks.append(("finished", result["stop"] == "submitted", f"stop={result['stop']}"))
    return checks


def score(cases: list[dict], results: list[dict]) -> dict:
    by_id = {r["email_id"]: r for r in results}
    rows = []
    for case in cases:
        checks = check(case, by_id.get(case["id"]))
        rows.append({"id": case["id"], "passed": all(c[1] for c in checks), "checks": checks})
    passed = sum(r["passed"] for r in rows)
    total_checks = sum(len(r["checks"]) for r in rows)
    passed_checks = sum(c[1] for r in rows for c in r["checks"])
    return {"rows": rows, "passed": passed, "total": len(rows),
            "passed_checks": passed_checks, "total_checks": total_checks}


def report(s: dict) -> str:
    lines = []
    for row in s["rows"]:
        lines.append(f"{'PASS' if row['passed'] else 'FAIL'}  {row['id']}")
        for name, ok, detail in row["checks"]:
            if not ok:
                lines.append(f"      x {name}: {detail}")
    lines.append("")
    lines.append(f"Emails: {s['passed']}/{s['total']} fully correct, checks: {s['passed_checks']}/{s['total_checks']}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Score shop-agent results against eval cases.")
    parser.add_argument("results", nargs="?", default="outbox/results.json", type=Path)
    parser.add_argument("--cases", default="evals/cases.json", type=Path)
    args = parser.parse_args()

    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    results = json.loads(args.results.read_text(encoding="utf-8"))
    s = score(cases, results)
    print(report(s))
    sys.exit(0 if s["passed"] == s["total"] else 1)
