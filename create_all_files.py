import os

files = {
    "draw_agent.py": '''#!/usr/bin/env python3
"""
Draw Matrix Pro – Complete System with Fixture Caching
"""

import logging
import os
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import requests

import config
from database import init_db, save_recommendation

init_db()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class BzzoiroClient:
    def __init__(self, api_token: str):
        self.base_url = "https://sports.bzzoiro.com/api/v2"
        self.headers = {"Authorization": f"Token {api_token}"}
    
    def get_live_events(self) -> List[Dict]:
        r = requests.get(f"{self.base_url}/events/live/", headers=self.headers, timeout=10)
        r.raise_for_status()
        return r.json().get('events', [])
    
    def get_events_by_date(self, date_from: str, date_to: str, league_id: Optional[int] = None) -> List[Dict]:
        params = {
            "date_from": date_from,
            "date_to": date_to,
            "limit": 200,
        }
        if league_id:
            params["league_id"] = league_id
        params["status"] = "notstarted"
        r = requests.get(f"{self.base_url}/events/", headers=self.headers, params=params, timeout=10)
        r.raise_for_status()
        result = r.json()
        if not result.get('events'):
            params.pop("status", None)
            r = requests.get(f"{self.base_url}/events/", headers=self.headers, params=params, timeout=10)
            r.raise_for_status()
            result = r.json()
        return result.get('events', [])
    
    def get_standings(self, league_id: int) -> List[Dict]:
        try:
            r = requests.get(f"{self.base_url}/leagues/{league_id}/standings/", headers=self.headers, timeout=10)
            r.raise_for_status()
            return r.json().get('standings', [])
        except Exception as e:
            logger.warning(f"Standings fetch failed: {e}")
            return []
    
    def get_event_odds(self, event_id: int) -> Dict:
        try:
            r = requests.get(f"{self.base_url}/events/{event_id}/odds/", headers=self.headers, timeout=10)
            r.raise_for_status()
            return r.json().get('odds', {})
        except Exception as e:
            logger.warning(f"Odds fetch failed: {e}")
            return {}
    
    def get_event_h2h(self, event_id: int) -> Dict:
        try:
            r = requests.get(f"{self.base_url}/events/{event_id}/h2h/", headers=self.headers, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f"H2H fetch failed: {e}")
            return {}
    
    def get_event_stats(self, event_id: int) -> Dict:
        try:
            r = requests.get(f"{self.base_url}/events/{event_id}/stats/", headers=self.headers, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f"Stats fetch failed: {e}")
            return {}
    
    def search_match_by_teams(self, home_team: str, away_team: str) -> Optional[Dict]:
        \"\"\"Search Bzzoiro for a match between two teams by name\"\"\"
        try:
            r = requests.get(
                f"{self.base_url}/events/",
                headers=self.headers,
                params={"team_name": home_team, "status": "notstarted", "limit": 20},
                timeout=10
            )
            r.raise_for_status()
            events = r.json().get('events', [])
            for e in events:
                if e.get('home_team') == home_team and e.get('away_team') == away_team:
                    return e
                if e.get('home_team') == away_team and e.get('away_team') == home_team:
                    return e
            return None
        except Exception as e:
            logger.debug(f"Match search failed: {e}")
            return None


def load_cached_fixtures() -> List[Dict]:
    try:
        with open("fixtures_cache.json", "r") as f:
            data = json.load(f)
            fixtures = data.get("fixtures", [])
            if fixtures:
                logger.info(f"📦 Loaded {len(fixtures)} fixtures from cache")
            return fixtures
    except Exception as e:
        logger.debug(f"Cache load failed: {e}")
        return []


# ----------------------------------------------------------------------
# SCORING FUNCTIONS
# ----------------------------------------------------------------------

def score_h2h_overall(h2h_data: Dict) -> float:
    total = h2h_data.get('total_matches', 0)
    draws = h2h_data.get('draws', 0)
    if total == 0:
        return config.LEAGUE_DRAW_RATES.get("default", 0.25)
    rate = draws / total
    weight = min(total / 10, 1.0)
    return rate * weight + 0.25 * (1 - weight)

def score_h2h_recent(h2h_data: Dict) -> float:
    recent = h2h_data.get('recent_matches', [])
    if len(recent) < 3:
        return config.LEAGUE_DRAW_RATES.get("default", 0.25)
    draws = sum(1 for m in recent[:5] if m.get('home_score') == m.get('away_score'))
    return draws / min(len(recent), 5)

def score_team_draw_form(event: Dict, stats: Dict) -> float:
    return 0.25

def score_team_streaks(stats: Dict) -> float:
    return 0.55

def score_league_draw_rate(league_name: str) -> float:
    return config.LEAGUE_DRAW_RATES.get(league_name, config.LEAGUE_DRAW_RATES.get("default", 0.25))

def score_match_importance(event: Dict, odds: Dict) -> float:
    importance = 0.4
    league_name = event.get('league_name', '')
    if league_name in config.LEAGUE_BONUSES:
        importance += config.LEAGUE_BONUSES[league_name]
    if 'cup' in league_name.lower() or 'puchar' in league_name.lower():
        importance += 0.0
    elif 'friendly' in league_name.lower():
        importance += config.FRIENDLY_PENALTY
    home_odds = odds.get('home_win', 3.0)
    away_odds = odds.get('away_win', 3.0)
    if home_odds <= config.HEAVY_FAVOURITE_ODDS or away_odds <= config.HEAVY_FAVOURITE_ODDS:
        importance += config.HEAVY_FAVOURITE_PENALTY
    draw_odds = odds.get('draw', 0)
    if 2.60 <= draw_odds <= 2.90:
        importance += 0.05
    return max(0.0, min(1.0, importance))

def score_referee(event: Dict) -> float:
    return 0.5

def score_odds_value(odds: float, estimated_prob: float) -> float:
    if odds <= 0:
        return 0.5
    implied = 1 / odds
    if estimated_prob <= 0:
        estimated_prob = 0.25
    ratio = implied / estimated_prob if estimated_prob > 0 else 0.5
    ratio_score = min(max(ratio, 0.3), 1.0)
    sweet_score = config.odds_preference_score(odds)
    return (ratio_score + sweet_score) / 2

def score_motivation(event: Dict, standings: List[Dict]) -> float:
    bonus = 0.0
    if event.get('is_local_derby', False):
        bonus += 0.50
    if standings:
        home_team = event.get('home_team')
        away_team = event.get('away_team')
        home_entry = next((s for s in standings if s.get('team_name') == home_team), None)
        away_entry = next((s for s in standings if s.get('team_name') == away_team), None)
        if home_entry and away_entry:
            home_pos = home_entry.get('position', 10)
            away_pos = away_entry.get('position', 10)
            if home_pos >= 18 and away_pos >= 18:
                bonus += 0.75
            elif home_pos >= 18 or away_pos >= 18:
                bonus += 0.50
    return max(-1.0, min(1.0, bonus))


def compute_draw_score(event: Dict, odds: Dict, h2h: Dict, stats: Dict, standings: List[Dict] = None) -> float:
    s1 = score_h2h_overall(h2h)
    s2 = score_h2h_recent(h2h)
    s3 = score_team_draw_form(event, stats)
    s4 = score_team_streaks(stats)
    s5 = score_league_draw_rate(event.get('league_name', ''))
    s6 = score_match_importance(event, odds)
    s7 = score_referee(event)
    
    raw_prob = (
        s1 * config.WEIGHTS["h2h_overall"] +
        s2 * config.WEIGHTS["h2h_recent"] +
        s3 * config.WEIGHTS["team_draw_form"] +
        s4 * config.WEIGHTS["team_streaks"] +
        s5 * config.WEIGHTS["league_draw_rate"] +
        s6 * config.WEIGHTS["match_importance"] +
        s7 * config.WEIGHTS["referee"]
    )
    if standings is not None:
        mot_bonus = score_motivation(event, standings)
        raw_prob += mot_bonus * config.WEIGHTS.get("motivation", 0.05)
    draw_odds = odds.get('draw', 3.50)
    s8 = score_odds_value(draw_odds, raw_prob)
    final_prob = raw_prob * (1 - config.WEIGHTS["odds_value"]) + s8 * config.WEIGHTS["odds_value"]
    return max(0.05, min(0.60, final_prob))


# ----------------------------------------------------------------------
# ANALYSIS
# ----------------------------------------------------------------------

def analyze_events(events: List[Dict], client: BzzoiroClient, source: str = "live", 
                   standings_cache: Dict[int, List[Dict]] = None) -> List[Dict]:
    results = []
    real_data_count = 0
    fallback_count = 0
    
    for event in events:
        event_id = event.get('id')
        home = event.get('home_team', 'Home')
        away = event.get('away_team', 'Away')
        league = event.get('league_name', 'Unknown')
        status = event.get('status', '')
        
        # Try to find real Bzzoiro match by team names
        bzzoiro_match = None
        if not str(event_id).isdigit():
            bzzoiro_match = client.search_match_by_teams(home, away)
            if bzzoiro_match:
                event_id = bzzoiro_match.get('id')
                event['league_id'] = bzzoiro_match.get('league_id')
                event['league_name'] = bzzoiro_match.get('league_name', league)
                logger.info(f"✅ Found Bzzoiro match: {home} vs {away} (ID: {event_id})")
                real_data_count += 1
        
        if source == "live":
            minute = event.get('current_minute', 0)
            if status == 'inprogress' and minute > 80:
                logger.info(f"Skipping {home} vs {away} – minute {minute} too late")
                continue
        
        if event_id and str(event_id).isdigit():
            odds = client.get_event_odds(event_id)
            h2h = client.get_event_h2h(event_id)
            stats = client.get_event_stats(event_id)
        else:
            odds = {'draw': 3.50, 'home_win': 2.50, 'away_win': 2.50}
            h2h = {'total_matches': 0, 'draws': 0}
            stats = {}
            fallback_count += 1
        
        draw_odds = odds.get('draw', 3.50)
        standings = []
        if standings_cache and event.get('league_id'):
            standings = standings_cache.get(event.get('league_id'), [])
        
        draw_prob = compute_draw_score(event, odds, h2h, stats, standings)
        
        if draw_prob >= config.BET_THRESHOLD:
            rec = "BET"
            confidence = "HIGH" if draw_prob >= 0.40 else "MEDIUM"
        elif draw_prob >= config.BORDERLINE_THRESHOLD:
            rec = "BORDERLINE"
            confidence = "LOW"
        else:
            rec = "SKIP"
            confidence = None
        
        logger.info(f"{home} vs {away} ({league}): {draw_prob:.2%} odds {draw_odds} → {rec}")
        
        if rec in ("BET", "BORDERLINE"):
            save_recommendation({
                "event_id": str(event_id) if event_id else f"fs_{home}_{away}",
                "home_team": home,
                "away_team": away,
                "tournament": league,
                "match_date": event.get('event_date', datetime.now().isoformat()),
                "draw_odds": draw_odds,
                "h2h_draw_rate": h2h.get('draws', 0) / max(h2h.get('total_matches', 1), 1),
                "heatmap_score": draw_prob,
                "recommendation": rec,
                "confidence": confidence,
                "result": "PENDING",
                "actual_score": None,
                "roi": None,
            })
        
        results.append({
            "home": home,
            "away": away,
            "tournament": league,
            "draw_probability": draw_prob,
            "recommendation": rec,
            "confidence": confidence,
            "draw_odds": draw_odds,
            "event_id": event_id,
            "score": f"{event.get('home_score', 0)}-{event.get('away_score', 0)}",
            "minute": event.get('current_minute', 0),
            "date": event.get('event_date', ''),
            "status": status,
            "news": "",
        })
    
    logger.info(f"📊 Summary: {real_data_count} matches with real Bzzoiro data, {fallback_count} with fallback")
    return results

def print_results(results: List[Dict], title: str = "LIVE RECOMMENDATIONS"):
    print("\n" + "="*80)
    print(f" DRAW MATRIX PRO – {title}")
    print("="*80)
    sorted_results = sorted(results, key=lambda x: x["draw_probability"], reverse=True)
    for r in sorted_results:
        icon = "🏆" if "cup" in r['tournament'].lower() or "puchar" in r['tournament'].lower() else "⚽"
        status_icon = "🟢 LIVE" if r['status'] == 'inprogress' else "📅 UPCOMING"
        conf_icon = "🔥" if r.get('confidence') == "HIGH" else "👍" if r.get('confidence') == "MEDIUM" else "⚠️"
        print(f"{icon} {r['home']} vs {r['away']}  ({r['tournament']})")
        print(f"   {status_icon} | Score: {r['score']} | Draw Prob: {r['draw_probability']:.2%} | Odds: {r['draw_odds']:.2f}")
        print(f"   {conf_icon} {r['recommendation']} {r.get('confidence', '')}")
        print("-"*80)


# ----------------------------------------------------------------------
# MAIN RUN FUNCTIONS
# ----------------------------------------------------------------------

def run_live_analysis():
    logger.info("Draw Matrix Pro – Starting LIVE analysis")
    api_token = os.getenv("BZZOIRO_TOKEN") or config.BZZOIRO_TOKEN
    if not api_token:
        logger.error("No API token found.")
        return
    client = BzzoiroClient(api_token)
    try:
        events = client.get_live_events()
        logger.info(f"Fetched {len(events)} live events")
    except Exception as e:
        logger.error(f"Failed to fetch events: {e}")
        return
    if not events:
        logger.info("No live events found")
        return
    results = analyze_events(events, client, source="live")
    print_results(results, "LIVE RECOMMENDATIONS")
    try:
        from telegram_bot import send_recommendations
        send_recommendations(results)
    except Exception as e:
        logger.error(f"Telegram alert failed: {e}")
    logger.info("Live analysis complete")
    return results

def run_fixture_analysis(date_from: str = None, date_to: str = None, days: int = 1):
    if not date_from:
        date_from = datetime.now().strftime("%Y-%m-%d")
    if not date_to:
        date_to = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    logger.info(f"Draw Matrix Pro – FIXTURE analysis ({date_from} to {date_to})")
    api_token = os.getenv("BZZOIRO_TOKEN") or config.BZZOIRO_TOKEN
    if not api_token:
        logger.error("No API token found.")
        return
    client = BzzoiroClient(api_token)
    events = load_cached_fixtures()
    if not events:
        logger.info("No cached fixtures found. Try: python fetch.py")
        return
    logger.info(f"📦 Using cached fixtures ({len(events)} matches)")
    standings_cache = {}
    for event in events:
        if event.get('league_id') and event.get('league_id') not in standings_cache:
            try:
                standings = client.get_standings(event['league_id'])
                if standings:
                    standings_cache[event['league_id']] = standings
                    logger.info(f"Fetched standings for league {event['league_id']}")
            except Exception as e:
                logger.warning(f"Standings fetch failed: {e}")
    results = analyze_events(events, client, source="fixture", standings_cache=standings_cache)
    print_results(results, f"FIXTURE RECOMMENDATIONS ({date_from} to {date_to})")
    try:
        from telegram_bot import send_recommendations
        send_recommendations(results)
    except Exception as e:
        logger.error(f"Telegram alert failed: {e}")
    logger.info("Fixture analysis complete")
    return results


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        run_live_analysis()
    elif sys.argv[1] == "fixtures":
        run_fixture_analysis(days=3)
    elif sys.argv[1] == "date" and len(sys.argv) == 4:
        run_fixture_analysis(sys.argv[2], sys.argv[3])
    else:
        print("""
Usage:
  python draw_agent.py               # Live matches
  python draw_agent.py fixtures      # Cached fixtures
  python draw_agent.py date YYYY-MM-DD YYYY-MM-DD
        """)
''',

    "config.py": '''# Draw Matrix Pro – Configuration
import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
BZZOIRO_TOKEN = os.getenv("BZZOIRO_TOKEN", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

DATABASE_PATH = os.getenv("DATABASE_PATH", "data/draw_matrix_pro.db")
SCHEDULE_INTERVAL = int(os.getenv("SCHEDULE_INTERVAL_MINUTES", 30))

# Heatmap Weights
WEIGHTS = {
    "h2h_overall": 0.18,
    "h2h_recent": 0.18,
    "team_draw_form": 0.12,
    "team_streaks": 0.08,
    "league_draw_rate": 0.10,
    "match_importance": 0.05,
    "referee": 0.04,
    "odds_value": 0.15,
    "motivation": 0.10,
}

# League bonuses
LEAGUE_BONUSES = {
    "Argentina Primera B": 0.15,
    "Argentina Primera B Nacional": 0.15,
    "Ecuador LigaPro": 0.10,
    "Uruguay Primera": 0.10,
    "Paraguay Division Intermedia": 0.10,
    "K League 1": 0.10,
    "Brazil Serie B": 0.05,
    "default": 0.0,
}

def odds_preference_score(odds: float) -> float:
    if odds is None or odds <= 0:
        return 0.5
    if 2.60 <= odds <= 2.90:
        return 1.0
    elif 2.91 <= odds <= 3.60:
        return 0.8
    elif 3.61 <= odds <= 4.50:
        return 0.5
    else:
        return 0.3

# Penalties
HEAVY_FAVOURITE_ODDS = 1.80
HEAVY_FAVOURITE_PENALTY = -0.15
LEAGUE_MATCH_BONUS = 0.05
FRIENDLY_PENALTY = -0.10
WOMEN_PENALTY = -0.20

# Thresholds
BET_THRESHOLD = 0.32
BORDERLINE_THRESHOLD = 0.28

# League draw rates (fallback)
LEAGUE_DRAW_RATES = {
    "Argentina Primera B": 0.35,
    "Argentina Primera B Nacional": 0.33,
    "Ecuador LigaPro": 0.28,
    "Uruguay Primera": 0.30,
    "Paraguay Division Intermedia": 0.32,
    "K League 1": 0.30,
    "Brazil Serie B": 0.28,
    "default": 0.25,
}
''',

    "database.py": '''# database.py – SQLite storage
import os
import sqlite3
from datetime import datetime

os.makedirs("data", exist_ok=True)
DB_PATH = "data/draw_matrix_pro.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT UNIQUE,
            home_team TEXT,
            away_team TEXT,
            tournament TEXT,
            match_date TEXT,
            draw_odds REAL,
            h2h_draw_rate REAL,
            heatmap_score REAL,
            recommendation TEXT,
            confidence TEXT,
            created_at TEXT,
            result TEXT,
            actual_score TEXT,
            roi REAL
        )
    """)
    conn.commit()
    conn.close()

def save_recommendation(data):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO recommendations (
            event_id, home_team, away_team, tournament, match_date,
            draw_odds, h2h_draw_rate, heatmap_score, recommendation,
            confidence, created_at, result, actual_score, roi
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("event_id"),
        data.get("home_team"),
        data.get("away_team"),
        data.get("tournament"),
        data.get("match_date"),
        data.get("draw_odds"),
        data.get("h2h_draw_rate"),
        data.get("heatmap_score"),
        data.get("recommendation"),
        data.get("confidence"),
        datetime.now().isoformat(),
        data.get("result", "PENDING"),
        data.get("actual_score"),
        data.get("roi"),
    ))
    conn.commit()
    conn.close()
''',

    "telegram_bot.py": '''# telegram_bot.py
import requests
import logging
import os

logger = logging.getLogger(__name__)

def send_telegram(message: str):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        logger.warning("Telegram not configured.")
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        r = requests.post(url, data={"chat_id": chat_id, "text": message, "parse_mode": "HTML"}, timeout=5)
        r.raise_for_status()
        logger.info("Telegram message sent.")
    except Exception as e:
        logger.error(f"Telegram failed: {e}")

def send_recommendations(results):
    bets = [r for r in results if r.get("recommendation") == "BET"]
    borderlines = [r for r in results if r.get("recommendation") == "BORDERLINE"]
    if not bets and not borderlines:
        send_telegram("🤖 No new recommendations.")
        return
    msg = "🤖 <b>Draw Matrix Pro – Recommendations</b>\\n\\n"
    if bets:
        msg += "✅ <b>BETS</b>:\\n"
        for r in bets:
            msg += f"  • {r['home']} vs {r['away']}\\n"
            msg += f"    Odds: {r.get('draw_odds', 'N/A')} | Score: {r['draw_probability']:.2%}\\n"
        msg += "\\n"
    if borderlines:
        msg += "⚠️ <b>BORDERLINE</b>:\\n"
        for r in borderlines[:5]:
            msg += f"  • {r['home']} vs {r['away']} ({r['draw_probability']:.2%})\\n"
    send_telegram(msg)
''',

    "fetch.py": '''#!/usr/bin/env python3
import json
import glob
from datetime import datetime

def load_cached_fixtures():
    try:
        with open("fixtures_cache.json", "r") as f:
            data = json.load(f)
            return data.get("fixtures", [])
    except:
        return []

def save_cached_fixtures(fixtures):
    with open("fixtures_cache.json", "w") as f:
        json.dump({"timestamp": datetime.now().isoformat(), "fixtures": fixtures}, f, indent=2)

def fetch():
    files = glob.glob("flashscore_fixtures_*.json")
    if files:
        latest = max(files)
        with open(latest, "r") as f:
            fixtures = json.load(f)
            events = []
            for f in fixtures:
                events.append({
                    "home_team": f.get("home", ""),
                    "away_team": f.get("away", ""),
                    "event_date": f.get("kickoff", ""),
                    "status": "notstarted",
                    "league_name": "Unknown"
                })
            save_cached_fixtures(events)
            print(f"✅ Loaded {len(events)} fixtures from {latest}")
            return events
    print("❌ No fixtures found")
    return []

if __name__ == "__main__":
    fetch()
''',

    "requirements.txt": '''requests>=2.31.0
python-dotenv>=1.0.0
playwright>=1.40.0
beautifulsoup4>=4.12.0
lxml>=4.9.0
streamlit>=1.28.0
pandas>=2.0.0
plotly>=5.17.0
'''
}

# Create all files
for filename, content in files.items():
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✅ Created {filename}")

print("\n✅ All files created successfully!")
print("\nNext steps:")
print("  1. Copy your .env file with BZZOIRO_TOKEN")
print("  2. Run: python fetch.py")
print("  3. Run: python draw_agent.py fixtures")