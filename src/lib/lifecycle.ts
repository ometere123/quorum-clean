/**
 * The lifecycle of a write, and the contract's own programme of work inside it.
 *
 * Two things are kept apart here. The client phases are what this browser knows: it validated,
 * it asked the wallet, it has a hash, the node reports a consensus stage. The programme is what
 * the contract does inside that window, which a node does not report step by step, so those rows
 * are listed and never animated as though they were being observed.
 */

export type ClientPhase =
  | "idle"
  | "validating"
  | "wallet-pending"
  | "submitted"
  | "consensus-running"
  | "settled";

export type PhaseFacts = {
  key: ClientPhase;
  label: string;
  detail: string;
};

export const CLIENT_PHASES: readonly PhaseFacts[] = [
  {
    key: "validating",
    label: "checking the form",
    detail:
      "Field checks run here, in this browser, before anything is signed. A rejection at this step costs nothing and touches no bond.",
  },
  {
    key: "wallet-pending",
    label: "waiting for your signature",
    detail:
      "Your wallet has the method name and the amount. Nothing has been sent. Cancelling returns you to the form with what you typed still in it.",
  },
  {
    key: "submitted",
    label: "submitted",
    detail:
      "The transaction has a hash and is in the network's hands. The hash appears the moment it exists, and it is the same hash the explorer shows.",
  },
  {
    key: "consensus-running",
    label: "consensus",
    detail:
      "Validators are running the method independently and comparing results. The stage below is what the node reports, which is a consensus stage and not per step progress.",
  },
  {
    key: "settled",
    label: "settled",
    detail: "The transaction reached a terminal stage. What it returned is shown below it.",
  },
];

/**
 * `screen(id)`, step by step, in the order section 7 fixes.
 *
 * `reached` is the honest part. Most pairs in a real round never get past the fourth row, because
 * a deterministic intersection found nothing and every source that pair needed answered. Showing
 * an inference row as running when no prompt was issued would be a lie about the mechanism, and
 * this product's whole claim is that the common case costs zero prompts.
 */
export type ProgramStep = {
  key: string;
  label: string;
  kind: "deterministic" | "network" | "inference";
  reached: "always" | "unless-early-exit" | "only-when-a-tie-exists";
  detail: string;
  /** Where this step can end the screening, if it can. */
  exit: string | null;
};

export const SCREEN_PROGRAM: readonly ProgramStep[] = [
  {
    key: "guard",
    label: "guard",
    kind: "deterministic",
    reached: "always",
    detail: "The screening exists and is PENDING. The round is not locked.",
    exit: "Reverts [EXPECTED] if either is untrue. No bond is touched.",
  },
  {
    key: "handles",
    label: "resolving handles",
    kind: "deterministic",
    reached: "always",
    detail:
      "Reads the identifiers both parties declared at registration. No name is ever used to guess an identity.",
    exit: "No handles on an axis for either party ends the screening as UNSCREENED, with zero prompts and zero network reads.",
  },
  {
    key: "fetch",
    label: "fetching sources",
    kind: "network",
    reached: "unless-early-exit",
    detail:
      "Validators query OpenAlex, ORCID and GitHub independently, each from its own address, and record which answered.",
    exit: "Zero sources returning ends the screening as INSUFFICIENT. Nothing was searched, so nothing is claimed.",
  },
  {
    key: "accounting",
    label: "source accounting",
    kind: "deterministic",
    reached: "unless-early-exit",
    detail:
      "sources_checked and sources_failed are written down as facts. A source that did not answer is recorded, not smoothed over.",
    exit: null,
  },
  {
    key: "intersect",
    label: "set intersection",
    kind: "deterministic",
    reached: "unless-early-exit",
    detail:
      "Shared co-author ids, shared employers over overlapping date windows, shared repositories and shared organisations. Set operations on fetched records. The model is never asked whether a tie exists.",
    exit: null,
  },
  {
    key: "window",
    label: "COI window",
    kind: "deterministic",
    reached: "unless-early-exit",
    detail:
      "Every overlap is tested against the whole calendar years this round declared, closed at both ends. The window came from the operator at create_round and no clock is read here, because a lookback in months would put a boundary record in window for one validator and out of window for the next.",
    exit: "An overlap outside the window is not a tie, so the pair continues towards the clean exit with no prompt spent.",
  },
  {
    key: "gate2",
    label: "gate on failed sources",
    kind: "deterministic",
    reached: "unless-early-exit",
    detail:
      "No tie found, and a source that this pair needed did not answer. CLEAR is a claim that a search was run and found nothing, and on that axis no search was run.",
    exit: "INSUFFICIENT, never CLEAR. There is no path from a rate limit to a clean pair.",
  },
  {
    key: "clear",
    label: "clean exit",
    kind: "deterministic",
    reached: "unless-early-exit",
    detail:
      "No tie found and every source this pair needed answered. This is the overwhelming majority of pairs in a real round.",
    exit: "CLEAR, with zero prompts. The no inference used badge is earned here.",
  },
  {
    key: "identity",
    label: "identity link",
    kind: "inference",
    reached: "only-when-a-tie-exists",
    detail:
      "Reached only when an in-window intersection already found an overlap. Validators must agree on whether the handles denote one person and on the specific record that establishes it. Agreeing on the conclusion by different evidence is not agreement.",
    exit: "A named basis that is absent from the fetched records is rejected as [LLM_ERROR]. No weight changes.",
  },
  {
    key: "materiality",
    label: "materiality",
    kind: "inference",
    reached: "only-when-a-tie-exists",
    detail:
      "The prompt is handed the counted facts, which works, how many authors, how many months of overlap, how many commits, and asked only for the band. MATERIAL_UNCLEAR is told to it as an expected answer.",
    exit: null,
  },
  {
    key: "weight",
    label: "weight",
    kind: "deterministic",
    reached: "only-when-a-tie-exists",
    detail:
      "tie_basis is re-checked against the fetched records, then weight_bp is set in code. The model never returns a number.",
    exit: "CONFLICT at 0, or MATERIAL_UNCLEAR at 5000.",
  },
];

export const KIND_WORD: Record<ProgramStep["kind"], string> = {
  deterministic: "arithmetic",
  network: "network read",
  inference: "inference",
};

export const REACHED_WORD: Record<ProgramStep["reached"], string> = {
  always: "always runs",
  "unless-early-exit": "runs unless an earlier step ended it",
  "only-when-a-tie-exists": "runs only when a tie was already found",
};

/* ------------------------------------------------------------------------------------------
   The four endings that are not verdicts.

   These share one treatment in this system and that treatment is the hole, because the whole
   argument of the product is that an absence of evidence is not evidence of absence. A reviewer
   whose GitHub read hit a rate limit must not be able to read this as a judgement about them.
   ------------------------------------------------------------------------------------------ */

export type OutcomeClass = "verdict" | "expected" | "external" | "transient" | "llm-error";

export type OutcomeFacts = {
  tag: string;
  headline: string;
  body: string;
  /** What happened to the record and the bond. Always stated. */
  ledger: string;
  retry: boolean;
  /** Whether this is a refusal of your input, which is the only thing drawn in red. */
  refusal: boolean;
};

export const OUTCOMES: Record<Exclude<OutcomeClass, "verdict">, OutcomeFacts> = {
  expected: {
    tag: "[EXPECTED]",
    headline: "The contract refused this",
    body:
      "A check inside the contract rejected the call. The reason is below, in the contract's own words. This is a refusal of the input, not a failure of the network.",
    ledger: "Nothing was written and no bond was taken.",
    retry: false,
    refusal: true,
  },
  external: {
    tag: "[EXTERNAL]",
    headline: "A source was unreachable",
    body:
      "One of the evidence databases did not answer. Nothing was searched on that axis, so nothing was found and nothing was ruled out. This is not a finding about anybody.",
    ledger:
      "No weight changed. The failure is recorded in sources_failed, and the screening can be run again by anyone.",
    retry: true,
    refusal: false,
  },
  transient: {
    tag: "[TRANSIENT]",
    headline: "The validators did not resolve",
    body:
      "The network did not reach a resolution on this transaction. That is a state of the network, not a verdict, and it says nothing at all about the pair.",
    ledger: "No weight changed and nothing was written.",
    retry: true,
    refusal: false,
  },
  "llm-error": {
    tag: "[LLM_ERROR]",
    headline: "Validators could not agree, so nothing was recorded",
    body:
      "Either the identity link was not agreed on, or a named record came back that is absent from the fetched records. Both fail closed, on purpose: a downweight justified by evidence nobody can point at is not defensible to the reviewer it affects.",
    ledger: "No weight changed. Failing closed means no verdict, not a cautious verdict.",
    retry: true,
    refusal: false,
  },
};

/**
 * Sort an error string into the taxonomy.
 *
 * Order matters. A rate limit is checked before the generic network words, because a 403 from
 * GitHub is the ordinary case in this product rather than an unusual one, and misfiling it as a
 * transient network problem would lose the fact that a specific source is missing.
 */
export const classifyFailure = (message: string): Exclude<OutcomeClass, "verdict"> => {
  const text = message.toLowerCase();
  if (text.includes("[expected]")) return "expected";
  if (text.includes("[external]")) return "external";
  if (text.includes("[transient]")) return "transient";
  if (text.includes("[llm_error]") || text.includes("[llm error]")) return "llm-error";
  if (/\b(403|429)\b|rate limit|rate-limited|forbidden|unreachable|timed out|timeout/.test(text)) {
    return "external";
  }
  if (/undetermined|validators_timeout|leader_timeout|rotation|disagree/.test(text)) {
    return "transient";
  }
  if (/malformed|unparseable|could not agree|invalid json|absent from/.test(text)) {
    return "llm-error";
  }
  return "expected";
};
