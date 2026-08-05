import { getNflCommandCenter } from "../lib/api";
import type { NflCommandCenterResponse } from "../lib/sports";
import NflCommandCenter from "./nfl-command-center";

export default async function HomePage() {
  try {
    const data = (await getNflCommandCenter()) as NflCommandCenterResponse;
    return <NflCommandCenter data={data} />;
  } catch {
    return (
      <main><section className="card command-empty"><div className="eyebrow">NFL Command Center</div>
        <h1>Game intelligence is temporarily unavailable.</h1>
        <p className="subtle">Refresh shortly. No prediction inputs or outputs were changed.</p>
        <a className="command-button" href="/">Refresh</a>
      </section></main>
    );
  }
}
