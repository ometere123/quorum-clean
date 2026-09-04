"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { CONTRACT_ADDRESS } from "@/lib/genlayer/config";
import { waitAccepted, writeContract } from "@/lib/genlayer/tx";
import { genToWei, formatGen } from "@/lib/format";
import { normalizeError } from "@/lib/wallet-errors";
import { useWallet } from "./wallet-provider";

type Props = { roundId?: string; screeningId?: string; bondWei?: string; status?: string };

export function ParticipantForm({ roundId }: Props) {
  const [role, setRole] = useState("REVIEWER");
  const [values, setValues] = useState({ label: "", orcid: "", openalex: "", github: "" });
  return <ActionShell title="Add a participant" help="The round is taken from this page.">
    <label className="qc-field"><span>Role</span><select value={role} onChange={(e) => setRole(e.target.value)}><option>REVIEWER</option><option>APPLICANT</option></select></label>
    {(["label", "orcid", "openalex", "github"] as const).map((key) => <label className="qc-field" key={key}><span>{key === "label" ? "Label / name" : key === "openalex" ? "OpenAlex" : key === "github" ? "GitHub" : "ORCID"}</span><input value={values[key]} onChange={(e) => setValues({ ...values, [key]: e.target.value })} placeholder={key === "label" ? "Human-readable label" : "Optional identifier"} /></label>)}
    <SubmitButton functionName="register_participant" args={[roundId ?? "", role, values.label, values.orcid, values.openalex, values.github]} />
  </ActionShell>;
}

export function ScopeForm({ roundId, frozen = false }: Props & { frozen?: boolean }) {
  const [repos, setRepos] = useState<string[]>([]); const [orgs, setOrgs] = useState<string[]>([]);
  const [repo, setRepo] = useState(""); const [org, setOrg] = useState("");
  const add = (value: string, set: (next: string[]) => void, current: string[], clear: () => void) => { const item = value.trim(); if (item && !current.includes(item)) set([...current, item]); clear(); };
  return <ActionShell title="Declare GitHub scope" help="The operator-declared scope is frozen before screening so it cannot be changed after results are seen.">
    <div className="qc-field"><span>Repositories</span><div className="flex gap-2"><input value={repo} onChange={(e) => setRepo(e.target.value)} placeholder="owner/repository" disabled={frozen} /><button className="qc-button" type="button" onClick={() => add(repo, setRepos, repos, () => setRepo(""))} disabled={frozen}>Add</button></div><ChipList values={repos} remove={(item) => setRepos(repos.filter((x) => x !== item))} frozen={frozen} /></div>
    <div className="qc-field"><span>Organisations</span><div className="flex gap-2"><input value={org} onChange={(e) => setOrg(e.target.value)} placeholder="organisation" disabled={frozen} /><button className="qc-button" type="button" onClick={() => add(org, setOrgs, orgs, () => setOrg(""))} disabled={frozen}>Add</button></div><ChipList values={orgs} remove={(item) => setOrgs(orgs.filter((x) => x !== item))} frozen={frozen} /></div>
    <SubmitButton functionName="declare_github_scope" args={[roundId ?? "", JSON.stringify(repos), JSON.stringify(orgs)]} disabled={frozen || (!repos.length && !orgs.length)} />
  </ActionShell>;
}

export function ScreeningRequest({ roundId, reviewer, applicant, bondWei }: Props & { reviewer: string; applicant: string }) {
  const [confirm, setConfirm] = useState(false);
  const amount = bondWei ?? "0";
  return <ActionShell title="Request screening" help="A screening bond is attached to this pair.">
    <p className="qc-note">Pair <span className="qc-record">{reviewer.slice(0, 10)}… × {applicant.slice(0, 10)}…</span></p><p className="qc-note">Bond <span className="qc-record">{formatGen(amount)}</span></p>
    {!confirm ? <button className="qc-button qc-button-primary" type="button" onClick={() => setConfirm(true)}>Review request</button> : <><p className="qc-note">This sends {formatGen(amount)} to the canonical contract and creates a pending evidence request.</p><SubmitButton functionName="request_screening" args={[roundId ?? "", reviewer, applicant]} value={amount} /></>}
  </ActionShell>;
}

export function ScreeningRun({ screeningId, status }: Props) { return <ActionShell title="Run screening" help="Validators fetch the declared sources and record the result."><SubmitButton functionName="screen" args={[screeningId ?? ""]} disabled={status !== "PENDING"} /><Link className="qc-link" href={`/screenings/${encodeURIComponent(screeningId ?? "")}`}>Open result →</Link></ActionShell>; }

export function AppealForm({ screeningId, bondWei }: Props) {
  const [ground, setGround] = useState("WRONG_IDENTITY"); const [evidence, setEvidence] = useState(""); const [bond, setBond] = useState(bondWei ? formatGen(bondWei).replace(" GEN", "") : "");
  const value = genToWei(bond);
  return <ActionShell title="Appeal this screening" help="The original screening and evidence remain visible after an appeal."><label className="qc-field"><span>Ground</span><select value={ground} onChange={(e) => setGround(e.target.value)}><option>WRONG_IDENTITY</option><option>NOT_MATERIAL</option><option>STALE_TIE</option><option>MISSED_TIE</option></select></label><label className="qc-field"><span>Evidence URL</span><input value={evidence} onChange={(e) => setEvidence(e.target.value)} placeholder="https://…" /></label><label className="qc-field"><span>Bond (GEN)</span><input inputMode="decimal" value={bond} onChange={(e) => setBond(e.target.value)} placeholder="0.01" /></label>{value === null ? <p className="qc-alert">Enter a decimal GEN amount with up to 18 places.</p> : <SubmitButton functionName="appeal" args={[screeningId ?? "", ground, evidence]} value={value} />}</ActionShell>;
}

export function LockRound({ roundId, disabled = false, reason }: Props & { disabled?: boolean; reason?: string }) { return <ActionShell title="Lock round" help="Locking freezes the review set and its weights."><SubmitButton functionName="lock_round" args={[roundId ?? ""]} disabled={disabled} />{disabled && reason ? <p className="qc-note">{reason}</p> : null}</ActionShell>; }

export function AdjudicateAppeal({ appealId }: { appealId: string }) { return <ActionShell title="Adjudicate appeal" help="The original screening remains auditable; adjudication adds a disposition."><SubmitButton functionName="adjudicate_appeal" args={[appealId]} /></ActionShell>; }

function ChipList({ values, remove, frozen }: { values: string[]; remove: (item: string) => void; frozen: boolean }) { return values.length ? <ul className="mt-2 flex flex-wrap gap-2">{values.map((value) => <li className="qc-badge qc-unscreened" key={value}>{value}{!frozen ? <button type="button" className="ml-2 underline" onClick={() => remove(value)} aria-label={`Remove ${value}`}>×</button> : null}</li>)}</ul> : null; }

function ActionShell({ title, help, children }: { title: string; help: string; children: React.ReactNode }) { return <section className="qc-actions qc-card"><h2 className="qc-heading">{title}</h2><p className="qc-note">{help}</p><div className="mt-4 grid gap-3">{children}</div></section>; }

function SubmitButton({ functionName, args, value = "0", disabled = false }: { functionName: string; args: (string | bigint)[]; value?: string; disabled?: boolean }) {
  const router = useRouter();
  const wallet = useWallet();
  const [busy, setBusy] = useState(false); const [message, setMessage] = useState("");
  async function run() { setBusy(true); setMessage("Awaiting wallet approval…"); try { if (!CONTRACT_ADDRESS) throw new Error("The canonical contract is not configured."); const client = await wallet.getWriteClient(); const hash = await writeContract(client, functionName, args, BigInt(value)); setMessage(`Submitted ${String(hash)}. Waiting for FINALIZED GenVM execution…`); const outcome = await waitAccepted(client, hash); if (outcome.returned.kind === "returned" && outcome.returned.text.trim().startsWith("[REJECTED]")) setMessage(`REFUSED: ${outcome.returned.text} · ${String(hash)}`); else if (outcome.executionResult !== "SUCCESS") setMessage(`GenVM ERROR after finality: ${String(hash)}`); else { setMessage(`SUCCESS: ${functionName} finalized with GenVM SUCCESS · ${String(hash)}`); router.refresh(); } } catch (error) { setMessage(normalizeError(error)); } finally { setBusy(false); } }
  const walletNote = wallet.mode !== "injected" ? (wallet.hasInjected ? "Connect the wallet in the header to sign this." : "No injected wallet was found in this browser.") : (wallet.writeBlockedReason ?? null);
  return <div><div className="flex flex-wrap items-center gap-3"><button className="qc-button qc-button-primary" type="button" onClick={() => void run()} disabled={busy || disabled || !wallet.canWrite}>{busy ? "Waiting…" : functionName.replaceAll("_", " ")}</button></div>{walletNote ? <p className="qc-note mt-2">{walletNote}</p> : null}{message ? <p className="qc-action-message mt-2" role="status">{message}</p> : null}</div>;
}
