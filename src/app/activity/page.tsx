import Link from "next/link";
import { stats } from "@/lib/data-source";

export const dynamic = "force-dynamic";
export default async function ActivityPage() { const result = await stats(); return <main className="qc-shell"><nav className="qc-nav"><Link href="/">Dashboard</Link><Link href="/rounds">Rounds</Link></nav><header className="qc-round-header"><span className="qc-label">ACTIVITY</span><h1 className="qc-display">Protocol activity</h1><p>These counters are read from the canonical contract. Transaction-level receipts remain available from the chain explorer.</p></header>{result.kind === "AVAILABLE" ? <dl className="qc-stats">{Object.entries(result.value).map(([key,value]) => <div key={key}><dt className="qc-label">{key.replaceAll("_", " ")}</dt><dd className="qc-record">{value}</dd></div>)}</dl> : <p className="qc-alert">Activity could not be read. No fixture has been substituted.</p>}</main>; }
