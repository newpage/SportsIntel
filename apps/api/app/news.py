import os
import time

import feedparser

from app.models import NewsItem


TEAM_ALIASES = {
    "Buffalo Bills": ("buffalo bills", "bills", "buffalo"),
    "New York Jets": ("new york jets", "jets", "nyj"),
    "Detroit Lions": ("detroit lions", "lions", "detroit"),
    "Green Bay Packers": ("green bay packers", "packers", "green bay"),
    "Kansas City Chiefs": ("kansas city chiefs", "chiefs", "kansas city"),
    "Los Angeles Chargers": ("los angeles chargers", "chargers", "la chargers"),
}

NEGATIVE_TERMS = (
    "ruled out",
    "out for",
    "injured",
    "injury",
    "placed on ir",
    "injured reserve",
    "suspended",
    "questionable",
    "doubtful",
    "limited in practice",
    "will miss",
)
POSITIVE_TERMS = (
    "activated",
    "cleared",
    "returns",
    "returning",
    "full practice",
    "healthy",
    "available",
    "expected to play",
)

_CACHE: tuple[float, list[NewsItem]] | None = None
CACHE_SECONDS = 900


def _classify(title: str) -> tuple[str, int]:
    lowered = title.lower()
    if any(term in lowered for term in NEGATIVE_TERMS):
        return "INJURY", -3
    if any(term in lowered for term in POSITIVE_TERMS):
        return "AVAILABILITY", 2
    if any(term in lowered for term in ("trade", "signs", "waived", "released", "roster")):
        return "ROSTER", 0
    return "TEAM_NEWS", 0


def _matched_team(title: str) -> str | None:
    lowered = title.lower()
    for team, aliases in TEAM_ALIASES.items():
        if any(alias in lowered for alias in aliases):
            return team
    return None


def fetch_yahoo_nfl_news() -> list[NewsItem]:
    """Fetch Yahoo Sports NFL RSS headlines with a short in-memory cache.

    Yahoo is the only news provider in v1. A feed failure is non-fatal and
    leaves the prediction engine operational with neutral news impact.
    """
    global _CACHE
    now = time.monotonic()
    if _CACHE and _CACHE[0] > now:
        return _CACHE[1]

    url = os.getenv("YAHOO_NFL_RSS_URL", "https://sports.yahoo.com/nfl/rss/")
    feed = feedparser.parse(url)
    items: list[NewsItem] = []
    for entry in feed.entries[:24]:
        title = entry.get("title", "NFL update")
        category, impact = _classify(title)
        items.append(
            NewsItem(
                title=title,
                link=entry.get("link", ""),
                published=entry.get("published"),
                category=category,
                impact=impact,
                matched_team=_matched_team(title),
            )
        )

    _CACHE = (now + CACHE_SECONDS, items)
    return items


def news_for_teams(away_team: str, home_team: str) -> list[NewsItem]:
    teams = {away_team, home_team}
    return [item for item in fetch_yahoo_nfl_news() if item.matched_team in teams][:5]


def team_news_impact(team: str, items: list[NewsItem]) -> int:
    impact = sum(item.impact for item in items if item.matched_team == team)
    return max(-6, min(6, impact))
