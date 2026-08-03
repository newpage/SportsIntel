import Link from "next/link";
import { getMlb } from "../../../lib/api";
import { MlbResultsClient } from "../../../components/MlbResultsClient";

export default async function MlbResultsPage() {
  const data = await getMlb();

  return (
    <main>
      <header>
        <div>
          <div className="logo">SportsIntel</div>
          <div className="subtle">MLB prediction results</div>
        </div>
        <nav className="top-nav">
          <Link href="/">NFL</Link>
          <Link href="/mlb">MLB</Link>
          <Link href="/my-picks">My Picks</Link>
        </nav>
      </header>

      <section className="home-intro">
        <div>
          <div className="eyebrow">Daily feedback loop</div>
          <h1>How did the saved picks perform?</h1>
        </div>
        <div className="subtle home-intro-note">
          Only predictions saved in this browser before final scores are evaluated.
        </div>
      </section>

      <MlbResultsClient games={data.games} />
    </main>
  );
}
