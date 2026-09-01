import test from "node:test";
import assert from "node:assert/strict";
import { MOCK_ROUNDS, MOCK_STATS, MOCK_SUMMARIES } from "../src/lib/mock-data.ts";
import { SCREENING_STATUS, parseCount, pairKey } from "../src/lib/contract-types.ts";

test("bundled register contains rounds and summaries with matching ids", () => {
  assert.ok(MOCK_ROUNDS.length >= 3);
  for (const round of MOCK_ROUNDS) assert.equal(MOCK_SUMMARIES[round.id]?.id, round.id);
});

test("fixture totals are decimal strings and statuses have copy", () => {
  for (const value of Object.values(MOCK_STATS)) assert.match(value, /^\d+$/);
  for (const status of ["CLEAR", "CONFLICT", "MATERIAL_UNCLEAR", "UNSCREENED", "INSUFFICIENT"]) {
    assert.ok(SCREENING_STATUS[status]);
  }
});

test("pair keys remain stable and counts reject malformed values", () => {
  assert.equal(pairKey("0x1", "0x2"), "0x1|0x2");
  assert.equal(parseCount("12"), 12);
  assert.equal(parseCount("12.5"), null);
});
