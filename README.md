# SportsIntel

A simple NFL decision app for fast, explainable Survivor, Spread, and Totals picks.

## Version 1 scope

- NFL only
- One deterministic prediction engine
- Yahoo Sports as the only news source
- Home, Survivor, Spread, Totals, Game detail, and My Picks
- No enterprise features

## Run

```bash
cp .env.example .env
docker compose up --build
```

- Web: http://localhost:3300
- API: http://localhost:8300

## NFL prediction intelligence

NFL predictions use provisional team ratings and home field for the selected
team and model probability. Data-readiness and preseason guardrails may cap
displayed confidence. Quarterback context, market comparison, consensus,
consensus quality, team health, team intelligence, and the qualified-consensus
summary remain explainable, observation-only metadata unless a sprint explicitly
promotes a signal into prediction behavior.

`prediction.metadata.qualified_consensus` combines the existing consensus
classification and quality guardrail into one user-facing decision summary. It
includes model and no-vig market probabilities, edge, quality, status, reasons,
and `affects_prediction: false`.
