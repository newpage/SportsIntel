"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

type Pick = {
  gameId: string;
  category: string;
  pick: string;
  confidence: number;
};

const CATEGORY_ORDER = ["Survivor", "Spread", "Total"];

function confidenceLabel(value: number) {
  if (value >= 80) return "High confidence";
  if (value >= 68) return "Medium confidence";
  return "Low confidence";
}

export default function MyPicksPage() {
  const [picks, setPicks] = useState<Pick[]>([]);

  useEffect(() => {
    try {
      setPicks(JSON.parse(localStorage.getItem("sportsintel-picks") ?? "[]"));
    } catch {
      setPicks([]);
    }
  }, []);

  const orderedPicks = useMemo(
    () => [...picks].sort((a, b) => CATEGORY_ORDER.indexOf(a.category) - CATEGORY_ORDER.indexOf(b.category)),
    [picks],
  );

  const averageConfidence = orderedPicks.length
    ? Math.round(orderedPicks.reduce((total, pick) => total + pick.confidence, 0) / orderedPicks.length)
    : 0;

  function save(next: Pick[]) {
    setPicks(next);
    localStorage.setItem("sportsintel-picks", JSON.stringify(next));
  }

  function remove(category: string) {
    save(picks.filter((pick) => pick.category !== category));
  }

  function clearAll() {
    save([]);
  }

  return (
    <main>
      <header>
        <Link className="back-link" href="/">← Home</Link>
        <div className="subtle">Saved on this browser</div>
      </header>

      <section className="picks-heading">
        <div>
          <div className="eyebrow">Weekly decision sheet</div>
          <h1>My Picks</h1>
          <p className="subtle">Your Survivor, Spread, and Total choices in one place.</p>
        </div>

        {orderedPicks.length > 0 && (
          <div className="picks-summary">
            <div>
              <strong>{orderedPicks.length}</strong>
              <span>saved picks</span>
            </div>
            <div>
              <strong>{averageConfidence}%</strong>
              <span>average confidence</span>
            </div>
          </div>
        )}
      </section>

      {orderedPicks.length === 0 ? (
        <article className="card empty-state picks-empty">
          <div className="empty-icon">✓</div>
          <h2>No picks saved yet</h2>
          <p className="subtle">Open a game and save your Survivor, Spread, or Total decision.</p>
          <Link className="primary-button-link" href="/">View recommendations</Link>
        </article>
      ) : (
        <>
          <section className="picks-grid">
            {orderedPicks.map((pick) => (
              <article className="card saved-pick-card" key={pick.category}>
                <div className="saved-pick-top">
                  <div>
                    <div className="kicker">{pick.category}</div>
                    <div className="saved-pick-name">{pick.pick}</div>
                  </div>
                  <div className="saved-confidence">
                    <strong>{pick.confidence}%</strong>
                    <span>{confidenceLabel(pick.confidence)}</span>
                  </div>
                </div>

                <div className="confidence-track">
                  <span style={{ width: `${pick.confidence}%` }} />
                </div>

                <div className="saved-pick-actions">
                  <Link href={`/games/${pick.gameId}`}>View game →</Link>
                  <button className="secondary-button" type="button" onClick={() => remove(pick.category)}>
                    Remove
                  </button>
                </div>
              </article>
            ))}
          </section>

          <div className="clear-picks-row">
            <button className="danger-button" type="button" onClick={clearAll}>
              Clear all picks
            </button>
          </div>
        </>
      )}
    </main>
  );
}
