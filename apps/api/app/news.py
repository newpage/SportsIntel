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

SEVERE_NEGATIVE_TERMS = (
    "ruled out",
    "will miss",
    "placed on ir",
    "injured reserve",
    "suspended",
    "season-ending",
    "out for season",
)
MODERATE_NEGATIVE_TERMS = (
    "doubtful",
    "questionable",
    "limited in practice",
    "did not practice",
    "injured",
    "injury",
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

POSITION_TERMS = {
    "QUARTERBACK": ("quarterback", " qb ", "starting qb", "signal-caller"),
    "OFFENSIVE_LINE": (
        "offensive line",
        "left tackle",
        "right tackle",
        "left guard",
        "right guard",
        "center",
    ),
    "DEFENSE": (
        "cornerback",
        "linebacker",
        "defensive end",
        "defensive tackle",
        "safety",
        "pass rusher",
    ),
}

_CACHE: tuple[float, list[NewsItem]] | None = None
CACHE_SECONDS = 900


def _category(title: str) -> str:
    lowered = f" {title.lower()} "
    for category, terms in POSITION_TERMS.items():
        if any(term in lowered for term in terms):
            return category
    if any(term in lowered for term in ("coach", "coordinator", "play-caller")):
        return "COACHING"
    if any(term in lowered for term in ("suspended", "suspension")):
        return "SUSPENSION"
    if any(term in lowered for term in ("trade", "signs", "waived", "released", "roster")):
        return "ROSTER"
    return "TEAM_NEWS"


def _impact(title: str, category: str) -> int:
    lowered = title.lower()

    if any(term in lowered for term in SEVERE_NEGATIVE_TERMS):
        base = -4
    elif any(term in lowered for term in MODERATE_NEGATIVE_TERMS):
        base = -2
    elif any(term in lowered for term in POSITIVE_TERMS):
        base = 2
    else:
        base = 0

    if base and category == "QUARTERBACK":
        base += -1 if base < 0 else 1
    elif base and category == "OFFENSIVE_LINE":
        base += -1 if base < 0 else 0

    return max(-5, min(4, base))


def _classify(title: str) -> tuple[str, int]:
    category = _category(title)
    return category, _impact(title, category)


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
    matched = [item for item in fetch_yahoo_nfl_news() if item.matched_team in teams]
    return sorted(matched, key=lambda item: abs(item.impact), reverse=True)[:5]


def team_news_impact(team: str, items: list[NewsItem]) -> int:
    impact = sum(item.impact for item in items if item.matched_team == team)
    return max(-7, min(7, impact))
