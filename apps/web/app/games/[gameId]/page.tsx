import Link from "next/link";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8300";

export default async function GamePage({ params }: { params: Promise<{ gameId: string }> }) {
  const { gameId } = await params;
  const response = await fetch(`${API_URL}/api/games/${gameId}`, { cache: "no-store" });
  if (!response.ok) return <main><p>Game not found.</p></main>;
  const game = await response.json();

  return (
    <main>
      <header><Link href="/">← Home</Link><div className="subtle">SportsIntel Game</div></header>
      <article className="card">
        <div className="kicker">{game.away_team} at {game.home_team}</div>
        <div className="pick">Pick: {game.winner}</div>
        <div className="confidence">{game.confidence}% confidence · {Math.round(game.win_probability * 100)}% win probability</div>
        <h3>Why</h3>
        <ul>{game.reasons.map((reason: string) => <li key={reason}>{reason}</li>)}</ul>
        <p><strong>Spread:</strong> {game.spread_pick}</p>
        <p><strong>Total:</strong> {game.total_pick} {game.market_total}</p>
        <p><strong>Model total:</strong> {game.projected_total}</p>
        <h3>Yahoo Sports News</h3>
        {game.news.length ? (
          <ul>{game.news.map((item: any) => <li key={item.link}><a href={item.link} target="_blank">{item.title}</a></li>)}</ul>
        ) : <p className="subtle">No matching Yahoo NFL headlines right now.</p>}
      </article>
    </main>
  );
}
