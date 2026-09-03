#!/usr/bin/env python3
"""
Backtest Engine – Draw Matrix Pro
Tests the model against historical match data
"""

import json
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import sys

# Import your scoring functions
from draw_agent import (
    BzzoiroClient, compute_draw_score,
    score_h2h_overall, score_h2h_recent,
    score_league_draw_rate, score_match_importance,
    score_odds_value, score_referee,
    score_team_draw_form, score_team_streaks
)
import config

class BacktestEngine:
    def __init__(self, api_token: str):
        self.client = BzzoiroClient(api_token)
        self.results = []
    
    def fetch_historical_matches(self, date_from: str, date_to: str, league_id: Optional[int] = None) -> List[Dict]:
        """Fetch finished matches for a date range"""
        params = {
            "date_from": date_from,
            "date_to": date_to,
            "status": "finished",
            "limit": 200,
        }
        if league_id:
            params["league_id"] = league_id
        
        r = requests.get(
            f"{self.client.base_url}/events/",
            headers=self.client.headers,
            params=params,
            timeout=10
        )
        r.raise_for_status()
        return r.json().get('events', [])
    
    def run_backtest(self, date_from: str, date_to: str, league_id: Optional[int] = None):
        """Run backtest on historical matches"""
        print(f"\n{'='*60}")
        print(f" BACKTEST: {date_from} to {date_to}")
        print(f"{'='*60}")
        
        events = self.fetch_historical_matches(date_from, date_to, league_id)
        print(f"Found {len(events)} finished matches")
        
        bets = []
        correct = 0
        total_roi = 0
        total_stake = 0
        
        for event in events:
            event_id = event.get('id')
            home = event.get('home_team', 'Home')
            away = event.get('away_team', 'Away')
            league = event.get('league_name', 'Unknown')
            
            # Get actual result
            home_score = event.get('home_score', 0)
            away_score = event.get('away_score', 0)
            is_draw = home_score == away_score
            
            # Skip if no score
            if home_score is None or away_score is None:
                continue
            
            # Get odds, H2H, stats
            odds = self.client.get_event_odds(event_id)
            h2h = self.client.get_event_h2h(event_id)
            stats = self.client.get_event_stats(event_id)
            
            if not odds:
                continue
            
            draw_odds = odds.get('draw')
            if not draw_odds:
                continue
            
            # Compute draw probability
            draw_prob = compute_draw_score(event, odds, h2h, stats)
            
            # Check if it would be a bet
            is_bet = draw_prob >= config.BET_THRESHOLD
            is_borderline = draw_prob >= config.BORDERLINE_THRESHOLD
            
            if is_bet or is_borderline:
                result = "WIN" if is_draw else "LOSS"
                if is_draw:
                    correct += 1
                    roi = draw_odds - 1
                    total_roi += roi
                else:
                    roi = -1
                    total_roi += roi
                total_stake += 1
                
                bets.append({
                    "match": f"{home} vs {away}",
                    "league": league,
                    "score": f"{home_score}-{away_score}",
                    "draw_prob": draw_prob,
                    "odds": draw_odds,
                    "result": result,
                    "roi": roi,
                    "confidence": "HIGH" if draw_prob >= 0.40 else "MEDIUM" if draw_prob >= 0.32 else "BORDERLINE"
                })
        
        # Summary
        print(f"\n📊 RESULTS")
        print(f"{'-'*40}")
        print(f"Total bets: {total_stake}")
        print(f"Wins: {correct}")
        print(f"Losses: {total_stake - correct}")
        print(f"Win rate: {correct/total_stake*100:.1f}%" if total_stake > 0 else "N/A")
        print(f"Total ROI: {total_roi:.2f} units")
        print(f"Avg ROI per bet: {(total_roi/total_stake)*100:.1f}%" if total_stake > 0 else "N/A")
        
        # Show winning bets
        print(f"\n✅ WINNING BETS")
        print(f"{'-'*40}")
        for b in bets:
            if b['result'] == 'WIN':
                print(f"  {b['match']} ({b['league']})")
                print(f"    Score: {b['score']} | Prob: {b['draw_prob']:.1%} | Odds: {b['odds']:.2f} | ROI: +{b['roi']:.2f}")
        
        # Show losing bets (top 10)
        print(f"\n❌ LOSING BETS (Top 10 by probability)")
        print(f"{'-'*40}")
        losers = [b for b in bets if b['result'] == 'LOSS']
        losers_sorted = sorted(losers, key=lambda x: x['draw_prob'], reverse=True)
        for b in losers_sorted[:10]:
            print(f"  {b['match']} ({b['league']})")
            print(f"    Score: {b['score']} | Prob: {b['draw_prob']:.1%} | Odds: {b['odds']:.2f} | ROI: {b['roi']:.1f}")
        
        # Confidence breakdown
        print(f"\n📈 CONFIDENCE BREAKDOWN")
        print(f"{'-'*40}")
        high = [b for b in bets if b['confidence'] == 'HIGH']
        med = [b for b in bets if b['confidence'] == 'MEDIUM']
        border = [b for b in bets if b['confidence'] == 'BORDERLINE']
        
        if high:
            wins = sum(1 for b in high if b['result'] == 'WIN')
            print(f"  HIGH ({len(high)} bets): {wins/len(high)*100:.1f}% win rate")
        if med:
            wins = sum(1 for b in med if b['result'] == 'WIN')
            print(f"  MEDIUM ({len(med)} bets): {wins/len(med)*100:.1f}% win rate")
        if border:
            wins = sum(1 for b in border if b['result'] == 'WIN')
            print(f"  BORDERLINE ({len(border)} bets): {wins/len(border)*100:.1f}% win rate")
        
        self.results = bets
        return bets

def run():
    api_token = "acec18e5caf0091791d1afee0a220d04140fc040"
    engine = BacktestEngine(api_token)
    
    # Backtest last 30 days
    today = datetime.now().strftime("%Y-%m-%d")
    month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    engine.run_backtest(month_ago, today)
    
    # Optional: test specific league
    # engine.run_backtest(month_ago, today, league_id=1)  # Premier League

if __name__ == "__main__":
    run()