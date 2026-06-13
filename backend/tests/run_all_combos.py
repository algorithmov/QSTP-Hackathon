#!/usr/bin/env python3
"""Run all evaluation cases across every provider combination.

Cycles through combinations by rewriting .env between runs, restarting
the backend each time.  Saves both summary metrics AND full response
payloads for deep analysis.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx

BASE_URL = "http://localhost:8000"
ROOT = Path(__file__).resolve().parent
BACKEND = ROOT.parent
CASES_PATH = ROOT / "masar_evaluation_cases.json"
ENV_PATH = BACKEND / ".env"
ENV_BACKUP = BACKEND / ".env.combo_backup"
RESULTS_DIR = ROOT / "combo_results"
RESULTS_DIR.mkdir(exist_ok=True)

# ── Combinations to test ─────────────────────────────────────────────
# Each combo sets LLM_PROVIDER_ORDER and optionally disables Fanar
# caption refinement for A/B comparison.
COMBOS = [
    {
        "name": "gemini-only",
        "LLM_PROVIDER_ORDER": "gemini",
        "fanar_captions": False,
        "label": "Gemini solo, no Fanar caption pass",
    },
    {
        "name": "groq-only",
        "LLM_PROVIDER_ORDER": "groq",
        "fanar_captions": False,
        "label": "Groq solo, no Fanar caption pass",
    },
    {
        "name": "fanar-only",
        "LLM_PROVIDER_ORDER": "fanar",
        "fanar_captions": False,
        "label": "Fanar solo (everything through Fanar)",
    },
    {
        "name": "gemini-groq",
        "LLM_PROVIDER_ORDER": "gemini,groq",
        "fanar_captions": False,
        "label": "Gemini primary + Groq fallback, no Fanar",
    },
    {
        "name": "gemini-fanar-captions",
        "LLM_PROVIDER_ORDER": "gemini",
        "fanar_captions": True,
        "label": "Gemini + Fanar caption refinement (current best)",
    },
    {
        "name": "gemini-groq-fanar-captions",
        "LLM_PROVIDER_ORDER": "gemini,groq",
        "fanar_captions": True,
        "label": "Gemini+Groq chain + Fanar caption refinement",
    },
    {
        "name": "fanar-gemini-captions",
        "LLM_PROVIDER_ORDER": "fanar,gemini",
        "fanar_captions": True,
        "label": "Fanar primary + Gemini fallback + Fanar captions",
    },
]


# ── Helpers ───────────────────────────────────────────────────────────
def _contains_keyword(text: str, idea_text: str) -> bool:
    text_lower = text.lower()
    for raw in idea_text.lower().replace("-", " ").split():
        token = raw.strip(".,:;!?()[]{}")
        if len(token) >= 5 and token in text_lower:
            return True
    return False


def _rewrite_env(combo: dict) -> None:
    """Patch .env for this combination, preserving secrets."""
    lines = ENV_BACKUP.read_text().splitlines()
    env = {}
    for line in lines:
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()

    env["LLM_PROVIDER_ORDER"] = combo["LLM_PROVIDER_ORDER"]
    env["USE_LLM_ENRICHMENT"] = "true"
    env["MOCK_MODE"] = "false"

    # If fanar_captions is False, temporarily remove FANAR_API_KEY
    if not combo["fanar_captions"]:
        env.pop("FANAR_API_KEY", None)
        env.pop("FANAR_MODEL", None)
        env.pop("FANAR_BASE_URL", None)
    else:
        # Restore from backup if missing
        for key in ["FANAR_API_KEY", "FANAR_MODEL", "FANAR_BASE_URL"]:
            if key not in env:
                backup_env = dict(
                    line.split("=", 1)
                    for line in ENV_BACKUP.read_text().splitlines()
                    if "=" in line and not line.strip().startswith("#")
                )
                if key in backup_env:
                    env[key] = backup_env[key]

    ENV_PATH.write_text("\n".join(f"{k}={v}" for k, v in env.items()) + "\n")


def _restart_backend() -> bool:
    """Kill any running backend and start fresh."""
    subprocess.run(["bash", "-c", "lsof -ti :8000 2>/dev/null | xargs kill -9 2>/dev/null"],
                   capture_output=True)
    time.sleep(1)

    proc = subprocess.Popen(
        [str(BACKEND / ".venv/bin/uvicorn"), "app.main:app",
         "--host", "0.0.0.0", "--port", "8000", "--log-level", "warning"],
        cwd=str(BACKEND),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for health check
    for _ in range(30):
        try:
            r = httpx.get(f"{BASE_URL}/health", timeout=2)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(1)

    print(f"  ERROR: Backend did not start (pid {proc.pid})")
    return False


def _kill_backend() -> None:
    subprocess.run(["bash", "-c", "lsof -ti :8000 2>/dev/null | xargs kill -9 2>/dev/null"],
                   capture_output=True)


# ── Test runners (enriched versions that capture full payloads) ──────
def _run_review(client: httpx.Client, case: dict) -> dict:
    t0 = time.perf_counter()
    r = client.post("/api/review", json={"idea_text": case["idea_text"], "goal": case["goal"]})
    elapsed = round(time.perf_counter() - t0, 2)
    r.raise_for_status()
    payload = r.json()

    rankings = payload.get("rankings", [])
    top = rankings[0] if rankings else {}
    why = str(top.get("why", ""))
    top_evidence = top.get("top_evidence", [])

    errors = []
    if not rankings:
        errors.append("no rankings")
    if len(rankings) < 5:
        errors.append(f"only {len(rankings)} rankings")
    if top.get("platform") not in case["expected_any_platforms"]:
        errors.append(f"top platform {top.get('platform')!r} unexpected (expected {case['expected_any_platforms']})")
    if len(top_evidence) < case["min_top_evidence"]:
        errors.append(f"evidence {len(top_evidence)} < {case['min_top_evidence']}")
    if len(why.split()) < 8:
        errors.append("why too short")
    if why and not _contains_keyword(why, case["idea_text"]):
        errors.append("why not topic-aware")

    # Enrich: capture full ranking details
    ranking_details = []
    for rank in rankings:
        ranking_details.append({
            "platform": rank.get("platform"),
            "fit_score": rank.get("fit_score"),
            "confidence": rank.get("confidence"),
            "why": rank.get("why", ""),
            "evidence_count": len(rank.get("evidence", [])),
            "idea_summary": rank.get("idea_summary"),
        })

    # Enrich: capture idea summary
    idea_summary = payload.get("idea_summary", {})

    return {
        "id": case["id"],
        "passed": not errors,
        "errors": errors,
        "elapsed_s": elapsed,
        "top_platform": top.get("platform"),
        "top_score": top.get("fit_score"),
        "top_confidence": top.get("confidence"),
        "why_words": len(why.split()),
        "why_text": why,
        "top_evidence_count": len(top_evidence),
        "total_rankings": len(rankings),
        "all_rankings": ranking_details,
        "idea_summary": idea_summary,
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

    seen = {str(r.get("caption", "")).strip() for r in reports}
    if len(seen) < max(1, len(reports) // 2):
        errors.append("too many duplicate captions")

    # Enrich: capture full report details for analysis
    report_details = []
    for rep in reports:
        report_details.append({
            "country": rep.get("country"),
            "platform": rep.get("platform"),
            "caption": rep.get("caption", ""),
            "hashtags": rep.get("hashtags", []),
            "why": rep.get("why", ""),
            "hook": rep.get("hook", ""),
            "recommended_format": rep.get("recommended_format", ""),
            "dos": rep.get("dos", []),
            "donts": rep.get("donts", []),
            "evidence_count": len(rep.get("evidence", [])),
            "confidence": rep.get("confidence"),
            "language_direction": rep.get("language_direction"),
        })

    idea_summary = payload.get("idea_summary", {})

    return {
        "id": case["id"],
        "passed": not errors,
        "errors": errors,
        "elapsed_s": elapsed,
        "report_count": len(reports),
        "avg_caption_words": round(sum(caption_lengths) / len(caption_lengths), 1) if caption_lengths else 0,
        "avg_evidence_count": round(sum(evidence_counts) / len(evidence_counts), 1) if evidence_counts else 0,
        "unique_captions": len(seen),
        "reports": report_details,
        "idea_summary": idea_summary,
    }


def run_combo(combo: dict, cases: dict) -> dict:
    """Run all cases for a single combination."""
    name = combo["name"]
    print(f"\n{'=' * 70}")
    print(f"  COMBO: {name}")
    print(f"  {combo['label']}")
    print(f"  Provider order: {combo['LLM_PROVIDER_ORDER']}")
    print(f"  Fanar captions: {combo['fanar_captions']}")
    print(f"{'=' * 70}")

    _rewrite_env(combo)
    if not _restart_backend():
        return {"combo": combo, "error": "Backend failed to start"}

    client = httpx.Client(base_url=BASE_URL, timeout=90.0)

    results = {
        "combo": combo,
        "review": [],
        "personalize": [],
        "total_time_s": 0,
    }

    t_start = time.perf_counter()

    for case in cases["review"]:
        try:
            res = _run_review(client, case)
            results["review"].append(res)
            status = "PASS" if res["passed"] else "FAIL"
            print(f"  [{status}] {res['id']} — {res['elapsed_s']}s  "
                  f"why={res['why_words']}w  ev={res['top_evidence_count']}  "
                  f"top={res['top_platform']}", flush=True)
        except Exception as exc:
            print(f"  [ERROR] {case['id']} — {exc}", flush=True)
            results["review"].append({"id": case["id"], "passed": False, "errors": [str(exc)], "elapsed_s": 0})

    for case in cases["personalize"]:
        try:
            res = _run_personalize(client, case)
            results["personalize"].append(res)
            status = "PASS" if res["passed"] else "FAIL"
            print(f"  [{status}] {res['id']} — {res['elapsed_s']}s  "
                  f"cap={res['avg_caption_words']}w  ev={res['avg_evidence_count']}  "
                  f"uniq={res['unique_captions']}", flush=True)
        except Exception as exc:
            print(f"  [ERROR] {case['id']} — {exc}", flush=True)
            results["personalize"].append({"id": case["id"], "passed": False, "errors": [str(exc)], "elapsed_s": 0})

    results["total_time_s"] = round(time.perf_counter() - t_start, 1)
    client.close()

    # Summary
    rev_pass = sum(1 for r in results["review"] if r["passed"])
    pers_pass = sum(1 for r in results["personalize"] if r["passed"])
    total = rev_pass + pers_pass
    print(f"\n  SUMMARY: {rev_pass}/{len(results['review'])} review + "
          f"{pers_pass}/{len(results['personalize'])} personalize = "
          f"{total}/{len(results['review']) + len(results['personalize'])} "
          f"({total / (len(results['review']) + len(results['personalize'])) * 100:.0f}%)  "
          f"in {results['total_time_s']}s")

    return results


def main() -> int:
    # Backup original .env
    shutil.copy2(ENV_PATH, ENV_BACKUP)
    print(f"Backed up .env to {ENV_BACKUP}")

    cases = json.loads(CASES_PATH.read_text())
    all_results = []

    try:
        for i, combo in enumerate(COMBOS):
            print(f"\n>>> Combo {i + 1}/{len(COMBOS)}: {combo['name']}")
            results = run_combo(combo, cases)
            all_results.append(results)

            # Save individual combo result
            out = RESULTS_DIR / f"combo_{combo['name']}.json"
            out.write_text(json.dumps(results, indent=2, ensure_ascii=False))
            print(f"  Saved to {out}")

    finally:
        # Restore original .env and restart backend
        shutil.copy2(ENV_BACKUP, ENV_PATH)
        ENV_BACKUP.unlink()
        print("\nRestored original .env")
        _restart_backend()
        print("Backend restarted with original config")

    # ── Summary table ────────────────────────────────────────────────
    print(f"\n\n{'=' * 80}")
    print("GRAND SUMMARY")
    print(f"{'=' * 80}")

    summary_path = RESULTS_DIR / "all_combos_summary.json"
    summary = []
    for r in all_results:
        if "error" in r:
            summary.append({"combo": r["combo"]["name"], "error": r["error"]})
            continue
        rev_pass = sum(1 for x in r["review"] if x["passed"])
        pers_pass = sum(1 for x in r["personalize"] if x["passed"])
        rev_total = len(r["review"])
        pers_total = len(r["personalize"])
        total = rev_pass + pers_pass
        grand = rev_total + pers_total
        summary.append({
            "combo": r["combo"]["name"],
            "label": r["combo"]["label"],
            "review_pass": f"{rev_pass}/{rev_total}",
            "personalize_pass": f"{pers_pass}/{pers_total}",
            "total_pass": f"{total}/{grand}",
            "total_pct": round(total / grand * 100, 1),
            "total_time_s": r["total_time_s"],
            "review_errors": [e for x in r["review"] if not x["passed"] for e in x.get("errors", [])],
            "personalize_errors": [e for x in r["personalize"] if not x["passed"] for e in x.get("errors", [])],
        })

    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Summary saved to {summary_path}")

    # Print table
    print(f"\n{'Combo':<32} {'Review':>10} {'Personalize':>14} {'Total':>10} {'%':>6} {'Time':>8}")
    print("-" * 80)
    for s in summary:
        if "error" in s:
            print(f"{s['combo']:<32} ERROR: {s['error']}")
        else:
            print(f"{s['combo']:<32} {s['review_pass']:>10} {s['personalize_pass']:>14} "
                  f"{s['total_pass']:>10} {s['total_pct']:>5.0f}% {s['total_time_s']:>6.0f}s")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
