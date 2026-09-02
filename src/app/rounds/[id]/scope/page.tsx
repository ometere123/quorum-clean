import Link from "next/link";
import { ScopeForm } from "@/components/contextual-quorum-actions";
import { summary } from "@/lib/data-source";

export default async function ScopePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params; const result = await summary(id);
  if (result.kind !== "AVAILABLE") return <main className="qc-shell"><Link className="qc-link" href="/rounds">← Rounds</Link><h1 className="qc-display">Scope unavailable</h1><p className="qc-alert">{result.kind === "NOT_FOUND" ? "This round does not exist." : result.error}</p></main>;
  // `declare_github_scope` rejects on two independent contract guards: the round is LOCKED, or
  // `window_frozen` (set at the first `screen()` call, not at the first `request_screening`,
  // so `status !== "OPEN"` alone is too early and was disabling this form before the contract
  // would actually refuse it).
  const frozen = result.value.status === "LOCKED" || result.value.window_frozen;
  return <main className="qc-shell"><Link className="qc-link" href={`/rounds/${id}`}>← Round overview</Link><header className="qc-round-header"><span className="qc-label">EVIDENCE SCOPE · {id}</span><h1 className="qc-display">Declared GitHub scope</h1><p>Scope is operator-declared and freezes before screening. The contract cannot discover every private or omitted relationship.</p></header><ScopeForm roundId={id} frozen={frozen} />{frozen ? <p className="qc-note mt-3">The evidence scope is frozen before screening so it cannot be changed after results are seen.</p> : <p className="qc-note mt-3">Add repositories and organisations before requesting a screening.</p>}</main>;
}
