#!/usr/bin/env python3
"""
Standalone FlashScore scraper using Playwright.
No external dependencies except Playwright itself.
"""

import asyncio
import re
from datetime import datetime, timezone


def clean_league_name(raw_header_text: str) -> str:
    """Clean league name by removing round/stage suffix."""
    text = re.sub(r"\s+", " ", raw_header_text).strip()
    for sep in (" - Round", " - Play", " - Group", " - "):
        if sep in text:
            text = text.split(sep)[0].strip()
            break
    return text


def league_short_name(full_header_name: str) -> str:
    """Extract short league name."""
    if ":" in full_header_name:
        return full_header_name.split(":", 1)[1].strip()
    return full_header_name


class FlashscoreProvider:
    """Standalone FlashScore scraper using Playwright."""

    def __init__(self, headless: bool = True, slow_mo: int = 0):
        self.headless = headless
        self.slow_mo = slow_mo

    def get_upcoming_fixtures(self) -> list[dict]:
        """Scrape today's fixtures from FlashScore."""
        return asyncio.run(self._scrape())

    async def _scrape(self) -> list[dict]:
        from playwright.async_api import async_playwright, TimeoutError

        fixtures: list[dict] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.headless,
                slow_mo=self.slow_mo
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1920, "height": 1080},
            )
            page = await context.new_page()

            print("🔍 Navigating to FlashScore...")
            await page.goto("https://www.flashscore.com/football/", timeout=60000)
            await page.wait_for_load_state("networkidle")
            print("✅ Page loaded")

            # Accept cookies if banner appears
            try:
                await page.click("button#onetrust-accept-btn-handler", timeout=5000)
                print("🍪 Cookies accepted")
            except Exception:
                print("ℹ️ No cookie banner found")

            # Wait for matches
            try:
                await page.wait_for_selector("div.event__match", timeout=20000)
                print("✅ Match selector found")
            except TimeoutError:
                print("❌ Match selector not found")
                await browser.close()
                return fixtures

            # Get all nodes (headers + matches)
            nodes = await page.query_selector_all("div.event__header, div.event__match")
            print(f"📊 Found {len(nodes)} nodes")

            current_league = "Unknown"
            match_count = 0

            for node in nodes:
                class_attr = (await node.get_attribute("class")) or ""

                if "event__header" in class_attr:
                    raw_text = (await node.inner_text()).strip()
                    current_league = clean_league_name(raw_text)
                    print(f"📋 League: {current_league}")
                    continue

                try:
                    # Match elements
                    home_el = await node.query_selector("div.event__homeParticipant")
                    away_el = await node.query_selector("div.event__awayParticipant")
                    time_el = await node.query_selector("div.event__time")
                    match_id = await node.get_attribute("id")

                    if not all([home_el, away_el, time_el, match_id]):
                        continue

                    home = (await home_el.inner_text()).strip()
                    away = (await away_el.inner_text()).strip()
                    kickoff_raw = (await time_el.inner_text()).strip().replace("\n", " ")
                    match_id = match_id.replace("g_1_", "")

                    fixtures.append({
                        "fixture_id": f"fs_{match_id}",
                        "league": current_league,
                        "league_short": league_short_name(current_league),
                        "home_team": home,
                        "away_team": away,
                        "kickoff_raw": kickoff_raw,
                        "url": f"https://www.flashscore.com/match/{match_id}/",
                    })
                    match_count += 1

                    if match_count % 10 == 0:
                        print(f"📊 Scraped {match_count} matches...")

                except Exception as e:
                    print(f"⚠️ Error parsing match: {e}")
                    continue

            print(f"✅ Total fixtures scraped: {len(fixtures)}")
            await browser.close()

        return fixtures


if __name__ == "__main__":
    scraper = FlashscoreProvider(headless=True, slow_mo=500)
    fixtures = scraper.get_upcoming_fixtures()
    print(f"\n✅ Found {len(fixtures)} fixtures")
    for f in fixtures[:15]:
        print(f"  {f['home_team']} vs {f['away_team']} ({f['league_short']})")
        print(f"    Kickoff: {f['kickoff_raw']}")
        print(f"    URL: {f['url']}")