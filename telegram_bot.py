# telegram_bot.py
import requests
import logging
from typing import List, Dict
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
        data = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        response = requests.post(url, data=data, timeout=5)
        response.raise_for_status()
        logger.info("Telegram message sent.")
    except Exception as e:
        logger.error(f"Failed to send Telegram: {e}")
        
def send_recommendations(results):
    bets = [r for r in results if r.get("recommendation") == "BET"]
    borderlines = [r for r in results if r.get("recommendation") == "BORDERLINE"]
    
    if not bets and not borderlines:
        send_telegram("🤖 No new recommendations.")
        return
    
    msg = "🤖 <b>Draw Matrix Pro – Recommendations</b>\n\n"
    
    if bets:
        msg += "✅ <b>BETS</b>:\n"
        for r in bets:
            msg += f"  • {r['home']} vs {r['away']}\n"
            msg += f"    Odds: {r.get('draw_odds', 'N/A')} | Score: {r['draw_probability']:.2%}\n"
            if r.get('reasoning'):
                msg += f"    💡 {r['reasoning']}\n"
        msg += "\n"
    
    if borderlines:
        msg += "⚠️ <b>BORDERLINE</b>:\n"
        for r in borderlines[:5]:
            msg += f"  • {r['home']} vs {r['away']} ({r['draw_probability']:.2%})\n"
    
    send_telegram(msg)


def send_recommendations(results: List[Dict]):
    bets = [r for r in results if r.get("recommendation") == "BET"]
    borderlines = [r for r in results if r.get("recommendation") == "BORDERLINE"]
    
    if not bets and not borderlines:
        send_telegram("🤖 Draw Matrix Pro: No new recommendations.")
        return
    
    message = "🤖 <b>Draw Matrix Pro – Recommendations</b>\n\n"
    
    if bets:
        message += "✅ <b>BETS</b>:\n"
        for r in bets:
            message += f"  • {r['home']} vs {r['away']}\n"
            message += f"    Odds: {r.get('draw_odds', 'N/A')} | Score: {r['draw_probability']:.2%}\n"
        message += "\n"
    
    if borderlines:
        message += "⚠️ <b>BORDERLINE</b>:\n"
        for r in borderlines[:5]:
            message += f"  • {r['home']} vs {r['away']} ({r['draw_probability']:.2%})\n"
    
    send_telegram(message)