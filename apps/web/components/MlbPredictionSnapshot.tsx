"use client";

import { useEffect } from "react";

type Game = {
  game_id: string;
  away_team: string;
  home_team: string;
  moneyline_pick: string;
  confidence: number;
};

export function MlbPredictionSnapshot({ date, games }: { date: string; games: Game[] }) {
  useEffect(() => {
    const key = "sportsintel-mlb-predictions";
    let stored: Record<string, any> = {};

    try {
      stored = JSON.parse(localStorage.getItem(key) ?? "{}");
    } catch {
      stored = {};
    }

    for (const game of games) {
      if (!stored[game.game_id]) {
        stored[game.game_id] = {
          ...game,
          prediction_date: date,
          saved_at: new Date().toISOString(),
        };
      }
    }

    localStorage.setItem(key, JSON.stringify(stored));
  }, [date, games]);

  return null;
}
