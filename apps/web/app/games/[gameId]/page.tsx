import Link from "next/link";
import { SavePickButton } from "../../../components/SavePickButton";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8300";

export default async function GamePage({ params }: { params: Promise<{ gameId: string }> }) {
  const { gameId } = await params;
  const response = await fetch(`${API_URL}/api/games/${gameId}`, { cache: "no-store" });
  if (!response.ok) return <main><p>Game not found.</p></main>;
  const game = await response.json();

  return (
    <main>
      <header><Link href="/">← Home</Link><Link href="/my-picks">My Picks</Link></header>
      <article className="card game-analysis">
        <div className="kicker">{game.away_team} at {game.home_team}</div>
        <div className="pick">{game.winner}</div>
        <div className="confidence-row"><strong>{game.confidence}%</strong><span>confidence</span></div>
        <div className="confidence-track"><span style={{ width: `${game.confidence}%` }} /></div>
        <p className="subtle">{Math.round(game.win_probability * 100)}% projected win probability</p>

        <h2>Why</h2>
        <ul className="reason-list">{game.reasons.slice(0, 4).map((reason: string) => <li key={reason}>{reason}</li>)}</ul>

        <section className="decision-grid">
          <div><span className="subtle">Spread</span><strong>{game.spread_pick}</strong></div>
          <div><span className="subtle">Total</span><strong>{game.total_pick} {game.market_total}</strong></div>
          <div><span className="subtle">Model total</span><strong>{game.projected_total}</strong></div>
        </section>

        <div className="save-actions">
          <SavePickButton gameId={gameId} category="Survivor" pick={game.winner} confidence={game.confidence} />
          <SavePickButton gameId={gameId} category="Spread" pick={game.spread_pick} confidence={game.confidence} />
          <SavePickButton gameId={gameId} category="Total" pick={`${game.total_pick} ${game.market_total}`} confidence={game.confidence} />
        </div>

        <h2>Yahoo Sports News</h2>
        {game.news.length ? (
          <ul className="news-list">{game.news.slice(0, 4).map((item: any) => <li key={item.link}><a href={item.link} target="_blank" rel="noreferrer">{item.title}</a></li>)}</ul>
        ) : <p className="subtle">No matching Yahoo NFL headlines right now.</p>}
      </article>
    </main>
  );
}
