#!/usr/bin/env python3
"""
Draw Matrix Pro – Complete System with Date Selection, Live Indicators, News
"""

import logging
import os
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
    """Fetch events for a specific date range"""
    params = {
        "date_from": date_from,
        "date_to": date_to,
        "limit": 200,
    }
    if league_id:
        params["league_id"] = league_id
    
    # Try with status=notstarted
    params["status"] = "upcoming"
    
    r = requests.get(f"{self.base_url}/events/", headers=self.headers, params=params, timeout=10)
    r.raise_for_status()
    result = r.json()
    
    # If no results, try without status filter
    if not result.get('events'):
        params.pop("status", None)
        r = requests.get(f"{self.base_url}/events/", headers=self.headers, params=params, timeout=10)
        r.raise_for_status()
        result = r.json()
    
    return result.get('events', [])
    
    
    
    
    def get_event_odds(self, event_id: int) -> Dict:
        try:
            r = requests.get(f"{self.base_url}/events/{event_id}/odds/", headers=self.headers, timeout=10)
            r.raise_for_status()
            return r.json().get('odds', {})
        except Exception as e:
            logger.warning(f"Odds fetch failed for {event_id}: {e}")
            return {}
    
    def get_event_h2h(self, event_id: int) -> Dict:
        try:
            r = requests.get(f"{self.base_url}/events/{event_id}/h2h/", headers=self.headers, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f"H2H fetch failed for {event_id}: {e}")
            return {}
    
    def get_event_stats(self, event_id: int) -> Dict:
        try:
            r = requests.get(f"{self.base_url}/events/{event_id}/stats/", headers=self.headers, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f"Stats fetch failed for {event_id}: {e}")
            return {}
    
    def get_event_news(self, event_id: int) -> List[Dict]:
        """Fetch match news/preview"""
        try:
            r = requests.get(f"{self.base_url}/events/{event_id}/metadata/", headers=self.headers, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f"News fetch failed for {event_id}: {e}")
            return {}


# ----------------------------------------------------------------------
# Scoring functions
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


# ----------------------------------------------------------------------
# Main scoring engine
# ----------------------------------------------------------------------

def compute_draw_score(event: Dict, odds: Dict, h2h: Dict, stats: Dict) -> float:
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
    
    draw_odds = odds.get('draw', 3.50)
    s8 = score_odds_value(draw_odds, raw_prob)
    final_prob = raw_prob * (1 - config.WEIGHTS["odds_value"]) + s8 * config.WEIGHTS["odds_value"]
    
    return max(0.05, min(0.60, final_prob))


# ----------------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------------

def get_match_icon(league_name: str) -> str:
    """Return icon based on competition type"""
    league_lower = league_name.lower()
    if 'cup' in league_lower or 'puchar' in league_lower:
        return "🏆"
    elif 'champions' in league_lower:
        return "⭐"
    elif 'europa' in league_lower:
        return "🌍"
    elif 'friendly' in league_lower:
        return "🤝"
    else:
        return "⚽"

def get_status_icon(status: str, minute: Optional[int] = None) -> str:
    """Return status indicator"""
    if status == 'live' or status == 'inprogress':
        return f"🟢 LIVE {minute}'" if minute else "🟢 LIVE"
    elif status == 'notstarted':
        return "📅 UPCOMING"
    elif status == 'finished':
        return "✅ FINISHED"
    else:
        return f"⏸️ {status}"

def get_confidence_icon(confidence: str) -> str:
    """Return confidence indicator"""
    if confidence == "HIGH":
        return "🔥"
    elif confidence == "MEDIUM":
        return "👍"
    elif confidence == "LOW":
        return "⚠️"
    return ""

def format_match_output(result: Dict) -> str:
    """Format a single match recommendation"""
    icon = get_match_icon(result['tournament'])
    status_icon = get_status_icon(result['status'], result.get('minute'))
    confidence_icon = get_confidence_icon(result.get('confidence', ''))
    
    lines = []
    lines.append(f"{icon} {result['home']} vs {result['away']}  ({result['tournament']})")
    lines.append(f"   {status_icon} | Score: {result['score']} | Draw Prob: {result['draw_probability']:.2%} | Odds: {result['draw_odds']:.2f}")
    lines.append(f"   {confidence_icon} {result['recommendation']} {result.get('confidence', '')}")
    
    if result.get('news'):
        lines.append(f"   📰 {result['news'][:100]}...")
    
    return "\n".join(lines)


# ----------------------------------------------------------------------
# Analysis functions
# ----------------------------------------------------------------------

def analyze_events(events: List[Dict], client: BzzoiroClient, source: str = "live") -> List[Dict]:
    """Analyze a list of events and return recommendations"""
    results = []
    
    for event in events:
        event_id = event.get('id')
        home = event.get('home_team', 'Home')
        away = event.get('away_team', 'Away')
        league = event.get('league_name', 'Unknown')
        status = event.get('status', '')
        
        # Skip live matches that are too old
        if source == "live":
            minute = event.get('current_minute', 0)
            if status == 'inprogress' and minute > 80:
                logger.info(f"Skipping {home} vs {away} – minute {minute} too late")
                continue
        
        # Fetch odds, H2H, stats, news
        odds = client.get_event_odds(event_id)
        h2h = client.get_event_h2h(event_id)
        stats = client.get_event_stats(event_id)
        news = client.get_event_news(event_id)
        
        if not odds:
            logger.info(f"Skipping {home} vs {away} – no odds available")
            continue
        
        draw_odds = odds.get('draw')
        if not draw_odds:
            logger.info(f"Skipping {home} vs {away} – no draw odds")
            continue
        
        draw_prob = compute_draw_score(event, odds, h2h, stats)
        
        if draw_prob >= config.BET_THRESHOLD:
            rec = "BET"
            confidence = "HIGH" if draw_prob >= 0.40 else "MEDIUM"
        elif draw_prob >= config.BORDERLINE_THRESHOLD:
            rec = "BORDERLINE"
            confidence = "LOW"
        else:
            rec = "SKIP"
            confidence = None
        
        # Extract news preview
        news_preview = ""
        if news and isinstance(news, dict):
            if 'preview' in news:
                news_preview = news['preview']
            elif 'fun_facts' in news:
                news_preview = news['fun_facts']
        
        logger.info(f"{home} vs {away} ({league}): {draw_prob:.2%} odds {draw_odds} → {rec}")
        
        if rec in ("BET", "BORDERLINE"):
            save_recommendation({
                "event_id": str(event_id),
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
            "news": news_preview,
        })
    
    return results

def print_results(results: List[Dict], title: str = "LIVE RECOMMENDATIONS"):
    print("\n" + "="*80)
    print(f" DRAW MATRIX PRO – {title}")
    print("="*80)
    
    sorted_results = sorted(results, key=lambda x: x["draw_probability"], reverse=True)
    for r in sorted_results:
        print(format_match_output(r))
        print("-"*80)


# ----------------------------------------------------------------------
# Main run functions
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
    
    try:
        events = client.get_events_by_date(date_from, date_to)
        logger.info(f"Fetched {len(events)} fixtures")
    except Exception as e:
        logger.error(f"Failed to fetch fixtures: {e}")
        return
    
    if not events:
        logger.info("No fixtures found for this date range")
        return
    
    results = analyze_events(events, client, source="fixture")
    print_results(results, f"FIXTURE RECOMMENDATIONS ({date_from} to {date_to})")
    
    try:
        from telegram_bot import send_recommendations
        send_recommendations(results)
    except Exception as e:
        logger.error(f"Telegram alert failed: {e}")
    
    logger.info("Fixture analysis complete")
    return results


# ----------------------------------------------------------------------
# CLI entry point
# ----------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        # Default: live analysis
        run_live_analysis()
    
    elif sys.argv[1] == "today":
        run_fixture_analysis(days=1)
    
    elif sys.argv[1] == "tomorrow":
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        run_fixture_analysis(tomorrow, tomorrow)
    
    elif sys.argv[1] == "fixtures":
        run_fixture_analysis(days=3)
    
    elif sys.argv[1] == "date" and len(sys.argv) == 4:
        run_fixture_analysis(sys.argv[2], sys.argv[3])
    
    else:
        print("""
Usage:
  python draw_agent.py               # Live matches
  python draw_agent.py today         # Today's fixtures
  python draw_agent.py tomorrow      # Tomorrow's fixtures
  python draw_agent.py fixtures      # Next 3 days fixtures
  python draw_agent.py date YYYY-MM-DD YYYY-MM-DD   # Custom date range
        """)