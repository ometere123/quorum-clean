import Link from "next/link";
import { CreateRoundForm } from "@/components/create-round-form";

export default function NewRoundPage() { return <main className="qc-shell"><nav className="qc-nav"><Link href="/">Dashboard</Link><Link href="/rounds">Rounds</Link></nav><header className="qc-round-header"><span className="qc-label">NEW ROUND</span><h1 className="qc-display">Create a review round</h1><p>Choose a stable identifier and a closed calendar-year COI window. Participants and evidence scope are added after creation.</p></header><CreateRoundForm /></main>; }
