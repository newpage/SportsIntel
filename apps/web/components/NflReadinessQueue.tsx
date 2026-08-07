"use client";

import Link from "next/link";
import { useState } from "react";
import type { NflReviewResponse } from "../lib/sports";

type Attention = NflReviewResponse["attention"];
type Disposition = "all" | "ready" | "watch" | "hold";

const filters: Array<{
  disposition: Exclude<Disposition, "all">;
  label: string;
  description: string;
}> = [
  {
    disposition: "ready",
    label: "Ready",
    description: "No major review blocker detected",
  },
  {
    disposition: "watch",
    label: "Watch",
    description: "Monitor new information before game time",
  },
  {
    disposition: "hold",
    label: "Hold",
    description: "Resolve major gaps before promotion",
  },
];

export default function NflReadinessQueue({ attention }: { attention: Attention }) {
  const [selected, setSelected] = useState<Disposition>("all");
  const games = selected === "all"
    ? attention.queue
    : attention.queue.filter((item) => item.disposition === selected);

  return (
    <>
      <div className="readiness-filter-heading">
        <span className="subtle" aria-live="polite">
          Showing {games.length} of {attention.queue.length} games
        </span>
        <button
          className="readiness-all-button"
          type="button"
          aria-pressed={selected === "all"}
          onClick={() => setSelected("all")}
        >
          All games
        </button>
      </div>
      <div className="mlb-detail-grid readiness-filters">
        {filters.map((filter) => (
          <button
            className="market-card readiness-filter"
            data-active={selected === filter.disposition}
            type="button"
            aria-pressed={selected === filter.disposition}
            onClick={() => setSelected(filter.disposition)}
            key={filter.disposition}
          >
            <span>{filter.label}</span>
            <strong>{attention.disposition_counts[filter.disposition] || 0}</strong>
            <small>{filter.description}</small>
          </button>
        ))}
      </div>
      <div className="grid">
        {games.map((item) => (
          <article className="card recommendation-card" key={item.game_id || item.matchup}>
            <div className="section-heading">
              <span className="status-badge">{item.disposition_label}</span>
              <span className="subtle">
                {item.priority_level} priority · {item.priority_score}
              </span>
            </div>
            <h3>{item.matchup}</h3>
            <div className="game-pick-label">Current lean</div>
            <div className="compact-pick-name">
              {item.pick || "Not available"}
              {item.confidence !== null && item.confidence !== undefined
                ? ` · ${item.confidence}%`
                : ""}
            </div>
            <ul>
              {item.reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
            <div className="subtle">{item.recommended_action}</div>
            {item.game_id && (
              <Link className="primary-button-link" href={`/nfl/${item.game_id}`}>
                Review game
              </Link>
            )}
          </article>
        ))}
        {!games.length && (
          <div className="card subtle readiness-empty">
            No games currently have this readiness status.
          </div>
        )}
      </div>
    </>
  );
}
