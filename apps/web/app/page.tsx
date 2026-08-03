import Link from "next/link";
import { getHome } from "../lib/api";

function ConfidenceBar({ value }: { value: number }) {
  return <div className="confidence-track"><span style={{ width: `${value}%` }} /></div>;
}

function PickCard({ title, pick, confidence, why, href }: any) {
  return (
    <article className="card recommendation-card">
      <div className="kicker">{title}</div>
      <div className="pick">{pick}</div>
      <div className="confidence-row">
        <strong>{confidence}%</strong>
        <span>confidence</span>
      </div>
      <ConfidenceBar value={confidence} />
      <div className="reason">{why}</div>
      <Link className="primary-link" href={href}>Why this pick →</Link>
    </article>
  );
}

export default async function HomePage() {
  const data = await getHome();
  return (
    <main>
      <header>
        <div><div className="logo">SportsIntel</div><div className="subtle">NFL Week {data.week}</div></div>
        <nav className="top-nav"><Link href="/my-picks">My Picks</Link></nav>
      </header>

      <section className="hero-copy">
        <h1>Make your NFL decisions in under a minute.</h1>
        <p className="subtle">One clear pick, one confidence score, and the reasons that matter.</p>
      </section>

      <section className="grid">
        <PickCard title="Best Survivor" pick={data.best_survivor.winner} confidence={data.best_survivor.confidence} why={data.best_survivor.reasons[0]} href={`/games/${data.best_survivor.game_id}`} />
        <PickCard title="Best Spread" pick={data.best_spread.spread_pick} confidence={data.best_spread.confidence} why={data.best_spread.reasons[0]} href={`/games/${data.best_spread.game_id}`} />
        <PickCard title="Best Total" pick={`${data.best_total.total_pick} ${data.best_total.market_total}`} confidence={data.best_total.confidence} why={data.best_total.reasons.find((reason: string) => reason.startsWith("Model total")) ?? data.best_total.reasons[0]} href={`/games/${data.best_total.game_id}`} />
      </section>

      {data.latest_news?.length > 0 && (
        <section className="news-impact card">
          <div className="section-heading"><h2>Latest Yahoo Impact</h2><span className="subtle">Only headlines that may affect a pick.</span></div>
          <ul className="news-list">
            {data.latest_news.map((item: any) => (
              <li key={item.link}>
                <a href={item.link} target="_blank" rel="noreferrer">{item.title}</a>
                <span className={item.impact < 0 ? "impact-negative" : "impact-positive"}>
                  {item.impact < 0 ? "Negative" : "Positive"} impact
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="games">
        <div className="section-heading"><h2>Today's Games</h2><span className="subtle">Tap any matchup for the full decision.</span></div>
        {data.games.map((game: any) => (
          <Link className="card game" key={game.game_id} href={`/games/${game.game_id}`}>
            <span><strong>{game.away_team}</strong> at <strong>{game.home_team}</strong></span>
            <span>{game.winner} · {game.confidence}% →</span>
          </Link>
        ))}
      </section>
    </main>
  );
}
