import Link from "next/link";
import { getHome } from "../lib/api";

function PickCard({ title, pick, confidence, why, href }: any) {
  return (
    <article className="card">
      <div className="kicker">{title}</div>
      <div className="pick">{pick}</div>
      <div className="confidence">{confidence}% confidence</div>
      <div className="reason">{why}</div>
      <p><Link href={href}>Why →</Link></p>
    </article>
  );
}

export default async function HomePage() {
  const data = await getHome();
  return (
    <main>
      <header>
        <div><div className="logo">SportsIntel</div><div className="subtle">NFL Week {data.week}</div></div>
        <div className="subtle">Make your picks in under a minute.</div>
      </header>

      <section className="grid">
        <PickCard title="Best Survivor" pick={data.best_survivor.winner} confidence={data.best_survivor.confidence} why={data.best_survivor.reasons[0]} href={`/games/${data.best_survivor.game_id}`} />
        <PickCard title="Best Spread" pick={data.best_spread.spread_pick} confidence={data.best_spread.confidence} why={data.best_spread.reasons[0]} href={`/games/${data.best_spread.game_id}`} />
        <PickCard title="Best Total" pick={`${data.best_total.total_pick} ${data.best_total.market_total}`} confidence={data.best_total.confidence} why={data.best_total.reasons[2]} href={`/games/${data.best_total.game_id}`} />
      </section>

      <section className="games">
        <h2>Today's Games</h2>
        {data.games.map((game: any) => (
          <Link className="card game" key={game.game_id} href={`/games/${game.game_id}`}>
            <span>{game.away_team} at {game.home_team}</span>
            <strong>{game.winner} · {game.confidence}%</strong>
          </Link>
        ))}
      </section>
    </main>
  );
}
