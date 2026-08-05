"use client";

import Link from "next/link";
import { useMemo, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import type { CommandCenterGame, NflCommandCenterResponse } from "../lib/sports";

const percent = (value?: number | null) => value == null ? "—" : `${Math.round(value * 100)}%`;
const time = (value: string) => { const parsed = new Date(value); return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString("en-US", { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }); };
const title = (value: string) => value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());

function GameRow({ game, note }: { game: CommandCenterGame; note?: string }) {
  return <Link className="command-game" href={`/nfl/${encodeURIComponent(game.game_id)}`}>
    <div><div className="kicker">{time(game.start_time)}</div><strong>{game.away_team} at {game.home_team}</strong><small>{note || `${title(game.qualified_consensus_status)} · ${game.qualified_consensus_classification}`}</small></div>
    <div className="command-metrics"><span>Pick <b>{game.pick || "Pending"}</b></span><span>Confidence <b>{game.displayed_confidence ?? "—"}%</b></span><span>Edge <b>{percent(game.model_market_edge)}</b></span><span className={`score score-${game.opportunity_label.toLowerCase()}`}>{game.opportunity_score} · {game.opportunity_label}</span></div>
  </Link>;
}

export default function NflCommandCenter({ data }: { data: NflCommandCenterResponse }) {
  const router = useRouter(); const [pending, startTransition] = useTransition();
  const [query, setQuery] = useState(""); const [status, setStatus] = useState("all"); const [sort, setSort] = useState("score");
  const games = useMemo(() => data.all_games.filter((game) => `${game.away_team} ${game.home_team} ${game.pick}`.toLowerCase().includes(query.toLowerCase()) && (status === "all" || game.qualified_consensus_status === status)).sort((a, b) => sort === "time" ? a.start_time.localeCompare(b.start_time) : sort === "confidence" ? (b.displayed_confidence || 0) - (a.displayed_confidence || 0) : b.opportunity_score - a.opportunity_score), [data.all_games, query, status, sort]);
  return <main>
    <header><div><div className="logo">SportsIntel</div><div className="subtle">NFL decision intelligence</div></div><nav className="top-nav"><Link href="/">Command Center</Link><Link href="/nfl/review">Readiness</Link><Link href="/mlb">MLB</Link><Link href="/my-picks">My Picks</Link></nav></header>
    <section className="command-hero"><div><div className="eyebrow">NFL Command Center</div><h1>Every signal. One review surface.</h1><p className="subtle">Observation-only prioritization across model, market, readiness, and recent changes.</p></div><button className="command-button" disabled={pending} onClick={() => startTransition(() => router.refresh())}>{pending ? "Refreshing…" : "Refresh intelligence"}</button></section>
    {data.system_status.status === "degraded" && <div className="command-alert">{data.system_status.message}</div>}
    <section className="command-stats"><div><b>{data.game_count}</b><span>Games</span></div><div><b>{data.market_coverage_count}</b><span>Market covered</span></div><div><b>{data.snapshot_history_count}</b><span>With history</span></div><div><b>{title(data.season_phase)}</b><span>Season phase</span></div></section>
    {data.game_count === 0 ? <section className="card command-empty"><h2>No upcoming NFL games</h2><p className="subtle">The schedule provider returned no games. Refresh when the next slate is available.</p></section> : <>
      <section className="command-section"><div className="section-heading"><div><div className="eyebrow">Ranked review</div><h2>Top opportunities</h2></div></div><div className="command-list">{data.opportunities.slice(0, 5).map((game) => <GameRow key={game.game_id} game={game} />)}</div></section>
      <div className="command-grid"><section className="card command-panel"><div className="eyebrow">What changed</div><h2>Major & notable</h2>{data.major_changes.length ? data.major_changes.map((change) => <Link href={`/nfl/${encodeURIComponent(change.game_id)}`} key={change.game_id} className="command-note"><b>{change.matchup}</b><span>{title(change.significance)} · {change.summary}</span></Link>) : <p className="subtle">No meaningful snapshot changes detected.</p>}</section><section className="card command-panel"><div className="eyebrow">Caution queue</div><h2>Games to review</h2>{data.games_to_avoid.slice(0, 5).map((game) => <GameRow key={game.game_id} game={game} note="Review data quality and availability before acting." />)}</section></div>
      <section className="command-section"><div className="section-heading"><div><div className="eyebrow">Model vs market</div><h2>Meaningful disagreements</h2></div></div>{data.market_disagreements.length ? <div className="command-list">{data.market_disagreements.map((game) => <GameRow key={game.game_id} game={game} />)}</div> : <p className="card subtle">No meaningful disagreements detected.</p>}</section>
      <section className="command-section"><div className="section-heading"><div><div className="eyebrow">Featured views</div><h2>Slate leaders</h2></div></div><div className="featured-grid">{Object.entries(data.featured_picks).map(([label, game]) => <div className="card featured" key={label}><span>{title(label)}</span>{game ? <><b>{game.pick}</b><small>{game.away_team} at {game.home_team}</small></> : <small>No qualifying game</small>}</div>)}</div></section>
      <section className="command-section"><div className="section-heading"><div><div className="eyebrow">Full slate</div><h2>All games</h2></div></div><div className="command-controls"><label>Search<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Team or pick" /></label><label>Status<select value={status} onChange={(event) => setStatus(event.target.value)}><option value="all">All</option>{["qualified", "watch", "caution", "hold", "unavailable"].map((value) => <option key={value}>{value}</option>)}</select></label><label>Sort<select value={sort} onChange={(event) => setSort(event.target.value)}><option value="score">Opportunity</option><option value="confidence">Confidence</option><option value="time">Start time</option></select></label></div><div className="command-list">{games.map((game) => <GameRow key={game.game_id} game={game} />)}{!games.length && <p className="card subtle">No games match these filters.</p>}</div></section>
    </>}
  </main>;
}
