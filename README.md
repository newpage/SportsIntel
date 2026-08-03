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
