import asyncio
import json
import subprocess
import re
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError


async def scrape_flashscore():
    fixtures = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    async with async_playwright() as p:
        print("Launching browser...")
        browser = await p.chromium.launch(headless=False, slow_mo=100)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()

        print("Loading Flashscore...")
        try:
            await page.goto("https://www.flashscore.com/football/", timeout=60000)
            await page.wait_for_load_state("networkidle")
            # Wait for any match or section to load
            await page.wait_for_selector("div.section__content, div.event__match, div.tournament__matches", timeout=20000)
        except PlaywrightTimeoutError:
            print("Timeout – no matches found or page too slow")
            await browser.close()
            return

        # Accept cookies
        try:
            await page.click("button#onetrust-accept-btn-handler", timeout=5000)
            print("Cookie banner dismissed")
        except:
            print("No cookie banner")

        # Get all match blocks
        matches = await page.query_selector_all("div.event__match")
        print(f"Found {len(matches)} matches")

        # Try to get league from surrounding elements
        for idx, match in enumerate(matches, 1):
            try:
                # Get match elements
                home_el = await match.query_selector("div.event__homeParticipant")
                away_el = await match.query_selector("div.event__awayParticipant")
                time_el = await match.query_selector("div.event__time")
                match_id = await match.get_attribute("id")

                if not all([home_el, away_el, time_el, match_id]):
                    continue

                home = (await home_el.inner_text()).strip()
                away = (await away_el.inner_text()).strip()
                kickoff = (await time_el.inner_text()).strip().replace("\n", " ")
                match_id = match_id.replace("g_1_", "")

                # Try to find league from parent elements
                league = "Unknown"
                try:
                    # Walk up the DOM to find league name
                    parent = match
                    for _ in range(5):
                        parent = await parent.evaluate("el => el.parentElement")
                        if not parent:
                            break
                        # Check for league-related attributes
                        class_name = await parent.get_attribute("class") or ""
                        if "tournament" in class_name or "section" in class_name or "league" in class_name:
                            text = await parent.inner_text()
                            if text and len(text) < 100:
                                # Extract first line as league name
                                league = text.split("\n")[0].strip()
                                if league and league != home and league != away:
                                    break
                except:
                    pass

                # If still Unknown, try to find a header near this match
                if league == "Unknown":
                    try:
                        # Look for a header before this match
                        prev_sibling = await match.evaluate("""
                            el => {
                                let prev = el.previousElementSibling;
                                while (prev) {
                                    if (prev.className && prev.className.includes('header')) {
                                        return prev.innerText;
                                    }
                                    prev = prev.previousElementSibling;
                                }
                                return null;
                            }
                        """)
                        if prev_sibling:
                            league = prev_sibling.split(" - ")[0].strip() if " - " in prev_sibling else prev_sibling.strip()
                    except:
                        pass

                fixture = {
                    "home": home,
                    "away": away,
                    "kickoff": kickoff,
                    "league": league,
                    "url": f"https://www.flashscore.com/match/{match_id}/"
                }
                fixtures.append(fixture)

                # Print with league
                print(f"{idx:3d}. {home} vs {away} @ {kickoff} [{league}]")

            except Exception as e:
                continue

        await browser.close()

    # Save JSON
    if fixtures:
        filename = f"flashscore_fixtures_{timestamp}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(fixtures, f, indent=2, ensure_ascii=False)
        print(f"\n✅ Saved {len(fixtures)} fixtures → {filename}")

        # Auto GitHub push
        try:
            subprocess.run(["git", "add", "."], check=True)
            subprocess.run(["git", "commit", "-m", f"Daily fixtures {timestamp}"], check=True)
            subprocess.run(["git", "push"], check=True)
            print("Pushed to GitHub successfully!")
        except subprocess.CalledProcessError as e:
            print(f"Git failed: {e}")
        except FileNotFoundError:
            print("Git not found in PATH – install Git or remove push block")
    else:
        print("No fixtures scraped today.")


if __name__ == "__main__":
    asyncio.run(scrape_flashscore())