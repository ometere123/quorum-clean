import Link from "next/link";
import { AdjudicateAppeal } from "@/components/contextual-quorum-actions";
import { appeal } from "@/lib/data-source";
export const dynamic = "force-dynamic";

export default async function AppealPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params; const result = await appeal(decodeURIComponent(id));
  if (result.kind !== "AVAILABLE") return <main className="qc-shell"><Link className="qc-link" href="/rounds">← Rounds</Link><h1 className="qc-display">Appeal unavailable</h1><p className="qc-alert">{result.kind === "NOT_FOUND" ? "No appeal record exists for this id." : result.error}</p></main>;
  const row = result.value;
  return <main className="qc-shell"><Link className="qc-link" href={`/screenings/${encodeURIComponent(row.screening_id)}`}>← Original screening</Link><header className="qc-round-header"><span className="qc-label">APPEAL · {row.id}</span><h1 className="qc-display">{row.status}</h1><p>Appeal of screening {row.screening_id}; the original finding is preserved.</p></header><section className="qc-card"><p>Ground: <span className="qc-record">{row.grounds}</span></p><p className="qc-note mt-2">Evidence: {row.evidence_url || "none supplied"}</p><p className="qc-record mt-2">Bond: {row.bond} wei</p></section>{row.status === "OPEN" ? <AdjudicateAppeal appealId={row.id} /> : <p className="qc-note mt-4">This appeal is terminal and cannot be adjudicated again.</p>}</main>;
}
