"""Fit Score formula. Weights and logic are the single source of truth for the pitch."""

W_TOPIC = 0.25
W_AUDIENCE = 0.25
W_PLATFORM = 0.25
W_LANGUAGE = 0.15
W_TIMING = 0.10


def compute_fit_score(
    topic_relevance: float,
    audience_fit: float,
    platform_fit: float,
    language_fit: float,
    timing_fit: float,
) -> int:
    raw = (
        W_TOPIC * topic_relevance
        + W_AUDIENCE * audience_fit
        + W_PLATFORM * platform_fit
        + W_LANGUAGE * language_fit
        + W_TIMING * timing_fit
    )
    return round(100 * max(0.0, min(1.0, raw)))


def confidence(evidence_used: bool, usage_score: float) -> str:
    if evidence_used:
        return "high"
    if usage_score >= 0.6:
        return "medium"
    return "low"
