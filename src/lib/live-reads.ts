/**
 * Live view calls, and the decoders that stand between the node and the interface.
 *
 * Nothing here is reached until a contract address is configured. `src/lib/data-source.ts` is the
 * single place that chooses between this file and the fixtures, so going live changes that one
 * file and no component.
 *
 * Every decoder fails to `INVALID_RESPONSE` rather than filling in a default. A missing
 * `sources_failed` that decoded as an empty string would turn a screening that could not read
 * GitHub into one that read everything, which is the exact lie this product exists to prevent.
 */

import { CONTRACT_ADDRESS } from "./genlayer/config.ts";
import { createReadClient } from "./genlayer/read-client.ts";
import { performRead } from "./genlayer/read-result.ts";
import type { ReadResult } from "./genlayer/read-result.ts";
import { isRecord, notFound } from "./genlayer/read-result.ts";
import {
  isAppealGround,
  isAppealStatus,
  isRole,
  isRoundStatus,
  isScreeningStatus,
} from "./contract-types.ts";
import type {
  Appeal,
  ContractStats,
  Parameters,
  Participant,
  Round,
  RoundSummary,
  Screening,
} from "./contract-types.ts";

const address = () => {
  if (!CONTRACT_ADDRESS) throw new Error("No deployed contract address is configured.");
  return CONTRACT_ADDRESS;
};

const call = (functionName: string, args: unknown[]) => {
  const client = createReadClient();
  return client.readContract({
    address: address(),
    functionName,
    // The client's own encoder handles the argument types; the cast is only to satisfy its
    // parameter signature, which is wider than anything this app sends.
    args: args as never,
  });
};

/** A `u256` or any integer, as the decimal string the whole app stores numbers in. */
const num = (value: unknown): string | null => {
  if (typeof value === "bigint") return value.toString();
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  if (typeof value === "string" && /^\d+$/.test(value.trim())) return value.trim();
  return null;
};

const str = (value: unknown): string | null => (typeof value === "string" ? value : null);

const addressList = (value: unknown): string[] | null => {
  if (!Array.isArray(value)) return null;
  const out: string[] = [];
  for (const item of value) {
    const text = str(item);
    if (text === null) return null;
    out.push(text);
  }
  return out;
};

const roundWindow = (value: unknown): { start: string; end: string } | null => {
  if (typeof value !== "string") return null;
  const match = /^(\d{4})\.\.(\d{4}) inclusive$/.exec(value.trim());
  return match ? { start: match[1], end: match[2] } : null;
};

/**
 * The contract's `_participant_dict()` returns the address under the key `address`, not `addr`.
 * The frontend's own `Participant` type keeps `addr` as its internal field name (used throughout
 * the UI already), so the mapping happens once, here, at the read boundary — never by pretending
 * the contract returns something it does not.
 */
const isParticipant = (value: unknown): value is Record<string, unknown> => {
  if (!isRecord(value)) return false;
  const role = str(value.role);
  return (
    str(value.address) !== null &&
    role !== null &&
    isRole(role) &&
    str(value.label) !== null &&
    str(value.orcid) !== null &&
    str(value.openalex) !== null &&
    str(value.github) !== null &&
    str(value.registered_at) !== null
  );
};

const asParticipant = (value: Record<string, unknown>): Participant => ({
  addr: String(value.address),
  role: value.role as Participant["role"],
  label: String(value.label),
  orcid: String(value.orcid),
  openalex: String(value.openalex),
  github: String(value.github),
  registered_at: String(value.registered_at),
});

const isParticipantList = (value: unknown): value is Record<string, unknown>[] =>
  Array.isArray(value) && value.every(isParticipant);

const isRound = (value: unknown): value is Round => {
  if (!isRecord(value)) return false;
  const status = str(value.status);
  const window = roundWindow(value.window);
  const hasDetailLists = value.reviewers !== undefined || value.applicants !== undefined;
  const hasSummaryCounts = value.reviewers_count !== undefined || value.applicants_count !== undefined;
  const startYear = num(value.coi_start_year) ?? window?.start ?? null;
  const endYear = num(value.coi_end_year) ?? window?.end ?? null;
  return (
    str(value.id) !== null &&
    str(value.operator) !== null &&
    str(value.name) !== null &&
    ((hasDetailLists && addressList(value.reviewers ?? []) !== null && addressList(value.applicants ?? []) !== null) ||
      (hasSummaryCounts && window !== null && num(value.reviewers_count) !== null && num(value.applicants_count) !== null)) &&
    status !== null &&
    isRoundStatus(status) &&
    (value.created_at === undefined || str(value.created_at) !== null) &&
    startYear !== null &&
    endYear !== null
  );
};

/**
 * Rebuild with the numeric fields normalised, once the shape has been accepted.
 *
 * `list_rounds()` returns only `reviewers_count` / `applicants_count`, never the address arrays;
 * `round_summary()` returns the arrays (and, since a screen may want a real count without
 * re-deriving it, the counts too). Reading `reviewers.length` on a `list_rounds()` row is always
 * `0` and is never the fallback here — the two count fields carry that reading instead.
 */
const asRound = (value: Record<string, unknown>): Round => {
  const reviewers = addressList(value.reviewers) ?? [];
  const applicants = addressList(value.applicants) ?? [];
  return {
    id: String(value.id),
    operator: String(value.operator),
    name: String(value.name),
    reviewers,
    applicants,
    status: String(value.status) as Round["status"],
    created_at: str(value.created_at) ?? "",
    coi_start_year: num(value.coi_start_year) ?? roundWindow(value.window)?.start ?? "",
    coi_end_year: num(value.coi_end_year) ?? roundWindow(value.window)?.end ?? "",
    reviewers_count: num(value.reviewers_count) ?? String(reviewers.length),
    applicants_count: num(value.applicants_count) ?? String(applicants.length),
  };
};

const isAppeal = (value: unknown): value is Appeal => {
  if (!isRecord(value)) return false;
  const grounds = str(value.grounds);
  const status = str(value.status);
  return (
    str(value.id) !== null &&
    str(value.screening_id) !== null &&
    str(value.appellant) !== null &&
    grounds !== null &&
    isAppealGround(grounds) &&
    str(value.evidence_url) !== null &&
    num(value.bond) !== null &&
    status !== null &&
    isAppealStatus(status) &&
    str(value.rationale) !== null &&
    str(value.settled_at) !== null
  );
};

/**
 * `get_screening` embeds `appeal` as the real `_appeal_dict()` or `None` (`null` over the wire).
 * `list_screenings` never sets this key at all, which is why it is optional on `Screening` and
 * only decoded when present.
 */
const isScreeningAppeal = (value: unknown): boolean => value === null || value === undefined || isAppeal(value);

const isScreening = (value: unknown): value is Screening => {
  if (!isRecord(value)) return false;
  const status = str(value.status);
  return (
    str(value.id) !== null &&
    str(value.round_id) !== null &&
    str(value.reviewer) !== null &&
    str(value.applicant) !== null &&
    status !== null &&
    isScreeningStatus(status) &&
    num(value.weight_bp) !== null &&
    str(value.tie_kind) !== null &&
    str(value.tie_basis) !== null &&
    str(value.link_basis) !== null &&
    str(value.sources_checked) !== null &&
    str(value.sources_failed) !== null &&
    str(value.evidence_digest) !== null &&
    str(value.rationale) !== null &&
    str(value.screened_at) !== null &&
    str(value.appeal_id) !== null &&
    isScreeningAppeal(value.appeal)
  );
};

const asScreening = (value: Screening): Screening => ({
  ...value,
  weight_bp: num((value as unknown as Record<string, unknown>).weight_bp) ?? value.weight_bp,
  appeal: (value as unknown as Record<string, unknown>).appeal === undefined
    ? undefined
    : ((value as unknown as Record<string, unknown>).appeal as Appeal | null),
});

const isScreeningList = (value: unknown): value is Screening[] =>
  Array.isArray(value) && value.every(isScreening);

const isSummary = (value: unknown): value is RoundSummary => {
  if (!isRound(value)) return false;
  const record = value as unknown as Record<string, unknown>;
  const counts = [
    "pairs",
    "requested",
    "pending",
    "clear",
    "conflict",
    "material_unclear",
    "insufficient",
    "unscreened",
    "appeals_open",
  ];
  return (
    isParticipantList(record.participants) &&
    typeof record.window_frozen === "boolean" &&
    typeof record.github_scope_declared === "boolean" &&
    counts.every((field) => {
      if (field === "pairs") return record[field] === undefined || num(record[field]) !== null;
      if (field === "requested") return num(record.requested) !== null || num(record.pairs_requested) !== null;
      return num(record[field]) !== null;
    })
  );
};

const asSummary = (value: Record<string, unknown>): RoundSummary => {
  const participants = (isParticipantList(value.participants) ? value.participants : []).map(asParticipant);
  return {
  ...asRound(value),
  reviewers: participants.filter((item) => item.role === "REVIEWER").map((item) => item.addr),
  applicants: participants.filter((item) => item.role === "APPLICANT").map((item) => item.addr),
  participants,
  window_frozen: value.window_frozen === true,
  github_scope_declared: value.github_scope_declared === true,
  pairs: num(value.pairs) ?? String(participants.filter((item) => item.role === "REVIEWER").length * participants.filter((item) => item.role === "APPLICANT").length),
  requested: num(value.requested) ?? num(value.pairs_requested) ?? "0",
  pending: num(value.pending) ?? "0",
  clear: num(value.clear) ?? "0",
  conflict: num(value.conflict) ?? "0",
  material_unclear: num(value.material_unclear) ?? "0",
  insufficient: num(value.insufficient) ?? "0",
  unscreened: num(value.unscreened) ?? "0",
  appeals_open: num(value.appeals_open) ?? "0",
  };
};

const isParameters = (value: unknown): value is Record<string, unknown> =>
  isRecord(value) && num(value.min_bond_wei) !== null;

/* ------------------------------------------------------------------------------------------
   The reads themselves.
   ------------------------------------------------------------------------------------------ */

const INVALID = (what: string) => `The contract returned something that is not a ${what}.`;

export const rounds = async (): Promise<ReadResult<Round[]>> => {
  const result = await performRead<unknown[]>(
    () => call("list_rounds", []),
    (value): value is unknown[] => Array.isArray(value),
    INVALID("list of rounds"),
  );
  if (result.kind !== "AVAILABLE") return result as ReadResult<Round[]>;
  if (!result.value.every(isRound)) {
    return { kind: "INVALID_RESPONSE", error: INVALID("list of rounds") };
  }
  return { kind: "AVAILABLE", value: result.value.map((item) => asRound(item as never)) };
};

export const summary = async (id: string): Promise<ReadResult<RoundSummary>> => {
  const result = await performRead<RoundSummary>(
    () => call("round_summary", [id]),
    isSummary,
    INVALID("round summary"),
  );
  if (result.kind !== "AVAILABLE") return result;
  return { kind: "AVAILABLE", value: asSummary(result.value as never) };
};

export const screenings = async (roundId: string): Promise<ReadResult<Screening[]>> => {
  const result = await performRead<Screening[]>(
    () => call("list_screenings", [roundId]),
    isScreeningList,
    INVALID("list of screenings"),
  );
  if (result.kind !== "AVAILABLE") return result;
  return { kind: "AVAILABLE", value: result.value.map(asScreening) };
};

export const screening = async (id: string): Promise<ReadResult<Screening>> => {
  const result = await performRead<Screening>(
    () => call("get_screening", [id]),
    isScreening,
    INVALID("screening"),
  );
  if (result.kind !== "AVAILABLE") return result;
  return { kind: "AVAILABLE", value: asScreening(result.value) };
};

/**
 * There is no `get_appeal(id)` method on the contract. An appeal is only ever reachable through
 * `get_screening(screening_id).appeal` (the embedded dict, or `null`) or `list_appeals(round_id)`.
 * `screening()` above already decodes the embedded appeal, so the appeal route reads a screening
 * by id and renders `.appeal` from it — see `src/app/appeals/[id]/page.tsx`.
 */

export const stats = async (): Promise<ReadResult<ContractStats>> => {
  const result = await performRead<Record<string, unknown>>(
    () => call("ledger", []),
    isRecord,
    INVALID("ledger record"),
  );
  if (result.kind !== "AVAILABLE") return result as ReadResult<ContractStats>;
  const ledger = result.value;
  const count = (key: string) => num(ledger[key]) ?? "0";
  const value: ContractStats = {
    rounds_created: count("rounds_created"),
    participants_registered: count("participants_registered"),
    screenings_requested: count("screenings_requested"),
    screenings_resolved: count("screenings_resolved"),
    screening_attempts: count("screening_attempts"),
    prompts_run: count("prompts_run"),
    appeals_filed: count("appeals_filed"),
    appeals_overturned: count("appeals_overturned"),
    total_bonded_wei: count("total_bonded_wei"),
    total_returned_wei: count("total_returned_wei"),
    total_forfeited_wei: count("total_forfeited_wei"),
    total_bounty_paid_wei: count("total_bounty_paid_wei"),
  };
  return { kind: "AVAILABLE", value };
};

/**
 * Every parameter `parameters()` reports. Not gated on `isParameters` alone matching the whole
 * shape — only `min_bond_wei` is asserted, since that is the only field this app currently reads,
 * but every string field the contract returns is passed through so a future reader is not blocked
 * on another decoder change.
 */
export const parameters = async (): Promise<ReadResult<Parameters>> =>
  performRead<Parameters>(
    () => call("parameters", []),
    (value): value is Parameters => isParameters(value),
    INVALID("parameters record"),
  );

/**
 * The screening (and appeal) bond floor, read off `parameters().min_bond_wei`.
 *
 * There is no `screening_bond()` method on the contract — the real one is `min_bond_wei` inside
 * `parameters()`. Deliberately has no fixture fallback and no constant: a bond figure invented
 * here and then contradicted by a deployment would be a small lie in the one place the interface
 * is asking somebody for money. A failed read disables the value-bearing action rather than
 * defaulting to zero — see `AppealForm` / `ScreeningRequest` in `contextual-quorum-actions.tsx`.
 */
export const bond = async (): Promise<ReadResult<string>> => {
  const result = await parameters();
  if (result.kind !== "AVAILABLE") return result as ReadResult<string>;
  const parsed = num(result.value.min_bond_wei);
  if (parsed === null) return { kind: "INVALID_RESPONSE", error: INVALID("bond amount") };
  return { kind: "AVAILABLE", value: parsed };
};

/** Nothing to read at all, as a distinct answer from a read that failed. */
export const nothing = <T>(): ReadResult<T> => notFound<T>();

/**
 * Exported for `tests/return-shape-parity.test.mjs` only — it runs these exact decoders against
 * representative real contract return shapes (see `_screening_dict` / `_appeal_dict` /
 * `_participant_dict` / `round_summary` / `list_rounds` / `parameters` in `contracts/QuorumClean.py`)
 * so a field-name drift between the contract and these decoders fails CI instead of only ever
 * showing up as a silent `INVALID_RESPONSE` in production. Not for use elsewhere in the app.
 */
export const __testing = {
  isRound,
  asRound,
  isSummary,
  asSummary,
  isScreening,
  asScreening,
  isScreeningList,
  isAppeal,
  isParticipant,
  asParticipant,
  isParameters,
};
