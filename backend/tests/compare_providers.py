#!/usr/bin/env python3
"""Run all evaluation cases against a single provider and dump metrics as JSON."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

BASE_URL = "http://localhost:8000"
ROOT = Path(__file__).resolve().parent
CASES_PATH = ROOT / "masar_evaluation_cases.json"


def _contains_keyword(text: str, idea_text: str) -> bool:
    text_lower = text.lower()
    for raw in idea_text.lower().replace("-", " ").split():
        token = raw.strip(".,:;!?()[]{}")
        if len(token) >= 5 and token in text_lower:
            return True
    return False


def _run_review(client: httpx.Client, case: dict) -> dict:
    t0 = time.perf_counter()
    r = client.post("/api/review", json={"idea_text": case["idea_text"], "goal": case["goal"]})
    elapsed = round(time.perf_counter() - t0, 2)
    r.raise_for_status()
    payload = r.json()

    rankings = payload.get("rankings", [])
    top = rankings[0] if rankings else {}
    why = str(top.get("why", ""))
    top_evidence = top.get("evidence", [])

    errors = []
    if not rankings:
        errors.append("no rankings")
    if len(rankings) < 5:
        errors.append(f"only {len(rankings)} rankings")
    if top.get("platform") not in case["expected_any_platforms"]:
        errors.append(f"top platform {top.get('platform')!r} unexpected")
    if len(top_evidence) < case["min_top_evidence"]:
        errors.append(f"evidence {len(top_evidence)} < {case['min_top_evidence']}")
    if len(why.split()) < 8:
        errors.append("why too short")
    if why and not _contains_keyword(why, case["idea_text"]):
        errors.append("why not topic-aware")

    return {
        "id": case["id"],
        "passed": not errors,
        "errors": errors,
        "elapsed_s": elapsed,
        "top_platform": top.get("platform"),
        "top_score": top.get("fit_score"),
        "top_confidence": top.get("confidence"),
        "why_words": len(why.split()),
        "top_evidence_count": len(top_evidence),
        "total_rankings": len(rankings),
    }


def _run_personalize(client: httpx.Client, case: dict) -> dict:
    t0 = time.perf_counter()
    r = client.post("/api/personalize", json={
        "idea_text": case["idea_text"],
        "goal": case["goal"],
        "countries": case["countries"],
        "platforms": case["platforms"],
    })
    elapsed = round(time.perf_counter() - t0, 2)
    r.raise_for_status()
    payload = r.json()

    reports = payload.get("reports", [])
    expected = len(case["countries"]) * len(case["platforms"])
    errors = []
    caption_lengths = []
    evidence_counts = []

    if len(reports) != expected:
        errors.append(f"reports {len(reports)} != {expected}")
    for rep in reports:
        caption = str(rep.get("caption", "")).strip()
        caption_lengths.append(len(caption.split()))
        evidence_counts.append(len(rep.get("evidence", [])))
        if not caption:
            errors.append(f"{rep['country']}/{rep['platform']}: empty caption")
        if caption and not _contains_keyword(caption, case["idea_text"]):
            errors.append(f"{rep['country']}/{rep['platform']}: caption not topic-aware")
        if len(rep.get("evidence", [])) < case["min_evidence_per_report"]:
            errors.append(f"{rep['country']}/{rep['platform']}: evidence {len(rep.get('evidence',[]))} < {case['min_evidence_per_report']}")
        if len(rep.get("dos", [])) < 2 or len(rep.get("donts", [])) < 2:
            errors.append(f"{rep['country']}/{rep['platform']}: incomplete dos/donts")
        if not str(rep.get("recommended_format", "")).strip():
            errors.append(f"{rep['country']}/{rep['platform']}: empty format")
        if not str(rep.get("hook", "")).strip():
            errors.append(f"{rep['country']}/{rep['platform']}: empty hook")

    seen = {str(r.get("caption","")).strip() for r in reports}
    if len(seen) < max(1, len(reports) // 2):
        errors.append("too many duplicate captions")

    return {
        "id": case["id"],
        "passed": not errors,
        "errors": errors,
        "elapsed_s": elapsed,
        "report_count": len(reports),
        "avg_caption_words": round(sum(caption_lengths) / len(caption_lengths), 1) if caption_lengths else 0,
        "avg_evidence_count": round(sum(evidence_counts) / len(evidence_counts), 1) if evidence_counts else 0,
        "unique_captions": len(seen),
    }


def main() -> int:
    provider = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    cases = json.loads(CASES_PATH.read_text())
    client = httpx.Client(base_url=BASE_URL, timeout=90.0)

    client.get("/health").raise_for_status()

    results = {"provider": provider, "review": [], "personalize": []}

    for case in cases["review"]:
        res = _run_review(client, case)
        results["review"].append(res)
        status = "PASS" if res["passed"] else "FAIL"
        print(f"  [{status}] {res['id']} — {res['elapsed_s']}s  why={res['why_words']}w  ev={res['top_evidence_count']}", flush=True)

    for case in cases["personalize"]:
        res = _run_personalize(client, case)
        results["personalize"].append(res)
        status = "PASS" if res["passed"] else "FAIL"
        print(f"  [{status}] {res['id']} — {res['elapsed_s']}s  cap={res['avg_caption_words']}w  ev={res['avg_evidence_count']}", flush=True)

    out = ROOT / f"results_{provider}.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"\nSaved to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
