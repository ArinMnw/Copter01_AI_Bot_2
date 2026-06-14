import httpx
import asyncio
from datetime import datetime, timezone, timedelta
import config

# Use bot_log or direct print depending on project structure
try:
    from bot_log import log_event
except ImportError:
    def log_event(*args, **kwargs):
        pass

NEWS_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
BKK = timezone(timedelta(hours=7))

_news_events = []
_last_fetch_time = 0

async def fetch_news_loop(app=None):
    """Background task to fetch news every 6 hours"""
    while True:
        try:
            await _fetch_news()
        except Exception as e:
            print(f"[{datetime.now(BKK).strftime('%H:%M:%S')}] ⚠️ [News Filter] Error fetching news: {e}")
        
        await asyncio.sleep(6 * 3600)  # Sleep for 6 hours

async def _fetch_news():
    global _news_events, _last_fetch_time
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(NEWS_URL)
        response.raise_for_status()
        data = response.json()
        
        events = []
        for item in data:
            if item.get("country") == "USD" and item.get("impact") == "High":
                date_str = item.get("date")
                try:
                    # ff_calendar_thisweek returns ISO format with offset e.g., "2024-06-14T10:00:00-04:00"
                    event_time = datetime.fromisoformat(date_str)
                    events.append({
                        "title": item.get("title"),
                        "time": event_time,
                        "impact": item.get("impact"),
                        "country": item.get("country")
                    })
                except Exception as e:
                    print(f"[{datetime.now(BKK).strftime('%H:%M:%S')}] ⚠️ [News Filter] Parse error: {e} for date {date_str}")
        
        _news_events = sorted(events, key=lambda x: x["time"])
        _last_fetch_time = datetime.now().timestamp()
        print(f"[{datetime.now(BKK).strftime('%H:%M:%S')}] 📰 [News Filter] Fetch complete. Found {len(_news_events)} High-Impact USD events this week.")

def is_news_embargo_active() -> tuple[bool, str]:
    """
    Check if we are within the embargo window of any high-impact news.
    Returns (is_active, reason_string)
    """
    if not getattr(config, "NEWS_FILTER_ENABLED", True):
        return False, ""
        
    embargo_before = getattr(config, "NEWS_EMBARGO_BEFORE_MINS", 15)
    embargo_after = getattr(config, "NEWS_EMBARGO_AFTER_MINS", 15)
        
    now = datetime.now(timezone.utc)
    
    for event in _news_events:
        event_time = event["time"].astimezone(timezone.utc)
        start_embargo = event_time - timedelta(minutes=embargo_before)
        end_embargo = event_time + timedelta(minutes=embargo_after)
        
        if start_embargo <= now <= end_embargo:
            event_bkk = event_time.astimezone(BKK).strftime('%H:%M BKK')
            reason = f"High Impact News: '{event['title']}' at {event_bkk}"
            return True, reason
            
    return False, ""

def get_upcoming_news() -> list[dict]:
    """Return a list of upcoming high impact news events"""
    now = datetime.now(timezone.utc)
    return [e for e in _news_events if e["time"].astimezone(timezone.utc) >= now]
