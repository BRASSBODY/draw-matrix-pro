#!/usr/bin/env python3
"""
API Manager – Routes requests to the best available API
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import config
from bzzoiro_client import BzzoiroClient

logger = logging.getLogger(__name__)


class APIManager:
    def __init__(self):
        self.bzzoiro = BzzoiroClient(config.BZZOIRO_TOKEN) if config.BZZOIRO_TOKEN else None
        
    def get_live_matches(self) -> List[Dict]:
        """Get live matches from Bzzoiro"""
        if self.bzzoiro:
            try:
                events = self.bzzoiro.get_live_events()
                if events:
                    logger.info(f"Bzzoiro: {len(events)} live matches")
                    return events
            except Exception as e:
                logger.warning(f"Bzzoiro live failed: {e}")
        return []
    
    def get_fixtures(self, date_from: str = None, date_to: str = None, days: int = 3) -> List[Dict]:
        """Get fixtures – try Bzzoiro, then FlashScore scraper"""
        if not date_from:
            date_from = datetime.now().strftime("%Y-%m-%d")
        if not date_to:
            date_to = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        
        # Try Bzzoiro first
        if self.bzzoiro:
            try:
                events = self.bzzoiro.get_events_by_date(date_from, date_to)
                if events:
                    logger.info(f"Bzzoiro: {len(events)} fixtures")
                    return events
            except Exception as e:
                logger.warning(f"Bzzoiro fixtures failed: {e}")
        
        # Try FlashScore scraper
        try:
            from flashscore_scraper import FlashscoreProvider
            scraper = FlashscoreProvider(headless=True)
            fixtures = scraper.get_upcoming_fixtures()
            if fixtures:
                logger.info(f"FlashScore: {len(fixtures)} fixtures")
                # Convert to Bzzoiro format
                events = []
                for f in fixtures:
                    events.append({
                        'id': f.get('fixture_id', '').replace('fs_', ''),
                        'home_team': f.get('home_team', ''),
                        'away_team': f.get('away_team', ''),
                        'league_name': f.get('league_short', f.get('league', '')),
                        'event_date': f.get('kickoff_raw', ''),
                        'status': 'notstarted',
                        'source': 'flashscore'
                    })
                return events
        except Exception as e:
            logger.warning(f"FlashScore scraper failed: {e}")
        
        return []
    
    def get_odds(self, event_id: int) -> Dict:
        if self.bzzoiro:
            try:
                return self.bzzoiro.get_event_odds(event_id)
            except Exception as e:
                logger.warning(f"Bzzoiro odds failed for {event_id}: {e}")
        return {}
    
    def get_h2h(self, event_id: int) -> Dict:
        if self.bzzoiro:
            try:
                return self.bzzoiro.get_event_h2h(event_id)
            except Exception as e:
                logger.warning(f"Bzzoiro H2H failed for {event_id}: {e}")
        return {}
    
    def get_stats(self, event_id: int) -> Dict:
        if self.bzzoiro:
            try:
                return self.bzzoiro.get_event_stats(event_id)
            except Exception as e:
                logger.warning(f"Bzzoiro stats failed: {e}")
        return {}
    
    def get_standings(self, league_id: int) -> List[Dict]:
        if self.bzzoiro:
            try:
                return self.bzzoiro.get_standings(league_id)
            except Exception as e:
                logger.warning(f"Bzzoiro standings failed: {e}")
        return []