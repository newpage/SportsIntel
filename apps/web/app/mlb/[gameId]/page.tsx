import Link from "next/link";
import { getMlbGame, getMlb } from "../../../lib/api";
import { ConfidenceDetails } from "../../../components/ConfidenceDetails";

function PitcherStat({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="pitcher-stat">
      <span>{label}</span>
      <strong>{value || "—"}</strong>
    </div>
  );
}

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
            <p className="game-probability">
              {Math.round(game.win_probability * 100)}% projected win probability
              {game.confidence_change !== 0 && (
                <span className={game.confidence_change > 0 ? "confidence-trend trend-up" : "confidence-trend trend-down"}>
                  {game.confidence_change > 0 ? "▲" : "▼"} {Math.abs(game.confidence_change)}
                </span>
              )}
            </p>
          </div>
          <ConfidenceDetails
            confidence={game.confidence}
            stars={game.stars}
            recommendation={game.recommendation}
            details={game.confidence_details}
            predictionFactors={game.prediction_factors}
            factorEngineVersion={game.factor_engine_version}
            factorEngineAffectsConfidence={game.factor_engine_affects_confidence}
          />
        </section>

        <section className="mlb-detail-grid">
          <div className="market-card momentum-card">
            <span>{game.away_team} recent form</span>
            <strong>{game.away_momentum.record}</strong>
            <small>Last {game.away_momentum.games} completed games · {game.away_momentum.label}</small>
          </div>
          <div className="market-card split-card">
            <span>{game.away_team} road record</span>
            <strong>{game.away_split.away_record}</strong>
            <small>Season-to-date away performance</small>
          </div>
          <div className="market-card">
            <span>Away team</span>
            <strong>{game.away_team}</strong>
            <small>{game.away_record}</small>
          </div>
          <div className="market-card">
            <span>Probable pitchers · {game.pitcher_status.label}</span>
            <strong>{game.away_pitcher || "Not yet announced"}</strong>
            <small>vs {game.home_pitcher || "Not yet announced"}</small>
            <small>{game.pitcher_status.message}</small>
            <small>Source: {game.pitcher_source_label || "MLB"}</small>
          </div>
          <div className="market-card">
            <span>Home team</span>
            <strong>{game.home_team}</strong>
            <small>{game.home_record}</small>
          </div>
          <div className="market-card split-card">
            <span>{game.home_team} home record</span>
            <strong>{game.home_split.home_record}</strong>
            <small>Season-to-date home performance</small>
          </div>
          <div className="market-card momentum-card">
            <span>{game.home_team} recent form</span>
            <strong>{game.home_momentum.record}</strong>
            <small>Last {game.home_momentum.games} completed games · {game.home_momentum.label}</small>
          </div>
        </section>

        {(game.away_pitcher || game.home_pitcher) && (
          <section className="why-section">
            <div className="eyebrow">Yahoo Sports pitcher data</div>
            <h2>Starting Pitcher Comparison</h2>
            <div className="market-grid">
              <div className="market-card">
                <span>{game.away_team}</span>
                <strong>{game.away_pitcher || "Not yet announced"}</strong>
                <div className="pitcher-stat-grid">
                  <PitcherStat label="Record" value={game.away_pitcher_stats?.record} />
                  <PitcherStat label="ERA" value={game.away_pitcher_stats?.era} />
                  <PitcherStat label="WHIP" value={game.away_pitcher_stats?.whip} />
                  <PitcherStat label="Throws" value={game.away_pitcher_stats?.throws} />
                </div>
              </div>
              <div className="market-card">
                <span>{game.home_team}</span>
                <strong>{game.home_pitcher || "Not yet announced"}</strong>
                <div className="pitcher-stat-grid">
                  <PitcherStat label="Record" value={game.home_pitcher_stats?.record} />
                  <PitcherStat label="ERA" value={game.home_pitcher_stats?.era} />
                  <PitcherStat label="WHIP" value={game.home_pitcher_stats?.whip} />
                  <PitcherStat label="Throws" value={game.home_pitcher_stats?.throws} />
                </div>
              </div>
            </div>
            {game.pitcher_advantage && (
              <div className="pitcher-advantage-card">
                <div>
                  <span>SportsIntel pitcher edge</span>
                  <strong>
                    {game.pitcher_advantage.team
                      ? `${game.pitcher_advantage.team} · ${game.pitcher_advantage.label}`
                      : "Even matchup"}
                  </strong>
                </div>
                <p>{game.pitcher_advantage.summary}</p>
                <ul>
                  {game.pitcher_advantage.reasons.map((reason: string) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
              </div>
            )}
            <p className="subtle">Displayed for comparison only; pitcher statistics do not change confidence yet.</p>
          </section>
        )}

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

        {game.prediction_timeline?.length > 0 && (
          <section className="prediction-timeline-section">
            <div className="eyebrow">Prediction history</div>
            <h2>Prediction Timeline</h2>
            <div className="prediction-timeline">
              {game.prediction_timeline.map((event: any, index: number) => {
                const nextEvent = game.prediction_timeline[index + 1];
                const change = nextEvent ? event.confidence - nextEvent.confidence : 0;
                return (
                  <article className="prediction-timeline-event" key={`${event.timestamp}-${index}`}>
                    <div className="prediction-timeline-marker" />
                    <div>
                      <div className="prediction-timeline-heading">
                        <time>{new Date(event.timestamp).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}</time>
                        <strong>{event.confidence}%</strong>
                        {change !== 0 && (
                          <span className={change > 0 ? "trend-up" : "trend-down"}>
                            {change > 0 ? "▲" : "▼"} {Math.abs(change)}
                          </span>
                        )}
                      </div>
                      <p>{event.reason}</p>
                    </div>
                  </article>
                );
              })}
            </div>
          </section>
        )}

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
