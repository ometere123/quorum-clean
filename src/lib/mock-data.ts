/**
 * Fixtures.
 *
 * Every read in `src/lib/data-source.ts` returns one of these until a contract address is set, so
 * the whole interface is explorable before a deployment exists. Shapes are field for field the
 * ones in section 6 of the PRD, which is what makes going live a change to one file.
 *
 * What the fixtures deliberately cover, because a fixture set that only shows the happy path is a
 * demo rather than a test of the design:
 *
 *   every screening status, including all four kinds of absence
 *   a CONFLICT standing on one axis while another axis failed, which gate 2 permits
 *   an INSUFFICIENT from a GitHub 403, which is the ordinary case at 60 requests an hour
 *   an INSUFFICIENT where nothing answered at all
 *   a reviewer who declared no handles, so every one of their pairs is UNSCREENED
 *   a reviewer who declared only a GitHub handle, so two axes are unreachable rather than failed
 *   an identity link the validators agreed was AMBIGUOUS, which establishes no finding
 *   a CLEAR carrying a record that this round's own COI window put out of scope
 *   pairs nobody ever requested, which are emptier than UNSCREENED and drawn that way
 *   a round with a fully cleared reviewer row, the only row that may say CLEAR
 *   a round with no screenings at all, which is what an operator most needs to see before locking
 *   all four appeal grounds, including MISSED_TIE raised by an applicant against a CLEAR
 *   all three appeal dispositions
 *
 * Labels are round codes rather than personal names, matching the risk table in section 12: this
 * contract stores handles and record identifiers, not names. Addresses are obviously fixtures.
 */

import type {
  Appeal,
  ContractStats,
  Participant,
  Round,
  RoundSummary,
  Screening,
} from "./contract-types.ts";

/** A fixture address. Recognisable as one on sight, which is the point. */
const addr = (seed: string): string => `0x${seed.padEnd(40, "0").slice(0, 40)}`;

const OPERATOR_GRANTS = addr("0ba1");
const OPERATOR_ETHICS = addr("0ba2");

/* ------------------------------------------------------------------------------------------
   Round 12. The round the matrix is drawn from.
   ------------------------------------------------------------------------------------------ */

const R12_REVIEWERS = ["a101", "a102", "a103", "a104", "a105"].map(addr);
const R12_APPLICANTS = ["b101", "b102", "b103", "b104", "b105", "b106"].map(addr);

const R12_PARTICIPANTS: Participant[] = [
  {
    addr: R12_REVIEWERS[0],
    role: "REVIEWER",
    label: "R-01",
    orcid: "0000-0002-1825-0097",
    openalex: "A5069172917",
    github: "dohernandez",
    registered_at: "2026-07-02T09:14:00Z",
  },
  {
    addr: R12_REVIEWERS[1],
    role: "REVIEWER",
    label: "R-02",
    orcid: "0000-0001-5109-3700",
    openalex: "A5023888391",
    github: "",
    registered_at: "2026-07-02T09:20:00Z",
  },
  {
    // No handles at all. Every pair on this row is UNSCREENED, at full weight and flagged.
    addr: R12_REVIEWERS[2],
    role: "REVIEWER",
    label: "R-03",
    orcid: "",
    openalex: "",
    github: "",
    registered_at: "2026-07-02T09:31:00Z",
  },
  {
    addr: R12_REVIEWERS[3],
    role: "REVIEWER",
    label: "R-04",
    orcid: "0000-0003-1613-5981",
    openalex: "A5044142581",
    github: "mriedmann",
    registered_at: "2026-07-02T10:02:00Z",
  },
  {
    // GitHub only. The other two axes are unreachable for this reviewer, which is not a failure.
    addr: R12_REVIEWERS[4],
    role: "REVIEWER",
    label: "R-05",
    orcid: "",
    openalex: "",
    github: "kestrelbuild",
    registered_at: "2026-07-03T08:44:00Z",
  },
  {
    addr: R12_APPLICANTS[0],
    role: "APPLICANT",
    label: "A-01",
    orcid: "0000-0002-7285-4406",
    openalex: "A5017898742",
    github: "aureliaops",
    registered_at: "2026-07-03T11:10:00Z",
  },
  {
    addr: R12_APPLICANTS[1],
    role: "APPLICANT",
    label: "A-02",
    orcid: "0000-0001-9884-1913",
    openalex: "A5001299710",
    github: "meridianlabs",
    registered_at: "2026-07-03T11:18:00Z",
  },
  {
    addr: R12_APPLICANTS[2],
    role: "APPLICANT",
    label: "A-03",
    orcid: "0000-0002-3355-7091",
    openalex: "A5033471998",
    github: "",
    registered_at: "2026-07-03T11:26:00Z",
  },
  {
    addr: R12_APPLICANTS[3],
    role: "APPLICANT",
    label: "A-04",
    orcid: "0000-0003-4820-1177",
    openalex: "A5028119004",
    github: "sextantworks",
    registered_at: "2026-07-04T09:03:00Z",
  },
  {
    addr: R12_APPLICANTS[4],
    role: "APPLICANT",
    label: "A-05",
    orcid: "",
    openalex: "A5091730244",
    github: "tidewaterco",
    registered_at: "2026-07-04T09:12:00Z",
  },
  {
    addr: R12_APPLICANTS[5],
    role: "APPLICANT",
    label: "A-06",
    orcid: "0000-0001-6739-0209",
    openalex: "A5060228812",
    github: "verdigrisdao",
    registered_at: "2026-07-04T09:20:00Z",
  },
];

const ROUND_12: Round = {
  id: "r-12",
  operator: OPERATOR_GRANTS,
  name: "Protocol Grants, cycle 12",
  reviewers: R12_REVIEWERS,
  applicants: R12_APPLICANTS,
  status: "SCREENING",
  created_at: "2026-07-02T08:00:00Z",
  coi_start_year: "2022",
  coi_end_year: "2026",
};

/* ------------------------------------------------------------------------------------------
   Round 11, locked and fully screened. Holds the one reviewer row that may say CLEAR.
   ------------------------------------------------------------------------------------------ */

const R11_REVIEWERS = ["a111", "a112"].map(addr);
const R11_APPLICANTS = ["b111", "b112", "b113"].map(addr);

const R11_PARTICIPANTS: Participant[] = [
  {
    addr: R11_REVIEWERS[0],
    role: "REVIEWER",
    label: "R-11",
    orcid: "0000-0002-0198-9218",
    openalex: "A5040007113",
    github: "cartwrightj",
    registered_at: "2026-05-11T10:00:00Z",
  },
  {
    addr: R11_REVIEWERS[1],
    role: "REVIEWER",
    label: "R-12",
    orcid: "0000-0001-7295-8330",
    openalex: "A5011992388",
    github: "sable-io",
    registered_at: "2026-05-11T10:06:00Z",
  },
  {
    addr: R11_APPLICANTS[0],
    role: "APPLICANT",
    label: "A-11",
    orcid: "0000-0003-9910-4472",
    openalex: "A5077391220",
    github: "orielgrid",
    registered_at: "2026-05-11T10:22:00Z",
  },
  {
    addr: R11_APPLICANTS[1],
    role: "APPLICANT",
    label: "A-12",
    orcid: "0000-0002-5540-1188",
    openalex: "A5002884401",
    github: "harrowsystems",
    registered_at: "2026-05-11T10:29:00Z",
  },
  {
    addr: R11_APPLICANTS[2],
    role: "APPLICANT",
    label: "A-13",
    orcid: "0000-0001-3388-7712",
    openalex: "A5019004557",
    github: "lanternfish",
    registered_at: "2026-05-11T10:35:00Z",
  },
];

const ROUND_11: Round = {
  id: "r-11",
  operator: OPERATOR_ETHICS,
  name: "Ethics board, spring intake",
  reviewers: R11_REVIEWERS,
  applicants: R11_APPLICANTS,
  status: "LOCKED",
  created_at: "2026-05-11T09:00:00Z",
  coi_start_year: "2021",
  coi_end_year: "2026",
};

/* ------------------------------------------------------------------------------------------
   Round 13, open and entirely unscreened. Twelve pairs, no records, every cell a hole.
   ------------------------------------------------------------------------------------------ */

const R13_REVIEWERS = ["a121", "a122", "a123"].map(addr);
const R13_APPLICANTS = ["b121", "b122", "b123", "b124"].map(addr);

const R13_PARTICIPANTS: Participant[] = [
  {
    addr: R13_REVIEWERS[0],
    role: "REVIEWER",
    label: "R-21",
    orcid: "0000-0002-8817-3300",
    openalex: "A5055120933",
    github: "quillfen",
    registered_at: "2026-08-19T13:40:00Z",
  },
  {
    addr: R13_REVIEWERS[1],
    role: "REVIEWER",
    label: "R-22",
    orcid: "",
    openalex: "A5088441027",
    github: "",
    registered_at: "2026-08-19T13:47:00Z",
  },
  {
    addr: R13_REVIEWERS[2],
    role: "REVIEWER",
    label: "R-23",
    orcid: "0000-0003-2277-8814",
    openalex: "",
    github: "brackenhaus",
    registered_at: "2026-08-20T08:11:00Z",
  },
  {
    addr: R13_APPLICANTS[0],
    role: "APPLICANT",
    label: "A-21",
    orcid: "0000-0001-4402-6690",
    openalex: "A5006612288",
    github: "peridotworks",
    registered_at: "2026-08-20T09:02:00Z",
  },
  {
    addr: R13_APPLICANTS[1],
    role: "APPLICANT",
    label: "A-22",
    orcid: "",
    openalex: "",
    github: "slateharbour",
    registered_at: "2026-08-20T09:09:00Z",
  },
  {
    addr: R13_APPLICANTS[2],
    role: "APPLICANT",
    label: "A-23",
    orcid: "0000-0002-9931-5514",
    openalex: "A5071230118",
    github: "",
    registered_at: "2026-08-20T09:15:00Z",
  },
  {
    addr: R13_APPLICANTS[3],
    role: "APPLICANT",
    label: "A-24",
    orcid: "0000-0003-6604-2231",
    openalex: "A5049880067",
    github: "tallowmoss",
    registered_at: "2026-08-20T09:21:00Z",
  },
];

const ROUND_13: Round = {
  id: "r-13",
  operator: OPERATOR_GRANTS,
  name: "Security bounties, cycle 3",
  reviewers: R13_REVIEWERS,
  applicants: R13_APPLICANTS,
  status: "OPEN",
  created_at: "2026-08-19T13:00:00Z",
  coi_start_year: "2024",
  coi_end_year: "2026",
};

export const MOCK_ROUNDS: Round[] = [ROUND_12, ROUND_11, ROUND_13];

export const MOCK_PARTICIPANTS: Record<string, Participant[]> = {
  "r-12": R12_PARTICIPANTS,
  "r-11": R11_PARTICIPANTS,
  "r-13": R13_PARTICIPANTS,
};

/* ------------------------------------------------------------------------------------------
   Screenings.

   Note what is absent as carefully as what is present. Four pairs in round 12 have no record at
   all, and round 13 has none, because a pair nobody asked about is a different and emptier fact
   than a pair that was looked at and could not be resolved.
   ------------------------------------------------------------------------------------------ */

const clear = (
  reviewer: string,
  applicant: string,
  sources: string,
  at: string,
  extra: Partial<Screening> = {},
): Screening => ({
  id: `r-12:${reviewer}:${applicant}`,
  round_id: "r-12",
  reviewer,
  applicant,
  status: "CLEAR",
  weight_bp: "10000",
  tie_kind: "NONE",
  tie_basis: "",
  link_basis: "DECLARED: handles matched on the OpenAlex author record's own ORCID field",
  sources_checked: sources,
  // Empty on every CLEAR, by gate 2. There is no such thing as a weak CLEAR to render.
  sources_failed: "",
  evidence_digest: "",
  rationale:
    "No overlap in the sources checked, inside the round's declared window. No prompt was issued.",
  screened_at: at,
  appeal_id: "",
  ...extra,
});

const MOCK_SCREENINGS_R12: Screening[] = [
  clear(R12_REVIEWERS[0], R12_APPLICANTS[0], "OPENALEX ORCID GITHUB", "2026-07-05T10:02:00Z", {
    evidence_digest: "9c1f4a02be77d5310c8e",
  }),
  clear(R12_REVIEWERS[0], R12_APPLICANTS[1], "OPENALEX ORCID GITHUB", "2026-07-05T10:04:00Z", {
    evidence_digest: "41b8ee0397ac26d5f188",
  }),
  {
    id: `r-12:${R12_REVIEWERS[0]}:${R12_APPLICANTS[2]}`,
    round_id: "r-12",
    reviewer: R12_REVIEWERS[0],
    applicant: R12_APPLICANTS[2],
    status: "CONFLICT",
    weight_bp: "0",
    tie_kind: "COAUTHOR",
    tie_basis: "W4392011884 (2024), W4285991230 (2023), 2 authors each",
    link_basis: "DECLARED: OpenAlex A5069172917 carries ORCID 0000-0002-1825-0097",
    sources_checked: "OPENALEX ORCID",
    sources_failed: "",
    evidence_digest: "b70cc4a1d9ff08215e33",
    rationale:
      "2 co-authored works inside the window, 2 authors on each. Both work ids appear in the fetched OpenAlex records.",
    screened_at: "2026-07-05T10:09:00Z",
    appeal_id: "ap-1",
  },
  clear(R12_REVIEWERS[0], R12_APPLICANTS[3], "OPENALEX ORCID GITHUB", "2026-07-05T10:12:00Z", {
    evidence_digest: "2ad9107fbc4e8831a075",
  }),
  {
    // The ordinary case. 60 unauthenticated requests an hour is not much of a budget.
    id: `r-12:${R12_REVIEWERS[0]}:${R12_APPLICANTS[4]}`,
    round_id: "r-12",
    reviewer: R12_REVIEWERS[0],
    applicant: R12_APPLICANTS[4],
    status: "INSUFFICIENT",
    weight_bp: "10000",
    tie_kind: "NONE",
    tie_basis: "",
    link_basis: "",
    sources_checked: "OPENALEX",
    sources_failed: "GITHUB",
    evidence_digest: "",
    rationale:
      "api.github.com answered 403, rate limited. No tie was found on the axes that answered, so gate 2 forbids CLEAR. No weight changed.",
    screened_at: "2026-07-05T10:15:00Z",
    appeal_id: "",
  },
  clear(R12_REVIEWERS[0], R12_APPLICANTS[5], "OPENALEX ORCID GITHUB", "2026-07-05T10:18:00Z", {
    evidence_digest: "5518c0aa2e3f9d740b61",
  }),

  clear(R12_REVIEWERS[1], R12_APPLICANTS[0], "OPENALEX ORCID", "2026-07-05T11:01:00Z", {
    id: `r-12:${R12_REVIEWERS[1]}:${R12_APPLICANTS[0]}`,
    reviewer: R12_REVIEWERS[1],
    applicant: R12_APPLICANTS[0],
    evidence_digest: "cc02b8419e770a3d1145",
    rationale:
      "No overlap on the two axes both parties declared. Neither party's GitHub handle was declared on both sides, so that axis was never reachable and nothing on it failed.",
  }),
  {
    id: `r-12:${R12_REVIEWERS[1]}:${R12_APPLICANTS[1]}`,
    round_id: "r-12",
    reviewer: R12_REVIEWERS[1],
    applicant: R12_APPLICANTS[1],
    status: "MATERIAL_UNCLEAR",
    weight_bp: "5000",
    tie_kind: "COAUTHOR",
    tie_basis: "W4319922017 (2023), 41 authors",
    link_basis: "DECLARED: OpenAlex A5023888391 carries ORCID 0000-0001-5109-3700",
    sources_checked: "OPENALEX ORCID",
    sources_failed: "",
    evidence_digest: "e91a4470bb2c85d30f19",
    rationale:
      "1 co-authored work inside the window, 41 authors on it. Validators agreed the band was unclear rather than settling it either way.",
    screened_at: "2026-07-05T11:06:00Z",
    appeal_id: "ap-2",
  },
  clear(R12_REVIEWERS[1], R12_APPLICANTS[2], "OPENALEX ORCID", "2026-07-05T11:09:00Z", {
    id: `r-12:${R12_REVIEWERS[1]}:${R12_APPLICANTS[2]}`,
    reviewer: R12_REVIEWERS[1],
    applicant: R12_APPLICANTS[2],
    evidence_digest: "77dd10bb4e9f2a680c53",
  }),
  clear(R12_REVIEWERS[1], R12_APPLICANTS[3], "OPENALEX ORCID", "2026-07-05T11:13:00Z", {
    id: `r-12:${R12_REVIEWERS[1]}:${R12_APPLICANTS[3]}`,
    reviewer: R12_REVIEWERS[1],
    applicant: R12_APPLICANTS[3],
    evidence_digest: "3b4e88170ac9dd25f602",
  }),
  clear(R12_REVIEWERS[1], R12_APPLICANTS[4], "OPENALEX", "2026-07-05T11:17:00Z", {
    id: `r-12:${R12_REVIEWERS[1]}:${R12_APPLICANTS[4]}`,
    reviewer: R12_REVIEWERS[1],
    applicant: R12_APPLICANTS[4],
    evidence_digest: "1f0cc3a8b74e2059dd81",
    rationale:
      "One axis was reachable and it answered. The applicant declared no ORCID and the reviewer declared no GitHub handle, so neither of those axes could be asked. Nothing failed.",
  }),
  // r-12 : R-02 : A-06 has no record. Nobody requested it.

  ...R12_APPLICANTS.slice(0, 4).map(
    (applicant, index): Screening => ({
      id: `r-12:${R12_REVIEWERS[2]}:${applicant}`,
      round_id: "r-12",
      reviewer: R12_REVIEWERS[2],
      applicant,
      status: "UNSCREENED",
      weight_bp: "10000",
      tie_kind: "NONE",
      tie_basis: "",
      link_basis: "",
      sources_checked: "",
      sources_failed: "",
      evidence_digest: "",
      rationale:
        "The reviewer declared no identifier for any source, so there was nothing to look up. Zero network reads and zero prompts. Full weight, and flagged, because nobody looked.",
      screened_at: `2026-07-05T12:0${index}:00Z`,
      appeal_id: "",
    }),
  ),
  // r-12 : R-03 : A-05 and A-06 have no record either.

  {
    // A finding that stands on the axis that answered while another axis went unread.
    id: `r-12:${R12_REVIEWERS[3]}:${R12_APPLICANTS[0]}`,
    round_id: "r-12",
    reviewer: R12_REVIEWERS[3],
    applicant: R12_APPLICANTS[0],
    status: "CONFLICT",
    weight_bp: "0",
    tie_kind: "SHARED_AFFILIATION",
    tie_basis: "Institut Fourier, overlapping 2022-03 to 2024-08, 30 months",
    link_basis: "DECLARED: both employments read from pub.orcid.org records",
    sources_checked: "OPENALEX ORCID",
    sources_failed: "GITHUB",
    evidence_digest: "6604ab19cc37e0d5f281",
    rationale:
      "Employment windows overlap by 30 months inside the round's window, from the two ORCID records. GitHub answered 429 and was not read, which cannot un-find a tie another axis already produced.",
    screened_at: "2026-07-06T09:04:00Z",
    appeal_id: "ap-5",
  },
  clear(R12_REVIEWERS[3], R12_APPLICANTS[1], "OPENALEX ORCID GITHUB", "2026-07-06T09:08:00Z", {
    id: `r-12:${R12_REVIEWERS[3]}:${R12_APPLICANTS[1]}`,
    reviewer: R12_REVIEWERS[3],
    applicant: R12_APPLICANTS[1],
    evidence_digest: "0a97ff2b1e4c8830d557",
  }),
  // r-12 : R-04 : A-03 has no record.
  {
    id: `r-12:${R12_REVIEWERS[3]}:${R12_APPLICANTS[3]}`,
    round_id: "r-12",
    reviewer: R12_REVIEWERS[3],
    applicant: R12_APPLICANTS[3],
    status: "PENDING",
    weight_bp: "10000",
    tie_kind: "NONE",
    tie_basis: "",
    link_basis: "",
    sources_checked: "",
    sources_failed: "",
    evidence_digest: "",
    rationale: "",
    screened_at: "",
    appeal_id: "",
  },
  {
    // The identity was neither established nor ruled out. No finding rests on this.
    id: `r-12:${R12_REVIEWERS[3]}:${R12_APPLICANTS[4]}`,
    round_id: "r-12",
    reviewer: R12_REVIEWERS[3],
    applicant: R12_APPLICANTS[4],
    status: "MATERIAL_UNCLEAR",
    weight_bp: "5000",
    tie_kind: "CODE_CONTRIBUTION",
    tie_basis: "tidewaterco/estuary, 14 commits, rank 4 of 22",
    link_basis:
      "AMBIGUOUS: two OpenAlex authors carry the surname on the commit trailer and no record ties either to github.com/mriedmann",
    sources_checked: "OPENALEX GITHUB",
    sources_failed: "",
    evidence_digest: "d4471f00ba98c2e63510",
    rationale:
      "A contribution overlap exists in the fetched records. Validators agreed the GitHub account could not be tied to either candidate identity, so the tie was not attributed. Half weight and flagged, appealable on WRONG_IDENTITY.",
    screened_at: "2026-07-06T09:22:00Z",
    appeal_id: "",
  },
  clear(R12_REVIEWERS[3], R12_APPLICANTS[5], "OPENALEX ORCID GITHUB", "2026-07-06T09:26:00Z", {
    id: `r-12:${R12_REVIEWERS[3]}:${R12_APPLICANTS[5]}`,
    reviewer: R12_REVIEWERS[3],
    applicant: R12_APPLICANTS[5],
    evidence_digest: "8812cc03a4be7f10d629",
  }),

  clear(R12_REVIEWERS[4], R12_APPLICANTS[0], "GITHUB", "2026-07-06T14:01:00Z", {
    id: `r-12:${R12_REVIEWERS[4]}:${R12_APPLICANTS[0]}`,
    reviewer: R12_REVIEWERS[4],
    applicant: R12_APPLICANTS[0],
    tie_kind: "NONE",
    // A CLEAR that still names a record. The only thing that record can be is an overlap this
    // round's own window excluded, since an in-window overlap would have moved the verdict.
    tie_basis: "aureliaops/lambdaframe, 3 commits, 2019, outside the 2022 to 2026 window",
    link_basis: "DECLARED: both GitHub logins read from the contributor list",
    evidence_digest: "aa0b3391c74f28d5e017",
    rationale:
      "One overlap was found and it falls outside the years this round declared, so it is not a tie here. No prompt was issued. The record is shown because the window is the operator's own policy and a reader should see it working.",
    appeal_id: "ap-3",
  }),
  {
    id: `r-12:${R12_REVIEWERS[4]}:${R12_APPLICANTS[1]}`,
    round_id: "r-12",
    reviewer: R12_REVIEWERS[4],
    applicant: R12_APPLICANTS[1],
    status: "CONFLICT",
    weight_bp: "0",
    tie_kind: "CODE_CONTRIBUTION",
    tie_basis: "meridianlabs/quorum-core, 218 commits, rank 2 of 34, 2024 to 2026",
    link_basis: "DECLARED: both GitHub logins read from the contributor list",
    sources_checked: "GITHUB",
    sources_failed: "",
    evidence_digest: "f109bb27ac4e0d8351a2",
    rationale:
      "Second ranked contributor to the applicant's repository inside the window. Top-N is a comparison on fetched counts, not an opinion.",
    screened_at: "2026-07-06T14:07:00Z",
    appeal_id: "",
  },
  {
    id: `r-12:${R12_REVIEWERS[4]}:${R12_APPLICANTS[2]}`,
    round_id: "r-12",
    reviewer: R12_REVIEWERS[4],
    applicant: R12_APPLICANTS[2],
    status: "UNSCREENED",
    weight_bp: "10000",
    tie_kind: "NONE",
    tie_basis: "",
    link_basis: "",
    sources_checked: "",
    sources_failed: "",
    evidence_digest: "",
    rationale:
      "The reviewer declared only a GitHub handle and the applicant declared none, so no axis had an identifier on both sides. Nothing to look up, zero prompts, full weight, flagged.",
    screened_at: "2026-07-06T14:10:00Z",
    appeal_id: "",
  },
  {
    id: `r-12:${R12_REVIEWERS[4]}:${R12_APPLICANTS[3]}`,
    round_id: "r-12",
    reviewer: R12_REVIEWERS[4],
    applicant: R12_APPLICANTS[3],
    status: "INSUFFICIENT",
    weight_bp: "10000",
    tie_kind: "NONE",
    tie_basis: "",
    link_basis: "",
    sources_checked: "",
    sources_failed: "GITHUB",
    evidence_digest: "",
    rationale:
      "The only reachable axis did not answer. api.github.com answered 403 twice, rate limited. Nothing was searched, so nothing is claimed. No weight changed.",
    screened_at: "2026-07-06T14:13:00Z",
    appeal_id: "",
  },
  clear(R12_REVIEWERS[4], R12_APPLICANTS[4], "GITHUB", "2026-07-06T14:16:00Z", {
    id: `r-12:${R12_REVIEWERS[4]}:${R12_APPLICANTS[4]}`,
    reviewer: R12_REVIEWERS[4],
    applicant: R12_APPLICANTS[4],
    link_basis: "DECLARED: both GitHub logins read from the contributor list",
    evidence_digest: "31bb9007ce4a2f85d013",
  }),
  {
    id: `r-12:${R12_REVIEWERS[4]}:${R12_APPLICANTS[5]}`,
    round_id: "r-12",
    reviewer: R12_REVIEWERS[4],
    applicant: R12_APPLICANTS[5],
    status: "CONFLICT",
    weight_bp: "0",
    tie_kind: "ORG_MEMBERSHIP",
    tie_basis: "github.com/orgs/verdigrisdao, both accounts on the public member list",
    link_basis: "DECLARED: both GitHub logins read from the organisation member list",
    sources_checked: "GITHUB",
    sources_failed: "",
    evidence_digest: "7a20dd18bb4c0e9351f6",
    rationale:
      "Both declared accounts appear on the same public organisation member list, read inside the window.",
    screened_at: "2026-07-06T14:20:00Z",
    appeal_id: "",
  },
];

const MOCK_SCREENINGS_R11: Screening[] = [
  {
    id: `r-11:${R11_REVIEWERS[0]}:${R11_APPLICANTS[0]}`,
    round_id: "r-11",
    reviewer: R11_REVIEWERS[0],
    applicant: R11_APPLICANTS[0],
    status: "CLEAR",
    weight_bp: "10000",
    tie_kind: "NONE",
    tie_basis: "Harrow Systems, employment ended 2019, outside the 2021 to 2026 window",
    link_basis: "DECLARED: both employments read from pub.orcid.org records",
    sources_checked: "OPENALEX ORCID GITHUB",
    sources_failed: "",
    evidence_digest: "0b7714aa39cc2e08d541",
    rationale:
      "Recorded CONFLICT on a shared affiliation, then overturned on appeal ap-4 as stale against this round's declared window. Full weight restored.",
    screened_at: "2026-05-19T15:40:00Z",
    appeal_id: "ap-4",
  },
  {
    id: `r-11:${R11_REVIEWERS[0]}:${R11_APPLICANTS[1]}`,
    round_id: "r-11",
    reviewer: R11_REVIEWERS[0],
    applicant: R11_APPLICANTS[1],
    status: "CLEAR",
    weight_bp: "10000",
    tie_kind: "NONE",
    tie_basis: "",
    link_basis: "DECLARED: handles matched on the OpenAlex author record's own ORCID field",
    sources_checked: "OPENALEX ORCID GITHUB",
    sources_failed: "",
    evidence_digest: "44c1900bae7f2d3851c0",
    rationale: "No overlap in the sources checked, inside the round's declared window.",
    screened_at: "2026-05-13T09:02:00Z",
    appeal_id: "",
  },
  {
    id: `r-11:${R11_REVIEWERS[0]}:${R11_APPLICANTS[2]}`,
    round_id: "r-11",
    reviewer: R11_REVIEWERS[0],
    applicant: R11_APPLICANTS[2],
    status: "CLEAR",
    weight_bp: "10000",
    tie_kind: "NONE",
    tie_basis: "",
    link_basis: "DECLARED: handles matched on the OpenAlex author record's own ORCID field",
    sources_checked: "OPENALEX ORCID GITHUB",
    sources_failed: "",
    evidence_digest: "9e30cc11ba784f0d2513",
    rationale: "No overlap in the sources checked, inside the round's declared window.",
    screened_at: "2026-05-13T09:06:00Z",
    appeal_id: "",
  },
  {
    id: `r-11:${R11_REVIEWERS[1]}:${R11_APPLICANTS[0]}`,
    round_id: "r-11",
    reviewer: R11_REVIEWERS[1],
    applicant: R11_APPLICANTS[0],
    status: "MATERIAL_UNCLEAR",
    weight_bp: "5000",
    tie_kind: "COAUTHOR",
    tie_basis: "W4288117702 (2022), 12 authors",
    link_basis: "INFERRED: github.com/sable-io tied to ORCID 0000-0001-7295-8330 by W4288117702",
    sources_checked: "OPENALEX ORCID GITHUB",
    sources_failed: "",
    evidence_digest: "22ba4407cc19f0d8e356",
    rationale:
      "Appealed on NOT_MATERIAL and adjudicated UNCLEAR. The ground was neither established nor refuted, so the pair sits at half weight and both bonds were returned.",
    screened_at: "2026-05-20T11:18:00Z",
    appeal_id: "ap-6",
  },
  {
    id: `r-11:${R11_REVIEWERS[1]}:${R11_APPLICANTS[1]}`,
    round_id: "r-11",
    reviewer: R11_REVIEWERS[1],
    applicant: R11_APPLICANTS[1],
    status: "CLEAR",
    weight_bp: "10000",
    tie_kind: "NONE",
    tie_basis: "",
    link_basis: "DECLARED: handles matched on the OpenAlex author record's own ORCID field",
    sources_checked: "OPENALEX ORCID GITHUB",
    sources_failed: "",
    evidence_digest: "5f0088bb1c4a2ed37019",
    rationale: "No overlap in the sources checked, inside the round's declared window.",
    screened_at: "2026-05-13T09:11:00Z",
    appeal_id: "",
  },
  {
    id: `r-11:${R11_REVIEWERS[1]}:${R11_APPLICANTS[2]}`,
    round_id: "r-11",
    reviewer: R11_REVIEWERS[1],
    applicant: R11_APPLICANTS[2],
    status: "CONFLICT",
    weight_bp: "0",
    tie_kind: "COAUTHOR",
    tie_basis: "W4401229907 (2025), 3 authors",
    link_basis: "DECLARED: OpenAlex A5011992388 carries ORCID 0000-0001-7295-8330",
    sources_checked: "OPENALEX ORCID GITHUB",
    sources_failed: "",
    evidence_digest: "c30144bb9e78a2f05d21",
    rationale: "1 co-authored work inside the window, 3 authors on it.",
    screened_at: "2026-05-13T09:15:00Z",
    appeal_id: "",
  },
];

export const MOCK_SCREENINGS: Record<string, Screening[]> = {
  "r-12": MOCK_SCREENINGS_R12,
  "r-11": MOCK_SCREENINGS_R11,
  "r-13": [],
};

/* ------------------------------------------------------------------------------------------
   Appeals. All four grounds, all three dispositions, and both parties exercising standing.
   ------------------------------------------------------------------------------------------ */

export const MOCK_APPEALS: Appeal[] = [
  {
    id: "ap-1",
    screening_id: `r-12:${R12_REVIEWERS[0]}:${R12_APPLICANTS[2]}`,
    appellant: R12_REVIEWERS[0],
    grounds: "WRONG_IDENTITY",
    evidence_url: "https://orcid.org/0000-0002-1825-0097",
    bond: "50000000000000000000",
    status: "OPEN",
    rationale: "",
    settled_at: "",
  },
  {
    id: "ap-2",
    screening_id: `r-12:${R12_REVIEWERS[1]}:${R12_APPLICANTS[1]}`,
    appellant: R12_REVIEWERS[1],
    grounds: "NOT_MATERIAL",
    evidence_url: "https://openalex.org/W4319922017",
    bond: "50000000000000000000",
    status: "OPEN",
    rationale: "",
    settled_at: "",
  },
  {
    // The symmetry no existing process has: the applicant appeals a CLEAR.
    id: "ap-3",
    screening_id: `r-12:${R12_REVIEWERS[4]}:${R12_APPLICANTS[0]}`,
    appellant: R12_APPLICANTS[0],
    grounds: "MISSED_TIE",
    evidence_url: "https://github.com/aureliaops/lambdaframe/graphs/contributors",
    bond: "50000000000000000000",
    status: "UPHELD",
    rationale:
      "The record raised is the same 2019 contribution the screening already found and placed outside this round's declared window. The window is the operator's policy and the appeal did not argue against the window itself.",
    settled_at: "2026-07-09T16:30:00Z",
  },
  {
    id: "ap-4",
    screening_id: `r-11:${R11_REVIEWERS[0]}:${R11_APPLICANTS[0]}`,
    appellant: R11_REVIEWERS[0],
    grounds: "STALE_TIE",
    evidence_url: "https://orcid.org/0000-0002-0198-9218",
    bond: "50000000000000000000",
    status: "OVERTURNED",
    rationale:
      "The employment ended in 2019, before the round's declared window opens in 2021. The tie is a fact and it is out of scope here. Full weight restored and the bond returned with a share of the pool.",
    settled_at: "2026-05-19T15:40:00Z",
  },
  {
    id: "ap-5",
    screening_id: `r-12:${R12_REVIEWERS[3]}:${R12_APPLICANTS[0]}`,
    appellant: R12_REVIEWERS[3],
    grounds: "STALE_TIE",
    evidence_url: "https://orcid.org/0000-0003-1613-5981",
    bond: "50000000000000000000",
    status: "OPEN",
    rationale: "",
    settled_at: "",
  },
  {
    id: "ap-6",
    screening_id: `r-11:${R11_REVIEWERS[1]}:${R11_APPLICANTS[0]}`,
    appellant: R11_REVIEWERS[1],
    grounds: "NOT_MATERIAL",
    evidence_url: "https://openalex.org/W4288117702",
    bond: "50000000000000000000",
    status: "UNCLEAR",
    rationale:
      "12 authors, 2022, and no further tie on any other axis. The ground was neither established nor refuted, so the pair stands at half weight and both bonds were returned. A hard case is not penalised.",
    settled_at: "2026-05-20T11:18:00Z",
  },
];

/* ------------------------------------------------------------------------------------------
   Summaries and totals. Counted from the records above rather than typed out, so a fixture
   cannot claim a coverage figure the records do not support.
   ------------------------------------------------------------------------------------------ */

const countStatus = (screenings: readonly Screening[], status: string): string =>
  String(screenings.filter((s) => s.status === status).length);

const summarise = (round: Round, participants: Participant[]): RoundSummary => {
  const screenings = MOCK_SCREENINGS[round.id] ?? [];
  const openAppeals = MOCK_APPEALS.filter(
    (appeal) => appeal.status === "OPEN" && appeal.screening_id.startsWith(`${round.id}:`),
  );
  return {
    id: round.id,
    operator: round.operator,
    name: round.name,
    status: round.status,
    created_at: round.created_at,
    coi_start_year: round.coi_start_year,
    coi_end_year: round.coi_end_year,
    reviewers: round.reviewers,
    applicants: round.applicants,
    participants,
    pairs: String(round.reviewers.length * round.applicants.length),
    requested: String(screenings.length),
    pending: countStatus(screenings, "PENDING"),
    clear: countStatus(screenings, "CLEAR"),
    conflict: countStatus(screenings, "CONFLICT"),
    material_unclear: countStatus(screenings, "MATERIAL_UNCLEAR"),
    insufficient: countStatus(screenings, "INSUFFICIENT"),
    unscreened: countStatus(screenings, "UNSCREENED"),
    appeals_open: String(openAppeals.length),
  };
};

export const MOCK_SUMMARIES: Record<string, RoundSummary> = {
  "r-12": summarise(ROUND_12, R12_PARTICIPANTS),
  "r-11": summarise(ROUND_11, R11_PARTICIPANTS),
  "r-13": summarise(ROUND_13, R13_PARTICIPANTS),
};

const ALL_SCREENINGS = [...MOCK_SCREENINGS_R12, ...MOCK_SCREENINGS_R11];

export const MOCK_STATS: ContractStats = {
  rounds: String(MOCK_ROUNDS.length),
  participants: String(
    R12_PARTICIPANTS.length + R11_PARTICIPANTS.length + R13_PARTICIPANTS.length,
  ),
  screenings: String(ALL_SCREENINGS.length),
  clear: countStatus(ALL_SCREENINGS, "CLEAR"),
  conflict: countStatus(ALL_SCREENINGS, "CONFLICT"),
  material_unclear: countStatus(ALL_SCREENINGS, "MATERIAL_UNCLEAR"),
  insufficient: countStatus(ALL_SCREENINGS, "INSUFFICIENT"),
  appeals: String(MOCK_APPEALS.length),
  overturned: String(MOCK_APPEALS.filter((appeal) => appeal.status === "OVERTURNED").length),
};

/**
 * The screening request bond, as the fixtures present it.
 *
 * A real figure comes off the contract. This is stated as a fixture value and the interface says
 * so wherever it is shown, because inventing a bond that a live deployment then contradicts is
 * exactly the sort of small lie that makes the rest untrustworthy.
 */
export const MOCK_BOND_WEI = "50000000000000000000";
