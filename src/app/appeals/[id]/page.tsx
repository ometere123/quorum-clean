import Link from "next/link";
import { AdjudicateAppeal } from "@/components/contextual-quorum-actions";
import { screening } from "@/lib/data-source";
export const dynamic = "force-dynamic";

/**
 * There is no `get_appeal(id)` method on the contract, so this route is keyed by the
 * *screening* id, not the appeal's own id, and reads the appeal embedded in
 * `get_screening(screening_id).appeal` — the only way the contract exposes one appeal without
 * a round id to scope `list_appeals` by. See `src/lib/live-reads.ts`.
 */
export default async function AppealPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params; const result = await screening(decodeURIComponent(id));
  if (result.kind !== "AVAILABLE") return <main className="qc-shell"><Link className="qc-link" href="/rounds">← Rounds</Link><h1 className="qc-display">Appeal unavailable</h1><p className="qc-alert">{result.kind === "NOT_FOUND" ? "No screening record exists for this id." : result.error}</p></main>;
  const sc = result.value;
  const row = sc.appeal;
  if (!row) return <main className="qc-shell"><Link className="qc-link" href={`/screenings/${encodeURIComponent(sc.id)}`}>← Original screening</Link><h1 className="qc-display">No appeal filed</h1><p className="qc-alert">Screening {sc.id} has no appeal on record.</p></main>;
  return <main className="qc-shell"><Link className="qc-link" href={`/screenings/${encodeURIComponent(row.screening_id)}`}>← Original screening</Link><header className="qc-round-header"><span className="qc-label">APPEAL · {row.id}</span><h1 className="qc-display">{row.status}</h1><p>Appeal of screening {row.screening_id}; the original finding is preserved.</p></header><section className="qc-card"><p>Ground: <span className="qc-record">{row.grounds}</span></p><p className="qc-note mt-2">Evidence: {row.evidence_url || "none supplied"}</p><p className="qc-record mt-2">Bond: {row.bond} wei</p></section>{row.status === "OPEN" ? <AdjudicateAppeal appealId={row.id} /> : <p className="qc-note mt-4">This appeal is terminal and cannot be adjudicated again.</p>}</main>;
}
