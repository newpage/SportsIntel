import Link from "next/link";
import { getMlbGame, getMlb } from "../../../lib/api";
import { ConfidenceDetails } from "../../../components/ConfidenceDetails";

export default async function MlbGamePage({ params }: { params: Promise<{ gameId: string }> }) {
  const { gameId } = await params;
  const [game, home] = await Promise.all([getMlbGame(gameId), getMlb()]);

  return (
    <main>
      <header>
        <Link className="back-link" href="/mlb">← MLB</Link>
        <nav className="top-nav"><Link href="/">NFL</Link><Link href="/my-picks">My Picks</Link></nav>
      </header>

      <article className="card game-analysis">
        <section className="game-summary">
          <div>
            <div className="kicker">{game.status}</div>
            <div className="matchup">{game.away_team} at {game.home_team}</div>
            <div className="game-pick-label">SportsIntel moneyline pick</div>
            <div className="game-pick">{game.moneyline_pick}</div>
            <p className="game-probability">{Math.round(game.win_probability * 100)}% projected win probability</p>
          </div>
          <ConfidenceDetails
            confidence={game.confidence}
            stars={game.stars}
            recommendation={game.recommendation}
            details={game.confidence_details}
          />
        </section>

        <section className="mlb-detail-grid">
          <div className="market-card">
            <span>Away team</span>
            <strong>{game.away_team}</strong>
            <small>{game.away_record}</small>
          </div>
          <div className="market-card">
            <span>Probable pitchers</span>
            <strong>{game.away_pitcher || "TBD"}</strong>
            <small>vs {game.home_pitcher || "TBD"}</small>
          </div>
          <div className="market-card">
            <span>Home team</span>
            <strong>{game.home_team}</strong>
            <small>{game.home_record}</small>
          </div>
        </section>

        <section className="why-section">
          <div className="eyebrow">Simple model</div>
          <h2>Why this pick</h2>
          <ul className="reason-list clean-reasons">
            {game.reasons.map((reason: string) => <li key={reason}>{reason}</li>)}
          </ul>
        </section>

        <section className="market-grid">
          <div className="market-card"><span>Moneyline</span><strong>{game.moneyline_pick}</strong></div>
          <div className="market-card"><span>Run line</span><strong>{game.run_line_pick}</strong></div>
          <div className="market-card"><span>Total</span><strong>{game.total_pick}</strong></div>
        </section>

        {home.latest_news.length > 0 && (
          <section className="game-news-section">
            <div className="eyebrow">Yahoo Sports only</div>
            <h2>Latest MLB News</h2>
            <div className="game-news-list">
              {home.latest_news.slice(0, 5).map((item: any) => (
                <a className="game-news-item" key={item.link} href={item.link} target="_blank" rel="noreferrer">
                  <span>{item.title}</span>
                </a>
              ))}
            </div>
          </section>
        )}
      </article>
    </main>
  );
}
