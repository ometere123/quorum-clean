import { QuorumActions } from "@/components/quorum-actions";
import Link from "next/link";

export default function ManagePage() { return <main className="qc-shell"><Link className="qc-link" href="/">← Register</Link><header className="qc-round-header"><span className="qc-label">ADVANCED CONTRACT TOOLS</span><h1 className="qc-display">Technical action rail.</h1><p>Normal workflows now live on their round and screening pages. Keep this route for operators and reviewers who need a raw contract surface for diagnostics or exceptional cases.</p><nav className="qc-nav"><Link href="/rounds">Browse rounds</Link><Link href="/rounds/new">Create a round</Link></nav></header><QuorumActions /></main>; }
