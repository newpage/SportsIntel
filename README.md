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

## NFL prediction change detection

Sprint 14.4 adds an observation-only snapshot comparison engine. It does not
persist snapshots and does not modify the NFL provider or prediction pipeline.

`PredictionSnapshot` captures the game, timestamp, pick, model probability,
displayed and raw confidence, confidence cap, readiness, season phase,
quarterback statuses, moneylines, no-vig market probability, model-market edge,
qualified-consensus status/classification/quality, and model version.

`PredictionComparison` reports whether meaningful changes were detected, the
highest significance (`none`, `minor`, `notable`, or `major`), a structured
list of changes, and `affects_prediction: false`. Each change contains its
field, label, previous/current values, direction, significance, and explanation.

The development diagnostic route accepts two validated snapshot payloads:

```http
POST /api/sports/nfl/compare
Content-Type: application/json

{
  "previous": { "game_id": "nfl-123", "...": "complete snapshot" },
  "current": { "game_id": "nfl-123", "...": "complete snapshot" }
}
```

Major changes include a changed pick, qualified consensus moving to or from
Hold, and a quarterback downgrade from expected/confirmed to
out/inactive/doubtful. Notable changes include confidence movement of at least
three points, model-market edge movement of at least five percentage points,
classification changes, and readiness changes. Other threshold-qualified
changes are minor; no meaningful changes produce `none`.

The comparison contract is diagnostic only: picks, model probabilities,
displayed confidence, ratings, and consensus calculations remain unchanged.

## NFL automatic snapshot history

The NFL sports endpoint automatically captures each available prediction into a
thread-safe, process-local `PredictionSnapshotStore`. One timezone-aware UTC
timestamp is shared by every game generated in the same response.

History is memory-only:

- At most 20 snapshots are retained per game.
- History is returned newest first.
- A snapshot is deduplicated when all comparison-relevant fields except
  `captured_at` match an existing stored version.
- Capture failures are logged and never fail the NFL response.
- All history disappears whenever the API process restarts.
- The store implements an isolated interface so persistent storage can replace
  it in a future sprint.

Diagnostic endpoints:

- `GET /api/sports/nfl/{game_id}/history?limit=10` returns up to 20 snapshots.
- `GET /api/sports/nfl/{game_id}/changes` returns the latest comparison, or a
  typed “No prior snapshot” response when only one version exists.
- `DELETE /api/sports/nfl/{game_id}/history` clears one game.
- `POST /api/sports/nfl/history/clear` clears the entire in-memory store.

Snapshot diagnostics are also included in `GET /api/sports/nfl/review`,
including coverage, multiple-version counts, meaningful changes, major/notable
change counts, store type, and persistence status.

Snapshot history and all related endpoints remain observation-only and return
`affects_prediction: false` where applicable. They do not change picks,
probabilities, confidence, ratings, consensus, providers, or scheduling.
