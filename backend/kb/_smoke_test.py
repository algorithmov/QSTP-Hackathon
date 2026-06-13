"""Standalone smoke test. Run: python -m kb._smoke_test"""
from kb import knowledge_base as kb
from kb import evidence

countries = kb.list_countries()
assert len(countries) == 10, f"Expected 10 countries, got {len(countries)}"
print(f"list_countries: {len(countries)} countries OK")

platforms = kb.list_platforms()
assert len(platforms) == 5, f"Expected 5 platforms, got {len(platforms)}"
print(f"list_platforms: {len(platforms)} platforms OK")

usage = kb.get_usage("TikTok", "EG")
assert "usage_score" in usage and "peak_hours_local" in usage
print(f"get_usage TikTok/EG: {usage}")

for platform in ["TikTok", "Instagram", "YouTube", "LinkedIn", "X"]:
    for country in ["EG", "SA", "AE", "QA", "DZ", "MA", "JO", "SD", "IQ", "KW"]:
        u = kb.get_usage(platform, country)
        assert u["usage_score"] != 0, f"Zero usage_score for {platform}/{country}"
print("get_usage: all 50 combinations non-zero OK")

fit = kb.get_content_platform_fit("product_demo", "TikTok")
assert fit > 0
print(f"get_content_platform_fit product_demo/TikTok: {fit}")

for ct in ["product_demo", "talking_head", "educational", "announcement", "behind_the_scenes", "achievement_story"]:
    for p in ["TikTok", "Instagram", "YouTube", "LinkedIn", "X"]:
        f = kb.get_content_platform_fit(ct, p)
        assert f > 0, f"Zero fit for {ct}/{p}"
print("get_content_platform_fit: all 30 combinations non-zero OK")

goal_map = kb.get_audience_goal_map("applications")
assert "preferred_platforms" in goal_map
print(f"get_audience_goal_map applications: {goal_map}")

ev = evidence.search_topic_evidence(
    "water purification invention",
    "Egypt",
    idea_text="An Egyptian student demos a water purification invention for farms.",
    platform="TikTok",
)
print(f"search_topic_evidence water/Egypt: {len(ev)} items returned")
for item in ev:
    assert "claim" in item and "source" in item

print("All smoke tests passed.")
