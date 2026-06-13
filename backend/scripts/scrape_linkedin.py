"""LinkedIn scraper for Stars of Science using Playwright.

A visible browser window opens. If LinkedIn asks for a verification code,
type it directly in that browser window — the script continues automatically.

Credentials via .env:
    LI_EMAIL=your_email
    LI_PASSWORD=your_password
    LI_COMPANY_URLS=https://www.linkedin.com/company/stars-of-science/posts/
    LI_MAX_POSTS=200
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("scrape_linkedin")

LI_EMAIL    = os.getenv("LI_EMAIL", "")
LI_PASSWORD = os.getenv("LI_PASSWORD", "")
LI_MAX      = int(os.getenv("LI_MAX_POSTS", "200"))
LI_PAUSE    = float(os.getenv("LI_SCROLL_PAUSE", "3"))
LI_TARGETS  = [u.strip() for u in os.getenv(
    "LI_COMPANY_URLS",
    "https://www.linkedin.com/company/stars-of-science/posts/,"
    "https://www.linkedin.com/company/qatar-foundation/posts/"
).split(",") if u.strip()]

_DATA    = Path(__file__).resolve().parent.parent / "data"
_SESSION = _DATA / "li_session.json"


def _detect_language(text: str) -> tuple[str, bool]:
    arabic = sum(1 for c in text if "؀" <= c <= "ۿ")
    ratio = arabic / max(len(text), 1)
    if ratio > 0.35:
        return "ar", True
    if ratio > 0.08:
        return "mixed", False
    return "en", False


def _url_id(url: str) -> str:
    import hashlib
    return hashlib.sha1(url.encode()).hexdigest()[:16]


def _parse_metric(text: str) -> int:
    text = text.strip().replace(",", "")
    m = re.search(r"([\d.]+)\s*([KkMm]?)", text)
    if not m:
        return 0
    num, suf = float(m.group(1)), m.group(2).upper()
    return int(num * (1000 if suf == "K" else 1_000_000 if suf == "M" else 1))


def _wait_for_feed(page, timeout: int = 180) -> bool:
    logger.info("Waiting up to %ds for LinkedIn login (type any code in the browser window) …", timeout)
    deadline = time.time() + timeout
    while time.time() < deadline:
        url = page.url
        if "linkedin.com/feed" in url or "linkedin.com/company" in url or "linkedin.com/mynetwork" in url:
            logger.info("  Logged into LinkedIn — URL: %s", url)
            return True
        remaining = int(deadline - time.time())
        if remaining % 20 == 0:
            logger.info("  Waiting … %ds left.", remaining)
        time.sleep(3)
    return False


def main() -> None:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

    if not LI_EMAIL or not LI_PASSWORD:
        logger.error("Set LI_EMAIL and LI_PASSWORD in .env.")
        sys.exit(1)

    all_posts: list[dict] = []
    seen: set[str] = set()

    with sync_playwright() as pw:
        ctx_kwargs: dict = {
            "user_agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }
        if _SESSION.exists():
            ctx_kwargs["storage_state"] = str(_SESSION)
            logger.info("Reusing saved LinkedIn session.")

        browser = pw.chromium.launch(headless=False)
        ctx = browser.new_context(**ctx_kwargs)
        page = ctx.new_page()

        # ── Login ──────────────────────────────────────────────────────────
        page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
        time.sleep(3)

        if "login" in page.url or "authwall" in page.url or "uas/login" in page.url:
            logger.info("Not logged in — filling credentials …")
            page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
            time.sleep(3)

            filled = False
            for email_sel in ['#username', 'input[name="session_key"]', 'input[autocomplete="username"]', 'input[type="email"]']:
                try:
                    page.fill(email_sel, LI_EMAIL, timeout=5000)
                    filled = True
                    break
                except PlaywrightTimeout:
                    pass

            for pass_sel in ['#password', 'input[name="session_password"]', 'input[type="password"]']:
                try:
                    page.fill(pass_sel, LI_PASSWORD, timeout=5000)
                    break
                except PlaywrightTimeout:
                    pass

            for btn_sel in ['button[type="submit"]', 'button[data-litms-control-urn]', '.sign-in-form__submit-btn--full-width']:
                try:
                    page.click(btn_sel, timeout=5000)
                    break
                except PlaywrightTimeout:
                    pass

            time.sleep(4)

        if not _wait_for_feed(page, timeout=180):
            logger.error("Could not reach LinkedIn feed after 180s.")
            browser.close()
            sys.exit(1)

        ctx.storage_state(path=str(_SESSION))
        logger.info("Session saved → %s", _SESSION)

        # ── Scrape company pages ───────────────────────────────────────────
        for target_url in LI_TARGETS:
            logger.info("Scraping %s …", target_url)
            page.goto(target_url, wait_until="domcontentloaded")
            time.sleep(4)

            count = 0
            prev_height = 0
            no_change = 0

            while count < LI_MAX and no_change < 5:
                post_els = (
                    page.query_selector_all("div.feed-shared-update-v2") or
                    page.query_selector_all("div[data-urn]") or
                    page.query_selector_all("li.profile-creator-shared-feed-update__container")
                )

                for el in post_els:
                    try:
                        urn = el.get_attribute("data-urn") or ""
                        post_url = ""
                        link_el = el.query_selector('a[href*="/feed/update/"]')
                        if link_el:
                            post_url = (link_el.get_attribute("href") or "").split("?")[0]
                        uid = _url_id(urn or post_url or str(count))

                        if uid in seen:
                            continue
                        seen.add(uid)

                        text_el = (
                            el.query_selector("span.break-words") or
                            el.query_selector("div.feed-shared-text") or
                            el.query_selector(".update-components-text") or
                            el.query_selector('[data-test-id="main-feed-activity-card__commentary"]')
                        )
                        text = text_el.inner_text().strip() if text_el else ""
                        if not text:
                            continue

                        likes = 0
                        for like_sel in [
                            "span.social-details-social-counts__reactions-count",
                            "li.social-details-social-counts__item--reactions button",
                        ]:
                            like_el = el.query_selector(like_sel)
                            if like_el:
                                likes = _parse_metric(like_el.inner_text())
                                break

                        comments = 0
                        comment_el = el.query_selector("li.social-details-social-counts__item--comments button")
                        if comment_el:
                            comments = _parse_metric(comment_el.inner_text())

                        published_at = ""
                        time_el = el.query_selector("time") or el.query_selector("span.update-components-actor__sub-description")
                        if time_el:
                            raw = time_el.get_attribute("datetime") or time_el.inner_text()
                            published_at = raw[:10] if raw else ""

                        media_type = "video" if el.query_selector("video") else \
                                     "image" if el.query_selector("img.ivm-view-attr__img--main") else "article"

                        lang, arabic_primary = _detect_language(text)
                        hashtags = [f"#{h}" for h in re.findall(r"#(\w+)", text)]

                        all_posts.append({
                            "platform": "LinkedIn",
                            "post_id": f"li-{uid}",
                            "url": post_url or target_url,
                            "published_at": published_at,
                            "title": "",
                            "caption": text[:500],
                            "description": text[:2000],
                            "hashtags": hashtags[:10],
                            "media_type": media_type,
                            "views": 0,
                            "likes": likes,
                            "comments_count": comments,
                            "shares_count": 0,
                            "transcript": "",
                            "summary": text[:120].replace("\n", " "),
                            "language": lang,
                            "arabic_primary": arabic_primary,
                            "source_name": "Stars of Science LinkedIn",
                            "source_type": "scraped",
                        })
                        count += 1
                        if count % 20 == 0:
                            logger.info("  %d posts collected …", count)
                        if count >= LI_MAX:
                            break
                    except Exception:
                        continue

                current_height = page.evaluate("document.body.scrollHeight")
                no_change = 0 if current_height != prev_height else no_change + 1
                prev_height = current_height
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(LI_PAUSE)

            logger.info("  Done: %d posts from %s", count, target_url)

        browser.close()

    if not all_posts:
        logger.warning("No LinkedIn posts scraped.")
        return

    out = _DATA / "scraped_linkedin.json"
    out.write_text(json.dumps(all_posts, ensure_ascii=False, indent=2))
    logger.info("Saved %d posts → %s", len(all_posts), out)

    from kb import stars_intelligence as kb
    inserted, updated = kb._upsert_posts(all_posts, mode="scraped")
    kb._update_platform_state("LinkedIn", "scraped", None)
    logger.info("DB: +%d inserted  %d updated", inserted, updated)


if __name__ == "__main__":
    main()
