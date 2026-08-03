from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.engine import all_predictions

app = FastAPI(title="SportsIntel API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3300"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "healthy", "service": "SportsIntel API"}


@app.get("/api/home")
def home():
    predictions = all_predictions()
    survivor = max(predictions, key=lambda item: item.survivor_score)
    spread = max(predictions, key=lambda item: abs(item.projected_margin + item.market_spread))
    total = max(predictions, key=lambda item: abs(item.projected_total - item.market_total))
    return {
        "week": 1,
        "best_survivor": survivor,
        "best_spread": spread,
        "best_total": total,
        "games": predictions,
    }


@app.get("/api/games/{game_id}")
def game(game_id: str):
    for prediction in all_predictions():
        if prediction.game_id == game_id:
            return prediction
    raise HTTPException(status_code=404, detail="Game not found")
