#!/usr/bin/env python3
"""Run remaining combos individually. Usage: python run_remaining.py <combo_name>"""
from __future__ import annotations

import json
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
ENV_ORIG = BACKEND / ".env.orig_combo"
RESULTS_DIR = ROOT / "combo_results"

COMBOS = {
    "gemini-fanar-captions": {
        "LLM_PROVIDER_ORDER": "gemini",
        "fanar_captions": True,
    },
    "gemini-groq-fanar-captions": {
        "LLM_PROVIDER_ORDER": "gemini,groq",
        "fanar_captions": True,
    },
    "fanar-gemini-captions": {
        "LLM_PROVIDER_ORDER": "fanar,gemini",
        "fanar_captions": True,
    },
}

def _contains_keyword(text: str, idea_text: str) -> bool:
    text_lower = text.lower()
    for raw in idea_text.lower().replace("-", " ").split():
        token = raw.strip(".,:;!?()[]{}")
        if len(token) >= 5 and token in text_lower:
            return True
    return False

def _rewrite_env(combo_name: str, combo: dict) -> None:
    """Read current .env, patch provider order, ensure Fanar keys present if needed."""
    # Always start from the original full .env
    orig_env = BACKEND / ".env.full_backup"
    if orig_env.exists():
        lines = orig_env.read_text().splitlines()
    else:
        lines = ENV_PATH.read_text().splitlines()

    env = {}
    for line in lines:
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()

    env["LLM_PROVIDER_ORDER"] = combo["LLM_PROVIDER_ORDER"]
    env["USE_LLM_ENRICHMENT"] = "true"
    env["MOCK_MODE"] = "false"

    if not combo["fanar_captions"]:
        env.pop("FANAR_API_KEY", None)
        env.pop("FANAR_MODEL", None)
        env.pop("FANAR_BASE_URL", None)

    ENV_PATH.write_text("\n".join(f"{k}={v}" for k, v in env.items()) + "\n")
    print(f"Patched .env: LLM_PROVIDER_ORDER={combo['LLM_PROVIDER_ORDER']}, fanar_captions={combo['fanar_captions']}")

def _restart_backend() -> bool:
    subprocess.run(["bash", "-c", "lsof -ti :8000 2>/dev/null | xargs kill -9 2>/dev/null"], capture_output=True)
    time.sleep(1.5)
    proc = subprocess.Popen(
        [str(BACKEND / ".venv/bin/uvicorn"), "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "warning"],
        cwd=str(BACKEND), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(30):
        try:
            r = httpx.get(f"{BASE_URL}/health", timeout=2)
            if r.status_code == 200:
                print(f"Backend ready (pid {proc.pid})")
                return True
        except Exception:
            pass
        time.sleep(1)
    print(f"Backend FAILED to start")
    return False

def _run_review(client, case):
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
    if not rankings: errors.append("no rankings")
    if len(rankings) < 5: errors.append(f"only {len(rankings)} rankings")
    if top.get("platform") not in case["expected_any_platforms"]:
        errors.append(f"top platform {top.get('platform')!r} unexpected")
    if len(top_evidence) < case["min_top_evidence"]:
        errors.append(f"evidence {len(top_evidence)} < {case['min_top_evidence']}")
    if len(why.split()) < 8: errors.append("why too short")
    if why and not _contains_keyword(why, case["idea_text"]):
        errors.append("why not topic-aware")
    ranking_details = [{"platform": r.get("platform"), "fit_score": r.get("fit_score"),
                        "confidence": r.get("confidence"), "why": r.get("why",""),
                        "evidence_count": len(r.get("evidence",[]))} for r in rankings]
    return {"id": case["id"], "passed": not errors, "errors": errors, "elapsed_s": elapsed,
            "top_platform": top.get("platform"), "top_score": top.get("fit_score"),
            "top_confidence": top.get("confidence"), "why_words": len(why.split()),
            "why_text": why, "top_evidence_count": len(top_evidence),
            "total_rankings": len(rankings), "all_rankings": ranking_details,
            "idea_summary": payload.get("idea_summary", {})}

def _run_personalize(client, case):
    t0 = time.perf_counter()
    r = client.post("/api/personalize", json={
        "idea_text": case["idea_text"], "goal": case["goal"],
        "countries": case["countries"], "platforms": case["platforms"],
    })
    elapsed = round(time.perf_counter() - t0, 2)
    r.raise_for_status()
    payload = r.json()
    reports = payload.get("reports", [])
    expected = len(case["countries"]) * len(case["platforms"])
    errors, cap_lens, ev_counts = [], [], []
    if len(reports) != expected: errors.append(f"reports {len(reports)} != {expected}")
    for rep in reports:
        caption = str(rep.get("caption","")).strip()
        cap_lens.append(len(caption.split()))
        ev_counts.append(len(rep.get("evidence",[])))
        if not caption: errors.append(f"{rep['country']}/{rep['platform']}: empty caption")
        if caption and not _contains_keyword(caption, case["idea_text"]):
            errors.append(f"{rep['country']}/{rep['platform']}: caption not topic-aware")
        if len(rep.get("evidence",[])) < case["min_evidence_per_report"]:
            errors.append(f"{rep['country']}/{rep['platform']}: evidence {len(rep.get('evidence',[]))} < {case['min_evidence_per_report']}")
        if len(rep.get("dos",[])) < 2 or len(rep.get("donts",[])) < 2:
            errors.append(f"{rep['country']}/{rep['platform']}: incomplete dos/donts")
        if not str(rep.get("recommended_format","")).strip():
            errors.append(f"{rep['country']}/{rep['platform']}: empty format")
        if not str(rep.get("hook","")).strip():
            errors.append(f"{rep['country']}/{rep['platform']}: empty hook")
    seen = {str(r.get("caption","")).strip() for r in reports}
    if len(seen) < max(1, len(reports)//2): errors.append("too many duplicate captions")
    report_details = [{"country": r.get("country"), "platform": r.get("platform"),
                       "caption": r.get("caption",""), "hashtags": r.get("hashtags",[]),
                       "why": r.get("why",""), "hook": r.get("hook",""),
                       "recommended_format": r.get("recommended_format",""),
                       "dos": r.get("dos",[]), "donts": r.get("donts",[]),
                       "evidence_count": len(r.get("evidence",[])),
                       "confidence": r.get("confidence"),
                       "language_direction": r.get("language_direction")} for r in reports]
    return {"id": case["id"], "passed": not errors, "errors": errors, "elapsed_s": elapsed,
            "report_count": len(reports),
            "avg_caption_words": round(sum(cap_lens)/len(cap_lens),1) if cap_lens else 0,
            "avg_evidence_count": round(sum(ev_counts)/len(ev_counts),1) if ev_counts else 0,
            "unique_captions": len(seen), "reports": report_details,
            "idea_summary": payload.get("idea_summary",{})}

def main():
    combo_name = sys.argv[1]
    if combo_name not in COMBOS:
        print(f"Unknown combo: {combo_name}")
        print(f"Available: {', '.join(COMBOS.keys())}")
        return 1

    combo = COMBOS[combo_name]

    # Save original .env if not already saved
    full_backup = BACKEND / ".env.full_backup"
    if not full_backup.exists():
        import shutil
        shutil.copy2(ENV_PATH, full_backup)
        print(f"Saved original .env to {full_backup}")

    _rewrite_env(combo_name, combo)
    if not _restart_backend():
        return 1

    cases = json.loads(CASES_PATH.read_text())
    client = httpx.Client(base_url=BASE_URL, timeout=90.0)
    results = {"combo": {"name": combo_name, **combo}, "review": [], "personalize": [], "total_time_s": 0}
    t_start = time.perf_counter()

    for case in cases["review"]:
        try:
            res = _run_review(client, case)
            results["review"].append(res)
            s = "PASS" if res["passed"] else "FAIL"
            print(f"  [{s}] {res['id']} — {res['elapsed_s']}s  why={res['why_words']}w  ev={res['top_evidence_count']}  top={res['top_platform']}", flush=True)
        except Exception as exc:
            print(f"  [ERROR] {case['id']} — {exc}", flush=True)
            results["review"].append({"id": case["id"], "passed": False, "errors": [str(exc)], "elapsed_s": 0})

    for case in cases["personalize"]:
        try:
            res = _run_personalize(client, case)
            results["personalize"].append(res)
            s = "PASS" if res["passed"] else "FAIL"
            print(f"  [{s}] {res['id']} — {res['elapsed_s']}s  cap={res['avg_caption_words']}w  ev={res['avg_evidence_count']}  uniq={res['unique_captions']}", flush=True)
        except Exception as exc:
            print(f"  [ERROR] {case['id']} — {exc}", flush=True)
            results["personalize"].append({"id": case["id"], "passed": False, "errors": [str(exc)], "elapsed_s": 0})

    results["total_time_s"] = round(time.perf_counter() - t_start, 1)
    client.close()

    rp = sum(1 for r in results["review"] if r["passed"])
    pp = sum(1 for r in results["personalize"] if r["passed"])
    print(f"\n  SUMMARY: {rp}/10 review + {pp}/10 personalize = {rp+pp}/20 ({(rp+pp)/20*100:.0f}%) in {results['total_time_s']}s")

    out = RESULTS_DIR / f"combo_{combo_name}.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"Saved to {out}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
