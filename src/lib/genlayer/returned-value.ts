/**
 * What a write actually returned, read off the leader receipt.
 *
 * This exists because of one uncomfortable fact about GenLayer: a transaction can
 * finalize with GenVM SUCCESS and still be a refusal. The payable methods here refund
 * the bond and return `[REJECTED] <reason>` rather than raising, because raising after
 * value has arrived strands that value in the contract with no way to get it out. The
 * cost of that choice is that "the transaction succeeded" and "the request was
 * accepted" stop being the same statement, and a UI that only checks the first one
 * would tell someone their review was requested when the contract had just handed
 * their bond back.
 *
 * StudioNet's `leader_receipt[0].result` is a base64 payload whose first byte is a
 * result code — 0 return, 1 rollback, 2 contract error — and genlayer-js decodes it
 * into `{status, payload}` before the app ever sees it. Both shapes are handled here:
 * the decoded object, and the raw base64 string, so this works whether the caller went
 * through the client or read the RPC directly.
 */

const REJECTED_PREFIX = "[REJECTED]";

export type ReturnedValue =
  /** The call returned. `text` is the returned value rendered as text. */
  | { kind: "returned"; text: string }
  /** The call rolled back or errored. `message` is the contract's own words. */
  | { kind: "reverted"; message: string }
  /** No receipt, or a payload in a shape this decoder does not recognise. */
  | { kind: "unreadable" };

/** Decodes one leader receipt's `result` field, in either shape. */
export function returnedValue(result: unknown): ReturnedValue {
  if (typeof result === "string") return fromBase64(result);
  if (!isRecord(result)) return { kind: "unreadable" };

  const status = result.status;
  const payload = result.payload;

  if (status === "rollback" || status === "contract_error" || status === "error") {
    return { kind: "reverted", message: typeof payload === "string" ? payload : "" };
  }
  if (status === "return") {
    if (payload === null || payload === undefined) return { kind: "returned", text: "" };
    if (typeof payload === "string") return { kind: "returned", text: payload };
    if (isRecord(payload) && typeof payload.readable === "string") {
      return { kind: "returned", text: unquote(payload.readable) };
    }
    return { kind: "unreadable" };
  }
  if (status === "none") return { kind: "returned", text: "" };
  if (typeof result.raw === "string") return fromBase64(result.raw);
  return { kind: "unreadable" };
}

/**
 * The reason a payable call refused, or undefined if it did not refuse.
 *
 * Only a returned value counts. A revert carrying the same words is a different
 * event with different consequences for the caller's GEN, and conflating the two
 * would defeat the point of having separated them in the contract.
 */
export function rejectionReason(value: ReturnedValue): string | undefined {
  if (value.kind !== "returned") return undefined;
  const text = value.text.trim();
  if (!text.startsWith(REJECTED_PREFIX)) return undefined;
  return text.slice(REJECTED_PREFIX.length).trim() || "no reason was given";
}

/** Convenience for the common case: decode a receipt result and test it. */
export function rejectionIn(result: unknown): string | undefined {
  return rejectionReason(returnedValue(result));
}

/** The leader receipt's `result`, decoded, however deeply the client wrapped it. */
export function returnedFromTransaction(transaction: unknown): ReturnedValue {
  if (!isRecord(transaction)) return { kind: "unreadable" };
  const consensus = transaction.consensus_data;
  if (!isRecord(consensus)) return { kind: "unreadable" };
  const leader = consensus.leader_receipt;
  const first = Array.isArray(leader) ? leader[0] : leader;
  return returnedValue(isRecord(first) ? first.result : undefined);
}

/**
 * The undecoded form. First byte is the result code; for a return the remainder is
 * calldata-encoded, which is not worth reimplementing here, so the bytes are read as
 * text and only the `[REJECTED]` prefix is looked for. A calldata string is length-
 * prefixed, so the prefix does not sit at byte zero and `includes` is the honest test.
 */
function fromBase64(encoded: string): ReturnedValue {
  let bytes: Uint8Array;
  try {
    const binary = atob(encoded);
    bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
  } catch {
    return { kind: "unreadable" };
  }
  if (bytes.length === 0) return { kind: "unreadable" };
  const body = new TextDecoder("utf-8", { fatal: false }).decode(bytes.subarray(1));
  if (bytes[0] === 1 || bytes[0] === 2 || bytes[0] === 3) {
    return { kind: "reverted", message: body };
  }
  if (bytes[0] === 0) {
    const at = body.indexOf(REJECTED_PREFIX);
    return { kind: "returned", text: at === -1 ? body : body.slice(at) };
  }
  if (bytes[0] === 4) return { kind: "returned", text: "" };
  return { kind: "unreadable" };
}

/** `"\"d2\""` is how a returned string arrives once decoded. */
function unquote(readable: string): string {
  const trimmed = readable.trim();
  if (!trimmed.startsWith('"')) return trimmed;
  try {
    const parsed: unknown = JSON.parse(trimmed);
    return typeof parsed === "string" ? parsed : trimmed;
  } catch {
    return trimmed.replace(/^"|"$/g, "");
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
