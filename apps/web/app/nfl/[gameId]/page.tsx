import Link from "next/link";
import { notFound } from "next/navigation";
import { getNflChanges, getNflGameContext, getSport } from "../../../lib/api";
import type {
  MarketPrediction,
  QualifiedConsensus,
  SportGameEnvelope,
  SportHomeResponse,
  SnapshotChangesResponse,
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

function formatCaptureTime(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;

  return parsed.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
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

const QUALIFIED_CONSENSUS_STATUS_LABELS: Record<
  QualifiedConsensus["status"],
  string
> = {
  qualified: "Qualified",
  watch: "Watch",
  caution: "Caution",
  hold: "Hold",
  unavailable: "Unavailable",
};

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
  const yahooContext = await getNflGameContext(game.game_id) as {
    venue?: string | null;
    metadata?: Record<string, unknown>;
  } | null;
  const snapshotChanges = (await getNflChanges(
    game.game_id,
  )) as SnapshotChangesResponse | null;
  const latestSnapshotChanges =
    snapshotChanges?.latest_comparison?.changes.slice(0, 5) ?? [];
  const moneyline = market(item, "moneyline");
  const spread = market(item, "spread");
  const total = market(item, "total");
  const explanation = prediction.explanation || {};
  const reasons = Array.isArray(explanation.reasons)
    ? explanation.reasons
    : [];
  const metadata = prediction.metadata || {};
  const gameMetadata = {
    ...(game.metadata || {}),
    ...(yahooContext?.metadata || {}),
  };
  const awayRecord =
    typeof gameMetadata.away_record === "string"
      ? gameMetadata.away_record
      : null;
  const homeRecord =
    typeof gameMetadata.home_record === "string"
      ? gameMetadata.home_record
      : null;
  const hasRecord = Boolean(awayRecord || homeRecord);
  const awayQb =
    gameMetadata.away_qb &&
    typeof gameMetadata.away_qb === "object"
      ? (gameMetadata.away_qb as Record<string, unknown>)
      : null;
  const homeQb =
    gameMetadata.home_qb &&
    typeof gameMetadata.home_qb === "object"
      ? (gameMetadata.home_qb as Record<string, unknown>)
      : null;
  const awayInjuries = Array.isArray(gameMetadata.away_injuries)
    ? gameMetadata.away_injuries as Array<Record<string, unknown>>
    : [];
  const homeInjuries = Array.isArray(gameMetadata.home_injuries)
    ? gameMetadata.home_injuries as Array<Record<string, unknown>>
    : [];
  const awayQbInjuries = Array.isArray(gameMetadata.away_qb_injuries)
    ? gameMetadata.away_qb_injuries as Array<Record<string, unknown>>
    : [];
  const homeQbInjuries = Array.isArray(gameMetadata.home_qb_injuries)
    ? gameMetadata.home_qb_injuries as Array<Record<string, unknown>>
    : [];
  const readinessScore =
    typeof metadata.data_readiness_score === "number"
      ? metadata.data_readiness_score
      : 60;
  const readinessLabel =
    typeof metadata.data_readiness_label === "string"
      ? metadata.data_readiness_label
      : "limited";
  const confidenceCap =
    typeof metadata.confidence_cap === "number"
      ? metadata.confidence_cap
      : 60;
  const guardrailApplied =
    metadata.confidence_guardrail_applied === true;
  const awayTeamNormalized =
    typeof metadata.away_team_normalized === "string"
      ? metadata.away_team_normalized
      : game.away_team;
  const homeTeamNormalized =
    typeof metadata.home_team_normalized === "string"
      ? metadata.home_team_normalized
      : game.home_team;
  const teamNameNormalized =
    metadata.team_name_normalized === true;
  const seasonPhase =
    typeof metadata.season_phase === "string"
      ? metadata.season_phase
      : "regular";
  const predictionLabel =
    typeof metadata.prediction_label === "string"
      ? metadata.prediction_label
      : "Moneyline Pick";
  const preseasonWeek =
    typeof metadata.preseason_week === "number"
      ? metadata.preseason_week
      : null;
  const isPreseason = seasonPhase === "preseason";
  const marketAvailable = metadata.market_available === true;
  const awayMoneyline =
    typeof metadata.away_moneyline === "number"
      ? metadata.away_moneyline
      : null;
  const homeMoneyline =
    typeof metadata.home_moneyline === "number"
      ? metadata.home_moneyline
      : null;
  const modelPickProbability =
    typeof metadata.model_pick_probability === "number"
      ? metadata.model_pick_probability
      : null;
  const marketPickProbability =
    typeof metadata.market_pick_probability === "number"
      ? metadata.market_pick_probability
      : null;
  const marketEdge =
    typeof metadata.market_edge === "number"
      ? metadata.market_edge
      : null;
  const marketSignalLabel =
    typeof metadata.market_signal_label === "string"
      ? metadata.market_signal_label
      : "Market unavailable";
  const marketSignalSummary =
    typeof metadata.market_signal_summary === "string"
      ? metadata.market_signal_summary
      : "A complete moneyline market is not available.";
  const qualifiedConsensus =
    metadata.qualified_consensus &&
    typeof metadata.qualified_consensus === "object"
      ? (metadata.qualified_consensus as QualifiedConsensus)
      : null;
  const qualifiedConsensusReasons =
    qualifiedConsensus?.reasons.slice(0, 3) ?? [];
  const predictionWaterfall =
    metadata.prediction_waterfall &&
    typeof metadata.prediction_waterfall === "object"
      ? (metadata.prediction_waterfall as Record<string, unknown>)
      : null;
  const waterfallSteps = Array.isArray(predictionWaterfall?.steps)
    ? predictionWaterfall.steps.filter(
        (step): step is Record<string, unknown> =>
          Boolean(step) && typeof step === "object",
      )
    : [];

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

      <article className="card game-analysis">
        <section className="game-summary">
          <div>
            <div className="kicker">{formatGameTime(game.start_time)}</div>
            <div className="matchup">
              {game.away_team} at {game.home_team}
            </div>
            <div className="subtle">
              {yahooContext?.venue || game.venue || "Venue not yet available"}
            </div>
            {hasRecord && (
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
            <div className="game-pick-label">
              SportsIntel {predictionLabel}
            </div>
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

        {hasRecord && (
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

        <section className="mlb-detail-grid">
            <div className="market-card">
              <span>Away quarterback</span>
              <strong>
                {awayQb?.name ? String(awayQb.name) : "Not announced"}
              </strong>
              <small>
                {awayQb?.status ? String(awayQb.status) : "Starter not announced"}
                {awayQbInjuries.length > 0
                  ? ` · ${String(awayQbInjuries[0].name)}: ${String(awayQbInjuries[0].status)}`
                  : ""}
              </small>
            </div>
            <div className="market-card">
              <span>Quarterback factor</span>
              <strong>Observation only</strong>
              <small>QB status does not affect confidence yet.</small>
            </div>
            <div className="market-card">
              <span>Home quarterback</span>
              <strong>
                {homeQb?.name ? String(homeQb.name) : "Not announced"}
              </strong>
              <small>
                {homeQb?.status ? String(homeQb.status) : "Starter not announced"}
                {homeQbInjuries.length > 0
                  ? ` · ${String(homeQbInjuries[0].name)}: ${String(homeQbInjuries[0].status)}`
                  : ""}
              </small>
            </div>
        </section>

        {(awayInjuries.length > 0 || homeInjuries.length > 0) && (
          <section className="card">
            <div className="section-heading">
              <div>
                <div className="eyebrow">Yahoo Sports</div>
                <h2>Injury observations</h2>
              </div>
              <span className="subtle">Observation only</span>
            </div>
            <div className="mlb-detail-grid">
              {[
                [game.away_team, awayInjuries],
                [game.home_team, homeInjuries],
              ].map(([team, injuries]) => (
                <div className="market-card" key={String(team)}>
                  <span>{String(team)}</span>
                  <strong>{(injuries as Array<Record<string, unknown>>).length} listed</strong>
                  <small>
                    {(injuries as Array<Record<string, unknown>>).slice(0, 3).map((injury) =>
                      `${String(injury.name)} — ${String(injury.status)}`
                    ).join(" · ") || "No injuries listed"}
                  </small>
                </div>
              ))}
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

        {snapshotChanges && (
          <section className="why-section">
            <div className="eyebrow">What changed</div>
            <h2>
              {snapshotChanges.previous_snapshot
                ? `${snapshotChanges.significance.charAt(0).toUpperCase()}${snapshotChanges.significance.slice(1)} change`
                : "No prior snapshot"}
            </h2>
            <p className="subtle">
              Current capture:{" "}
              {formatCaptureTime(snapshotChanges.current_snapshot.captured_at)}
              {snapshotChanges.previous_snapshot && (
                <>
                  {" "}· Previous capture:{" "}
                  {formatCaptureTime(
                    snapshotChanges.previous_snapshot.captured_at,
                  )}
                </>
              )}
            </p>
            <p>{snapshotChanges.summary}</p>
            {latestSnapshotChanges.length > 0 && (
              <div className="model-factor-list">
                {latestSnapshotChanges.map((change) => (
                  <article className="model-factor-card" key={change.field}>
                    <div className="model-factor-heading">
                      <strong>{change.label}</strong>
                      <span>{change.significance}</span>
                    </div>
                    <p>{change.explanation}</p>
                  </article>
                ))}
              </div>
            )}
            <p className="subtle">
              Snapshot history is held in memory and resets when the API
              service restarts.
            </p>
          </section>
        )}

        {isPreseason && (
          <section className="card breaking-impact">
            <div>
              <div className="kicker">Season context</div>
              <div className="breaking-headline">
                {preseasonWeek
                  ? `Preseason Week ${preseasonWeek}`
                  : "Preseason"}
              </div>
              <div className="subtle">
                Confidence is reduced because playing time and
                participation are highly variable.
              </div>
            </div>
            <span className="impact-badge positive">
              Preseason lean
            </span>
          </section>
        )}

        <section className="mlb-detail-grid">
          <div className="market-card">
            <span>Data readiness</span>
            <strong>{readinessScore}%</strong>
            <small>{readinessLabel} input coverage</small>
          </div>
          <div className="market-card">
            <span>Confidence guardrail</span>
            <strong>{confidenceCap}% maximum</strong>
            <small>
              {guardrailApplied
                ? "The guardrail reduced displayed confidence."
                : "The model is already below the current cap."}
            </small>
          </div>
          <div className="market-card">
            <span>Pick behavior</span>
            <strong>Team selection unchanged</strong>
            <small>
              Readiness changes confidence, not the selected team.
            </small>
          </div>
        </section>

        {teamNameNormalized && (
          <section className="mlb-detail-grid">
            <div className="market-card">
              <span>Away rating identity</span>
              <strong>{game.away_team}</strong>
              <small>Uses {awayTeamNormalized}</small>
            </div>
            <div className="market-card">
              <span>Normalization</span>
              <strong>Canonical franchise names</strong>
              <small>
                Yahoo display names are mapped before rating lookup.
              </small>
            </div>
            <div className="market-card">
              <span>Home rating identity</span>
              <strong>{game.home_team}</strong>
              <small>Uses {homeTeamNormalized}</small>
            </div>
          </section>
        )}

        {marketAvailable && (
          <section className="mlb-detail-grid">
            <div className="market-card">
              <span>Yahoo moneyline</span>
              <strong>
                {game.away_team} {awayMoneyline !== null
                  ? (awayMoneyline > 0 ? `+${awayMoneyline}` : awayMoneyline)
                  : "—"}
              </strong>
              <small>
                {game.home_team} {homeMoneyline !== null
                  ? (homeMoneyline > 0 ? `+${homeMoneyline}` : homeMoneyline)
                  : "—"}
              </small>
            </div>
            <div className="market-card">
              <span>Model vs. market</span>
              <strong>
                {modelPickProbability !== null
                  ? `${(modelPickProbability * 100).toFixed(1)}% model`
                  : "Model unavailable"}
              </strong>
              <small>
                {marketPickProbability !== null
                  ? `${(marketPickProbability * 100).toFixed(1)}% no-vig market`
                  : "Market probability unavailable"}
              </small>
            </div>
            <div className="market-card">
              <span>Market signal</span>
              <strong>{marketSignalLabel}</strong>
              <small>{marketSignalSummary}</small>
            </div>
          </section>
        )}

        {qualifiedConsensus && (
          <section className="mlb-detail-grid">
            <div className="market-card">
              <span>Qualified consensus</span>
              <strong>
                {QUALIFIED_CONSENSUS_STATUS_LABELS[qualifiedConsensus.status]}
              </strong>
              <small>Observation only · does not change the prediction</small>
            </div>
            <div className="market-card">
              <span>Classification</span>
              <strong>{qualifiedConsensus.classification}</strong>
              <small>
                {qualifiedConsensus.quality_score}/100 {qualifiedConsensus.quality_label} quality
              </small>
            </div>
            <div className="market-card">
              <span>Model vs. market</span>
              <strong>
                {(qualifiedConsensus.model_probability * 100).toFixed(1)}% model
              </strong>
              <small>
                {qualifiedConsensus.no_vig_market_probability !== null &&
                qualifiedConsensus.no_vig_market_probability !== undefined
                  ? `${(qualifiedConsensus.no_vig_market_probability * 100).toFixed(1)}% no-vig market`
                  : "No-vig market unavailable"}
              </small>
            </div>
            <div className="market-card">
              <span>Decision context</span>
              <strong>{qualifiedConsensus.market_favorite || "Market unavailable"}</strong>
              <small>{qualifiedConsensus.explanation}</small>
            </div>
          </section>
        )}

        {qualifiedConsensusReasons.length > 0 && (
          <section className="why-section">
            <div className="eyebrow">Quality considerations</div>
            <ul className="reason-list clean-reasons">
              {qualifiedConsensusReasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          </section>
        )}

        {waterfallSteps.length > 0 && (
          <section className="why-section">
            <div className="eyebrow">Prediction waterfall</div>
            <h2>How confidence reached {prediction.confidence ?? "—"}%</h2>
            <div className="model-factor-list">
              {waterfallSteps.map((step, index) => {
                const value =
                  typeof step.value === "number" ? step.value : 0;
                const kind =
                  typeof step.kind === "string" ? step.kind : "observation";
                const valueLabel =
                  kind === "baseline"
                    ? `${value.toFixed(0)}%`
                    : kind === "adjustment"
                      ? `${value > 0 ? "+" : ""}${value.toFixed(0)}%`
                      : "Observed";

                return (
                  <article
                    className="model-factor-card"
                    key={String(step.step_id || index)}
                  >
                    <div className="model-factor-heading">
                      <div>
                        <span>{kind}</span>
                        <strong>{String(step.label || "Waterfall step")}</strong>
                      </div>
                      <strong>{valueLabel}</strong>
                    </div>
                    <p>{String(step.explanation || "")}</p>
                  </article>
                );
              })}
            </div>
          </section>
        )}

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
