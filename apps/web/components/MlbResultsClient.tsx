"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

type CurrentGame = {
  game_id: string;
  away_team: string;
  home_team: string;
  completed: boolean;
  away_score: number | null;
  home_score: number | null;
  actual_winner: string | null;
};

type SavedPrediction = {
  game_id: string;
  away_team: string;
  home_team: string;
  moneyline_pick: string;
  confidence: number;
  prediction_date: string;
};

export function MlbResultsClient({ games }: { games: CurrentGame[] }) {
  const [saved, setSaved] = useState<Record<string, SavedPrediction>>({});

  useEffect(() => {
    try {
      setSaved(JSON.parse(localStorage.getItem("sportsintel-mlb-predictions") ?? "{}"));
    } catch {
      setSaved({});
    }
  }, []);

  const rows = useMemo(
    () =>
      games
        .filter((game) => saved[game.game_id])
        .map((game) => {
          const prediction = saved[game.game_id];
          const result = game.completed
            ? prediction.moneyline_pick === game.actual_winner
              ? "WIN"
              : "LOSS"
            : "PENDING";
          return { game, prediction, result };
        }),
    [games, saved],
  );

  const completed = rows.filter((row) => row.result !== "PENDING");
  const wins = completed.filter((row) => row.result === "WIN").length;
  const accuracy = completed.length ? Math.round((wins / completed.length) * 100) : 0;

  return (
    <>
      <section className="results-summary">
        <div><strong>{wins}</strong><span>wins</span></div>
        <div><strong>{completed.length - wins}</strong><span>losses</span></div>
        <div><strong>{accuracy}%</strong><span>accuracy</span></div>
      </section>

      {rows.length === 0 ? (
        <article className="card empty-state">
          <h2>No tracked MLB predictions yet</h2>
          <p className="subtle">Open the MLB page before games begin to save today&apos;s predictions.</p>
          <Link className="primary-button-link" href="/mlb">View MLB picks</Link>
        </article>
      ) : (
        <section className="results-list">
          {rows.map(({ game, prediction, result }) => (
            <article className="card result-row" key={game.game_id}>
              <div>
                <div className="kicker">{prediction.prediction_date}</div>
                <h3>{game.away_team} at {game.home_team}</h3>
                <p className="subtle">Pick: <strong>{prediction.moneyline_pick}</strong> · {prediction.confidence}% confidence</p>
              </div>
              <div className="result-score">
                {game.away_score !== null && game.home_score !== null
                  ? `${game.away_score} - ${game.home_score}`
                  : "Not final"}
              </div>
              <span className={`result-badge ${result.toLowerCase()}`}>{result}</span>
            </article>
          ))}
        </section>
      )}
    </>
  );
}
