import Link from "next/link";
import { SavePickButton } from "../../../components/SavePickButton";
import { getGame } from "../../../lib/api";

function confidenceLevel(confidence: number) {
  if (confidence >= 80) return { label: "High confidence", className: "high" };
  if (confidence >= 68) return { label: "Medium confidence", className: "medium" };
  return { label: "Low confidence", className: "low" };
}

export default async function GamePage({ params }: { params: Promise<{ gameId: string }> }) {
  const { gameId } = await params;
  const game = await getGame(gameId);
  if (!game) return <main><p>Game not found.</p></main>;

  const confidence = confidenceLevel(game.confidence);
  const spreadEdge = Math.abs(game.projected_margin + game.market_spread);
  const totalEdge = Math.abs(game.projected_total - game.market_total);

  return (
    <main>
      <header>
        <Link className="back-link" href="/">← Home</Link>
        <Link className="top-nav-link" href="/my-picks">My Picks</Link>
      </header>

      <article className="card game-analysis">
        <section className="game-summary">
          <div className="game-summary-copy">
            <div className="kicker">Game decision</div>
            <div className="matchup">{game.away_team} at {game.home_team}</div>
            <div className="game-pick-label">SportsIntel pick</div>
            <div className="game-pick">{game.winner}</div>
            <p className="game-probability">
              {Math.round(game.win_probability * 100)}% projected win probability
            </p>
          </div>

          <div className={`confidence-panel ${confidence.className}`}>
            <span>{confidence.label}</span>
            <strong>{game.confidence}%</strong>
            <div className="confidence-track">
              <span style={{ width: `${game.confidence}%` }} />
            </div>
          </div>
        </section>

        <section className="why-section">
          <div className="section-heading">
            <div>
              <div className="eyebrow">Decision factors</div>
              <h2>Why this pick</h2>
            </div>
          </div>
          <ul className="reason-list clean-reasons">
            {game.reasons.slice(0, 5).map((reason: string) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </section>

        <section className="market-grid">
          <div className="market-card">
            <span>Spread pick</span>
            <strong>{game.spread_pick}</strong>
            <small>{spreadEdge.toFixed(1)} point model edge</small>
          </div>
          <div className="market-card">
            <span>Total pick</span>
            <strong>{game.total_pick} {game.market_total}</strong>
            <small>{totalEdge.toFixed(1)} point model edge</small>
          </div>
          <div className="market-card">
            <span>Model projection</span>
            <strong>{game.winner} by {Math.abs(game.projected_margin).toFixed(1)}</strong>
            <small>Projected total {game.projected_total}</small>
          </div>
        </section>

        <div className="save-actions">
          <SavePickButton gameId={gameId} category="Survivor" pick={game.winner} confidence={game.confidence} />
          <SavePickButton gameId={gameId} category="Spread" pick={game.spread_pick} confidence={game.confidence} />
          <SavePickButton gameId={gameId} category="Total" pick={`${game.total_pick} ${game.market_total}`} confidence={game.confidence} />
        </div>

        <section className="game-news-section">
          <div className="section-heading">
            <div>
              <div className="eyebrow">Only source used</div>
              <h2>Yahoo Sports News</h2>
            </div>
            <span className="subtle">Relevant headlines only.</span>
          </div>

          {game.news.length ? (
            <div className="game-news-list">
              {game.news.slice(0, 5).map((item: any) => (
                <a className="game-news-item" key={item.link} href={item.link} target="_blank" rel="noreferrer">
                  <span>{item.title}</span>
                  <small className={item.impact < 0 ? "impact-negative" : item.impact > 0 ? "impact-positive" : "subtle"}>
                    {item.category.replaceAll("_", " ")}
                    {item.impact ? ` · impact ${item.impact > 0 ? "+" : ""}${item.impact}` : ""}
                  </small>
                </a>
              ))}
            </div>
          ) : (
            <p className="subtle">No matching Yahoo NFL headlines right now.</p>
          )}
        </section>
      </article>
    </main>
  );
}
