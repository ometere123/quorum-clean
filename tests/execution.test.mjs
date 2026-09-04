/**
 * `assertSuccessfulGenVMExecution` is the one place a submitted transaction is allowed to be
 * called successful. It must never say so before the GenVM leader receipt actually says SUCCESS,
 * and when it does not, the leader's own error belongs in the thrown message rather than a
 * detail-free "GenVM ERROR after finality: <hash>".
 */

import test from "node:test";
import assert from "node:assert/strict";
import { assertSuccessfulGenVMExecution, inspectGenVMExecution } from "../src/lib/genlayer/execution.ts";

const receipt = (execution_result, error) => ({
  consensus_data: { leader_receipt: [{ execution_result, error: error ?? null }] },
});

test("SUCCESS is returned, not thrown, and is the only outcome treated as success", () => {
  const outcome = assertSuccessfulGenVMExecution(receipt("SUCCESS"), "0xabc");
  assert.equal(outcome.executionResult, "SUCCESS");
});

test("ROLLBACK with a leader error throws that error, not a bare hash", () => {
  assert.throws(
    () => assertSuccessfulGenVMExecution(receipt("ROLLBACK", "round qc-final-1 is locked"), "0xdead"),
    (err) => {
      assert.match(err.message, /round qc-final-1 is locked/);
      assert.match(err.message, /ROLLBACK/);
      assert.match(err.message, /0xdead/);
      return true;
    },
  );
});

test("ERROR with no leader-supplied detail still names the outcome and the hash, without inventing detail", () => {
  assert.throws(
    () => assertSuccessfulGenVMExecution(receipt("ERROR"), "0xfeed"),
    (err) => {
      assert.match(err.message, /ERROR/);
      assert.match(err.message, /0xfeed/);
      // No colon-and-detail suffix when the receipt carried none.
      assert.doesNotMatch(err.message, /ERROR\):/);
      return true;
    },
  );
});

test("UNKNOWN (a missing or malformed leader receipt) fails closed rather than reading as success", () => {
  assert.throws(() => assertSuccessfulGenVMExecution({}, "0x0"), /UNKNOWN/);
  assert.throws(() => assertSuccessfulGenVMExecution(null, "0x0"), /UNKNOWN/);
});

test("inspectGenVMExecution carries the leader error through untouched for callers that want it directly", () => {
  const outcome = inspectGenVMExecution(receipt("ROLLBACK", "insufficient bond"));
  assert.equal(outcome.executionResult, "ROLLBACK");
  assert.equal(outcome.executionError, "insufficient bond");
});
