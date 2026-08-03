import os
from functools import lru_cache

import feedparser

from app.models import NewsItem


@lru_cache(maxsize=1)
def fetch_yahoo_nfl_news() -> list[NewsItem]:
    """Fetch the latest Yahoo Sports NFL RSS headlines.

    Failure is non-fatal: the prediction engine continues without news.
    """
    url = os.getenv("YAHOO_NFL_RSS_URL", "https://sports.yahoo.com/nfl/rss/")
    feed = feedparser.parse(url)
    return [
        NewsItem(
            title=entry.get("title", "NFL update"),
            link=entry.get("link", ""),
            published=entry.get("published"),
        )
        for entry in feed.entries[:12]
    ]


def news_for_teams(away_team: str, home_team: str) -> list[NewsItem]:
    names = {away_team.lower(), home_team.lower()}
    matched = [item for item in fetch_yahoo_nfl_news() if any(name in item.title.lower() for name in names)]
    return matched[:3]
