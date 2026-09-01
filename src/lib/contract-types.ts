/**
 * The shapes the contract returns, as the frontend consumes them.
 *
 * Every `u256` arrives as a decimal string and every `Address` as a `0x` string, because
 * that is what calldata decoding produces. Keeping them as strings here rather than
 * coercing at the boundary means a value that is too large for a JS number cannot be
 * quietly mangled on the way in.
 */

/** Consensus stages a write passes through, plus the retryable ones that are not failures. */
export type TxStage =
  | "UNINITIALIZED"
  | "PENDING"
  | "PROPOSING"
  | "COMMITTING"
  | "REVEALING"
  | "ACCEPTED"
  | "READY_TO_FINALIZE"
  | "APPEAL_COMMITTING"
  | "APPEAL_REVEALING"
  | "FINALIZED"
  | "UNDETERMINED"
  | "VALIDATORS_TIMEOUT"
  | "LEADER_TIMEOUT"
  | "CANCELED";

export type StoredTransaction = {
  hash: string;
  label: string;
  createdAt: string;
  status: TxStage;
  executionResult?: "SUCCESS" | "ROLLBACK" | "ERROR" | "UNKNOWN";
  executionError?: string;
};

/** Consensus stages in the order a write passes through them, for display. */
export const CONSENSUS_STAGES: readonly TxStage[] = [
  "PENDING",
  "PROPOSING",
  "COMMITTING",
  "REVEALING",
  "ACCEPTED",
  "FINALIZED",
];

/**
 * Stages that are not failures. A validator set that could not agree, or a leader that went
 * away, means the transaction did not resolve. It does not mean the screening found nothing,
 * and it must never be drawn like a verdict.
 */
export const RETRYABLE_STAGES: readonly TxStage[] = [
  "UNDETERMINED",
  "VALIDATORS_TIMEOUT",
  "LEADER_TIMEOUT",
];

export const TERMINAL_STAGES: readonly TxStage[] = ["FINALIZED", "CANCELED"];

/* ------------------------------------------------------------------------------------------
   Vocabularies. Each is the exact set of strings the contract stores, so a value that drifts
   is caught by a type guard at the read boundary rather than rendered as an empty cell.
   ------------------------------------------------------------------------------------------ */

export type Role = "REVIEWER" | "APPLICANT";

export type RoundStatus = "OPEN" | "SCREENING" | "LOCKED";

export type ScreeningStatus =
  | "PENDING"
  | "CLEAR"
  | "CONFLICT"
  | "MATERIAL_UNCLEAR"
  | "UNSCREENED"
  | "INSUFFICIENT";

export type TieKind =
  | "COAUTHOR"
  | "SHARED_AFFILIATION"
  | "CODE_CONTRIBUTION"
  | "ORG_MEMBERSHIP"
  | "NONE";

export type AppealGround = "WRONG_IDENTITY" | "NOT_MATERIAL" | "STALE_TIE" | "MISSED_TIE";

export type AppealStatus = "OPEN" | "UPHELD" | "OVERTURNED" | "UNCLEAR";

export const ROLES: readonly Role[] = ["REVIEWER", "APPLICANT"];
export const ROUND_STATUSES: readonly RoundStatus[] = ["OPEN", "SCREENING", "LOCKED"];
export const SCREENING_STATUSES: readonly ScreeningStatus[] = [
  "PENDING",
  "CLEAR",
  "CONFLICT",
  "MATERIAL_UNCLEAR",
  "UNSCREENED",
  "INSUFFICIENT",
];
export const APPEAL_GROUND_KEYS: readonly AppealGround[] = [
  "WRONG_IDENTITY",
  "NOT_MATERIAL",
  "STALE_TIE",
  "MISSED_TIE",
];
export const APPEAL_STATUSES: readonly AppealStatus[] = [
  "OPEN",
  "UPHELD",
  "OVERTURNED",
  "UNCLEAR",
];

export const isRole = (value: string): value is Role => (ROLES as readonly string[]).includes(value);

export const isRoundStatus = (value: string): value is RoundStatus =>
  (ROUND_STATUSES as readonly string[]).includes(value);

export const isScreeningStatus = (value: string): value is ScreeningStatus =>
  (SCREENING_STATUSES as readonly string[]).includes(value);

export const isAppealGround = (value: string): value is AppealGround =>
  (APPEAL_GROUND_KEYS as readonly string[]).includes(value);

export const isAppealStatus = (value: string): value is AppealStatus =>
  (APPEAL_STATUSES as readonly string[]).includes(value);

/* ------------------------------------------------------------------------------------------
   Records, field for field as the contract stores them.
   ------------------------------------------------------------------------------------------ */

export type Participant = {
  addr: string;
  role: Role;
  label: string;
  /** Declared handles. An empty string means the participant declared none for that source, */
  /** which is why a source can be unavailable for a pair without anything having failed. */
  orcid: string;
  openalex: string;
  github: string;
  registered_at: string;
};

export type Round = {
  id: string;
  operator: string;
  name: string;
  reviewers: string[];
  applicants: string[];
  status: RoundStatus;
  created_at: string;
  /** Whole calendar years, closed at both ends. Declared by the operator, never computed. */
  coi_start_year: string;
  coi_end_year: string;
};

export type Screening = {
  /** `round_id : reviewer : applicant`, assigned by the contract. */
  id: string;
  round_id: string;
  reviewer: string;
  applicant: string;
  status: ScreeningStatus;
  /** Basis points as a decimal string. 10000 is full weight, 0 is excluded. */
  weight_bp: string;
  tie_kind: TieKind;
  /** The specific record: a work id, an organisation with a date window, or a repository. */
  tie_basis: string;
  /** How the handles were linked across sources. Shown wherever a tie is asserted. */
  link_basis: string;
  /** Sources that actually returned data, as a delimited list. */
  sources_checked: string;
  /** Sources that did not. Recorded, and displayed on every screen that shows the verdict. */
  sources_failed: string;
  evidence_digest: string;
  rationale: string;
  screened_at: string;
  appeal_id: string;
};

export type Appeal = {
  id: string;
  screening_id: string;
  /** The reviewer or the applicant. Both have standing, for opposite reasons. */
  appellant: string;
  grounds: AppealGround;
  evidence_url: string;
  /** Wei as a decimal string. Exactly the screening bond. */
  bond: string;
  status: AppealStatus;
  rationale: string;
  settled_at: string;
};

/**
 * `round_summary(id)` returns the round plus its counts per verdict, including `UNSCREENED`.
 *
 * It also returns the participant records, because a coverage matrix cannot be drawn from
 * addresses alone: a cell is only a hole if nothing was found, and telling "no handle was ever
 * declared for this source" apart from "the source was checked" needs the declared handles.
 * One call rather than one call per participant, since a 20x100 panel is 120 participants.
 */
export type RoundSummary = {
  id: string;
  operator: string;
  name: string;
  status: RoundStatus;
  created_at: string;
  coi_start_year: string;
  coi_end_year: string;
  reviewers: string[];
  applicants: string[];
  participants: Participant[];
  /** reviewers x applicants. The denominator of coverage, counted in pairs, never a rate. */
  pairs: string;
  /** Pairs with a screening record of any status. `pairs` minus this is the pairs nobody asked about. */
  requested: string;
  pending: string;
  clear: string;
  conflict: string;
  material_unclear: string;
  insufficient: string;
  /** Screenings whose verdict is UNSCREENED, meaning no handle was declared to look up. */
  unscreened: string;
  appeals_open: string;
};

export type ContractStats = {
  rounds: string;
  participants: string;
  screenings: string;
  clear: string;
  conflict: string;
  material_unclear: string;
  insufficient: string;
  appeals: string;
  overturned: string;
};

/**
 * What `get_weight` answers with.
 *
 * A bare number would be a false economy on the integration surface. `CLEAR` and `UNSCREENED`
 * both carry 10000, so a caller receiving `10000` alone cannot tell a reviewer who was screened
 * and found clean from a reviewer nobody ever looked at. The status and the flag travel with
 * the number so that distinction survives the call.
 */
export type WeightAnswer = {
  round_id: string;
  reviewer: string;
  applicant: string;
  weight_bp: string;
  status: ScreeningStatus;
  /** True for everything except `CLEAR`. `UNSCREENED` is flagged at full weight. */
  flagged: boolean;
  /** False when no screening record exists for the pair. */
  screened: boolean;
  /** Empty when `screened` is false. */
  screening_id: string;
  note: string;
};

/* ------------------------------------------------------------------------------------------
   The weight table. This is the contract's entire externally meaningful output, so it is
   written once here and every screen reads it from this object.
   ------------------------------------------------------------------------------------------ */

export const FULL_WEIGHT_BP = 10000;
export const HALF_WEIGHT_BP = 5000;
export const NO_WEIGHT_BP = 0;

export type Mark = "fill" | "hole";

/** Which ink a status is drawn in. `void` means the ground shows through: no ink at all. */
export type Tone = "cleared" | "conflict" | "unclear" | "void";

export type ScreeningStatusFacts = {
  /** The word. Always shown, because colour alone is not an encoding. */
  word: string;
  /** The unit glyph. Repeated to show more, never enlarged. */
  glyph: string;
  /** Filled cell or a hole cut in the grid. */
  mark: Mark;
  tone: Tone;
  /** Basis points this status sets, or `null` where the status changes no weight. */
  weightBp: number | null;
  /** Whether the pair is flagged for the operator. `UNSCREENED` is flagged at full weight. */
  flagged: boolean;
  /** Whether the screening can be run again. */
  retryable: boolean;
  /** The qualifier that must travel inline with the word, so no verdict stands unqualified. */
  qualifier: string;
  /** One administrative sentence. Never accusatory, never about a person. */
  meaning: string;
};

export const SCREENING_STATUS: Record<ScreeningStatus, ScreeningStatusFacts> = {
  CLEAR: {
    word: "CLEAR",
    glyph: "■",
    mark: "fill",
    tone: "cleared",
    weightBp: FULL_WEIGHT_BP,
    flagged: false,
    retryable: false,
    qualifier: "every source this pair needed answered, and no tie was found in them",
    meaning:
      "Every source this pair needed returned records, and no link between the two declared identities appears in them, inside this round's declared window. Full weight. By gate 2 a CLEAR always has an empty sources_failed, so there is no such thing as a weak CLEAR.",
  },
  UNSCREENED: {
    word: "UNSCREENED",
    glyph: "␀",
    // A hole. No fill, no border, the ground shows through. Never a grey square and never a
    // zero, both of which would read as a result that was arrived at.
    mark: "hole",
    tone: "void",
    weightBp: FULL_WEIGHT_BP,
    flagged: true,
    retryable: true,
    qualifier: "never screened, so nothing is known either way",
    meaning:
      "No screening was ever run for this pair. Full weight, and flagged, because never looked at is not the same as looked at and clean.",
  },
  CONFLICT: {
    word: "CONFLICT",
    glyph: "▲",
    mark: "fill",
    tone: "conflict",
    weightBp: NO_WEIGHT_BP,
    flagged: true,
    retryable: false,
    qualifier: "a specific tie was found and is named",
    meaning:
      "A named record ties the two declared identities. The vote carries no weight in this round.",
  },
  MATERIAL_UNCLEAR: {
    word: "MATERIAL_UNCLEAR",
    glyph: "◆",
    mark: "fill",
    tone: "unclear",
    weightBp: HALF_WEIGHT_BP,
    flagged: true,
    retryable: false,
    qualifier: "a link exists, its bearing on this decision is not settled",
    meaning: "A link was found and its materiality was not resolved. Half weight.",
  },
  INSUFFICIENT: {
    word: "INSUFFICIENT",
    glyph: "↻",
    // Also a hole: an attempt that did not close. The dashed edge is the attempt.
    mark: "hole",
    tone: "void",
    weightBp: null,
    flagged: false,
    retryable: true,
    qualifier: "a source was unreachable, so no finding was reached",
    meaning:
      "One or more sources did not answer. No weight was changed and the screening can be run again.",
  },
  PENDING: {
    word: "PENDING",
    glyph: "◌",
    mark: "hole",
    tone: "void",
    weightBp: null,
    flagged: false,
    retryable: false,
    qualifier: "requested, not yet run",
    meaning: "The pair has been requested. No source has been read yet.",
  },
};

/** Statuses that are a finding about a pair. The rest are absences, and are drawn as holes. */
export const FINDING_STATUSES: readonly ScreeningStatus[] = [
  "CLEAR",
  "CONFLICT",
  "MATERIAL_UNCLEAR",
];

/**
 * Legend order for the coverage matrix. Findings first, in descending severity, then the two
 * kinds of nothing. `CLEAR` and `UNSCREENED` are deliberately not adjacent: they carry the same
 * weight and must never read as two variants of one idea.
 */
export const LEGEND_ORDER: readonly ScreeningStatus[] = [
  "CONFLICT",
  "CLEAR",
  "MATERIAL_UNCLEAR",
  "UNSCREENED",
  "INSUFFICIENT",
  "PENDING",
];

/** Plain words for a basis point figure. The number is always shown beside them. */
export const weightWord = (bp: number | null): string => {
  if (bp === null) return "no change to weight";
  if (bp >= FULL_WEIGHT_BP) return "full weight";
  if (bp === NO_WEIGHT_BP) return "no weight";
  if (bp === HALF_WEIGHT_BP) return "half weight";
  return "reduced weight";
};

/* ------------------------------------------------------------------------------------------
   Tie kinds. A conflict is only ever shown as the specific record behind it, so each kind
   carries the noun for that record.
   ------------------------------------------------------------------------------------------ */

export const TIE_KIND_TEXT: Record<TieKind, { word: string; record: string }> = {
  COAUTHOR: { word: "co-authorship", record: "the work or works both names appear on" },
  SHARED_AFFILIATION: {
    word: "shared affiliation",
    record: "the organisation and the overlapping dates",
  },
  CODE_CONTRIBUTION: { word: "code contribution", record: "the repository both accounts touched" },
  ORG_MEMBERSHIP: {
    word: "organisation membership",
    record: "the organisation whose public member list holds both accounts",
  },
  NONE: { word: "none recorded", record: "no record was found to name" },
};

/* ------------------------------------------------------------------------------------------
   Appeals. Two parties, opposite reasons, one procedure.
   ------------------------------------------------------------------------------------------ */

export type AppealGroundFacts = {
  word: string;
  /** Who this ground gives standing to. `MISSED_TIE` is the applicant's ground. */
  standing: Role;
  /** What the appellant is asserting. */
  claim: string;
  /** What a successful appeal would change. */
  effect: string;
};

export const APPEAL_GROUNDS: Record<AppealGround, AppealGroundFacts> = {
  WRONG_IDENTITY: {
    word: "WRONG_IDENTITY",
    standing: "REVIEWER",
    claim: "The handles were linked to the wrong person, so the record is not mine.",
    effect: "The tie is withdrawn and full weight is restored.",
  },
  NOT_MATERIAL: {
    word: "NOT_MATERIAL",
    standing: "REVIEWER",
    claim: "The record is mine and it does not bear on this decision.",
    effect: "The tie stands as a fact and stops reducing weight.",
  },
  STALE_TIE: {
    word: "STALE_TIE",
    standing: "REVIEWER",
    claim: "The record is mine, it is old, and the relationship has ended.",
    effect: "The tie is treated as expired and weight is restored.",
  },
  MISSED_TIE: {
    word: "MISSED_TIE",
    standing: "APPLICANT",
    claim: "A tie exists that the screening did not find, and here is the record.",
    effect: "The clear finding is replaced by the tie that was raised.",
  },
};

export type AppealDispositionFacts = {
  word: string;
  /** What happens to the screening. */
  outcome: string;
  /** What happens to the bond. */
  bond: string;
  /** Set when the adjudication cannot settle the ground either way. */
  setsStatus: ScreeningStatus | null;
};

export const APPEAL_DISPOSITIONS: Record<
  Exclude<AppealStatus, "OPEN">,
  AppealDispositionFacts
> = {
  UPHELD: {
    word: "UPHELD",
    outcome: "The screening stands as it was recorded.",
    bond: "The appellant bond goes to the round bounty pool.",
    setsStatus: null,
  },
  OVERTURNED: {
    word: "OVERTURNED",
    outcome: "The screening is replaced by the finding the appeal argued for.",
    bond: "The bond is returned, plus a share of the bounty pool.",
    setsStatus: null,
  },
  UNCLEAR: {
    word: "UNCLEAR",
    outcome: "The ground was neither established nor refuted. The pair becomes MATERIAL_UNCLEAR.",
    bond: "Both bonds are returned. A hard case is not penalised.",
    setsStatus: "MATERIAL_UNCLEAR",
  },
};

export const APPEAL_STATUS_WORD: Record<AppealStatus, string> = {
  OPEN: "OPEN",
  UPHELD: "UPHELD",
  OVERTURNED: "OVERTURNED",
  UNCLEAR: "UNCLEAR",
};

/* ------------------------------------------------------------------------------------------
   Round status. Locking is the only irreversible step in the product, and the only reason it
   exists is so a weight set cannot move underneath a vote that is already being counted.
   ------------------------------------------------------------------------------------------ */

export const ROUND_STATUS_TEXT: Record<RoundStatus, { word: string; meaning: string }> = {
  OPEN: {
    word: "OPEN",
    meaning: "Participants can still be registered and pairs can still be requested.",
  },
  SCREENING: {
    word: "SCREENING",
    meaning: "At least one pair has been requested. Weights are still moving.",
  },
  LOCKED: {
    word: "LOCKED",
    meaning: "Weights are frozen. No screening, appeal or adjudication can change them.",
  },
};

/**
 * A key for a reviewer and applicant pair, for maps and React keys on the client.
 *
 * Not the contract id. The contract assigns `Screening.id` itself and this must never be sent
 * to a method that expects one, because a guess at an id that does not exist would be read as
 * a record that is absent rather than as a mistake here.
 */
export const pairKey = (reviewer: string, applicant: string): string =>
  `${reviewer.toLowerCase()}|${applicant.toLowerCase()}`;

/** `u256` decimal strings, safely. A value too large to count is reported, never wrapped. */
export const parseCount = (raw: string): number | null => {
  if (!/^\d+$/.test(raw.trim())) return null;
  const value = Number(raw.trim());
  return Number.isSafeInteger(value) ? value : null;
};

/* ------------------------------------------------------------------------------------------
   The second axis: evidence sources.

   `sources_checked` and `sources_failed` are recorded facts on the screening, per section 7's
   source accounting. They are the other axis of the coverage matrix, and the reason the matrix
   can have holes in it at all: a pair is only a finding if the sources that pair needed
   answered. Everything below reads those two strings and nothing else, so no coverage claim on
   any screen can be stronger than what the contract wrote down.
   ------------------------------------------------------------------------------------------ */

export type SourceKey = "OPENALEX" | "ORCID" | "GITHUB";

export const SOURCE_KEYS: readonly SourceKey[] = ["OPENALEX", "ORCID", "GITHUB"];

export type SourceFacts = {
  key: SourceKey;
  /** Column head in the matrix. */
  word: string;
  /** The database, named. A row nobody can name is a row that should not be drawn. */
  origin: string;
  /** Which declared handle reaches it. Empty on both parties means the source is unreachable. */
  handle: "openalex" | "orcid" | "github";
  /** What an intersection on this axis can establish. */
  establishes: string;
  /** Why this source fails, in the common case, stated so a failure is never a surprise. */
  failureMode: string;
};

export const SOURCES: Record<SourceKey, SourceFacts> = {
  OPENALEX: {
    key: "OPENALEX",
    word: "OPENALEX",
    origin: "api.openalex.org, the open bibliographic index",
    handle: "openalex",
    establishes: "co-authorship on a named work",
    failureMode: "An author id that no longer resolves, or the index refusing a burst of reads.",
  },
  ORCID: {
    key: "ORCID",
    word: "ORCID",
    origin: "pub.orcid.org, the public researcher record",
    handle: "orcid",
    establishes: "shared affiliation over overlapping employment dates",
    failureMode:
      "Content negotiation returning XML where JSON was asked for, or a record set to private.",
  },
  GITHUB: {
    key: "GITHUB",
    word: "GITHUB",
    origin: "api.github.com, contributor and organisation member lists",
    handle: "github",
    establishes: "code contribution to the same repository, or membership of the same organisation",
    failureMode:
      "The unauthenticated rate limit is 60 requests an hour for one address, so 403 and 429 are the ordinary case and not the exotic one.",
  },
};

/**
 * What is known about one source for one pair. Four states, and only the first is a mark.
 *
 * The other three are all holes, and they are kept apart because they are different absences:
 * nobody declared a handle, the source was asked and did not answer, and the screening has not
 * run. Collapsing them would leave the operator unable to tell a round that needs a retry from a
 * round whose participants have no public footprint, and those call for opposite responses.
 */
export type SourceCoverageState = "ANSWERED" | "FAILED" | "NOT_DECLARED" | "NOT_ATTEMPTED";

export type SourceCoverageFacts = {
  word: string;
  /** Filled cell or a hole. Only `ANSWERED` is a fill. */
  mark: Mark;
  /** Which hole class, so the edge treatment is decided here and not in a component. */
  hole: "none" | "plain" | "attempted" | "waiting";
  glyph: string;
  meaning: string;
};

export const SOURCE_COVERAGE: Record<SourceCoverageState, SourceCoverageFacts> = {
  ANSWERED: {
    word: "answered",
    mark: "fill",
    hole: "none",
    glyph: "■",
    meaning: "The source returned records and the intersection ran against them.",
  },
  FAILED: {
    word: "did not answer",
    mark: "hole",
    hole: "attempted",
    glyph: "↻",
    meaning:
      "The source was asked and did not answer. Nothing was searched on this axis, so nothing was found or ruled out on it.",
  },
  NOT_DECLARED: {
    word: "no handle declared",
    mark: "hole",
    hole: "plain",
    glyph: "␀",
    meaning:
      "At least one of the two parties declared no identifier for this source, so there was nothing to look up.",
  },
  NOT_ATTEMPTED: {
    word: "not attempted",
    mark: "hole",
    hole: "waiting",
    glyph: "◌",
    meaning: "No screening has read this source for this pair yet.",
  },
};

/**
 * Read a delimited source list off a screening.
 *
 * Comma, semicolon, pipe and whitespace are all accepted, because the field is a string the
 * contract writes and a delimiter is not worth a revert. Unknown tokens are returned separately
 * rather than dropped: a source this frontend has never heard of that failed is still a failure,
 * and silently discarding it would manufacture coverage.
 */
export const parseSourceList = (
  raw: string,
): { known: SourceKey[]; unknown: string[] } => {
  const known: SourceKey[] = [];
  const unknown: string[] = [];
  for (const token of raw.split(/[,;|\s]+/)) {
    const trimmed = token.trim();
    if (trimmed.length === 0) continue;
    const upper = trimmed.toUpperCase();
    if ((SOURCE_KEYS as readonly string[]).includes(upper)) {
      const key = upper as SourceKey;
      if (!known.includes(key)) known.push(key);
    } else if (!unknown.includes(trimmed)) {
      unknown.push(trimmed);
    }
  }
  return { known, unknown };
};

export type PairSourceCoverage = {
  source: SourceFacts;
  state: SourceCoverageState;
  /** Whether each party declared a handle for this source. Both must, or there is nothing to ask. */
  reviewerDeclared: boolean;
  applicantDeclared: boolean;
};

const declaredHandle = (participant: Participant | undefined, source: SourceFacts): boolean => {
  if (!participant) return false;
  return participant[source.handle].trim().length > 0;
};

/**
 * The source axis for one pair.
 *
 * `sources_failed` wins over `sources_checked` when a source somehow appears in both, because a
 * partial read is not a read. Failing closed here is the same discipline as gate 2 in the
 * contract: the frontend must not be able to reach a cleaner reading than the contract did.
 */
export const pairSourceCoverage = (
  screening: Screening | undefined,
  reviewer: Participant | undefined,
  applicant: Participant | undefined,
): PairSourceCoverage[] =>
  SOURCE_KEYS.map((key) => {
    const source = SOURCES[key];
    const reviewerDeclared = declaredHandle(reviewer, source);
    const applicantDeclared = declaredHandle(applicant, source);
    const reachable = reviewerDeclared && applicantDeclared;

    let state: SourceCoverageState;
    if (!screening) {
      state = reachable ? "NOT_ATTEMPTED" : "NOT_DECLARED";
    } else if (parseSourceList(screening.sources_failed).known.includes(key)) {
      state = "FAILED";
    } else if (parseSourceList(screening.sources_checked).known.includes(key)) {
      state = "ANSWERED";
    } else if (!reachable) {
      state = "NOT_DECLARED";
    } else {
      state = "NOT_ATTEMPTED";
    }

    return { source, state, reviewerDeclared, applicantDeclared };
  });

/** Sources named in `sources_failed` that this frontend does not recognise. Never dropped. */
export const unrecognisedFailures = (screening: Screening | undefined): string[] =>
  screening ? parseSourceList(screening.sources_failed).unknown : [];

/* ------------------------------------------------------------------------------------------
   Identity linkage. Section 4 treats this as the hard step, so it gets its own vocabulary.
   ------------------------------------------------------------------------------------------ */

/**
 * How firmly the two sets of handles were tied to the same two people.
 *
 * `AMBIGUOUS` is a state of its own and it collapses into neither of its neighbours. An
 * ambiguous link cannot support a `CONFLICT`, because the tie may belong to a stranger, and it
 * cannot support a `CLEAR`, because the search may have run against the wrong person entirely.
 * Anything this frontend cannot parse becomes `UNSTATED`, which is treated exactly as harshly.
 */
export type LinkCertainty = "DECLARED" | "INFERRED" | "AMBIGUOUS" | "UNSTATED";

export type LinkCertaintyFacts = {
  word: string;
  glyph: string;
  mark: Mark;
  /** Whether an inference was spent. The transparency badge reads this. */
  usedInference: boolean;
  /** Whether a finding may rest on a link of this certainty. */
  supportsFinding: boolean;
  meaning: string;
  /** What the reader should do about it. */
  consequence: string;
};

/**
 * The prefix convention on `Screening.link_basis`.
 *
 * The contract writes the certainty, a colon, then the named record. Section 8's
 * `EQ_IDENTITY_LINK` already requires validators to agree on that record, so the string is
 * always present on an inferred link and the parse below has something to hold.
 */
export const LINK_BASIS_PREFIX: Record<Exclude<LinkCertainty, "UNSTATED">, string> = {
  DECLARED: "DECLARED",
  INFERRED: "INFERRED",
  AMBIGUOUS: "AMBIGUOUS",
};

export const LINK_CERTAINTY: Record<LinkCertainty, LinkCertaintyFacts> = {
  DECLARED: {
    word: "DECLARED",
    glyph: "■",
    mark: "fill",
    usedInference: false,
    supportsFinding: true,
    meaning:
      "One authoritative record carries both identifiers, so the link is a lookup rather than a judgement. The OpenAlex author record's own ORCID field is the usual case.",
    consequence: "No inference was used to link the identities.",
  },
  INFERRED: {
    word: "INFERRED",
    glyph: "◆",
    mark: "fill",
    usedInference: true,
    supportsFinding: true,
    meaning:
      "No single record ties these identifiers together, so validators resolved the link and had to agree on the specific record that establishes it.",
    consequence:
      "Agreement was on the named record, not merely on the conclusion. The record is shown beside this line.",
  },
  AMBIGUOUS: {
    word: "AMBIGUOUS",
    glyph: "␀",
    // A hole. An unresolved identity is an absence of knowledge, not a third verdict about a
    // person, and the moment it is drawn as a fill it starts to read as a finding.
    mark: "hole",
    usedInference: true,
    supportsFinding: false,
    meaning:
      "The sources hold more than one candidate for at least one identifier, and no record settles which. The two handles were neither shown to be one person nor shown to be two.",
    consequence:
      "No finding rests on this. A tie found across an ambiguous link is reported as unestablished, and an absence of ties across one is not a clean pair.",
  },
  UNSTATED: {
    word: "UNSTATED",
    glyph: "◌",
    mark: "hole",
    usedInference: false,
    supportsFinding: false,
    meaning: "The screening recorded no linkage basis that this interface can read.",
    consequence:
      "Treated as unresolved rather than as agreement. An unreadable basis is not a basis.",
  },
};

export type LinkBasis = {
  certainty: LinkCertainty;
  facts: LinkCertaintyFacts;
  /** The named record, exactly as the contract wrote it. Empty when there is none. */
  record: string;
  /** The raw field, kept so a dossier can always show what was actually stored. */
  raw: string;
};

export const readLinkBasis = (raw: string): LinkBasis => {
  const trimmed = raw.trim();
  for (const certainty of ["DECLARED", "INFERRED", "AMBIGUOUS"] as const) {
    const prefix = LINK_BASIS_PREFIX[certainty];
    if (trimmed.toUpperCase().startsWith(`${prefix}:`)) {
      return {
        certainty,
        facts: LINK_CERTAINTY[certainty],
        record: trimmed.slice(prefix.length + 1).trim(),
        raw: trimmed,
      };
    }
  }
  return {
    certainty: "UNSTATED",
    facts: LINK_CERTAINTY.UNSTATED,
    record: "",
    raw: trimmed,
  };
};

/* ------------------------------------------------------------------------------------------
   Row standing. The reason a matrix of mostly-clean cells cannot be read as a clean row.
   ------------------------------------------------------------------------------------------ */

/**
 * How a whole reviewer row stands.
 *
 * Worst case, always, and there is deliberately no word for "mostly". A reviewer with three
 * findings of `CLEAR` and one hole has not been cleared, so the row says `INCOMPLETE` and not
 * "3 of 4 clear", because a fraction invites the reader to round it up.
 */
export type RowStanding = "CONFLICT" | "REDUCED" | "INCOMPLETE" | "CLEARED";

export type RowStandingFacts = {
  word: string;
  tone: Tone;
  meaning: string;
};

export const ROW_STANDING: Record<RowStanding, RowStandingFacts> = {
  CONFLICT: {
    word: "TIE FOUND",
    tone: "conflict",
    meaning: "At least one pair in this row rests on a named record. That pair carries no weight.",
  },
  REDUCED: {
    word: "REDUCED",
    tone: "unclear",
    meaning: "A link was found on at least one pair and its bearing was not settled.",
  },
  INCOMPLETE: {
    word: "NOT CLEARED",
    tone: "void",
    meaning:
      "At least one pair in this row was never screened, is still pending, or ran against a source that did not answer. The row has not been cleared, whatever the other cells say.",
  },
  CLEARED: {
    word: "CLEAR, IN THE SOURCES CHECKED",
    tone: "cleared",
    meaning:
      "Every pair in this row was screened, every source those pairs needed answered, and no tie was found in them. It does not mean no tie exists.",
  },
};

/**
 * Roll a row up to its worst cell. Order matters and it is the only order that is honest:
 * a tie outranks a reduction, a reduction outranks a gap, and a gap outranks a clean pair.
 */
export const rowStanding = (statuses: readonly (ScreeningStatus | null)[]): RowStanding => {
  if (statuses.length === 0) return "INCOMPLETE";
  if (statuses.some((status) => status === "CONFLICT")) return "CONFLICT";
  if (statuses.some((status) => status === "MATERIAL_UNCLEAR")) return "REDUCED";
  if (statuses.some((status) => status === null || SCREENING_STATUS[status].mark === "hole")) {
    return "INCOMPLETE";
  }
  return "CLEARED";
};

/* ------------------------------------------------------------------------------------------
   Gate 2, as the interface has to render it.

   By gate 2 a `CLEAR` always has an empty `sources_failed`, so there is deliberately no visual
   treatment here for a weak or annotated `CLEAR`. It cannot exist, and building a style for it
   would invite one into being.

   The cells that need a marker are the opposite case. Finding a tie is monotone, so a `CONFLICT`
   or a `MATERIAL_UNCLEAR` still stands when a source failed: an axis nobody could read cannot
   un-find a tie another axis already produced. Those cells are correct on the axis that answered
   and blind on the one that did not, and the matrix says so rather than presenting them as a
   complete picture.
   ------------------------------------------------------------------------------------------ */

export type BlindFinding = {
  /** Sources that did not answer while the finding still stood. */
  blind: SourceKey[];
  /** Names in `sources_failed` this interface does not recognise. Shown, never dropped. */
  unrecognised: string[];
};

/**
 * A finding that stands on one axis while another axis went unread.
 *
 * Returns `null` for anything that is not a finding, and for a finding with nothing failed. A
 * `CLEAR` can never reach the non-null branch, because gate 2 turns that case into `INSUFFICIENT`
 * inside the contract; if one ever did, this still reports it rather than hiding it, because a
 * contract that had drifted from gate 2 is exactly the thing worth seeing.
 */
export const blindFinding = (screening: Screening | undefined): BlindFinding | null => {
  if (!screening) return null;
  if (!(FINDING_STATUSES as readonly string[]).includes(screening.status)) return null;
  const { known, unknown } = parseSourceList(screening.sources_failed);
  if (known.length === 0 && unknown.length === 0) return null;
  return { blind: known, unrecognised: unknown };
};

/** The sources an `INSUFFICIENT` cell is missing, which is the whole content of that cell. */
export const missingSources = (screening: Screening | undefined): SourceKey[] =>
  screening ? parseSourceList(screening.sources_failed).known : [];

/* ------------------------------------------------------------------------------------------
   The COI window.

   Declared by the operator at `create_round`, stored on the round, immutable from the first
   screening. The contract never chooses it, because a window derived from a lookback in months
   would depend on when each validator evaluated the transaction, and a paper on the boundary
   would then be in window for the leader and out of window for a validator a minute behind.

   Nothing in this file reads a clock. The suggestion offered by the create form is built from
   the browser's year and labelled as the operator's choice, which is a different thing from a
   default the contract computed.
   ------------------------------------------------------------------------------------------ */

export type CoiWindow = {
  startYear: number | null;
  endYear: number | null;
  /** Exactly what the round stored, so an unreadable value is shown and not swallowed. */
  raw: { start: string; end: string };
};

export const readCoiWindow = (round: {
  coi_start_year: string;
  coi_end_year: string;
}): CoiWindow => ({
  startYear: parseCount(round.coi_start_year),
  endYear: parseCount(round.coi_end_year),
  raw: { start: round.coi_start_year, end: round.coi_end_year },
});

/** The window in words. Both ends are included, and the phrasing says so every time. */
export const coiWindowText = (window: CoiWindow): string => {
  if (window.startYear === null || window.endYear === null) {
    return `unreadable window, stored as ${window.raw.start || "empty"} to ${window.raw.end || "empty"}`;
  }
  if (window.startYear === window.endYear) {
    return `${window.startYear} only, the whole calendar year`;
  }
  return `${window.startYear} to ${window.endYear}, both years included`;
};

/** Closed at both ends, which is the boundary the module's tests pin. */
export const yearInWindow = (year: number, window: CoiWindow): boolean => {
  if (window.startYear === null || window.endYear === null) return false;
  return year >= window.startYear && year <= window.endYear;
};

/**
 * Client-side validation of a declared window.
 *
 * Returns a sentence for the person filling the form, or `null` when the two years are usable. A
 * start after an end reverts `[EXPECTED]` on chain, so catching it here saves a signature rather
 * than replacing the contract's own check.
 */
export const coiWindowProblem = (startRaw: string, endRaw: string): string | null => {
  const start = startRaw.trim();
  const end = endRaw.trim();
  if (start.length === 0 || end.length === 0) {
    return "Both years are required. The window is this round's stated policy, so it cannot be left open.";
  }
  if (!/^\d{4}$/.test(start) || !/^\d{4}$/.test(end)) {
    return "Each year is four digits, as a whole calendar year. Months and dates are not part of the window.";
  }
  if (Number(start) > Number(end)) {
    return "The start year is after the end year. The contract reverts [EXPECTED] on this, so it is worth fixing before signing.";
  }
  return null;
};

/**
 * An overlap the window excluded.
 *
 * A `CLEAR` means no tie was found in window. When a `CLEAR` still carries a named record, the
 * only thing that record can be is an overlap this round's own policy put out of scope, since an
 * in-window overlap would have moved the verdict. Worth showing rather than hiding: it is the
 * operator's declared window doing its job, and it is what a `STALE_TIE` appeal argues about.
 */
export const outOfWindowRecord = (screening: Screening | undefined): string | null => {
  if (!screening) return null;
  if (screening.status !== "CLEAR") return null;
  const basis = screening.tie_basis.trim();
  return basis.length > 0 ? basis : null;
};
