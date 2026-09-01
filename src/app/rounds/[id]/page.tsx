import Link from "next/link";
import { screenings, summary } from "@/lib/data-source";

export default async function RoundPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [sum, rows] = await Promise.all([summary(id), screenings(id)]);
  if (sum.kind !== "AVAILABLE") return <main className="qc-shell"><Link href="/">← Register</Link><h1 className="qc-display">Round not found</h1></main>;
  return <main className="qc-shell"><Link className="qc-link" href="/">← Register</Link><header className="qc-round-header"><span className="qc-label">ROUND {sum.value.id}</span><h1 className="qc-display">{sum.value.name}</h1><p>{sum.value.coi_start_year}—{sum.value.coi_end_year}, closed calendar-year window. {sum.value.reviewers.length} reviewers × {sum.value.applicants.length} applicants.</p></header><div className="qc-table-wrap"><table className="qc-table"><thead><tr><th>Reviewer</th><th>Applicant</th><th>Finding</th><th>Weight</th><th>Evidence</th></tr></thead><tbody>{rows.kind === "AVAILABLE" ? rows.value.map((row) => <tr key={row.id}><td className="qc-record">{row.reviewer}</td><td className="qc-record">{row.applicant}</td><td><span className={`qc-badge qc-${row.status.toLowerCase()}`}>{row.status}</span><p className="qc-note">{row.rationale || "Not screened yet."}</p></td><td className="qc-record">{row.weight_bp} bp</td><td className="qc-note">{row.tie_basis || "No tie named"}<br/>{row.sources_failed ? `Failed: ${row.sources_failed}` : "Sources answered"}</td></tr>) : <tr><td colSpan={5}>Screenings unavailable: {rows.kind === "UNAVAILABLE" || rows.kind === "INVALID_RESPONSE" ? rows.error : "not found"}</td></tr>}</tbody></table></div></main>;
}
