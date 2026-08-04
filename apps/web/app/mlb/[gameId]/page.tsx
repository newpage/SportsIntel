import Link from "next/link";
import { getMlbGame, getMlb } from "../../../lib/api";
import { ConfidenceDetails } from "../../../components/ConfidenceDetails";


function factorChanges(current: any, previous: any) {
  const currentSnapshot = current?.factor_snapshot || {};
  const previousSnapshot = previous?.factor_snapshot || {};
  const changes: Array<{
    id: string;
    name: string;
    message: string;
    direction: "up" | "down" | "neutral";
  }> = [];

  Object.entries(currentSnapshot).forEach(([factorId, currentValue]: [string, any]) => {
    const previousValue = previousSnapshot[factorId];

    if (!previousValue) {
      changes.push({
        id: `${factorId}-available`,
        name: currentValue.name || factorId,
        message: "Factor became available",
        direction: "neutral",
      });
      return;
    }

    if (currentValue.direction !== previousValue.direction) {
      changes.push({
        id: `${factorId}-direction`,
        name: currentValue.name || factorId,
        message: `Direction: ${previousValue.direction || "neutral"} → ${currentValue.direction || "neutral"}`,
        direction: "neutral",
      });
    }

    if (currentValue.score !== previousValue.score) {
      const delta = Number(currentValue.score || 0) - Number(previousValue.score || 0);
      changes.push({
        id: `${factorId}-score`,
        name: currentValue.name || factorId,
        message: `Score ${delta > 0 ? "+" : ""}${delta.toFixed(3)}`,
        direction: delta > 0 ? "up" : delta < 0 ? "down" : "neutral",
      });
    }

    if (currentValue.reliability !== previousValue.reliability) {
      const reliability = Math.round(Number(currentValue.reliability || 0) * 100);
      changes.push({
        id: `${factorId}-reliability`,
        name: currentValue.name || factorId,
        message: `Reliability now ${reliability}%`,
        direction: "neutral",
      });
    }

    if (currentValue.used_in_confidence !== previousValue.used_in_confidence) {
      changes.push({
        id: `${factorId}-scoring`,
        name: currentValue.name || factorId,
        message: currentValue.used_in_confidence ? "Now used in confidence" : "No longer scored",
        direction: currentValue.used_in_confidence ? "up" : "down",
      });
    }
  });

  Object.entries(previousSnapshot).forEach(([factorId, previousValue]: [string, any]) => {
    if (!currentSnapshot[factorId]) {
      changes.push({
        id: `${factorId}-removed`,
        name: previousValue.name || factorId,
        message: "Factor no longer available",
        direction: "down",
      });
    }
  });

  return changes.slice(0, 6);
}


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
            modelCoverage={game.factor_model_coverage}
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
                const changes = nextEvent ? factorChanges(event, nextEvent) : [];
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
                      {changes.length > 0 && (
                        <div className="timeline-factor-changes">
                          {changes.map((item) => (
                            <div className={`timeline-factor-change factor-${item.direction}`} key={item.id}>
                              <strong>{item.name}</strong>
                              <span>{item.message}</span>
                            </div>
                          ))}
                        </div>
                      )}
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
