#!/usr/bin/env python3
"""
Draw Matrix Pro – Complete System with Date Selection, Live Indicators, News
Version: 2.1
"""

import logging
import os
import json
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
        self._league_cache = {}
    
    def get_live_events(self) -> List[Dict]:
        r = requests.get(f"{self.base_url}/events/live/", headers=self.headers, timeout=10)
        r.raise_for_status()
        return r.json().get('events', [])
    
    def get_events_by_date(self, date_from: str, date_to: str, league_id: Optional[int] = None) -> List[Dict]:
        params = {
            "date_from": date_from,
            "date_to": date_to,
            "limit": 200,
            "status": "upcoming"
        }
        if league_id:
            params["league_id"] = league_id
        
        try:
            r = requests.get(f"{self.base_url}/events/", headers=self.headers, params=params, timeout=10)
            r.raise_for_status()
            result = r.json()
            events = result.get('results', []) or result.get('events', [])
            if events:
                logger.info(f"Bzzoiro: {len(events)} fixtures")
                return events
        except Exception as e:
            logger.warning(f"Bzzoiro fixtures failed: {e}")
        
        return []
    
    def get_standings(self, league_id: int) -> List[Dict]:
        try:
            r = requests.get(
                f"{self.base_url}/leagues/{league_id}/standings/",
                headers=self.headers,
                timeout=10
            )
            r.raise_for_status()
            return r.json().get('standings', [])
        except Exception as e:
            logger.warning(f"Standings fetch failed: {e}")
            return []
    
    def get_league_name(self, league_id: int) -> str:
        if league_id in self._league_cache:
            return self._league_cache[league_id]
        
        try:
            r = requests.get(
                f"{self.base_url}/leagues/{league_id}/",
                headers=self.headers,
                timeout=10
            )
            r.raise_for_status()
            data = r.json()
            name = data.get('name', 'Unknown')
            self._league_cache[league_id] = name
            return name
        except Exception as e:
            logger.warning(f"League fetch failed for {league_id}: {e}")
            return 'Unknown'
    
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
    
    def get_event_news(self, event_id: int) -> Dict:
        try:
            r = requests.get(f"{self.base_url}/events/{event_id}/metadata/", headers=self.headers, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f"News fetch failed for {event_id}: {e}")
            return {}
    
    def get_team_stats(self, team_id: int) -> Dict:
        try:
            r = requests.get(
                f"{self.base_url}/teams/{team_id}/stats/",
                headers=self.headers,
                timeout=10
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f"Team stats fetch failed for {team_id}: {e}")
            return {}


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
    if len(recent) < 2:
        return config.LEAGUE_DRAW_RATES.get("default", 0.25)
    
    weighted_draws = 0
    total_weight = 0
    for i, m in enumerate(recent[:8]):
        weight = 1 / (i + 1)
        if m.get('home_score') == m.get('away_score'):
            weighted_draws += weight
        total_weight += weight
    
    if total_weight == 0:
        return 0.25
    return weighted_draws / total_weight


def score_team_draw_form(event: Dict, stats: Dict) -> float:
    if not stats:
        return 0.25
    
    home_stats = stats.get('home', {})
    away_stats = stats.get('away', {})
    
    home_played = home_stats.get('played', 0)
    home_draws = home_stats.get('draws', 0)
    away_played = away_stats.get('played', 0)
    away_draws = away_stats.get('draws', 0)
    
    home_rate = home_draws / home_played if home_played > 0 else 0.25
    away_rate = away_draws / away_played if away_played > 0 else 0.25
    
    return (home_rate + away_rate) / 2


def score_team_streaks(stats: Dict) -> float:
    if not stats:
        return 0.55
    
    home_stats = stats.get('home', {})
    away_stats = stats.get('away', {})
    
    home_gf = home_stats.get('goals_for', 0)
    home_ga = home_stats.get('goals_against', 0)
    away_gf = away_stats.get('goals_for', 0)
    away_ga = away_stats.get('goals_against', 0)
    
    home_avg = (home_gf + home_ga) / 2 if home_stats else 0
    away_avg = (away_gf + away_ga) / 2 if away_stats else 0
    total_avg = home_avg + away_avg
    
    under_2_5 = 1 - min(total_avg / 4, 1)
    return 0.4 + (under_2_5 * 0.3)


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
    
    draw_odds = odds.get('draw', 0)
    if 2.60 <= draw_odds <= 2.90:
        importance += 0.05
    
    return max(0.0, min(1.0, importance))


def score_referee(event: Dict) -> float:
    return 0.5


def score_news(news: Dict) -> float:
    if not news:
        return 0
    
    preview = news.get('preview', '')
    if not preview:
        return 0
    
    bonus = 0
    keywords = {
        'must win': 0.3,
        'relegation': 0.3,
        'title race': 0.3,
        'derby': 0.4,
        'injury crisis': -0.2,
        'rested': 0.2,
        'fatigue': -0.2,
        'nothing to play for': -0.5,
        'dead rubber': -0.5
    }
    
    preview_lower = preview.lower()
    for word, value in keywords.items():
        if word in preview_lower:
            bonus += value
    
    return max(-0.5, min(0.5, bonus))


def score_motivation(event: Dict, standings: List[Dict], news: Dict = None) -> float:
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
    
    if news:
        bonus += score_news(news)
    
    return max(-1.0, min(1.0, bonus))


def calculate_kelly_fraction(probability: float, odds: float) -> float:
    if odds <= 1 or probability <= 0:
        return 0
    
    b = odds - 1
    p = probability
    q = 1 - p
    
    if b <= 0:
        return 0
    
    f = (b * p - q) / b
    return max(0, min(f, 0.25))


def score_odds_value(odds: float, estimated_prob: float) -> float:
    if odds <= 0 or estimated_prob <= 0:
        return 0.5
    
    ev = (estimated_prob * odds) - 1
    
    if ev > 0.2:
        return 1.0
    elif ev > 0.1:
        return 0.8
    elif ev > 0.0:
        return 0.6
    elif ev > -0.1:
        return 0.4
    else:
        return 0.2


# ----------------------------------------------------------------------
# MAIN SCORING ENGINE
# ----------------------------------------------------------------------

def compute_draw_score(event: Dict, odds: Dict, h2h: Dict, stats: Dict, standings: List[Dict] = None, news: Dict = None) -> Dict:
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
    
    mot_bonus = score_motivation(event, standings or [], news)
    raw_prob += mot_bonus * config.WEIGHTS.get("motivation", 0.10)
    
    draw_odds = odds.get('draw', 3.50)
    s8 = score_odds_value(draw_odds, raw_prob)
    final_prob = raw_prob * (1 - config.WEIGHTS["odds_value"]) + s8 * config.WEIGHTS["odds_value"]
    
    final_prob = max(0.05, final_prob)
    kelly = calculate_kelly_fraction(final_prob, draw_odds)
    ev = (final_prob * draw_odds) - 1
    
    return {
        "probability": final_prob,
        "kelly": kelly,
        "ev": ev,
        "motivation_bonus": mot_bonus
    }


# ----------------------------------------------------------------------
# REASONING GENERATOR
# ----------------------------------------------------------------------

def generate_reasoning(event: Dict, odds: Dict, h2h: Dict, draw_prob: float) -> str:
    reasons = []
    
    total = h2h.get('total_matches', 0)
    draws = h2h.get('draws', 0)
    if total > 0:
        rate = draws / total
        reasons.append(f"H2H draw rate: {rate:.1%} ({draws}/{total} meetings)")
    
    draw_odds = odds.get('draw', 0)
    if draw_odds > 0:
        implied = 1 / draw_odds
        reasons.append(f"Value odds ({draw_odds:.2f}, implied {implied:.1%})")
    
    league = event.get('league_name', 'Unknown')
    if league != 'Unknown':
        reasons.append(f"League: {league}")
    
    round_num = event.get('round_number')
    if round_num is not None and round_num >= 38:
        reasons.append("Late season (Round 38+)")
    
    if event.get('is_local_derby', False):
        reasons.append("Derby match")
    
    return " | ".join(reasons)


# ----------------------------------------------------------------------
# HELPER FUNCTIONS
# ----------------------------------------------------------------------

def get_match_icon(league_name: str) -> str:
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
    if status == 'live' or status == 'inprogress':
        return f"🟢 LIVE {minute}'" if minute else "🟢 LIVE"
    elif status == 'notstarted':
        return "📅 UPCOMING"
    elif status == 'finished':
        return "✅ FINISHED"
    else:
        return f"⏸️ {status}"

def get_confidence_icon(confidence: str) -> str:
    if confidence == "HIGH":
        return "🔥"
    elif confidence == "MEDIUM":
        return "👍"
    elif confidence == "LOW":
        return "⚠️"
    return ""

def format_match_output(result: Dict) -> str:
    icon = get_match_icon(result['tournament'])
    status_icon = get_status_icon(result['status'], result.get('minute'))
    confidence_icon = get_confidence_icon(result.get('confidence', ''))
    
    lines = []
    lines.append(f"{icon} {result['home']} vs {result['away']}  ({result['tournament']})")
    lines.append(f"   {status_icon} | Score: {result['score']} | Draw Prob: {result['draw_probability']:.2%} | Odds: {result['draw_odds']:.2f}")
    lines.append(f"   EV: {result.get('ev', 0):.2f} | Kelly: {result.get('kelly', 0):.2%}")
    lines.append(f"   {confidence_icon} {result['recommendation']} {result.get('confidence', '')}")
    
    if result.get('news'):
        lines.append(f"   {result['news'][:100]}...")
    
    return "\n".join(lines)


# ----------------------------------------------------------------------
# ANALYSIS FUNCTIONS
# ----------------------------------------------------------------------

def analyze_events(events: List[Dict], client: BzzoiroClient, source: str = "live") -> List[Dict]:
    results = []
    
    for event in events:
        event_id = event.get('id')
        home = event.get('home_team', 'Home')
        away = event.get('away_team', 'Away')
        
        league = 'Unknown'
        league_id = event.get('league_id')
        if league_id:
            league = client.get_league_name(league_id)
        
        status = event.get('status', '')
        
        if source == "live":
            minute = event.get('current_minute', 0)
            if status == 'inprogress' and minute > 80:
                logger.info(f"Skipping {home} vs {away} – minute {minute} too late")
                continue
        
        odds = client.get_event_odds(event_id)
        h2h = client.get_event_h2h(event_id)
        stats = client.get_event_stats(event_id)
        news = client.get_event_news(event_id)
        
        home_stats = {}
        away_stats = {}
        if event.get('home_team_id'):
            home_stats = client.get_team_stats(event['home_team_id'])
        if event.get('away_team_id'):
            away_stats = client.get_team_stats(event['away_team_id'])
        combined_stats = {'home': home_stats, 'away': away_stats}
        
        if not odds:
            logger.info(f"Skipping {home} vs {away} – no odds available")
            continue
        
        draw_odds = odds.get('draw')
        if not draw_odds:
            logger.info(f"Skipping {home} vs {away} – no draw odds")
            continue
        
        standings = []
        if league_id:
            standings = client.get_standings(league_id)
        
        result = compute_draw_score(event, odds, h2h, combined_stats, standings, news)
        draw_prob = result["probability"]
        kelly = result["kelly"]
        ev = result["ev"]
        
        if kelly > 0.10:
            confidence = "HIGH"
            rec = "BET"
        elif kelly > 0.05:
            confidence = "MEDIUM"
            rec = "BET"
        elif kelly > 0.02:
            confidence = "LOW"
            rec = "BORDERLINE"
        else:
            confidence = None
            rec = "SKIP"
        
        news_preview = ""
        if news and isinstance(news, dict):
            if 'preview' in news:
                news_preview = news['preview']
            elif 'fun_facts' in news:
                news_preview = news['fun_facts']
        
        reasoning = generate_reasoning(event, odds, h2h, draw_prob)
        logger.info(f"{home} vs {away} ({league}): {draw_prob:.2%} odds {draw_odds} | EV: {ev:.2f} Kelly: {kelly:.2%} -> {rec} | {reasoning}")
        
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
            "ev": ev,
            "kelly": kelly,
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
    
    try:
        events = client.get_events_by_date(date_from, date_to)
        if events:
            logger.info(f"Bzzoiro: {len(events)} fixtures")
        else:
            logger.info("No fixtures found from Bzzoiro")
            return
    except Exception as e:
        logger.error(f"Failed to fetch fixtures: {e}")
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
# CLI ENTRY POINT
# ----------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
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