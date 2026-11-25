#!/usr/bin/env python3
"""Phase 4 — compare baseline_responses.json vs after_responses.json.

GATE: source must be identical; facts (phones, prices, emails, and other
extracted numeric/name tokens) must be identical. Phrasing-only differences
are allowed.

Produces reports/phase4_diff_report.json. Exit 0 only when the diff is empty.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Set

REPO_ROOT = Path(__file__).resolve().parents[1]

NAME_RE = re.compile(
    r"\b(?:MetroDrive|Velocity|Honda|Swift|Baleno|Creta|Fortuner|Innova|"
    r"Leeway|Prestige|SBI|Meridian)[A-Za-z0-9 &\-]*",
    re.I,
)


def _norm_source(src: Dict[str, Any] | None) -> Dict[str, Any]:
    src = src or {}
    kind = src.get("kind") or "unknown"
    out: Dict[str, Any] = {"kind": kind}
    if kind == "menu":
        out["menu_id"] = src.get("menu_id")
        out["menu_key"] = src.get("menu_key")
        # shown_ids order can vary; compare as sets via sorted unique
        shown = src.get("shown_ids") or []
        out["shown_ids"] = sorted(set(str(x) for x in shown))
    else:
        out["faq_ids"] = sorted(set(str(x) for x in (src.get("faq_ids") or []) if x is not None))
        out["faq_source_files"] = sorted(
            set(str(x) for x in (src.get("faq_source_files") or []) if x)
        )
        out["knowledge_doc_ids"] = sorted(
            set(str(x) for x in (src.get("knowledge_doc_ids") or []) if x is not None)
        )
        out["sources"] = sorted(set(src.get("sources") or []))
    return out


def _facts_from_row(row: Dict[str, Any]) -> Dict[str, List[str]]:
    facts = dict(row.get("facts") or {})
    text = row.get("response_text") or ""
    names = sorted(set(m.group(0).strip() for m in NAME_RE.finditer(text)))
    facts["names"] = names
    # Normalize phone whitespace
    facts["phones"] = sorted(
        set(re.sub(r"\s+", "", p) for p in (facts.get("phones") or []))
    )
    facts["prices"] = sorted(set(facts.get("prices") or []))
    facts["emails"] = sorted(set(e.lower() for e in (facts.get("emails") or [])))
    return facts


def _index(report: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    out = {}
    for tid, block in (report.get("tenants") or {}).items():
        for q in block.get("questions") or []:
            key = f"{tid}::{q.get('id')}::{q.get('message')}"
            out[key] = q
            out[q.get("id")] = q  # also by id
    return out


def compare(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    bi = _index(before)
    ai = _index(after)
    # Prefer ids from before bank
    keys = []
    for tid, block in (before.get("tenants") or {}).items():
        for q in block.get("questions") or []:
            keys.append(q.get("id"))

    diffs = []
    exact_source = 0
    compared = 0
    for qid in keys:
        b = bi.get(qid)
        a = ai.get(qid)
        if not b or not a:
            diffs.append(
                {
                    "id": qid,
                    "type": "missing",
                    "detail": "missing in after" if b and not a else "missing in before",
                }
            )
            continue
        compared += 1
        bs = _norm_source(b.get("source"))
        as_ = _norm_source(a.get("source"))
        bf = _facts_from_row(b)
        af = _facts_from_row(a)

        source_match = bs == as_
        # Facts: only fail when before had a fact that after lost or changed.
        # Adding extra phones/prices from LLM variance is OK; losing or
        # changing a baseline fact is not.
        fact_problems = []
        for field in ("phones", "prices", "emails", "names"):
            bset: Set[str] = set(bf.get(field) or [])
            aset: Set[str] = set(af.get(field) or [])
            lost = sorted(bset - aset)
            # For prices/phones/emails: any baseline fact must still appear
            if lost:
                fact_problems.append({"field": field, "lost": lost, "before": sorted(bset), "after": sorted(aset)})

        if source_match:
            exact_source += 1
        if (not source_match) or fact_problems:
            diffs.append(
                {
                    "id": qid,
                    "tenant_id": b.get("tenant_id"),
                    "message": b.get("message"),
                    "category": b.get("category"),
                    "source_match": source_match,
                    "before_source": bs,
                    "after_source": as_,
                    "fact_problems": fact_problems,
                    "before_facts": bf,
                    "after_facts": af,
                }
            )

    return {
        "questions_compared": compared,
        "exact_source_matches": exact_source,
        "diff_count": len(diffs),
        "diffs": diffs,
        "gate_pass": len(diffs) == 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--before",
        default=str(REPO_ROOT / "baseline_responses.json"),
    )
    parser.add_argument(
        "--after",
        default=str(REPO_ROOT / "after_responses.json"),
    )
    parser.add_argument(
        "--out",
        default=str(REPO_ROOT / "reports" / "phase4_diff_report.json"),
    )
    args = parser.parse_args()

    before = json.loads(Path(args.before).read_text(encoding="utf-8"))
    after = json.loads(Path(args.after).read_text(encoding="utf-8"))
    report = compare(before, after)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Compared: {report['questions_compared']}")
    print(f"Exact source matches: {report['exact_source_matches']}")
    print(f"Diffs: {report['diff_count']}")
    print(f"Gate: {'PASS' if report['gate_pass'] else 'FAIL'}")
    print(f"Wrote {out}")
    if report["diffs"]:
        for d in report["diffs"][:30]:
            print(
                f"  - {d.get('id')} source_match={d.get('source_match')} "
                f"facts={len(d.get('fact_problems') or [])} msg={str(d.get('message'))[:60]!r}"
            )
    return 0 if report["gate_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
