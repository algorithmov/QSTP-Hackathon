#!/usr/bin/env python3
"""Evaluate Masar review and personalize flows against fixed test cases."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

BASE_URL = "http://localhost:8000"
ROOT = Path(__file__).resolve().parent
CASES_PATH = ROOT / "masar_evaluation_cases.json"


def _load_cases() -> dict:
    return json.loads(CASES_PATH.read_text())


def _contains_keyword(text: str, idea_text: str) -> bool:
    text_lower = text.lower()
    for raw in idea_text.lower().replace("-", " ").split():
        token = raw.strip(".,:;!?()[]{}")
        if len(token) >= 5 and token in text_lower:
            return True
    return False


def _score_review_case(case: dict, payload: dict) -> tuple[bool, list[str]]:
    errors: list[str] = []
    rankings = payload.get("rankings", [])
    if not rankings:
        errors.append("no rankings returned")
        return False, errors

    top = rankings[0]
    if len(rankings) < 5:
        errors.append(f"only {len(rankings)} rankings returned")

    expected_scope = case.get("expected_scope")
    if expected_scope:
        scope_mode = (payload.get("review_scope") or {}).get("mode")
        if scope_mode != expected_scope:
            errors.append(f"scope {scope_mode!r} != {expected_scope!r}")

    expected_country = case.get("expected_country")
    if expected_country:
        scope_country = (payload.get("review_scope") or {}).get("country")
        if scope_country != expected_country:
            errors.append(f"scope country {scope_country!r} != {expected_country!r}")

    if top.get("platform") not in case["expected_any_platforms"]:
        errors.append(f"top platform {top.get('platform')!r} not in {case['expected_any_platforms']!r}")

    top_evidence = top.get("evidence", [])
    if len(top_evidence) < case["min_top_evidence"]:
        errors.append(f"top evidence count {len(top_evidence)} < {case['min_top_evidence']}")

    why = str(top.get("why", ""))
    if len(why.split()) < 8:
        errors.append("top why line too short")
    if not _contains_keyword(why, case["idea_text"]):
        errors.append("top why line does not reflect the idea topic")

    for evidence in top_evidence:
        if not evidence.get("claim") or not evidence.get("source"):
            errors.append("top evidence item missing claim/source")
            break

    return not errors, errors


def _score_personalize_case(case: dict, payload: dict) -> tuple[bool, list[str]]:
    errors: list[str] = []
    reports = payload.get("reports", [])
    expected_reports = len(case["countries"]) * len(case["platforms"])
    if len(reports) != expected_reports:
        errors.append(f"report count {len(reports)} != {expected_reports}")
        return False, errors

    seen_captions: set[str] = set()
    for report in reports:
        caption = str(report.get("caption", "")).strip()
        if not caption:
            errors.append(f"{report['country']}/{report['platform']}: empty caption")
        if not _contains_keyword(caption, case["idea_text"]):
            errors.append(f"{report['country']}/{report['platform']}: caption not topic-aware")
        if len(report.get("evidence", [])) < case["min_evidence_per_report"]:
            errors.append(
                f"{report['country']}/{report['platform']}: evidence {len(report.get('evidence', []))} < {case['min_evidence_per_report']}"
            )
        if len(report.get("dos", [])) < 2 or len(report.get("donts", [])) < 2:
            errors.append(f"{report['country']}/{report['platform']}: incomplete do/don't guidance")
        if not str(report.get("recommended_format", "")).strip():
            errors.append(f"{report['country']}/{report['platform']}: empty recommended_format")
        if not str(report.get("hook", "")).strip():
            errors.append(f"{report['country']}/{report['platform']}: empty hook")
        seen_captions.add(caption)

    if len(seen_captions) < max(1, len(reports) // 2):
        errors.append("too many duplicated captions across reports")

    return not errors, errors


def main() -> int:
    cases = _load_cases()
    client = httpx.Client(base_url=BASE_URL, timeout=60.0)

    try:
        health = client.get("/health")
        health.raise_for_status()
    except Exception as exc:
        print(f"Failed to reach backend at {BASE_URL}: {exc}", file=sys.stderr)
        return 1

    review_results = []
    for case in cases["review"]:
        response = client.post("/api/review", json={
            "idea_text": case["idea_text"],
            "goal": case["goal"],
        })
        response.raise_for_status()
        payload = response.json()
        passed, errors = _score_review_case(case, payload)
        review_results.append({"id": case["id"], "passed": passed, "errors": errors})

    personalize_results = []
    for case in cases["personalize"]:
        response = client.post("/api/personalize", json={
            "idea_text": case["idea_text"],
            "goal": case["goal"],
            "countries": case["countries"],
            "platforms": case["platforms"],
        })
        response.raise_for_status()
        payload = response.json()
        passed, errors = _score_personalize_case(case, payload)
        personalize_results.append({"id": case["id"], "passed": passed, "errors": errors})

    review_passes = sum(1 for result in review_results if result["passed"])
    personalize_passes = sum(1 for result in personalize_results if result["passed"])

    print("Review cases:")
    for result in review_results:
        status = "PASS" if result["passed"] else "FAIL"
        print(f"- {status} {result['id']}")
        for error in result["errors"]:
            print(f"  - {error}")

    print("\nPersonalize cases:")
    for result in personalize_results:
        status = "PASS" if result["passed"] else "FAIL"
        print(f"- {status} {result['id']}")
        for error in result["errors"]:
            print(f"  - {error}")

    print(
        f"\nSummary: review {review_passes}/{len(review_results)} passed, "
        f"personalize {personalize_passes}/{len(personalize_results)} passed"
    )

    return 0 if review_passes == len(review_results) and personalize_passes == len(personalize_results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
