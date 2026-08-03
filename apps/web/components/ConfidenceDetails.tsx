"use client";

import { useEffect, useId, useState } from "react";

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

type Props = {
  confidence: number;
  stars: string;
  recommendation: string;
  details: ConfidenceDetailsData;
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
  variant = "panel",
}: Props) {
  const [open, setOpen] = useState(false);
  const titleId = useId();

  useEffect(() => {
    if (!open) return;

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }

    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
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

      {open && (
        <div className="confidence-modal-backdrop" role="presentation" onMouseDown={() => setOpen(false)}>
          <section
            className="confidence-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            onMouseDown={(event) => event.stopPropagation()}
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

            <div className="confidence-modal-summary">
              <strong>Overall summary</strong>
              <p>{details.summary}</p>
            </div>
          </section>
        </div>
      )}
    </>
  );
}
