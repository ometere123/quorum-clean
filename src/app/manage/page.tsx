import { QuorumActions } from "@/components/quorum-actions";
import Link from "next/link";

export default function ManagePage() { return <main className="qc-shell"><Link className="qc-link" href="/">← Register</Link><header className="qc-round-header"><span className="qc-label">OPERATOR + PARTICIPANT RAIL</span><h1 className="qc-display">Make a round accountable.</h1><p>Open a round, declare its evidence scope, register the identities that consent to screening, and progress pairs through permissionless consensus calls.</p></header><QuorumActions /></main>; }
