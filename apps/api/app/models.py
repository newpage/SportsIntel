from pydantic import BaseModel, Field


class NewsItem(BaseModel):
    title: str
    link: str
    published: str | None = None


class Prediction(BaseModel):
    game_id: str
    away_team: str
    home_team: str
    winner: str
    win_probability: float = Field(ge=0, le=1)
    projected_margin: float
    market_spread: float
    projected_total: float
    market_total: float
    confidence: int = Field(ge=0, le=100)
    survivor_score: int = Field(ge=0, le=100)
    spread_pick: str
    total_pick: str
    reasons: list[str]
    news: list[NewsItem] = []
