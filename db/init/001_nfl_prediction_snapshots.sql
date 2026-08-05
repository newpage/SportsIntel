CREATE TABLE IF NOT EXISTS nfl_prediction_snapshots (
    id BIGSERIAL PRIMARY KEY,
    game_id TEXT NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL,
    pick TEXT NOT NULL,
    model_probability DOUBLE PRECISION NOT NULL,
    displayed_confidence INTEGER NOT NULL,
    raw_confidence INTEGER NOT NULL,
    confidence_cap INTEGER NOT NULL,
    readiness_label TEXT NOT NULL,
    season_phase TEXT NOT NULL,
    away_qb_status TEXT NOT NULL,
    home_qb_status TEXT NOT NULL,
    away_moneyline DOUBLE PRECISION,
    home_moneyline DOUBLE PRECISION,
    market_pick_probability DOUBLE PRECISION,
    model_market_edge DOUBLE PRECISION,
    qualified_consensus_status TEXT NOT NULL,
    qualified_consensus_classification TEXT NOT NULL,
    qualified_consensus_quality_score INTEGER NOT NULL,
    model_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS nfl_prediction_snapshots_game_captured_idx
    ON nfl_prediction_snapshots (game_id, captured_at DESC, id DESC);
