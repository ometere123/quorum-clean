import Link from "next/link";
import { ParticipantForm } from "@/components/contextual-quorum-actions";
import { summary } from "@/lib/data-source";

export default async function ParticipantsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params; const result = await summary(id);
  if (result.kind !== "AVAILABLE") return <main className="qc-shell"><Link className="qc-link" href="/rounds">← Rounds</Link><h1 className="qc-display">Participants unavailable</h1><p className="qc-alert">{result.kind === "NOT_FOUND" ? "This round does not exist." : result.error}</p></main>;
  const reviewers = result.value.participants.filter((p) => p.role === "REVIEWER"); const applicants = result.value.participants.filter((p) => p.role === "APPLICANT");
  const group = (title: string, rows: typeof reviewers) => <section className="qc-card"><h2 className="qc-heading">{title}</h2>{rows.length ? <ul className="mt-3 grid gap-2">{rows.map((p) => <li className="qc-rule py-2" key={p.addr}><span>{p.label || "Unlabelled identity"}</span><span className="qc-record block">{p.addr}</span></li>)}</ul> : <p className="qc-note mt-3">None registered yet.</p>}</section>;
  return <main className="qc-shell"><Link className="qc-link" href={`/rounds/${id}`}>← Round overview</Link><header className="qc-round-header"><span className="qc-label">PARTICIPANTS · {id}</span><h1 className="qc-display">{result.value.name}</h1><p>Register identities here. The round id is taken from the route; no copy-and-paste into a technical tool is required.</p></header><div className="grid gap-4 md:grid-cols-2">{group("Reviewers", reviewers)}{group("Applicants", applicants)}</div><ParticipantForm roundId={id} /></main>;
}
