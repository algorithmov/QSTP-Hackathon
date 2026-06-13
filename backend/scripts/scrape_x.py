"""X (Twitter) scraper for Stars of Science using Playwright.

A visible browser window opens. If X asks for a verification code or email
confirmation, type it directly in that browser window — the script will
automatically continue once you're past it.

Credentials via .env:
    X_USERNAME=your_username_or_email
    X_PASSWORD=your_password
    X_EMAIL=your_email
    X_MAX_TWEETS=500
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
logger = logging.getLogger("scrape_x")

X_USERNAME = os.getenv("X_USERNAME", "")
X_PASSWORD = os.getenv("X_PASSWORD", "")
X_EMAIL    = os.getenv("X_EMAIL", "")
X_MAX      = int(os.getenv("X_MAX_TWEETS", "500"))

_DATA    = Path(__file__).resolve().parent.parent / "data"
_SESSION = _DATA / "x_session.json"

_SEARCH_QUERIES = [
    '"Stars of Science"',
    "#StarsOfScience",
    "نجوم العلوم",
    "starsofscience",
    "from:starsofscience",
]


def _detect_language(text: str) -> tuple[str, bool]:
    arabic = sum(1 for c in text if "؀" <= c <= "ۿ")
    ratio = arabic / max(len(text), 1)
    if ratio > 0.35:
        return "ar", True
    if ratio > 0.08:
        return "mixed", False
    return "en", False


def _parse_metric(text: str) -> int:
    text = text.strip().replace(",", "")
    m = re.search(r"([\d.]+)\s*([KkMm]?)", text)
    if not m:
        return 0
    num, suf = float(m.group(1)), m.group(2).upper()
    return int(num * (1000 if suf == "K" else 1_000_000 if suf == "M" else 1))


def _wait_for_home(page, timeout: int = 180) -> bool:
    logger.info("Waiting up to %ds for X login (type any code in the browser window) …", timeout)
    deadline = time.time() + timeout
    while time.time() < deadline:
        url = page.url
        if "x.com/home" in url or ("x.com/" in url and "login" not in url and "flow" not in url and "challenge" not in url):
            logger.info("  On X home — URL: %s", url)
            return True
        remaining = int(deadline - time.time())
        if remaining % 20 == 0:
            logger.info("  Waiting … %ds left.", remaining)
        time.sleep(3)
    return False


def main() -> None:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

    if not X_USERNAME or not X_PASSWORD:
        logger.error("Set X_USERNAME and X_PASSWORD in .env.")
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
            logger.info("Reusing saved X session.")

        browser = pw.chromium.launch(headless=False)
        ctx = browser.new_context(**ctx_kwargs)
        page = ctx.new_page()

        # ── Login ──────────────────────────────────────────────────────────
        page.goto("https://x.com/home", wait_until="domcontentloaded")
        time.sleep(3)

        if "login" in page.url or "flow" in page.url:
            logger.info("Not logged in — filling credentials …")
            page.goto("https://x.com/i/flow/login", wait_until="domcontentloaded")
            time.sleep(4)

            try:
                page.fill('input[autocomplete="username"]', X_USERNAME, timeout=8000)
                page.keyboard.press("Enter")
                time.sleep(3)

                # X sometimes asks for email mid-flow
                email_field = page.query_selector('input[data-testid="ocfEnterTextTextInput"]')
                if email_field:
                    logger.info("  X asked for email confirmation — filling …")
                    email_field.fill(X_EMAIL or X_USERNAME)
                    page.keyboard.press("Enter")
                    time.sleep(3)

                page.fill('input[name="password"]', X_PASSWORD, timeout=8000)
                page.keyboard.press("Enter")
                time.sleep(5)
            except PlaywrightTimeout as exc:
                logger.warning("Auto-fill issue: %s — please continue manually in the browser.", exc)

        if not _wait_for_home(page, timeout=180):
            logger.error("Could not reach X home after 180s.")
            browser.close()
            sys.exit(1)

        ctx.storage_state(path=str(_SESSION))
        logger.info("Session saved → %s", _SESSION)

        # ── Search for Stars of Science tweets ────────────────────────────
        for query in _SEARCH_QUERIES:
            if len(all_posts) >= X_MAX:
                break

            encoded = query.replace(" ", "%20").replace("#", "%23").replace('"', "%22")
            url = f"https://x.com/search?q={encoded}&src=typed_query&f=live"
            logger.info("Searching: %r …", query)
            page.goto(url, wait_until="domcontentloaded")
            time.sleep(4)

            no_change = 0
            prev_count = 0

            while len(all_posts) < X_MAX and no_change < 5:
                for article in page.query_selector_all('article[data-testid="tweet"]'):
                    try:
                        text_el = article.query_selector('[data-testid="tweetText"]')
                        text = text_el.inner_text().strip() if text_el else ""
                        if not text:
                            continue

                        link_el = article.query_selector('a[href*="/status/"]')
                        tweet_href = link_el.get_attribute("href") if link_el else ""
                        tweet_url = f"https://x.com{tweet_href}" if tweet_href.startswith("/") else tweet_href
                        id_m = re.search(r"/status/(\d+)", tweet_url)
                        if not id_m:
                            continue
                        tweet_id = id_m.group(1)
                        post_id = f"x-{tweet_id}"
                        if post_id in seen:
                            continue
                        seen.add(post_id)

                        time_el = article.query_selector("time[datetime]")
                        published_at = ((time_el.get_attribute("datetime") or "")[:10]) if time_el else ""

                        user_el = article.query_selector('[data-testid="User-Name"] a')
                        author = ""
                        if user_el:
                            href = user_el.get_attribute("href") or ""
                            author = href.lstrip("/").split("/")[0]

                        likes = replies = retweets = views = 0
                        for m_el in article.query_selector_all('[role="group"] [data-testid]') or []:
                            tid = m_el.get_attribute("data-testid") or ""
                            val = _parse_metric(m_el.inner_text())
                            if "like" in tid:
                                likes = val
                            elif "reply" in tid:
                                replies = val
                            elif "retweet" in tid:
                                retweets = val

                        lang, arabic_primary = _detect_language(text)
                        hashtags = [f"#{h}" for h in re.findall(r"#(\w+)", text)]

                        all_posts.append({
                            "platform": "X",
                            "post_id": post_id,
                            "url": tweet_url,
                            "published_at": published_at,
                            "title": "",
                            "caption": text[:500],
                            "description": text[:2000],
                            "hashtags": hashtags[:10],
                            "media_type": "tweet",
                            "views": views,
                            "likes": likes,
                            "comments_count": replies,
                            "shares_count": retweets,
                            "transcript": "",
                            "summary": text[:120].replace("\n", " "),
                            "language": lang,
                            "arabic_primary": arabic_primary,
                            "source_name": f"@{author} on X" if author else "Stars of Science X",
                            "source_type": "scraped",
                        })
                    except Exception:
                        pass

                if len(all_posts) == prev_count:
                    no_change += 1
                else:
                    logger.info("  %d tweets so far …", len(all_posts))
                    no_change = 0
                prev_count = len(all_posts)
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(3)

            logger.info("  Query %r done. Total: %d", query, len(all_posts))

        browser.close()

    if not all_posts:
        logger.warning("No tweets scraped.")
        return

    out = _DATA / "scraped_x.json"
    out.write_text(json.dumps(all_posts, ensure_ascii=False, indent=2))
    logger.info("Saved %d tweets → %s", len(all_posts), out)

    from kb import stars_intelligence as kb
    inserted, updated = kb._upsert_posts(all_posts, mode="scraped")
    kb._update_platform_state("X", "scraped", None)
    logger.info("DB: +%d inserted  %d updated", inserted, updated)


if __name__ == "__main__":
    main()
