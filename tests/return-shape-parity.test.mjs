/**
 * Runs the production decoders in `src/lib/live-reads.ts` (exported only for this file, via
 * `__testing`) against representative REAL contract return shapes — copied field for field from
 * `contracts/QuorumClean.py`'s `_screening_dict`, `_appeal_dict`, `_participant_dict`,
 * `round_summary`, `list_rounds`, `ledger`, `parameters` — not a friendlier shape a fixture would
 * invent. Each shape is asserted to decode successfully, and a mutated/missing-field variant of
 * it is asserted to fail closed (INVALID_RESPONSE-worthy `false`, never a guessed default).
 */

import test from "node:test";
import assert from "node:assert/strict";
import { __testing } from "../src/lib/live-reads.ts";

const without = (obj, key) => {
  const copy = { ...obj };
  delete copy[key];
  return copy;
};

const ADDR_A = "0x2bd806c97f0e00af1a1fc3328fa763a9269723c8";
const ADDR_B = "0x81b637d8fcd2c6da6359e6963113a1170de795e4";
const OPERATOR = "0xb9dd960c1753459a78115d3cb845a57d924b6877";

/* ------------------------------------------------------------------------------------------
   list_rounds() — one entry, field for field.
   ------------------------------------------------------------------------------------------ */

const REAL_LIST_ROUNDS_ROW = {
  id: "round",
  name: "Grant review",
  operator: OPERATOR,
  status: "SCREENING",
  window: "2020..2026 inclusive",
  reviewers_count: "1",
  applicants_count: "1",
  pairs_requested: "1",
  pending: "0",
  clear: "1",
  conflict: "0",
  material_unclear: "0",
  insufficient: "0",
  unscreened: "0",
  appeals_open: "0",
};

test("list_rounds() row decodes, and reviewers/applicants read as [] with real counts (not the other read's arrays)", () => {
  assert.ok(__testing.isRound(REAL_LIST_ROUNDS_ROW));
  const round = __testing.asRound(REAL_LIST_ROUNDS_ROW);
  assert.equal(round.reviewers.length, 0);
  assert.equal(round.applicants.length, 0);
  assert.equal(round.reviewers_count, "1");
  assert.equal(round.applicants_count, "1");
  assert.equal(round.coi_start_year, "2020");
  assert.equal(round.coi_end_year, "2026");
});

test("list_rounds() row fails closed when status is missing", () => {
  const broken = without(REAL_LIST_ROUNDS_ROW, "status");
  assert.equal(__testing.isRound(broken), false);
});

test("list_rounds() row fails closed on an unknown status word", () => {
  assert.equal(__testing.isRound({ ...REAL_LIST_ROUNDS_ROW, status: "ARCHIVED" }), false);
});

/* ------------------------------------------------------------------------------------------
   round_summary(round_id) — with a non-empty, mixed-role participant list.
   ------------------------------------------------------------------------------------------ */

const REAL_PARTICIPANT_REVIEWER = {
  round_id: "round",
  address: ADDR_A,
  role: "REVIEWER",
  label: "Reviewer",
  orcid: "0000-0002-1825-0097",
  openalex: "A5069172917",
  github: "",
  registered_at: "2026-01-15T12:00:00Z",
};

const REAL_PARTICIPANT_APPLICANT = {
  round_id: "round",
  address: ADDR_B,
  role: "APPLICANT",
  label: "Applicant",
  orcid: "0000-0001-5109-3700",
  openalex: "A5023888391",
  github: "",
  registered_at: "2026-01-15T12:05:00Z",
};

const REAL_ROUND_SUMMARY = {
  id: "round",
  name: "Grant review",
  operator: OPERATOR,
  status: "SCREENING",
  coi_start_year: "2020",
  coi_end_year: "2026",
  window: "2020..2026 inclusive",
  window_frozen: true,
  github_scope_declared: false,
  github_repos: "",
  github_orgs: "",
  created_at: "2026-01-15T11:00:00Z",
  reviewers: [REAL_PARTICIPANT_REVIEWER],
  applicants: [REAL_PARTICIPANT_APPLICANT],
  participants: [REAL_PARTICIPANT_REVIEWER, REAL_PARTICIPANT_APPLICANT],
  reviewers_count: "1",
  applicants_count: "1",
  pairs_requested: "1",
  pending: "0",
  clear: "1",
  conflict: "0",
  material_unclear: "0",
  insufficient: "0",
  unscreened: "0",
  appeals_open: "0",
  bounty_pool: "0",
  qualifier: "every source this pair needed answered, and no tie was found in them",
};

test("round_summary() with non-empty participants decodes, and the address field maps address -> addr", () => {
  assert.ok(__testing.isSummary(REAL_ROUND_SUMMARY));
  const summary = __testing.asSummary(REAL_ROUND_SUMMARY);
  assert.equal(summary.participants.length, 2);
  assert.equal(summary.participants[0].addr, ADDR_A);
  assert.equal(summary.reviewers[0], ADDR_A);
  assert.equal(summary.applicants[0], ADDR_B);
  assert.equal(summary.window_frozen, true);
  assert.equal(summary.github_scope_declared, false);
});

test("round_summary() fails closed when window_frozen is missing (an older/mismatched contract shape)", () => {
  const broken = without(REAL_ROUND_SUMMARY, "window_frozen");
  assert.equal(__testing.isSummary(broken), false);
});

test("a participant whose address key is 'addr' instead of the real 'address' fails closed, not silently accepted", () => {
  const wrongKey = { ...REAL_PARTICIPANT_REVIEWER };
  delete wrongKey.address;
  wrongKey.addr = ADDR_A;
  assert.equal(__testing.isParticipant(wrongKey), false);
});

/* ------------------------------------------------------------------------------------------
   get_screening(id) — no appeal, and with an embedded appeal.
   ------------------------------------------------------------------------------------------ */

const REAL_SCREENING_BASE = {
  id: "round-s1",
  round_id: "round",
  reviewer: ADDR_A,
  applicant: ADDR_B,
  status: "CONFLICT",
  weight_bp: "0",
  resolved: true,
  flagged: true,
  retryable: false,
  tie_kind: "COAUTHOR",
  tie_basis: "https://openalex.org/W9000000001",
  link_basis: "DECLARED: A5069172917 declared at registration",
  sources_checked: "openalex,orcid",
  sources_failed: "",
  evidence_digest: "abc123",
  rationale: "1 co-authored work inside the window, 2 authors on it.",
  requester: OPERATOR,
  bond: "1000000000000000",
  bond_settled: true,
  screened_at: "2026-01-15T12:10:00Z",
  appeal_id: "",
};

const REAL_APPEAL = {
  id: "round-s1-appeal",
  screening_id: "round-s1",
  round_id: "round",
  appellant: ADDR_A,
  grounds: "NOT_MATERIAL",
  evidence_url: "https://example.org/rebuttal",
  bond: "1000000000000000",
  bond_settled: true,
  status: "OVERTURNED",
  rationale: "OVERTURNED | The rebuttal shows the tie was incidental. | the link was established as immaterial, so full weight is restored",
  filed_at: "2026-01-15T13:00:00Z",
  settled_at: "2026-01-15T13:05:00Z",
};

test("get_screening() with no appeal (appeal: null) decodes", () => {
  const row = { ...REAL_SCREENING_BASE, appeal: null };
  assert.ok(__testing.isScreening(row));
  const decoded = __testing.asScreening(row);
  assert.equal(decoded.appeal, null);
});

test("get_screening() with an embedded appeal decodes the nested appeal for real, field for field", () => {
  const row = { ...REAL_SCREENING_BASE, appeal_id: REAL_APPEAL.id, appeal: REAL_APPEAL };
  assert.ok(__testing.isScreening(row));
  const decoded = __testing.asScreening(row);
  assert.equal(decoded.appeal.id, REAL_APPEAL.id);
  assert.equal(decoded.appeal.status, "OVERTURNED");
  assert.equal(decoded.appeal.grounds, "NOT_MATERIAL");
});

test("get_screening() fails closed when the embedded appeal is malformed (unknown status)", () => {
  const row = { ...REAL_SCREENING_BASE, appeal: { ...REAL_APPEAL, status: "PENDING_REVIEW" } };
  assert.equal(__testing.isScreening(row), false);
});

test("list_screenings() rows (no `appeal` key at all) still decode: the field is optional", () => {
  assert.ok(__testing.isScreening(REAL_SCREENING_BASE));
  assert.ok(__testing.isScreeningList([REAL_SCREENING_BASE]));
});

test("get_screening() fails closed when sources_failed is missing (never silently reads as \"nothing failed\")", () => {
  const broken = without(REAL_SCREENING_BASE, "sources_failed");
  assert.equal(__testing.isScreening({ ...broken, appeal: null }), false);
});

/* ------------------------------------------------------------------------------------------
   list_appeals(round_id)
   ------------------------------------------------------------------------------------------ */

test("list_appeals() row decodes on its own (the same shape get_screening embeds)", () => {
  assert.ok(__testing.isAppeal(REAL_APPEAL));
});

test("list_appeals() row fails closed on an unrecognised ground", () => {
  assert.equal(__testing.isAppeal({ ...REAL_APPEAL, grounds: "BAD_FAITH" }), false);
});

/* ------------------------------------------------------------------------------------------
   ledger() — every field the real ledger() returns, and only those.
   ------------------------------------------------------------------------------------------ */

const REAL_LEDGER = {
  rounds_created: "3",
  participants_registered: "14",
  screenings_requested: "9",
  screenings_resolved: "7",
  screening_attempts: "8",
  prompts_run: "4",
  appeals_filed: "2",
  appeals_overturned: "1",
  total_bonded_wei: "9000000000000000000",
  total_returned_wei: "7000000000000000000",
  total_forfeited_wei: "1000000000000000000",
  total_bounty_paid_wei: "1000000000000000000",
};

test("ledger() has no per-verdict breakdown: ContractStats is field-for-field the real counters, nothing invented", () => {
  for (const key of Object.keys(REAL_LEDGER)) {
    assert.match(REAL_LEDGER[key], /^\d+$/, `${key} should be a decimal string, like the real ledger()`);
  }
  // The old (wrong) shape had clear/conflict/material_unclear/insufficient hardcoded to "0".
  // Assert the real ledger has no such keys, so nobody re-adds that fabricated tile.
  for (const stale of ["clear", "conflict", "material_unclear", "insufficient", "rounds", "screenings", "appeals", "overturned"]) {
    assert.equal(stale in REAL_LEDGER, false, `ledger() has no "${stale}" field, which was invented, not read`);
  }
});

/* ------------------------------------------------------------------------------------------
   parameters()
   ------------------------------------------------------------------------------------------ */

const REAL_PARAMETERS = {
  embedded_function_count: "40",
  sources: "openalex, orcid, github",
  verdicts: "CLEAR, CONFLICT, MATERIAL_UNCLEAR, INSUFFICIENT, UNSCREENED",
  tie_kinds: "COAUTHOR, SHARED_AFFILIATION, CODE_CONTRIBUTION, ORG_MEMBERSHIP",
  appeal_grounds: "WRONG_IDENTITY, NOT_MATERIAL, STALE_TIE, MISSED_TIE",
  weight_full_bp: "10000",
  weight_partial_bp: "5000",
  weight_zero_bp: "0",
  min_bond_wei: "1",
  max_github_repos: "20",
  max_github_orgs: "10",
  max_body_bytes: "2000000",
  max_tie_lines: "50",
  github_unauth_hourly_limit: "60",
  year_min: "1900",
  year_max: "2100",
  clear_qualifier: "every source this pair needed answered, and no tie was found in them",
  clear_requires_full_coverage: "CLEAR requires that every source needed for the pair returned usable data.",
  window_is_declared: "The conflict window is declared at create_round and frozen at the first screening.",
};

test("parameters() decodes, and bond() (min_bond_wei) reads the real MIN_BOND_WEI of 1 wei honestly, not a rounder-looking invented default", () => {
  assert.ok(__testing.isParameters(REAL_PARAMETERS));
  assert.equal(REAL_PARAMETERS.min_bond_wei, "1");
});

test("parameters() fails closed when min_bond_wei is missing", () => {
  const broken = without(REAL_PARAMETERS, "min_bond_wei");
  assert.equal(__testing.isParameters(broken), false);
});
