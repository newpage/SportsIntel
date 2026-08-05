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

The NFL sports endpoint automatically captures each available prediction through
the existing snapshot-store interface. One timezone-aware UTC timestamp is
shared by every game generated in the same response. PostgreSQL is selected when
`DATABASE_URL` is configured; memory is selected when no database is configured
or when `NFL_SNAPSHOT_STORE=memory` is explicit. Set
`NFL_SNAPSHOT_STORE=postgres` to require durable storage. PostgreSQL failures do
not silently switch the running process to memory.

Storage semantics:

- At most 20 snapshots are retained per game.
- History is returned newest first.
- A snapshot is deduplicated when it is equivalent to the immediately previous
  stored snapshot, excluding `captured_at`.
- Capture failures are logged and never fail the NFL response.
- PostgreSQL history survives API and container restarts; memory history does
  not survive an API process restart.
- PostgreSQL uses a per-game advisory transaction lock so concurrent equivalent
  writes deduplicate and retention pruning is atomic with insertion.
- A → B → A reversions remain three stored versions.

The structured schema is defined in
`db/init/001_nfl_prediction_snapshots.sql`. Docker Compose applies it
automatically when creating a new PostgreSQL data volume. Existing deployments
must apply the idempotent file before setting `NFL_SNAPSHOT_STORE=postgres`, for
example with `psql "$DATABASE_URL" -f db/init/001_nfl_prediction_snapshots.sql`.
Memory-only history is intentionally not migrated because it has no durable
source; persistence begins with the first PostgreSQL-backed capture.

Diagnostic endpoints:

- `GET /api/sports/nfl/{game_id}/history?limit=10` returns up to 20 snapshots.
- `GET /api/sports/nfl/{game_id}/changes` returns the latest comparison, or a
  typed “No prior snapshot” response when only one version exists.
- `DELETE /api/sports/nfl/{game_id}/history` clears one game.
- `POST /api/sports/nfl/history/clear` clears the configured store.
- `GET /api/sports/nfl/snapshot-store/health` reports store type, persistence,
  database/table reachability, retained row count, and last successful write.

Snapshot diagnostics are also included in `GET /api/sports/nfl/review`,
including coverage, multiple-version counts, meaningful changes, major/notable
change counts, store type, and persistence status.

Snapshot history and all related endpoints remain observation-only and return
`affects_prediction: false` where applicable. They do not change picks,
probabilities, confidence, ratings, consensus, providers, or scheduling.

Back up `nfl_prediction_snapshots` with the same PostgreSQL backup policy used
for the application database. The clear endpoints are administrative diagnostics
and must be protected by authentication before public deployment. Credentials
and connection strings are never returned by health or history responses, and
database errors are reduced to a generic 503 response for API clients.

## NFL Command Center

`GET /api/sports/nfl/command-center` aggregates the current NFL slate, qualified
consensus, market context, readiness, and the latest bounded snapshot comparisons
into one observation-only response. The root web page uses this single endpoint.
If snapshot history is unavailable, current game intelligence remains available
and `system_status` reports the degraded dependency.

Opportunity scores are deterministic and range from 0–100: consensus status
(25 points), consensus quality (20), positive model-market edge (20), displayed
confidence (15), data readiness (10), market availability (5), and quarterback
availability (5), with a 10-point preseason uncertainty penalty. Labels are
`Priority` at 80+, `Strong` at 65+, `Watch` at 50+, and `Limited` below 50.
These rankings do not change picks, probabilities, confidence, ratings, or any
provider calculation; every result includes `affects_prediction: false`.

## Continuous integration

`.github/workflows/ci.yml` runs for pull requests targeting `main`, pushes to
`main`, and manual dispatches. Superseded pull-request or feature-branch runs are
cancelled; `main` runs are never cancelled by later pushes.

The workflow exposes four independent required checks:

- **Backend quality** installs Python 3.12 dependencies with a pip download
  cache, compiles API/test sources, and runs the complete non-PostgreSQL suite.
- **PostgreSQL integration** starts an isolated PostgreSQL 17 service, applies
  the idempotent snapshot schema, verifies the table, and runs the dedicated
  integration suite with `TEST_DATABASE_URL`.
- **Frontend quality** installs Node 22 dependencies with `npm ci` and the npm
  cache, then runs TypeScript validation and the production Next.js build. No
  lint step runs because this repository does not currently configure a linter.
- **Docker validation** validates Compose, builds API/web images without
  publishing them, starts the stack with temporary CI-only credentials, checks
  `/health` and the snapshot-store health endpoint, and always tears down the
  stack and volumes. Compose logs are collected when the smoke test fails.

Equivalent local commands:

```bash
python -m pip install -r apps/api/requirements-dev.txt
python -m compileall -q apps/api/app apps/api/tests
PYTHONPATH=apps/api NFL_SNAPSHOT_STORE=memory pytest -q --ignore=apps/api/tests/test_postgres_snapshot_store.py
PYTHONPATH=apps/api TEST_DATABASE_URL=postgresql://USER:PASSWORD@127.0.0.1:5432/DB pytest -q apps/api/tests/test_postgres_snapshot_store.py
cd apps/web && npm ci && npm run typecheck && npm run build
docker compose config --quiet
docker compose build api web
```

All four checks are recommended as required for `main`; see
`docs/branch-protection.md`. Test result XML is uploaded when a pytest job fails.
Open the failed job and its artifact first, then reproduce its displayed command
locally. For Docker failures, inspect the automatically collected Compose logs.
Use GitHub’s **Re-run failed jobs** action after pushing a fix, or
**Run workflow** for a manual validation. Fix failures on the same PR branch;
do not bypass or weaken checks to obtain a green run.

## Production security and operations

SportsIntel supports configuration-driven CORS, production-only HSTS, baseline
security headers, per-IP public/admin rate limits, request IDs, structured access
logs, and an `X-Admin-Key` guard on destructive snapshot-history routes.
Production startup validates PostgreSQL persistence, HTTPS CORS origins, build
metadata, and a non-placeholder admin key before serving traffic.

The enriched `/health` response reports application status, PostgreSQL and
snapshot-store reachability, version, UTC build timestamp, Git commit, and
environment without returning credentials. Docker services run as non-root where
applicable and include healthchecks, restart policies, and graceful shutdown
windows.

See [the production deployment guide](docs/production.md) for Linux setup,
Apache/HTTPS configuration, firewall rules, every environment variable,
backup/restore, rollback, monitoring, and log handling. Start from
`production.env.example`; never deploy its placeholder values.
