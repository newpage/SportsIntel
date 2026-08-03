"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

type Pick = {
  gameId: string;
  category: string;
  pick: string;
  confidence: number;
};

export default function MyPicksPage() {
  const [picks, setPicks] = useState<Pick[]>([]);

  useEffect(() => {
    setPicks(JSON.parse(localStorage.getItem("sportsintel-picks") ?? "[]"));
  }, []);

  function remove(category: string) {
    const next = picks.filter((pick) => pick.category !== category);
    setPicks(next);
    localStorage.setItem("sportsintel-picks", JSON.stringify(next));
  }

  return (
    <main>
      <header>
        <Link href="/">← Home</Link>
        <div className="subtle">Your saved decisions</div>
      </header>
      <h1>My Picks</h1>
      {picks.length === 0 ? (
        <article className="card empty-state">
          <h2>No picks saved yet</h2>
          <p className="subtle">Open a game and save your Survivor, Spread, or Total decision.</p>
          <Link className="primary-link" href="/">View recommendations</Link>
        </article>
      ) : (
        <section className="grid">
          {picks.map((pick) => (
            <article className="card" key={pick.category}>
              <div className="kicker">{pick.category}</div>
              <div className="pick">{pick.pick}</div>
              <div className="confidence">{pick.confidence}% confidence</div>
              <div className="card-actions">
                <Link href={`/games/${pick.gameId}`}>View game</Link>
                <button className="secondary-button" type="button" onClick={() => remove(pick.category)}>Remove</button>
              </div>
            </article>
          ))}
        </section>
      )}
    </main>
  );
}
