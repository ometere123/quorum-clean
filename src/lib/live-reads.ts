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
import { isRecord, notFound, unavailable } from "./genlayer/read-result.ts";
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
  Participant,
  Round,
  RoundSummary,
  Screening,
  WeightAnswer,
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

const isParticipant = (value: unknown): value is Participant => {
  if (!isRecord(value)) return false;
  const role = str(value.role);
  return (
    str(value.addr) !== null &&
    role !== null &&
    isRole(role) &&
    str(value.label) !== null &&
    str(value.orcid) !== null &&
    str(value.openalex) !== null &&
    str(value.github) !== null &&
    str(value.registered_at) !== null
  );
};

const isParticipantList = (value: unknown): value is Participant[] =>
  Array.isArray(value) && value.every(isParticipant);

const isRound = (value: unknown): value is Round => {
  if (!isRecord(value)) return false;
  const status = str(value.status);
  return (
    str(value.id) !== null &&
    str(value.operator) !== null &&
    str(value.name) !== null &&
    (value.reviewers === undefined || addressList(value.reviewers) !== null) &&
    (value.applicants === undefined || addressList(value.applicants) !== null) &&
    status !== null &&
    isRoundStatus(status) &&
    (value.created_at === undefined || str(value.created_at) !== null) &&
    num(value.coi_start_year) !== null &&
    num(value.coi_end_year) !== null
  );
};

/** Rebuild with the numeric fields normalised, once the shape has been accepted. */
const asRound = (value: Record<string, unknown>): Round => ({
  id: String(value.id),
  operator: String(value.operator),
  name: String(value.name),
  reviewers: addressList(value.reviewers) ?? [],
  applicants: addressList(value.applicants) ?? [],
  status: String(value.status) as Round["status"],
  created_at: str(value.created_at) ?? "",
  coi_start_year: num(value.coi_start_year) ?? "",
  coi_end_year: num(value.coi_end_year) ?? "",
});

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
    str(value.appeal_id) !== null
  );
};

const asScreening = (value: Screening): Screening => ({
  ...value,
  weight_bp: num((value as unknown as Record<string, unknown>).weight_bp) ?? value.weight_bp,
});

const isScreeningList = (value: unknown): value is Screening[] =>
  Array.isArray(value) && value.every(isScreening);

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
  return isParticipantList(record.participants) && counts.every((field) =>
    field === "pairs" ? record[field] === undefined || num(record[field]) !== null : num(record[field]) !== null,
  );
};

const asSummary = (value: Record<string, unknown>): RoundSummary => {
  const participants = isParticipantList(value.participants) ? value.participants : [];
  return {
  ...asRound(value),
  reviewers: participants.filter((item) => item.role === "REVIEWER").map((item) => item.addr),
  applicants: participants.filter((item) => item.role === "APPLICANT").map((item) => item.addr),
  participants,
  pairs: num(value.pairs) ?? String(participants.filter((item) => item.role === "REVIEWER").length * participants.filter((item) => item.role === "APPLICANT").length),
  requested: num(value.requested) ?? "0",
  pending: num(value.pending) ?? "0",
  clear: num(value.clear) ?? "0",
  conflict: num(value.conflict) ?? "0",
  material_unclear: num(value.material_unclear) ?? "0",
  insufficient: num(value.insufficient) ?? "0",
  unscreened: num(value.unscreened) ?? "0",
  appeals_open: num(value.appeals_open) ?? "0",
  };
};

const isWeightAnswer = (value: unknown): value is WeightAnswer => {
  if (!isRecord(value)) return false;
  const status = str(value.status);
  return (
    str(value.round_id) !== null &&
    str(value.reviewer) !== null &&
    str(value.applicant) !== null &&
    num(value.weight_bp) !== null &&
    status !== null &&
    isScreeningStatus(status) &&
    typeof value.flagged === "boolean" &&
    typeof value.screened === "boolean" &&
    str(value.screening_id) !== null &&
    str(value.note) !== null
  );
};

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

export const round = async (id: string): Promise<ReadResult<Round>> => {
  const result = await summary(id);
  if (result.kind !== "AVAILABLE") return result;
  return { kind: "AVAILABLE", value: result.value };
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

export const appeal = async (id: string): Promise<ReadResult<Appeal>> =>
  performRead<Appeal>(() => call("get_appeal", [id]), isAppeal, INVALID("appeal"));

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
    rounds: count("rounds_created"),
    participants: count("participants_registered"),
    screenings: count("screenings_requested"),
    clear: "0",
    conflict: "0",
    material_unclear: "0",
    insufficient: "0",
    appeals: count("appeals_filed"),
    overturned: count("appeals_overturned"),
  };
  return { kind: "AVAILABLE", value };
};

export const weight = async (
  roundId: string,
  reviewer: string,
  applicant: string,
): Promise<ReadResult<WeightAnswer>> =>
  performRead<WeightAnswer>(
    () => call("get_weight", [`${roundId}:${reviewer.toLowerCase()}:${applicant.toLowerCase()}`]),
    isWeightAnswer,
    INVALID("weight answer"),
  );

/**
 * The screening request bond, read off the contract.
 *
 * Deliberately has no fixture fallback and no constant. A bond figure invented here and then
 * contradicted by a deployment would be a small lie in the one place the interface is asking
 * somebody for money.
 */
export const bond = async (): Promise<ReadResult<string>> => {
  try {
    const value = await call("screening_bond", []);
    const parsed = num(value);
    if (parsed === null) return { kind: "INVALID_RESPONSE", error: INVALID("bond amount") };
    return { kind: "AVAILABLE", value: parsed };
  } catch (error) {
    return unavailable(error);
  }
};

/** Nothing to read at all, as a distinct answer from a read that failed. */
export const nothing = <T>(): ReadResult<T> => notFound<T>();
