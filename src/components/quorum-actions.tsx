"use client";

import { useState } from "react";
import { CONTRACT_ADDRESS } from "@/lib/genlayer/config";
import { createInjectedClient } from "@/lib/genlayer/client";
import { waitAccepted, writeContract } from "@/lib/genlayer/tx";

type FieldMap = Record<string, string>;
const initial: FieldMap = { round_id: "", name: "", start: "2022", end: "2026", role: "REVIEWER", label: "", orcid: "", openalex: "", github: "", repos: "[]", orgs: "[]", reviewer: "", applicant: "", screening: "", grounds: "WRONG_IDENTITY", evidence: "", bond: "", appeal: "" };

export function QuorumActions({ roundId = "" }: { roundId?: string }) {
  const [fields, setFields] = useState<FieldMap>({ ...initial, round_id: roundId });
  const [account, setAccount] = useState<`0x${string}` | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const set = (key: string) => (event: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setFields((current) => ({ ...current, [key]: event.target.value }));

  async function connect() {
    const provider = window.ethereum;
    if (!provider) { setMessage("No injected wallet was found."); return; }
    const accounts = await provider.request({ method: "eth_requestAccounts" }) as string[];
    const first = accounts?.[0];
    if (!/^0x[0-9a-fA-F]{40}$/.test(first ?? "")) throw new Error("The wallet returned no usable address.");
    setAccount(first as `0x${string}`);
    return first as `0x${string}`;
  }

  async function submit(functionName: string, args: (string | bigint)[], value = 0n) {
    if (!CONTRACT_ADDRESS) { setMessage("No deployed Quorum Clean contract is configured; writes are closed."); return; }
    setBusy(true); setMessage("Connecting wallet…");
    try {
      const address = account ?? await connect();
      if (!address) throw new Error("Connect the wallet and try again.");
      const client = await createInjectedClient(address);
      const hash = await writeContract(client, functionName, args, value);
      setMessage(`Submitted ${functionName}: ${String(hash)}. Waiting for finalized GenVM execution…`);
      const outcome = await waitAccepted(client, hash);
      setMessage(`${functionName} finalized with GenVM ${outcome.executionResult}. Transaction: ${String(hash)}`);
    } catch (error) { setMessage(error instanceof Error ? error.message : String(error)); }
    finally { setBusy(false); }
  }

  return <section className="qc-actions" aria-labelledby="actions-title">
    <div className="qc-section-head"><span id="actions-title" className="qc-label">WALLET ACTIONS</span><button className="qc-button" type="button" onClick={() => void connect()} disabled={busy}>{account ? `${account.slice(0, 6)}…${account.slice(-4)}` : "Connect wallet"}</button></div>
    <p className="qc-note">Writes are injected-wallet only. The contract remains the authority; this panel never treats a submitted transaction as a successful execution.</p>
    <div className="qc-action-grid">
      <Action title="Open round"><Input label="Round id" value={fields.round_id} onChange={set("round_id")}/><Input label="Name" value={fields.name} onChange={set("name")}/><Input label="Start year" value={fields.start} onChange={set("start")}/><Input label="End year" value={fields.end} onChange={set("end")}/><Run disabled={busy} onClick={() => void submit("create_round", [fields.round_id, fields.name, BigInt(fields.start || "0"), BigInt(fields.end || "0")])}/></Action>
      <Action title="Register participant"><Input label="Round id" value={fields.round_id} onChange={set("round_id")}/><Input label="Role" value={fields.role} onChange={set("role")}/><Input label="Label" value={fields.label} onChange={set("label")}/><Input label="ORCID" value={fields.orcid} onChange={set("orcid")}/><Input label="OpenAlex id" value={fields.openalex} onChange={set("openalex")}/><Input label="GitHub login" value={fields.github} onChange={set("github")}/><Run disabled={busy} onClick={() => void submit("register_participant", [fields.round_id, fields.role, fields.label, fields.orcid, fields.openalex, fields.github])}/></Action>
      <Action title="Declare GitHub scope"><Input label="Round id" value={fields.round_id} onChange={set("round_id")}/><Input label="Repositories JSON" value={fields.repos} onChange={set("repos")}/><Input label="Organisations JSON" value={fields.orgs} onChange={set("orgs")}/><Run disabled={busy} onClick={() => void submit("declare_github_scope", [fields.round_id, fields.repos, fields.orgs])}/></Action>
      <Action title="Request screening"><Input label="Round id" value={fields.round_id} onChange={set("round_id")}/><Input label="Reviewer address" value={fields.reviewer} onChange={set("reviewer")}/><Input label="Applicant address" value={fields.applicant} onChange={set("applicant")}/><Input label="Bond in wei" value={fields.bond} onChange={set("bond")}/><Run disabled={busy} onClick={() => void submit("request_screening", [fields.round_id, fields.reviewer, fields.applicant], BigInt(fields.bond || "0"))}/></Action>
      <Action title="Screen / lock"><Input label="Screening id" value={fields.screening} onChange={set("screening")}/><Run disabled={busy} onClick={() => void submit("screen", [fields.screening])}/><Input label="Round id to lock" value={fields.round_id} onChange={set("round_id")}/><Run disabled={busy} onClick={() => void submit("lock_round", [fields.round_id])}/></Action>
      <Action title="Appeal / adjudicate"><Input label="Screening id" value={fields.screening} onChange={set("screening")}/><Input label="Ground" value={fields.grounds} onChange={set("grounds")}/><Input label="Evidence URL" value={fields.evidence} onChange={set("evidence")}/><Input label="Appeal bond in wei" value={fields.bond} onChange={set("bond")}/><Run disabled={busy} onClick={() => void submit("appeal", [fields.screening, fields.grounds, fields.evidence], BigInt(fields.bond || "0"))}/><Input label="Appeal id" value={fields.appeal} onChange={set("appeal")}/><Run disabled={busy} onClick={() => void submit("adjudicate_appeal", [fields.appeal])}/></Action>
    </div>
    {message ? <p className="qc-action-message" role="status">{message}</p> : null}
  </section>;
}

function Action({ title, children }: { title: string; children: React.ReactNode }) { return <fieldset className="qc-action"><legend className="qc-label">{title}</legend>{children}</fieldset>; }
function Input({ label, value, onChange }: { label: string; value: string; onChange: (event: React.ChangeEvent<HTMLInputElement>) => void }) { return <label className="qc-field"><span>{label}</span><input value={value} onChange={onChange}/></label>; }
function Run({ disabled, onClick }: { disabled: boolean; onClick: () => void }) { return <button className="qc-button qc-button-primary" type="button" disabled={disabled} onClick={onClick}>Submit</button>; }
