#!/usr/bin/env python3
"""Evaluate Masar review and personalize flows against fixed and adversarial cases."""
from __future__ import annotations

import json
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

import httpx

BASE_URL = "http://localhost:8000"
ROOT = Path(__file__).resolve().parent
CASES_PATH = ROOT / "masar_evaluation_cases.json"

_TRANSLIT_MAP = str.maketrans({
    "ا": "a", "أ": "a", "إ": "i", "آ": "aa", "ب": "b", "ت": "t", "ث": "th",
    "ج": "j", "ح": "h", "خ": "kh", "د": "d", "ذ": "dh", "ر": "r", "ز": "z",
    "س": "s", "ش": "sh", "ص": "s", "ض": "d", "ط": "t", "ظ": "z", "ع": "a",
    "غ": "gh", "ف": "f", "ق": "q", "ك": "k", "ل": "l", "م": "m", "ن": "n",
    "ه": "h", "و": "w", "ي": "y", "ى": "a", "ة": "h",
})


def _load_cases() -> dict:
    return json.loads(CASES_PATH.read_text())


def _normalize_text(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return " ".join("".join(ch if ch.isalnum() or ch.isspace() else " " for ch in folded.lower()).split())


def _transliterate_arabic(value: str) -> str:
    return _normalize_text(value.translate(_TRANSLIT_MAP))


def _text_tokens(value: str) -> set[str]:
    return {token for token in _normalize_text(value).split() if len(token) >= 4}


def _contains_keyword(text: str, idea_text: str) -> bool:
    text_norm = _normalize_text(text)
    idea_norm = _normalize_text(idea_text)
    text_tokens = _text_tokens(text_norm)
    idea_tokens = _text_tokens(idea_norm)
    if text_tokens & idea_tokens:
        return True

    translit_text = _transliterate_arabic(text)
    translit_tokens = _text_tokens(translit_text)
    if translit_tokens & idea_tokens:
        return True

    for token in idea_tokens:
        if any(
            SequenceMatcher(None, token, candidate).ratio() >= 0.82
            for candidate in text_tokens | translit_tokens
        ):
            return True
    return False


def _score_caption_engagement(report: dict) -> int:
    score = 1
    if "|" in str(report.get("caption", "")):
        score += 1
    if len(str(report.get("hook", "")).split()) >= 8:
        score += 1
    if len(report.get("hashtags", [])) >= 4:
        score += 1
    if any(word in str(report.get("caption", "")).lower() for word in ["apply", "watch", "impact", "prototype", "innovation"]):
        score += 1
    return min(score, 5)


def _score_cultural_appropriateness(report: dict) -> int:
    score = 1
    if report.get("language_direction") in {"rtl", "ltr"}:
        score += 1
    if "#StarsOfScience" in report.get("hashtags", []):
        score += 1
    if report.get("recommended_day_window") and report.get("timing_rationale"):
        score += 1
    if len(report.get("evidence", [])) >= 5:
        score += 1
    return min(score, 5)


def _score_cta_clarity(report: dict, goal: str) -> int | None:
    if goal != "applications":
        return None
    score = 1
    combined = " ".join([report.get("caption", ""), *report.get("dos", []), report.get("hook", "")]).lower()
    if "apply" in combined or "التقديم" in combined:
        score += 2
    if "who should" in combined or "builder" in combined or "المبتكر" in combined:
        score += 1
    if "now" in combined or "urgent" in combined or "الآن" in combined:
        score += 1
    return min(score, 5)


def _score_review_case(case: dict, payload: dict) -> tuple[bool, list[str]]:
    errors: list[str] = []
    rankings = payload.get("rankings", [])
    if not rankings:
        return False, ["no rankings returned"]

    top = rankings[0]
    if len(rankings) != 5:
        errors.append(f"ranking count {len(rankings)} != 5")

    if case.get("expected_any_platforms") and top.get("platform") not in case["expected_any_platforms"]:
        errors.append(f"top platform {top.get('platform')!r} not in {case['expected_any_platforms']!r}")

    top_evidence = top.get("top_evidence", [])
    if case.get("min_top_evidence") and len(top_evidence) < case["min_top_evidence"]:
        errors.append(f"top evidence count {len(top_evidence)} < {case['min_top_evidence']}")

    why = str(top.get("why", ""))
    if len(why.split()) < 8:
        errors.append("top why line too short")

    if "country" in top or "country_name" in top:
        errors.append("review ranking still exposes country fields")
    if not top.get("report_available"):
        errors.append("top ranking should expose report availability")
    if not top.get("score_breakdown"):
        errors.append("top ranking missing score breakdown")

    for evidence in top_evidence:
        if not evidence.get("claim") or not evidence.get("source"):
            errors.append("top evidence item missing claim/source")
            break

    return not errors, errors


def _score_personalize_case(case: dict, payload: dict) -> tuple[bool, list[str], list[dict]]:
    errors: list[str] = []
    diagnostics: list[dict] = []
    reports = payload.get("reports", [])
    expected_reports = len(case["countries"]) * len(case["platforms"])
    if len(reports) != expected_reports:
        return False, [f"report count {len(reports)} != {expected_reports}"], diagnostics

    seen_captions: set[str] = set()
    for report in reports:
        caption = str(report.get("caption", "")).strip()
        if not caption:
            errors.append(f"{report['country']}/{report['platform']}: empty caption")
        if not _contains_keyword(caption, case["idea_text"]):
            errors.append(f"{report['country']}/{report['platform']}: caption not topic-aware")
        if case.get("min_evidence_per_report") and len(report.get("evidence", [])) < case["min_evidence_per_report"]:
            errors.append(
                f"{report['country']}/{report['platform']}: evidence {len(report.get('evidence', []))} < {case['min_evidence_per_report']}"
            )
        if len(report.get("dos", [])) < 2 or len(report.get("donts", [])) < 2:
            errors.append(f"{report['country']}/{report['platform']}: incomplete do/don't guidance")
        if not str(report.get("recommended_format", "")).strip():
            errors.append(f"{report['country']}/{report['platform']}: empty recommended_format")
        if not str(report.get("hook", "")).strip():
            errors.append(f"{report['country']}/{report['platform']}: empty hook")
        if not report.get("recommended_day_window") or not report.get("timing_rationale"):
            errors.append(f"{report['country']}/{report['platform']}: missing timing metadata")

        diagnostics.append({
            "country": report["country"],
            "platform": report["platform"],
            "caption_engagement": _score_caption_engagement(report),
            "cultural_appropriateness": _score_cultural_appropriateness(report),
            "cta_clarity": _score_cta_clarity(report, case["goal"]),
        })
        seen_captions.add(caption)

    if len(seen_captions) < max(1, len(reports) // 2):
        errors.append("too many duplicated captions across reports")

    return not errors, errors, diagnostics


def _run_adversarial_cases(client: httpx.Client, cases: dict) -> tuple[list[dict], list[dict]]:
    review_results = []
    for case in cases.get("review", []):
        response = client.post("/api/review", json={"idea_text": case["idea_text"], "goal": case["goal"]})
        response.raise_for_status()
        payload = response.json()
        rankings = payload.get("rankings", [])
        passed = bool(rankings) and len(rankings) == 5
        review_results.append({"id": case["id"], "passed": passed})

    personalize_results = []
    personalize_payloads: dict[str, dict] = {}
    for case in cases.get("personalize", []):
        response = client.post("/api/personalize", json={
            "idea_text": case["idea_text"],
            "goal": case["goal"],
            "countries": case["countries"],
            "platforms": case["platforms"],
        })
        response.raise_for_status()
        payload = response.json()
        personalize_payloads[case["id"]] = payload
        reports = payload.get("reports", [])
        captions = [report.get("caption", "") for report in reports]
        passed = bool(reports) and len(set(captions)) == len(captions)
        personalize_results.append({"id": case["id"], "passed": passed})

    variant_a = personalize_payloads.get("personalize-adv-02-same-topic-variant-a", {}).get("reports", [])
    variant_b = personalize_payloads.get("personalize-adv-03-same-topic-variant-b", {}).get("reports", [])
    if variant_a and variant_b:
        a_caption = variant_a[0].get("caption", "")
        b_caption = variant_b[0].get("caption", "")
        distinct = a_caption != b_caption
        personalize_results.append({"id": "personalize-adv-cache-key-separation", "passed": distinct})

    return review_results, personalize_results


def main() -> int:
    cases = _load_cases()
    client = httpx.Client(base_url=BASE_URL, timeout=60.0)

    try:
        client.get("/health").raise_for_status()
    except Exception as exc:
        print(f"Failed to reach backend at {BASE_URL}: {exc}", file=sys.stderr)
        return 1

    review_results = []
    for case in cases["review"]:
        response = client.post("/api/review", json={"idea_text": case["idea_text"], "goal": case["goal"]})
        response.raise_for_status()
        payload = response.json()
        passed, errors = _score_review_case(case, payload)
        review_results.append({"id": case["id"], "passed": passed, "errors": errors})

    personalize_results = []
    diagnostics: list[dict] = []
    for case in cases["personalize"]:
        response = client.post("/api/personalize", json={
            "idea_text": case["idea_text"],
            "goal": case["goal"],
            "countries": case["countries"],
            "platforms": case["platforms"],
        })
        response.raise_for_status()
        payload = response.json()
        passed, errors, case_diagnostics = _score_personalize_case(case, payload)
        personalize_results.append({"id": case["id"], "passed": passed, "errors": errors})
        diagnostics.extend([{"case_id": case["id"], **row} for row in case_diagnostics])

    adv_review, adv_personalize = _run_adversarial_cases(client, cases.get("adversarial", {}))

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

    print("\nDiagnostics:")
    for row in diagnostics:
        print(
            f"- {row['case_id']} {row['country']}/{row['platform']}: "
            f"engagement={row['caption_engagement']}, "
            f"cultural={row['cultural_appropriateness']}, "
            f"cta={row['cta_clarity']}"
        )

    print("\nAdversarial review:")
    for result in adv_review:
        print(f"- {'PASS' if result['passed'] else 'FAIL'} {result['id']}")

    print("\nAdversarial personalize:")
    for result in adv_personalize:
        print(f"- {'PASS' if result['passed'] else 'FAIL'} {result['id']}")

    print(
        f"\nSummary: review {review_passes}/{len(review_results)} passed, "
        f"personalize {personalize_passes}/{len(personalize_results)} passed, "
        f"adversarial review {sum(1 for r in adv_review if r['passed'])}/{len(adv_review)} passed, "
        f"adversarial personalize {sum(1 for r in adv_personalize if r['passed'])}/{len(adv_personalize)} passed"
    )

    all_passed = (
        review_passes == len(review_results)
        and personalize_passes == len(personalize_results)
        and all(result["passed"] for result in adv_review)
        and all(result["passed"] for result in adv_personalize)
    )
    return 0 if all_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
