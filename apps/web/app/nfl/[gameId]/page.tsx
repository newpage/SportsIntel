import Link from "next/link";
import { notFound } from "next/navigation";
import { getSport } from "../../../lib/api";
import type {
  MarketPrediction,
  SportGameEnvelope,
  SportHomeResponse,
} from "../../../lib/sports";

function formatGameTime(value: string) {
  if (!value || value === "TBD") return "Time TBD";

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;

  return parsed.toLocaleString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function markets(item: SportGameEnvelope): MarketPrediction[] {
  return Array.isArray(item.prediction.markets)
    ? item.prediction.markets
    : [];
}

function market(
  item: SportGameEnvelope,
  marketType: string,
): MarketPrediction | undefined {
  return markets(item).find(
    (candidate) => candidate.market_type === marketType,
  );
}

export default async function NflGamePage({
  params,
}: {
  params: Promise<{ gameId: string }>;
}) {
  const { gameId } = await params;
  const data = (await getSport("nfl")) as SportHomeResponse;
  const item = data.games.find(
    (candidate) => candidate.game.game_id === decodeURIComponent(gameId),
  );

  if (!item) notFound();

  const { game, prediction } = item;
  const moneyline = market(item, "moneyline");
  const spread = market(item, "spread");
  const total = market(item, "total");
  const explanation = prediction.explanation || {};
  const reasons = Array.isArray(explanation.reasons)
    ? explanation.reasons
    : [];
  const metadata = prediction.metadata || {};
  const gameMetadata = game.metadata || {};
  const awayRecord = gameMetadata.away_record;
  const homeRecord = gameMetadata.home_record;

  return (
    <main>
      <header>
        <Link className="back-link" href="/">← NFL</Link>
        <nav className="top-nav">
          <Link href="/">NFL</Link>
          <Link href="/mlb">MLB</Link>
          <Link href="/my-picks">My Picks</Link>
        </nav>
      </header>

      <article className="card game-analysis">
        <section className="game-summary">
          <div>
            <div className="kicker">{formatGameTime(game.start_time)}</div>
            <div className="matchup">
              {game.away_team} at {game.home_team}
            </div>
            <div className="subtle">
              {game.venue || "Venue not yet available"}
            </div>
            {(awayRecord || homeRecord) && (
              <div className="subtle">
                {awayRecord && (
                  <>
                    {game.away_team}: {String(awayRecord)}
                  </>
                )}
                {awayRecord && homeRecord && " · "}
                {homeRecord && (
                  <>
                    {game.home_team}: {String(homeRecord)}
                  </>
                )}
              </div>
            )}
            <div className="game-pick-label">SportsIntel moneyline lean</div>
            <div className="game-pick">
              {prediction.pick || "Prediction pending"}
            </div>
          </div>

          <div className="hero-confidence">
            <strong>{prediction.confidence ?? "—"}%</strong>
            <span>baseline confidence</span>
            <div className="confidence-track">
              <span
                style={{
                  width: `${prediction.confidence ?? 0}%`,
                }}
              />
            </div>
          </div>
        </section>

        {(awayRecord || homeRecord) && (
          <section className="mlb-detail-grid">
            <div className="market-card">
              <span>Away team</span>
              <strong>{game.away_team}</strong>
              <small>{awayRecord ? String(awayRecord) : "—"}</small>
            </div>
            <div className="market-card">
              <span>Matchup context</span>
              <strong>Records are display-only</strong>
              <small>They do not affect baseline confidence yet.</small>
            </div>
            <div className="market-card">
              <span>Home team</span>
              <strong>{game.home_team}</strong>
              <small>{homeRecord ? String(homeRecord) : "—"}</small>
            </div>
          </section>
        )}

        <section className="market-grid">
          <div className="market-card">
            <span>Moneyline</span>
            <strong>{moneyline?.selection || "Pending"}</strong>
            <small>{moneyline?.recommendation || "Early model lean"}</small>
          </div>
          <div className="market-card">
            <span>Spread</span>
            <strong>{spread?.selection || "Not available"}</strong>
            <small>Planned for a later NFL sprint</small>
          </div>
          <div className="market-card">
            <span>Total</span>
            <strong>{total?.selection || "Not available"}</strong>
            <small>Planned for a later NFL sprint</small>
          </div>
        </section>

        <section className="why-section">
          <div className="eyebrow">Current model explanation</div>
          <h2>{String(explanation.title || "Why this pick")}</h2>
          <p>
            {String(
              explanation.summary ||
                "This is an early baseline prediction.",
            )}
          </p>
          {reasons.length > 0 && (
            <ul className="reason-list clean-reasons">
              {reasons.map((reason) => (
                <li key={String(reason)}>{String(reason)}</li>
              ))}
            </ul>
          )}
        </section>

        <section className="why-section">
          <div className="eyebrow">Active prediction factors</div>
          <h2>What currently drives the pick</h2>
          <div className="model-factor-list">
            {prediction.factors.map((factor, index) => (
              <article
                className="model-factor-card"
                key={String(factor.factor_id || index)}
              >
                <div className="model-factor-heading">
                  <div>
                    <span>{String(factor.category || "Factor")}</span>
                    <strong>{String(factor.name || "Unnamed factor")}</strong>
                  </div>
                  <strong>
                    {Math.round(Number(factor.reliability || 0) * 100)}%
                  </strong>
                </div>
                <p>{String(factor.explanation || "")}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="card breaking-impact">
          <div>
            <div className="kicker">Model maturity</div>
            <div className="breaking-headline">Baseline phase</div>
            <div className="subtle">
              Version: {prediction.model_version || "nfl-baseline"}
            </div>
          </div>
          <span className="impact-badge positive">
            {String(metadata.prediction_scope || "moneyline_only")}
          </span>
        </section>
      </article>
    </main>
  );
}
