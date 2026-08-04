import Link from "next/link";
import { getSport } from "../lib/api";
import type { SportGameEnvelope, SportHomeResponse } from "../lib/sports";

function formatGameTime(value: string) {
  if (!value || value === "TBD") return "Time TBD";

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;

  return parsed.toLocaleString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function moneylineMarket(item: SportGameEnvelope) {
  const markets = Array.isArray(item.prediction.markets)
    ? item.prediction.markets
    : [];

  return markets.find((market) => market.market_type === "moneyline");
}

export default async function HomePage() {
  const data = (await getSport("nfl")) as SportHomeResponse;
  const games = data.games || [];

  return (
    <main>
      <header>
        <div>
          <div className="logo">SportsIntel</div>
          <div className="subtle">NFL schedule and early moneyline model</div>
        </div>
        <nav className="top-nav">
          <Link href="/">NFL</Link>
          <Link href="/mlb">MLB</Link>
          <Link href="/my-picks">My Picks</Link>
        </nav>
      </header>

      <section className="home-intro">
        <div>
          <div className="eyebrow">NFL is now live</div>
          <h1>Confirmed games. Simple early leans.</h1>
        </div>
        <div className="subtle home-intro-note">
          Schedule source: {String(data.provider?.schedule_source || "Yahoo Sports")}
        </div>
      </section>

      <section className="card breaking-impact">
        <div>
          <div className="kicker">Current model scope</div>
          <div className="breaking-headline">Moneyline only</div>
          <div className="subtle">
            Ratings and home field are active. Spread, total, injuries, and
            quarterback status are not included yet.
          </div>
        </div>
        <span className="impact-badge positive">
          {games.length} games
        </span>
      </section>

      <section className="games">
        <div className="section-heading">
          <div>
            <div className="eyebrow">Upcoming schedule</div>
            <h2>NFL Games</h2>
          </div>
          <span className="subtle">
            Tap a game for the full baseline explanation.
          </span>
        </div>

        {games.length === 0 ? (
          <section className="card">
            <div className="kicker">No games available</div>
            <h2>The schedule provider returned no upcoming NFL games.</h2>
            <p className="subtle">
              Provider status: {String(data.provider?.last_error || "No error reported")}
            </p>
          </section>
        ) : (
          <div className="game-list">
            {games.map((item) => {
              const game = item.game;
              const prediction = item.prediction;
              const market = moneylineMarket(item);

              return (
                <Link
                  className="card game"
                  key={game.game_id}
                  href={`/nfl/${encodeURIComponent(game.game_id)}`}
                >
                  <div>
                    <div className="kicker">
                      {formatGameTime(game.start_time)}
                    </div>
                    <span>
                      <strong>{game.away_team}</strong>
                      {game.metadata?.away_record
                        ? ` (${String(game.metadata.away_record)})`
                        : ""}
                      {" at "}
                      <strong>{game.home_team}</strong>
                      {game.metadata?.home_record
                        ? ` (${String(game.metadata.home_record)})`
                        : ""}
                    </span>
                    <div className="subtle">
                      {game.venue || "Venue not yet available"}
                    </div>
                  </div>

                  <div className="game-call">
                    {prediction.pick ? (
                      <>
                        <strong>{prediction.pick}</strong>
                        <span>
                          {" "}· {prediction.confidence ?? "—"}%
                        </span>
                        <small>
                          {market?.recommendation || prediction.recommendation}
                        </small>
                      </>
                    ) : (
                      <span>Prediction pending</span>
                    )}
                    <span> →</span>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </section>
    </main>
  );
}
