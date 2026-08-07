"use client";

import Link from "next/link";
import { useEffect, useId, useMemo, useRef, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import type { CommandCenterGame, NflCommandCenterResponse } from "../lib/sports";

const percent = (value?: number | null) => value == null ? "—" : `${Math.round(value * 100)}%`;
const time = (value: string) => { const parsed = new Date(value); return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString("en-US", { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }); };
const title = (value: string) => value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());

function opportunityStars(score: number) {
  if (score >= 80) return 5;
  if (score >= 65) return 4;
  if (score >= 50) return 3;
  if (score >= 25) return 2;
  return 1;
}

function OpportunityRating({ game }: { game: CommandCenterGame }) {
  const stars = opportunityStars(game.opportunity_score);
  return <span className={`opportunity-rating score-${game.opportunity_label.toLowerCase()}`} aria-label={`${stars} out of 5 stars, ${game.opportunity_label} opportunity readiness, score ${game.opportunity_score} out of 100`}>
    <span className="opportunity-stars" aria-hidden="true">{"★".repeat(stars)}{"☆".repeat(5 - stars)}</span>
    <span className="opportunity-label">{game.opportunity_label}</span>
    <small>{game.opportunity_score}/100 readiness</small>
  </span>;
}

function GameRow({ game, note }: { game: CommandCenterGame; note?: string }) {
  return <Link className="command-game" href={game.detail_url}>
    <div><div className="kicker">{time(game.start_time)}</div><strong>{game.away_team} at {game.home_team}</strong><small>{note || `${title(game.qualified_consensus_status)} · ${game.qualified_consensus_classification}`}</small></div>
    <div className="command-metrics"><span>Pick <b>{game.pick || "Pending"}</b></span><span>Confidence <b>{game.displayed_confidence ?? "—"}%</b></span><span>Edge <b>{percent(game.model_market_edge)}</b></span><OpportunityRating game={game} /></div>
  </Link>;
}

export default function NflCommandCenter({ data }: { data: NflCommandCenterResponse }) {
  const router = useRouter(); const [pending, startTransition] = useTransition();
  const [query, setQuery] = useState(""); const [status, setStatus] = useState("all"); const [sort, setSort] = useState("score");
  const [guideOpen, setGuideOpen] = useState(false);
  const guideRef = useRef<HTMLDialogElement>(null);
  const guideTitleId = useId();
  useEffect(() => {
    const dialog = guideRef.current;
    if (!dialog) return;
    if (guideOpen && !dialog.open) dialog.showModal();
    if (!guideOpen && dialog.open) dialog.close();
  }, [guideOpen]);
  const games = useMemo(() => data.all_games.filter((game) => `${game.away_team} ${game.home_team} ${game.pick}`.toLowerCase().includes(query.toLowerCase()) && (status === "all" || game.qualified_consensus_status === status)).sort((a, b) => sort === "time" ? a.start_time.localeCompare(b.start_time) : sort === "confidence" ? (b.displayed_confidence || 0) - (a.displayed_confidence || 0) : b.opportunity_score - a.opportunity_score), [data.all_games, query, status, sort]);
  return <main>
    <header><div><div className="logo">SportsIntel</div><div className="subtle">NFL decision intelligence</div></div><nav className="top-nav"><Link href="/">Command Center</Link><Link href="/nfl/review">Readiness</Link><Link href="/mlb">MLB</Link><Link href="/my-picks">My Picks</Link></nav></header>
    <section className="command-hero"><div><div className="eyebrow">NFL Command Center</div><h1>Every signal. One review surface.</h1><p className="subtle">Observation-only prioritization across model, market, readiness, and recent changes.</p></div><button className="command-button" disabled={pending} onClick={() => startTransition(() => router.refresh())}>{pending ? "Refreshing…" : "Refresh intelligence"}</button></section>
    {data.system_status.status === "degraded" && <div className="command-alert">{data.system_status.message}</div>}
    <section className="command-stats"><div><b>{data.game_count}</b><span>Games</span></div><div><b>{data.market_coverage_count}</b><span>Market covered</span></div><div><b>{data.snapshot_history_count}</b><span>With history</span></div><div><b>{title(data.season_phase)}</b><span>Season phase</span></div></section>
    {data.game_count === 0 ? <section className="card command-empty"><h2>No upcoming NFL games</h2><p className="subtle">The schedule provider returned no games. Refresh when the next slate is available.</p></section> : <>
      <section className="command-section"><div className="section-heading"><div><div className="eyebrow">Ranked review</div><h2>Top opportunities</h2><p className="subtle opportunity-caption">Stars show how much information supports reviewing a game—not its chance of winning.</p></div><button className="opportunity-help" type="button" aria-haspopup="dialog" onClick={() => setGuideOpen(true)}>ⓘ How ratings work</button></div><div className="command-list">{data.opportunities.slice(0, 5).map((game) => <GameRow key={game.game_id} game={game} />)}</div></section>
      <div className="command-grid"><section className="card command-panel"><div className="eyebrow">What changed</div><h2>Major & notable</h2>{data.major_changes.length ? data.major_changes.map((change) => <Link href={change.detail_url} key={change.game_id} className="command-note"><b>{change.matchup}</b><span>{title(change.significance)} · {change.summary}</span></Link>) : <p className="subtle">No meaningful snapshot changes detected.</p>}</section><section className="card command-panel"><div className="eyebrow">Caution queue</div><h2>Games to review</h2>{data.games_to_avoid.slice(0, 5).map((game) => <GameRow key={game.game_id} game={game} note="Review data quality and availability before acting." />)}</section></div>
      <section className="command-section"><div className="section-heading"><div><div className="eyebrow">Model vs market</div><h2>Meaningful disagreements</h2></div></div>{data.market_disagreements.length ? <div className="command-list">{data.market_disagreements.map((game) => <GameRow key={game.game_id} game={game} />)}</div> : <p className="card subtle">No meaningful disagreements detected.</p>}</section>
      <section className="command-section"><div className="section-heading"><div><div className="eyebrow">Featured views</div><h2>Slate leaders</h2></div></div><div className="featured-grid">{Object.entries(data.featured_picks).map(([label, game]) => game ? <Link className="card featured" href={game.detail_url} key={label}><span>{title(label)}</span><b>{game.pick}</b><small>{game.away_team} at {game.home_team}</small></Link> : <div className="card featured" key={label}><span>{title(label)}</span><small>No qualifying game</small></div>)}</div></section>
      <section className="command-section"><div className="section-heading"><div><div className="eyebrow">Full slate</div><h2>All games</h2></div></div><div className="command-controls"><label>Search<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Team or pick" /></label><label>Status<select value={status} onChange={(event) => setStatus(event.target.value)}><option value="all">All</option>{["qualified", "watch", "caution", "hold", "unavailable"].map((value) => <option key={value}>{value}</option>)}</select></label><label>Sort<select value={sort} onChange={(event) => setSort(event.target.value)}><option value="score">Opportunity</option><option value="confidence">Confidence</option><option value="time">Start time</option></select></label></div><div className="command-list">{games.map((game) => <GameRow key={game.game_id} game={game} />)}{!games.length && <p className="card subtle">No games match these filters.</p>}</div></section>
    </>}
    <dialog ref={guideRef} className="confidence-modal opportunity-modal" aria-labelledby={guideTitleId} onCancel={() => setGuideOpen(false)} onClose={() => setGuideOpen(false)}>
      <button className="confidence-modal-close" type="button" aria-label="Close opportunity rating explanation" onClick={() => setGuideOpen(false)}>×</button>
      <div className="eyebrow">Plain-language guide</div>
      <h2 id={guideTitleId}>What the opportunity rating means</h2>
      <p>The stars tell you how much trustworthy information supports reviewing this game. They do <strong>not</strong> predict the winner.</p>
      <div className="opportunity-scale">
        <div><span aria-hidden="true">★★★★★</span><strong>Priority</strong><small>80–100 · strongest overall support</small></div>
        <div><span aria-hidden="true">★★★★☆</span><strong>Strong</strong><small>65–79 · good support, fewer gaps</small></div>
        <div><span aria-hidden="true">★★★☆☆</span><strong>Watch</strong><small>50–64 · useful, but check new information</small></div>
        <div><span aria-hidden="true">★★☆☆☆</span><strong>Limited</strong><small>25–49 · important information is missing</small></div>
        <div><span aria-hidden="true">★☆☆☆☆</span><strong>Very limited</strong><small>0–24 · too little support for a strong review</small></div>
      </div>
      <div className="confidence-modal-summary">
        <strong>What improves the rating?</strong>
        <p>Clear model and market agreement, better data quality, available odds, announced quarterbacks, and higher displayed confidence. Preseason uncertainty lowers it.</p>
      </div>
    </dialog>
  </main>;
}
