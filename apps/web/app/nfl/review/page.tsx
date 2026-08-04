import Link from "next/link";
import { getNflReview } from "../../../lib/api";
import type { NflReviewResponse } from "../../../lib/sports";

function percent(value: number | null | undefined) {
  return value === null || value === undefined ? "—" : `${value.toFixed(1)}%`;
}

function coverage(value: number, total: number) {
  if (total <= 0) return "0%";
  return `${Math.round((value / total) * 100)}%`;
}

function distributionItems(values: Record<string, number>) {
  return Object.entries(values).sort((left, right) => right[1] - left[1]);
}

export default async function NflReviewPage() {
  const review = (await getNflReview()) as NflReviewResponse;
  const completeCoverage = coverage(
    review.coverage.complete_games,
    review.game_count,
  );

  return (
    <main>
      <header>
        <Link className="back-link" href="/">← NFL</Link>
        <nav className="top-nav">
          <Link href="/">NFL</Link>
          <Link href="/nfl/review">Readiness</Link>
          <Link href="/mlb">MLB</Link>
          <Link href="/my-picks">My Picks</Link>
        </nav>
      </header>

      <section className="home-intro">
        <div>
          <div className="eyebrow">Internal review checkpoint</div>
          <h1>NFL readiness dashboard</h1>
        </div>
        <div className="subtle home-intro-note">
          Review version: {review.review_version}
        </div>
      </section>

      <section className="card breaking-impact">
        <div>
          <div className="kicker">Review status</div>
          <div className="breaking-headline">
            {review.status === "ready_for_review"
              ? "Ready for model review"
              : "Coverage is still partial"}
          </div>
          <div className="subtle">
            This dashboard evaluates data and explanation coverage. It does not
            change any prediction.
          </div>
        </div>
        <span className="impact-badge positive">
          {review.game_count} games
        </span>
      </section>

      <section className="mlb-detail-grid">
        <div className="market-card">
          <span>Average confidence</span>
          <strong>{percent(review.average_confidence)}</strong>
          <small>Across the current NFL schedule</small>
        </div>
        <div className="market-card">
          <span>Confidence range</span>
          <strong>
            {percent(review.confidence_range.minimum)}–
            {percent(review.confidence_range.maximum)}
          </strong>
          <small>Minimum to maximum displayed confidence</small>
        </div>
        <div className="market-card">
          <span>Complete intelligence coverage</span>
          <strong>{completeCoverage}</strong>
          <small>
            {review.coverage.complete_games} of {review.game_count} games
          </small>
        </div>
      </section>

      <section className="games">
        <div className="section-heading">
          <div>
            <div className="eyebrow">Coverage</div>
            <h2>Prediction foundation</h2>
          </div>
        </div>
        <div className="mlb-detail-grid">
          <div className="market-card">
            <span>Team health</span>
            <strong>{coverage(review.coverage.team_health, review.game_count)}</strong>
            <small>{review.coverage.team_health} games covered</small>
          </div>
          <div className="market-card">
            <span>Team intelligence</span>
            <strong>
              {coverage(review.coverage.team_intelligence, review.game_count)}
            </strong>
            <small>{review.coverage.team_intelligence} games covered</small>
          </div>
          <div className="market-card">
            <span>Prediction waterfall</span>
            <strong>
              {coverage(review.coverage.prediction_waterfall, review.game_count)}
            </strong>
            <small>{review.coverage.prediction_waterfall} games covered</small>
          </div>
        </div>
      </section>

      <section className="games">
        <div className="section-heading">
          <div>
            <div className="eyebrow">Current context</div>
            <h2>Guardrails and live inputs</h2>
          </div>
        </div>
        <div className="mlb-detail-grid">
          <div className="market-card">
            <span>Preseason games</span>
            <strong>{review.context.preseason_games}</strong>
            <small>Games using preseason confidence controls</small>
          </div>
          <div className="market-card">
            <span>Guardrail applied</span>
            <strong>{review.context.guardrail_applied_games}</strong>
            <small>Predictions reduced below raw confidence</small>
          </div>
          <div className="market-card">
            <span>Moneylines available</span>
            <strong>{review.context.market_available_games}</strong>
            <small>Games with complete two-sided market odds</small>
          </div>
          <div className="market-card">
            <span>Quarterbacks announced</span>
            <strong>{review.context.quarterbacks_announced_games}</strong>
            <small>Games with both expected quarterbacks</small>
          </div>
        </div>
      </section>

      <section className="games">
        <div className="section-heading">
          <div>
            <div className="eyebrow">Human review</div>
            <h2>Attention queue</h2>
          </div>
          <div className="subtle">
            {review.attention.review_required_games} games require review
          </div>
        </div>
        <div className="mlb-detail-grid">
          <div className="market-card">
            <span>Ready</span>
            <strong>{review.attention.disposition_counts.ready || 0}</strong>
            <small>No major review blocker detected</small>
          </div>
          <div className="market-card">
            <span>Watch</span>
            <strong>{review.attention.disposition_counts.watch || 0}</strong>
            <small>Monitor new information before game time</small>
          </div>
          <div className="market-card">
            <span>Hold</span>
            <strong>{review.attention.disposition_counts.hold || 0}</strong>
            <small>Resolve major gaps before promotion</small>
          </div>
        </div>
        <div className="grid">
          {review.attention.queue.map((item) => (
            <article className="card recommendation-card" key={item.game_id || item.matchup}>
              <div className="section-heading">
                <span className="status-badge">{item.disposition_label}</span>
                <span className="subtle">
                  {item.priority_level} priority · {item.priority_score}
                </span>
              </div>
              <h3>{item.matchup}</h3>
              <div className="game-pick-label">Current lean</div>
              <div className="compact-pick-name">
                {item.pick || "Not available"}
                {item.confidence !== null && item.confidence !== undefined
                  ? ` · ${item.confidence}%`
                  : ""}
              </div>
              <ul>
                {item.reasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
              <div className="subtle">{item.recommended_action}</div>
              {item.game_id && (
                <Link className="primary-button-link" href={`/nfl/${item.game_id}`}>
                  Review game
                </Link>
              )}
            </article>
          ))}
        </div>
      </section>

      <section className="games">
        <div className="section-heading">
          <div>
            <div className="eyebrow">Distributions</div>
            <h2>Readiness and market signals</h2>
          </div>
        </div>
        <div className="mlb-detail-grid">
          <div className="market-card">
            <span>Data readiness</span>
            {distributionItems(review.readiness_distribution).map(([label, count]) => (
              <div key={label}>
                <strong>{label}</strong>
                <small>{count} games</small>
              </div>
            ))}
          </div>
          <div className="market-card">
            <span>Market signals</span>
            {distributionItems(review.market_signal_distribution).map(([label, count]) => (
              <div key={label}>
                <strong>{label}</strong>
                <small>{count} games</small>
              </div>
            ))}
          </div>
          <div className="market-card">
            <span>Prediction impact</span>
            <strong>Observation only</strong>
            <small>Review, team health, team intelligence, and market signals remain non-predictive.</small>
          </div>
        </div>
      </section>
    </main>
  );
}
