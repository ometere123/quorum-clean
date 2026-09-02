import Link from "next/link";
import { rounds } from "@/lib/data-source";

export const dynamic = "force-dynamic";

export default async function RoundsPage() {
  const result = await rounds();
  return <main className="qc-shell"><nav className="qc-nav"><Link href="/">Dashboard</Link><Link href="/rounds/new">Create round</Link><Link href="/activity">Activity</Link></nav><header className="qc-round-header"><span className="qc-label">ROUND REGISTER</span><h1 className="qc-display">Rounds</h1><p>Review rounds are the containers for participants, declared evidence scope, screening results and final weight.</p></header>{result.kind !== "AVAILABLE" ? <p className="qc-alert">The round register could not be read. No fixture has been substituted.</p> : <div className="qc-rounds">{result.value.map((round) => <article className="qc-card" key={round.id}><div className="qc-card-top"><span className="qc-label">{round.status}</span><span className="qc-record">{round.coi_start_year}–{round.coi_end_year}</span></div><h2 className="qc-heading">{round.name}</h2><p className="qc-note">{round.reviewers.length} reviewers · {round.applicants.length} applicants</p><Link className="qc-link" href={`/rounds/${round.id}`}>Open round →</Link></article>)}</div>}</main>;
}
