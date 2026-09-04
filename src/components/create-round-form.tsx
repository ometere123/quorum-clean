"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { CONTRACT_ADDRESS } from "@/lib/genlayer/config";
import { waitAccepted, writeContract } from "@/lib/genlayer/tx";
import { normalizeError } from "@/lib/wallet-errors";
import { useWallet } from "./wallet-provider";

export function CreateRoundForm() {
  const router = useRouter();
  const wallet = useWallet();
  const [id,setId]=useState(""); const [name,setName]=useState(""); const [start,setStart]=useState("2022"); const [end,setEnd]=useState("2026"); const [busy,setBusy]=useState(false); const [message,setMessage]=useState("");
  async function submit() { if(!CONTRACT_ADDRESS){setMessage("No deployed contract is configured; writes are closed.");return;} if(!id.trim()||!name.trim()){setMessage("Enter a round id and name before submitting.");return;} setBusy(true); setMessage("Awaiting wallet approval…"); try { const client=await wallet.getWriteClient(); const hash=await writeContract(client,"create_round",[id.trim(),name.trim(),BigInt(start),BigInt(end)],0n); setMessage(`Submitted ${String(hash)}. Waiting for FINALIZED GenVM execution…`); const outcome=await waitAccepted(client,hash); if(outcome.executionResult !== "SUCCESS"){setMessage(`Finalized with GenVM ${outcome.executionResult}; no successful round creation was recorded.`);return;} setMessage(`SUCCESS: round finalized. Opening ${id.trim()}…`); router.push(`/rounds/${encodeURIComponent(id.trim())}`); router.refresh(); } catch(error){setMessage(normalizeError(error));} finally{setBusy(false);} }
  const walletNote = wallet.mode !== "injected" ? (wallet.hasInjected ? "Connect the wallet in the header to create a round." : "No injected wallet was found in this browser.") : (wallet.writeBlockedReason ?? null);
  return <section className="qc-card" aria-labelledby="new-round-form"><h2 id="new-round-form" className="qc-heading">Round details</h2><div className="qc-form-grid"><label className="qc-field"><span>Round id</span><input value={id} onChange={e=>setId(e.target.value)} placeholder="grant-round-2026" /></label><label className="qc-field"><span>Name</span><input value={name} onChange={e=>setName(e.target.value)} placeholder="Spring review" /></label><label className="qc-field"><span>COI start year</span><input inputMode="numeric" value={start} onChange={e=>setStart(e.target.value)} /></label><label className="qc-field"><span>COI end year</span><input inputMode="numeric" value={end} onChange={e=>setEnd(e.target.value)} /></label></div><p className="qc-note">The window is inclusive and operator-declared. Participants and GitHub evidence scope are added before screening.</p><button className="qc-btn" type="button" disabled={busy || !wallet.canWrite} onClick={()=>void submit()}>{busy?"Working…":"Create round"}</button>{walletNote?<p className="qc-note mt-2">{walletNote}</p>:null}{message?<p className="qc-action-message" role="status">{message}</p>:null}</section>;
}
