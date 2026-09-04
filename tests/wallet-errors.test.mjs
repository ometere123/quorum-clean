/**
 * Regression coverage for the exact defect a live Register Participant transaction surfaced:
 * `error instanceof Error ? error.message : String(error)` rendering the plain
 * `{code, message, data}` object a wallet actually throws as the literal text `[object Object]`.
 * Every case here is a shape a real EIP-1193 provider, viem, or genlayer-js is known to throw.
 */

import test from "node:test";
import assert from "node:assert/strict";
import { normalizeError } from "../src/lib/wallet-errors.ts";

test("a real Error keeps its own message", () => {
  assert.equal(normalizeError(new Error("The canonical contract is not configured.")), "The canonical contract is not configured.");
});

test("the exact wallet_getSnaps rejection this session hit reads as its own message, not [object Object]", () => {
  const thrown = {
    code: -32601,
    message: "method [wallet_getSnaps] doesn't has corresponding handler",
    data: { method: "wallet_getSnaps" },
  };
  const result = normalizeError(thrown);
  assert.equal(result, "method [wallet_getSnaps] doesn't has corresponding handler");
  assert.doesNotMatch(result, /\[object Object\]/);
});

test("a bare plain object never renders as [object Object]", () => {
  assert.doesNotMatch(normalizeError({ foo: "bar", nested: { baz: 1 } }), /\[object Object\]/);
  assert.doesNotMatch(normalizeError({}), /\[object Object\]/);
  assert.doesNotMatch(normalizeError(Object.create(null)), /\[object Object\]/);
});

test("EIP-1193 user-rejection code 4001 reads as a calm cancellation, string or number", () => {
  assert.equal(normalizeError({ code: 4001, message: "User rejected the request." }), "Transaction rejected in wallet.");
  assert.equal(normalizeError({ code: "4001" }), "Transaction rejected in wallet.");
});

test("viem-style errors expose shortMessage over a generic wrapping message when shortMessage comes first", () => {
  // viem puts its own readable line on `shortMessage`; some of its error classes also carry a
  // separate `.message` with the full multi-line dump. The outermost object's fields are read in
  // MESSAGE_KEYS order, so shortMessage wins over a `message` on the *same* object.
  const viemLike = { shortMessage: "Execution reverted for an unknown reason.", message: "very long multi line dump\nwith details" };
  assert.equal(normalizeError(viemLike), "Execution reverted for an unknown reason.");
});

test("a nested cause is reached when the outer object has no usable field", () => {
  const wrapped = { cause: { message: "insufficient funds for gas" } };
  assert.equal(normalizeError(wrapped), "insufficient funds for gas");
});

test("a nested RPC error under data.message is reached", () => {
  const wrapped = { code: -32000, data: { message: "execution reverted: round is locked" } };
  assert.equal(normalizeError(wrapped), "execution reverted: round is locked");
});

test("a circular object still returns a safe, non-crashing string", () => {
  const circular = {};
  circular.self = circular;
  assert.doesNotThrow(() => normalizeError(circular));
  assert.doesNotMatch(normalizeError(circular), /\[object Object\]/);
});

test("string, number, null and undefined all pass through safely", () => {
  assert.equal(normalizeError("plain string reason"), "plain string reason");
  assert.equal(normalizeError(""), "The request failed with no further detail.");
  assert.equal(normalizeError(42), "42");
  assert.equal(normalizeError(null), "The request failed with no further detail.");
  assert.equal(normalizeError(undefined), "The request failed with no further detail.");
});
