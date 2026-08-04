from __future__ import annotations

TEAM_RATINGS: dict[str, float] = {
    "Arizona Cardinals": 47.0,
    "Atlanta Falcons": 50.0,
    "Baltimore Ravens": 58.0,
    "Buffalo Bills": 59.0,
    "Carolina Panthers": 44.0,
    "Chicago Bears": 50.0,
    "Cincinnati Bengals": 56.0,
    "Cleveland Browns": 46.0,
    "Dallas Cowboys": 52.0,
    "Denver Broncos": 54.0,
    "Detroit Lions": 58.0,
    "Green Bay Packers": 56.0,
    "Houston Texans": 55.0,
    "Indianapolis Colts": 49.0,
    "Jacksonville Jaguars": 49.0,
    "Kansas City Chiefs": 60.0,
    "Las Vegas Raiders": 45.0,
    "Los Angeles Chargers": 54.0,
    "Los Angeles Rams": 55.0,
    "Miami Dolphins": 52.0,
    "Minnesota Vikings": 55.0,
    "New England Patriots": 48.0,
    "New Orleans Saints": 45.0,
    "New York Giants": 45.0,
    "New York Jets": 47.0,
    "Philadelphia Eagles": 60.0,
    "Pittsburgh Steelers": 52.0,
    "San Francisco 49ers": 56.0,
    "Seattle Seahawks": 53.0,
    "Tampa Bay Buccaneers": 55.0,
    "Tennessee Titans": 46.0,
    "Washington Commanders": 57.0,
}


NFL_TEAM_ALIASES: dict[str, str] = {
    "Arizona": "Arizona Cardinals",
    "Atlanta": "Atlanta Falcons",
    "Baltimore": "Baltimore Ravens",
    "Buffalo": "Buffalo Bills",
    "Carolina": "Carolina Panthers",
    "Chicago": "Chicago Bears",
    "Cincinnati": "Cincinnati Bengals",
    "Cleveland": "Cleveland Browns",
    "Dallas": "Dallas Cowboys",
    "Denver": "Denver Broncos",
    "Detroit": "Detroit Lions",
    "Green Bay": "Green Bay Packers",
    "Houston": "Houston Texans",
    "Indianapolis": "Indianapolis Colts",
    "Jacksonville": "Jacksonville Jaguars",
    "Kansas City": "Kansas City Chiefs",
    "LA Chargers": "Los Angeles Chargers",
    "LA Rams": "Los Angeles Rams",
    "Las Vegas": "Las Vegas Raiders",
    "Miami": "Miami Dolphins",
    "Minnesota": "Minnesota Vikings",
    "New England": "New England Patriots",
    "New Orleans": "New Orleans Saints",
    "NY Giants": "New York Giants",
    "NY Jets": "New York Jets",
    "Philadelphia": "Philadelphia Eagles",
    "Pittsburgh": "Pittsburgh Steelers",
    "San Francisco": "San Francisco 49ers",
    "Seattle": "Seattle Seahawks",
    "Tampa Bay": "Tampa Bay Buccaneers",
    "Tennessee": "Tennessee Titans",
    "Washington": "Washington Commanders",
}


def normalize_team_name(team_name: str) -> str:
    normalized = team_name.strip()
    return NFL_TEAM_ALIASES.get(normalized, normalized)


DEFAULT_TEAM_RATING = 50.0
HOME_FIELD_RATING = 1.5
RATING_VERSION = "nfl-provisional-ratings-v1"


def team_rating(team_name: str) -> float:
    return TEAM_RATINGS.get(team_name, DEFAULT_TEAM_RATING)
