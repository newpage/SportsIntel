import Link from "next/link";
import { getMlb } from "../../lib/api";

export default async function MlbPage() {
  const data = await getMlb();
  const best = data.best_pick;

  return (
    <main>
      <header>
        <div>
          <div className="logo">SportsIntel</div>
          <div className="subtle">MLB · {data.date}</div>
        </div>
        <nav className="top-nav">
          <Link href="/">NFL</Link>
          <Link href="/mlb">MLB</Link>
          <Link href="/my-picks">My Picks</Link>
        </nav>
      </header>

      <section className="home-intro">
        <div>
          <div className="eyebrow">Daily live testing</div>
          <h1>Today&apos;s simple MLB decisions.</h1>
        </div>
        <div className="subtle home-intro-note">
          MLB provides the schedule. Yahoo Sports remains the only news source.
        </div>
      </section>

      {best ? (
        <section className="card hero-pick">
          <div>
            <div className="kicker">Best Moneyline Pick</div>
            <div className="hero-pick-name">{best.moneyline_pick}</div>
            <div className="hero-pick-reason">{best.reasons[0]}</div>
          </div>
          <div className="hero-confidence">
            <strong>{best.confidence}%</strong>
            <span>confidence</span>
            <div className="confidence-track">
              <span style={{ width: `${best.confidence}%` }} />
            </div>
          </div>
        </section>
      ) : (
        <article className="card empty-state">
          <h2>No MLB games scheduled today</h2>
          <p className="subtle">Check back on the next game day.</p>
        </article>
      )}

      <section className="games">
        <div className="section-heading">
          <div>
            <div className="eyebrow">Live schedule</div>
            <h2>Today&apos;s MLB Games</h2>
          </div>
          <span className="subtle">{data.games.length} games</span>
        </div>

        <div className="grid">
          {data.games.map((game: any) => (
            <Link className="card mlb-link-card" key={game.game_id} href={`/mlb/${game.game_id}`}>
              <div className="kicker">{game.status}</div>
              <div className="pick">{game.moneyline_pick}</div>
              <p className="subtle">{game.away_team} at {game.home_team}</p>
              <p><strong>Run line:</strong> {game.run_line_pick}</p>
              <p><strong>Total:</strong> {game.total_pick}</p>
              <div className="confidence-track">
                <span style={{ width: `${game.confidence}%` }} />
              </div>
              <div className="confidence">{game.confidence}% confidence</div>
              <span className="primary-link">View game →</span>
            </Link>
          ))}
        </div>
      </section>

      {data.latest_news.length > 0 && (
        <section className="card news-impact">
          <div className="section-heading">
            <div>
              <div className="eyebrow">Only news source</div>
              <h2>Yahoo MLB News</h2>
            </div>
          </div>
          <ul className="news-list">
            {data.latest_news.map((item: any) => (
              <li key={item.link}>
                <a href={item.link} target="_blank" rel="noreferrer">
                  {item.title}
                </a>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
