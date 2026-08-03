import Link from "next/link";
import { getHome } from "../lib/api";

function ConfidenceBar({ value }: { value: number }) {
  return <div className="confidence-track"><span style={{ width: `${value}%` }} /></div>;
}

function SecondaryPick({ title, pick, confidence, why, href }: any) {
  return (
    <Link className="card compact-pick" href={href}>
      <div>
        <div className="kicker">{title}</div>
        <div className="compact-pick-name">{pick}</div>
        <div className="compact-reason">{why}</div>
      </div>
      <div className="compact-score">
        <strong>{confidence}%</strong>
        <span>confidence</span>
      </div>
    </Link>
  );
}

export default async function HomePage() {
  const data = await getHome();
  const topNews = data.latest_news?.[0];
  const totalReason =
    data.best_total.reasons.find((reason: string) => reason.startsWith("Model total")) ??
    data.best_total.reasons[0];

  return (
    <main>
      <header>
        <div>
          <div className="logo">SportsIntel</div>
          <div className="subtle">NFL Week {data.week}</div>
        </div>
        <nav className="top-nav"><Link href="/my-picks">My Picks</Link></nav>
      </header>

      <section className="home-intro">
        <div>
          <div className="eyebrow">Your 60-second NFL brief</div>
          <h1>One clear decision. The reasons that matter.</h1>
        </div>
        <div className="subtle home-intro-note">Yahoo Sports is the only news source used in this version.</div>
      </section>

      <section className="card hero-pick">
        <div className="hero-pick-copy">
          <div className="kicker">Best Survivor Pick</div>
          <div className="hero-pick-name">{data.best_survivor.winner}</div>
          <div className="hero-pick-reason">{data.best_survivor.reasons[0]}</div>
          <Link className="primary-button-link" href={`/games/${data.best_survivor.game_id}`}>
            See why this is the pick →
          </Link>
        </div>
        <div className="hero-confidence">
          <strong>{data.best_survivor.confidence}%</strong>
          <span>confidence</span>
          <ConfidenceBar value={data.best_survivor.confidence} />
        </div>
      </section>

      <section className="secondary-picks">
        <SecondaryPick
          title="Best Spread"
          pick={data.best_spread.spread_pick}
          confidence={data.best_spread.confidence}
          why={data.best_spread.reasons[0]}
          href={`/games/${data.best_spread.game_id}`}
        />
        <SecondaryPick
          title="Best Total"
          pick={`${data.best_total.total_pick} ${data.best_total.market_total}`}
          confidence={data.best_total.confidence}
          why={totalReason}
          href={`/games/${data.best_total.game_id}`}
        />
      </section>

      {topNews && (
        <section className="card breaking-impact">
          <div>
            <div className="kicker">Biggest Yahoo News Impact</div>
            <a href={topNews.link} target="_blank" rel="noreferrer" className="breaking-headline">
              {topNews.title}
            </a>
          </div>
          <span className={topNews.impact < 0 ? "impact-badge negative" : "impact-badge positive"}>
            {topNews.impact < 0 ? "Negative" : "Positive"} impact
          </span>
        </section>
      )}

      <section className="games">
        <div className="section-heading">
          <div><div className="eyebrow">Quick scan</div><h2>Today&apos;s Games</h2></div>
          <span className="subtle">Tap for the full prediction.</span>
        </div>
        <div className="game-list">
          {data.games.map((game: any) => (
            <Link className="card game" key={game.game_id} href={`/games/${game.game_id}`}>
              <span><strong>{game.away_team}</strong> at <strong>{game.home_team}</strong></span>
              <span className="game-call">{game.winner} · {game.confidence}% →</span>
            </Link>
          ))}
        </div>
      </section>
    </main>
  );
}
