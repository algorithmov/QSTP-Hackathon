# Provider Comparison — 2026-06-13

Models tested against all 20 evaluation cases (10 review + 10 personalize)
with `USE_LLM_ENRICHMENT=true`, single-provider runs.

| Provider | Model | Review | Personalize | Total | Avg why (words) | Avg caption (words) | Total time |
|---|---|---|---|---|---|---|---|
| Gemini | gemini-3.1-flash-lite | 9/10 | 4/10 | **13/20 (65%)** | 16.3 | 20.1 | 150.8s |
| Groq | llama-3.3-70b-versatile | 7/10 | 3/10 | 10/20 (50%) | 11.0 | 5.3 | 109.1s |

**Selected: Gemini as primary, Groq as fallback.**

Reasons:
- 3 more test cases pass with Gemini
- Why-lines are 48% longer on average (16.3w vs 11.0w) — more specific and topic-aware
- Captions are 4x longer on average (20.1w vs 5.3w) — Groq wrote very short captions that failed the topic-keyword check
- Groq is faster on review calls (~2s vs ~7s) but quality gap outweighs speed

Shared failures on both providers are primarily Arabic-script captions where the
English keyword check in `_score_personalize_case` cannot find topic words — this
is a test harness gap, not an LLM quality issue.

Raw results: `results_gemini.json`, `results_groq.json`
