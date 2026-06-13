"""Instagram scraper for Stars of Science using Playwright.

A visible browser window opens. If Instagram asks for a verification code,
type it directly in that browser window — the script will automatically
continue once you're past the challenge.

Credentials via .env:
    IG_USERNAME=your_email_or_username
    IG_PASSWORD=your_password
    IG_TARGET_PROFILES=starsofscience,starsofsciencetv
    IG_MAX_POSTS=300
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
logger = logging.getLogger("scrape_instagram")

IG_USERNAME  = os.getenv("IG_USERNAME", "")
IG_PASSWORD  = os.getenv("IG_PASSWORD", "")
IG_TARGETS   = [p.strip() for p in os.getenv("IG_TARGET_PROFILES", "starsofscience,starsofsciencetv").split(",") if p.strip()]
IG_MAX_POSTS = int(os.getenv("IG_MAX_POSTS", "300"))

_DATA        = Path(__file__).resolve().parent.parent / "data"
_SESSION     = _DATA / "ig_session.json"   # saved login state for reuse


def _detect_language(text: str) -> tuple[str, bool]:
    arabic = sum(1 for c in text if "؀" <= c <= "ۿ")
    ratio = arabic / max(len(text), 1)
    if ratio > 0.35:
        return "ar", True
    if ratio > 0.08:
        return "mixed", False
    return "en", False


def _extract_shortcode(url: str) -> str:
    m = re.search(r"/p/([A-Za-z0-9_-]+)", url)
    if m:
        return m.group(1)
    import hashlib
    return hashlib.sha1(url.encode()).hexdigest()[:16]


def _is_logged_in(page) -> bool:
    """Return True if we're on Instagram and there's a logged-in nav element."""
    url = page.url
    if any(x in url for x in ("login", "challenge", "checkpoint", "codeentry", "verify", "auth_platform")):
        return False
    # Check for nav icons that only appear when logged in
    return bool(
        page.query_selector('a[href="/"]') or
        page.query_selector('svg[aria-label="Home"]') or
        page.query_selector('a[href*="/direct/inbox"]') or
        page.query_selector('[aria-label="New post"]')
    )


def _wait_for_feed(page, timeout: int = 180) -> bool:
    """Poll until we're logged into Instagram or timeout expires."""
    logger.info("Waiting up to %ds for login (type any code directly in the browser window) …", timeout)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _is_logged_in(page):
            logger.info("  Logged in — URL: %s", page.url)
            return True
        remaining = int(deadline - time.time())
        if remaining % 20 == 0:
            logger.info("  Still waiting … %ds left.", remaining)
        time.sleep(3)
    return False


def main() -> None:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

    if not IG_USERNAME or not IG_PASSWORD:
        logger.error("Set IG_USERNAME and IG_PASSWORD in .env.")
        sys.exit(1)

    all_posts: list[dict] = []
    seen: set[str] = set()

    with sync_playwright() as pw:
        # Reuse saved session if it exists, so we don't need to log in every time
        launch_kwargs = {}
        ctx_kwargs: dict = {
            "user_agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "viewport": {"width": 1280, "height": 900},
        }
        if _SESSION.exists():
            ctx_kwargs["storage_state"] = str(_SESSION)
            logger.info("Reusing saved session from %s", _SESSION)

        browser = pw.chromium.launch(headless=False)
        ctx = browser.new_context(**ctx_kwargs)
        page = ctx.new_page()

        # ── Go to Instagram ────────────────────────────────────────────────
        page.goto("https://www.instagram.com/", wait_until="domcontentloaded")
        time.sleep(3)

        if any(x in page.url for x in ("login", "accounts")):
            logger.info("Not logged in yet — filling credentials …")
            page.goto("https://www.instagram.com/accounts/login/", wait_until="domcontentloaded")
            time.sleep(3)

            # Accept cookies
            for text in ("Allow all cookies", "Accept All", "Akzeptieren"):
                try:
                    page.click(f"text={text}", timeout=3000)
                    time.sleep(1)
                    break
                except PlaywrightTimeout:
                    pass

            try:
                page.fill('input[name="username"]', IG_USERNAME, timeout=8000)
                page.fill('input[name="password"]', IG_PASSWORD, timeout=8000)
                page.click('button[type="submit"]', timeout=8000)
                time.sleep(4)
            except PlaywrightTimeout as exc:
                logger.warning("Could not auto-fill login form: %s — please log in manually in the browser.", exc)

        # Wait for feed (user may need to type a code in the browser window)
        if not _wait_for_feed(page, timeout=180):
            logger.error("Never reached Instagram feed after 180s. Exiting.")
            browser.close()
            sys.exit(1)

        # Save session so next run skips login entirely
        ctx.storage_state(path=str(_SESSION))
        logger.info("Session saved → %s", _SESSION)

        # Dismiss any popups
        for text in ("Not Now", "Skip", "Cancel", "Later"):
            try:
                page.click(f"text={text}", timeout=2000)
                time.sleep(1)
            except PlaywrightTimeout:
                pass

        # ── Scrape each profile ────────────────────────────────────────────
        for profile in IG_TARGETS:
            logger.info("Scraping @%s (up to %d posts) …", profile, IG_MAX_POSTS)
            page.goto(f"https://www.instagram.com/{profile}/", wait_until="domcontentloaded")
            time.sleep(3)

            post_links: list[str] = []
            no_change = 0

            while len(post_links) < IG_MAX_POSTS and no_change < 8:
                prev = len(post_links)
                # Collect both /p/ posts and /reel/ links
                links = page.eval_on_selector_all(
                    "a[href*='/p/'], a[href*='/reel/']",
                    "els => els.map(e => e.href)"
                )
                for l in links:
                    if l not in post_links and ("instagram.com/p/" in l or "instagram.com/reel/" in l):
                        post_links.append(l)
                post_links = list(dict.fromkeys(post_links))[:IG_MAX_POSTS]
                if len(post_links) > prev:
                    logger.info("  Found %d links so far …", len(post_links))
                    no_change = 0
                else:
                    no_change += 1
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(3)

            logger.info("  Found %d post links — fetching details …", len(post_links))

            for link in post_links:
                shortcode = _extract_shortcode(link)
                post_id = f"ig-{shortcode}"
                if post_id in seen:
                    continue
                try:
                    page.goto(link, wait_until="domcontentloaded")
                    time.sleep(1.5)

                    caption_el = (
                        page.query_selector("h1._ap3a") or
                        page.query_selector("div._a9zs h1") or
                        page.query_selector("span._ap3a._aaco._aacu._aacx._aad7._aade") or
                        page.query_selector('meta[property="og:description"]')
                    )
                    if caption_el:
                        caption = (caption_el.inner_text() if hasattr(caption_el, "inner_text")
                                   else caption_el.get_attribute("content") or "").strip()
                    else:
                        caption = ""

                    likes = 0
                    for sel in ["section span span", "span.x193iq5w"]:
                        el = page.query_selector(sel)
                        if el:
                            raw = el.inner_text().replace(",", "").strip()
                            m = re.search(r"([\d.]+)\s*([KkMm]?)", raw)
                            if m:
                                n, s = float(m.group(1)), m.group(2).upper()
                                likes = int(n * (1000 if s == "K" else 1_000_000 if s == "M" else 1))
                            break

                    time_el = page.query_selector("time[datetime]")
                    published_at = ((time_el.get_attribute("datetime") or "")[:10]) if time_el else ""

                    media_type = "reel" if page.query_selector("video") else "image"
                    lang, arabic_primary = _detect_language(caption)
                    hashtags = [f"#{h}" for h in re.findall(r"#(\w+)", caption)]

                    all_posts.append({
                        "platform": "Instagram",
                        "post_id": post_id,
                        "url": f"https://www.instagram.com/p/{shortcode}/",
                        "published_at": published_at,
                        "title": "",
                        "caption": caption[:500],
                        "description": caption[:2000],
                        "hashtags": hashtags[:10],
                        "media_type": media_type,
                        "views": 0,
                        "likes": likes,
                        "comments_count": 0,
                        "shares_count": 0,
                        "transcript": "",
                        "summary": caption[:120].replace("\n", " "),
                        "language": lang,
                        "arabic_primary": arabic_primary,
                        "source_name": f"Stars of Science Instagram (@{profile})",
                        "source_type": "scraped",
                    })
                    seen.add(post_id)

                    if len(all_posts) % 20 == 0:
                        logger.info("  %d posts collected …", len(all_posts))
                except Exception as exc:
                    logger.debug("Skipping %s: %s", link, exc)
                    time.sleep(1)

            logger.info("  @%s done.", profile)

        browser.close()

    if not all_posts:
        logger.warning("No posts collected.")
        return

    out = _DATA / "scraped_instagram.json"
    out.write_text(json.dumps(all_posts, ensure_ascii=False, indent=2))
    logger.info("Saved %d posts → %s", len(all_posts), out)

    from kb import stars_intelligence as kb
    inserted, updated = kb._upsert_posts(all_posts, mode="scraped")
    kb._update_platform_state("Instagram", "scraped", None)
    logger.info("DB: +%d inserted  %d updated", inserted, updated)


if __name__ == "__main__":
    main()
