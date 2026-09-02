"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { rounds, sourceLabel, stats, summary } from "@/lib/data-source";
import type { ContractStats, Round, RoundSummary } from "@/lib/contract-types";
import { parseCount } from "@/lib/contract-types";

export default function HomePage() {
  const [items, setItems] = useState<Round[]>([]);
  const [summaries, setSummaries] = useState<Record<string, RoundSummary>>({});
  const [totals, setTotals] = useState<ContractStats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    void Promise.all([rounds(), stats()]).then(async ([roundResult, statsResult]) => {
      if (!mounted) return;
      if (roundResult.kind !== "AVAILABLE") { setError("The round register could not be read."); return; }
      setItems(roundResult.value);
      if (statsResult.kind === "AVAILABLE") setTotals(statsResult.value);
      const entries = await Promise.all(roundResult.value.map(async (round) => [round.id, await summary(round.id)] as const));
      if (!mounted) return;
      setSummaries(Object.fromEntries(entries.flatMap(([id, result]) => result.kind === "AVAILABLE" ? [[id, result.value]] : [])));
    }).catch((reason: unknown) => { if (mounted) setError(reason instanceof Error ? reason.message : "The register could not be read."); });
    return () => { mounted = false; };
  }, []);

  return <main className="qc-shell">
    <header className="qc-header"><div><span className="qc-label">GRANT-ROUND INTEGRITY REGISTER</span><h1 className="qc-display">Quorum Clean</h1></div><span className="qc-record">{sourceLabel}</span></header>
    <nav className="qc-nav" aria-label="Primary"><Link href="/">Dashboard</Link><Link href="/rounds">Rounds</Link><Link href="/rounds/new">Create round</Link><Link href="/activity">Activity</Link></nav>
    <section className="qc-intro"><p className="qc-heading">A public-evidence screen for reviewer weight.</p><p>Quorum Clean checks declared reviewer and applicant identities against public authorship, employment and code records. It reports a qualified tie or a qualified absence; it never claims that a clear pair is conflict-free.</p></section>
    {error ? <p className="qc-alert">{error} No fixture has been substituted.</p> : null}
    {totals ? <section className="qc-stats"><Stat label="Rounds" value={totals.rounds_created}/><Stat label="Screenings" value={totals.screenings_requested}/><Stat label="Conflicts" value={String(conflictsAcrossFetchedRounds(summaries))}/><Stat label="Appeals" value={totals.appeals_filed}/></section> : null}
    <section className="qc-next"><div><span className="qc-label">NEXT ACTION</span><p className="qc-heading">{items.length ? "Open a round to continue its evidence workflow." : "Create the first review round."}</p></div><div className="qc-actions-inline"><Link className="qc-btn" href="/rounds/new">Create round</Link><Link className="qc-btn-quiet" href="/rounds">Browse rounds</Link></div></section>
    <section><div className="qc-section-head"><span className="qc-label">RECENT ROUNDS</span><span className="qc-record">{items.length} records</span></div><div className="qc-rounds">{items.map((round) => { const item = summaries[round.id]; return <article className="qc-card" key={round.id}><div className="qc-card-top"><span className="qc-label">{round.status}</span><span className="qc-record">{round.coi_start_year} to {round.coi_end_year}</span></div><h2 className="qc-heading">{round.name}</h2><p className="qc-note">{item ? `${item.reviewers.length} reviewers × ${item.applicants.length} applicants · ${item.requested} requested` : "Summary unavailable"}</p><div className="qc-counts">{item ? <><Count label="CLEAR" value={item.clear} tone="cleared"/><Count label="CONFLICT" value={item.conflict} tone="conflict"/><Count label="UNSCREENED" value={item.unscreened} tone="hole"/><Count label="INSUFFICIENT" value={item.insufficient} tone="unclear"/></> : null}</div><Link className="qc-link" href={`/rounds/${round.id}`}>Open round →</Link></article>; })}</div></section>
    <footer className="qc-footer"><span>Clear means: no publicly evidenced tie found in sources that answered.</span><span>Weight is a read surface; the scoring system decides whether to honour it.</span></footer>
  </main>;
}

/**
 * `ledger()` has no global conflict counter — only `round_summary(id).conflict` does, per round.
 * The homepage already fetches every round's summary for the per-round tiles below, so the total
 * is a real client-side sum over that data rather than a number invented for this one tile.
 */
function conflictsAcrossFetchedRounds(summaries: Record<string, RoundSummary>): number {
  return Object.values(summaries).reduce((sum, item) => sum + (parseCount(item.conflict) ?? 0), 0);
}

function Stat({ label, value }: { label: string; value: string }) { return <div><span className="qc-label">{label}</span><strong className="qc-record">{value}</strong></div>; }
function Count({ label, value, tone }: { label: string; value: string; tone: string }) { return <span className={`qc-count qc-${tone}`}><b>{parseCount(value) ?? "-"}</b>{label}</span>; }
