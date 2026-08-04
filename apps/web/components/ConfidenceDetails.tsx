"use client";

import { useEffect, useId, useRef, useState } from "react";

type ConfidenceFactor = {
  title: string;
  impact: number;
  summary: string;
};

type ConfidenceDetailsData = {
  title: string;
  summary: string;
  factors: ConfidenceFactor[];
};

type PredictionFactor = {
  factor_id: string;
  name: string;
  category: string;
  score: number;
  weight: number;
  explanation: string;
  direction: string;
  reliability: number;
  used_in_confidence: boolean;
};

type ShadowContribution = {
  factor_id: string;
  name: string;
  edge: number;
};

type ShadowScore = {
  mode: string;
  official_model_unchanged: boolean;
  pick: string;
  confidence: number;
  agrees_with_official_pick: boolean;
  confidence_difference: number;
  home_edge: number;
  away_edge: number;
  contributions: ShadowContribution[];
  summary: string;
};

type ModelCoverage = {
  active_factors: number;
  observation_only_factors: number;
  total_factors: number;
  average_reliability: number;
  coverage_percent: number;
  status: string;
  missing_planned_areas: string[];
  summary: string;
};

type Props = {
  confidence: number;
  stars: string;
  recommendation: string;
  details: ConfidenceDetailsData;
  predictionFactors?: PredictionFactor[];
  modelCoverage?: ModelCoverage;
  shadowScore?: ShadowScore;
  factorEngineVersion?: string;
  factorEngineAffectsConfidence?: boolean;
  variant?: "hero" | "panel";
};

function impactLabel(value: number) {
  if (value >= 5) return "Very high";
  if (value >= 4) return "High";
  if (value >= 3) return "Medium";
  if (value >= 2) return "Low";
  return "Minimal";
}

export function ConfidenceDetails({
  confidence,
  stars,
  recommendation,
  details,
  predictionFactors = [],
  modelCoverage,
  shadowScore,
  factorEngineVersion,
  factorEngineAffectsConfidence = false,
  variant = "panel",
}: Props) {
  const [open, setOpen] = useState(false);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    if (open && !dialog.open) {
      dialog.showModal();
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);

  return (
    <>
      <button
        className={`confidence-details-trigger ${variant}`}
        type="button"
        onClick={() => setOpen(true)}
        aria-haspopup="dialog"
      >
        <span className="confidence-trigger-stars">{stars}</span>
        <span className="confidence-trigger-label">{recommendation}</span>
        <strong>{confidence}%</strong>
        <span className="confidence-trigger-help">ⓘ Why?</span>
        <span className="confidence-track" aria-hidden="true">
          <span style={{ width: `${confidence}%` }} />
        </span>
      </button>

      <dialog
        ref={dialogRef}
        className="confidence-modal"
        aria-labelledby={titleId}
        onCancel={() => setOpen(false)}
        onClose={() => setOpen(false)}
      >
        <button
          className="confidence-modal-close"
          type="button"
          aria-label="Close confidence explanation"
          onClick={() => setOpen(false)}
        >
          ×
        </button>

        <div className="eyebrow">SportsIntel explanation</div>
        <h2 id={titleId}>{details.title}</h2>

        <div className="confidence-modal-overall">
          <div className="rating-stars">{stars}</div>
          <strong>{recommendation}</strong>
          <span>{confidence}% SportsIntel Confidence</span>
        </div>

        <div className="confidence-factor-list">
          {details.factors.map((factor) => (
            <article className="confidence-factor" key={factor.title}>
              <div className="confidence-factor-heading">
                <strong>{factor.title}</strong>
                <span>{impactLabel(factor.impact)}</span>
              </div>
              <div className="factor-impact-track" aria-label={`${impactLabel(factor.impact)} impact`}>
                <span style={{ width: `${factor.impact * 20}%` }} />
              </div>
              <p>{factor.summary}</p>
            </article>
          ))}
        </div>

        {predictionFactors.length > 0 && (
          <section className="model-factor-section">
            <div className="model-factor-heading">
              <div>
                <strong>Model factors</strong>
                <span>{factorEngineVersion || "Prediction factor engine"}</span>
              </div>
              <span className={factorEngineAffectsConfidence ? "factor-engine-live" : "factor-engine-observe"}>
                {factorEngineAffectsConfidence ? "Live scoring" : "Observation only"}
              </span>
            </div>

            {modelCoverage && (
              <div className="model-coverage-card">
                <div className="model-coverage-topline">
                  <div>
                    <span>Model coverage</span>
                    <strong>{modelCoverage.status}</strong>
                  </div>
                  <strong>{modelCoverage.coverage_percent}%</strong>
                </div>
                <div
                  className="model-coverage-track"
                  aria-label={`${modelCoverage.coverage_percent}% model coverage`}
                >
                  <span style={{ width: `${modelCoverage.coverage_percent}%` }} />
                </div>
                <div className="model-coverage-metrics">
                  <span>{modelCoverage.active_factors} active</span>
                  <span>{modelCoverage.observation_only_factors} observation-only</span>
                  <span>{Math.round(modelCoverage.average_reliability * 100)}% avg reliability</span>
                </div>
                <p>{modelCoverage.summary}</p>
                {modelCoverage.missing_planned_areas.length > 0 && (
                  <div className="model-coverage-missing">
                    <strong>Planned next:</strong>
                    <span>{modelCoverage.missing_planned_areas.join(" · ")}</span>
                  </div>
                )}
              </div>
            )}

            {shadowScore && (
              <div className="shadow-score-card">
                <div className="shadow-score-heading">
                  <div>
                    <span>Experimental comparison</span>
                    <strong>Shadow Score</strong>
                  </div>
                  <span className="shadow-score-badge">Does not affect picks</span>
                </div>
                <div className="shadow-score-comparison">
                  <div>
                    <span>Official</span>
                    <strong>{confidence}%</strong>
                  </div>
                  <div>
                    <span>Shadow</span>
                    <strong>{shadowScore.confidence}%</strong>
                  </div>
                  <div>
                    <span>Difference</span>
                    <strong>
                      {shadowScore.confidence_difference > 0 ? "+" : ""}
                      {shadowScore.confidence_difference}
                    </strong>
                  </div>
                </div>
                <div className="shadow-score-result">
                  <strong>
                    {shadowScore.agrees_with_official_pick
                      ? `Agreement: ${shadowScore.pick}`
                      : `Disagreement: ${shadowScore.pick}`}
                  </strong>
                  <p>{shadowScore.summary}</p>
                </div>
                <div className="shadow-contribution-list">
                  {shadowScore.contributions.map((item) => (
                    <div key={item.factor_id}>
                      <span>{item.name}</span>
                      <strong>
                        {item.edge > 0 ? "+" : ""}
                        {item.edge.toFixed(4)}
                      </strong>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="model-factor-list">
              {predictionFactors.map((factor) => (
                <article className="model-factor-row" key={factor.factor_id}>
                  <div className="model-factor-row-heading">
                    <strong>{factor.name}</strong>
                    <span>{factor.used_in_confidence ? "Used now" : "Not scored yet"}</span>
                  </div>
                  <div className="model-factor-meta">
                    <span>Direction: {factor.direction}</span>
                    <span>Reliability: {Math.round(factor.reliability * 100)}%</span>
                  </div>
                  <p>{factor.explanation}</p>
                </article>
              ))}
            </div>
          </section>
        )}

        <div className="confidence-modal-summary">
          <strong>Overall summary</strong>
          <p>{details.summary}</p>
        </div>
      </dialog>
    </>
  );
}
