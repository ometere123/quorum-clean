/**
 * The wallet session, as a reducer.
 *
 * Injected wallet only. There is no chooser, because a chooser is a list of things this build has
 * not tested against, and offering one would be a claim about compatibility that nobody made.
 *
 * The state machine lives here rather than inside the provider so it can be reasoned about
 * without a browser. Every refusal returns a sentence, because a disabled button with no reason
 * is the single most common way an interface stops being honest about what it needs.
 */

import { chain, CHAIN_NAME } from "./genlayer/config.ts";

export type WalletStatus =
  /** No injected provider in the page at all. */
  | "unavailable"
  /** A provider is present and no account has been shared. Never auto-connected. */
  | "disconnected"
  /** The provider was asked and has not answered. */
  | "connecting"
  /** An account is shared. Whether it is on the right network is a separate question. */
  | "connected";

export type WalletState = {
  status: WalletStatus;
  address: `0x${string}` | null;
  /** The chain id the wallet reports, as the wallet reports it. `null` when unknown. */
  chainId: number | null;
  /** The last refusal, in words fit to show. */
  refusal: string | null;
};

export const INITIAL_WALLET: WalletState = {
  status: "disconnected",
  address: null,
  chainId: null,
  refusal: null,
};

export type WalletEvent =
  | { type: "detected"; present: boolean }
  | { type: "request" }
  | { type: "accounts"; addresses: readonly string[] }
  | { type: "chain"; chainId: number | null }
  | { type: "refused"; reason: string }
  | { type: "disconnect" };

const asAddress = (value: string): `0x${string}` | null =>
  /^0x[0-9a-fA-F]{40}$/.test(value) ? (value as `0x${string}`) : null;

export const nextWalletState = (current: WalletState, event: WalletEvent): WalletState => {
  switch (event.type) {
    case "detected":
      if (event.present) {
        return current.status === "unavailable"
          ? { ...current, status: "disconnected", refusal: null }
          : current;
      }
      return { ...INITIAL_WALLET, status: "unavailable" };
    case "request":
      return { ...current, status: "connecting", refusal: null };
    case "accounts": {
      const first = event.addresses.length > 0 ? asAddress(event.addresses[0]) : null;
      if (!first) {
        return { ...current, status: "disconnected", address: null, refusal: null };
      }
      return { ...current, status: "connected", address: first, refusal: null };
    }
    case "chain":
      return { ...current, chainId: event.chainId };
    case "refused":
      return {
        ...current,
        status: current.address ? "connected" : "disconnected",
        refusal: event.reason,
      };
    case "disconnect":
      return { ...INITIAL_WALLET, status: current.status === "unavailable" ? "unavailable" : "disconnected" };
  }
};

/** Hex chain id to a number, without turning a malformed value into zero. */
export const parseChainId = (value: unknown): number | null => {
  if (typeof value === "number" && Number.isInteger(value)) return value;
  if (typeof value !== "string") return null;
  const parsed = value.startsWith("0x") ? Number.parseInt(value, 16) : Number.parseInt(value, 10);
  return Number.isInteger(parsed) ? parsed : null;
};

export const chainIdHex = (id: number): string => `0x${id.toString(16)}`;

export const EXPECTED_CHAIN_ID: number | null =
  typeof chain.id === "number" ? chain.id : parseChainId(chain.id as unknown);

export const networkLabel = (id: number | null): string => {
  if (id === null) return "network not reported";
  if (EXPECTED_CHAIN_ID !== null && id === EXPECTED_CHAIN_ID) return CHAIN_NAME;
  return `chain ${id}`;
};

/**
 * Whether the connected wallet is on the network this build talks to.
 *
 * `unknown` fails closed. A wallet that will not say which chain it is on is not the same as a
 * wallet on the right one, and treating it as though it were would send a write into the dark.
 */
export type NetworkVerdict = "correct" | "wrong" | "unknown";

export const networkVerdict = (state: WalletState): NetworkVerdict => {
  if (state.chainId === null || EXPECTED_CHAIN_ID === null) return "unknown";
  return state.chainId === EXPECTED_CHAIN_ID ? "correct" : "wrong";
};

/**
 * Can this session sign a write, and if not, exactly why.
 *
 * `reason` is written to be shown next to the button, so it names the thing to do rather than
 * the state that is wrong.
 */
export type WriteGate = { ok: boolean; reason: string | null };

export const writeGate = (state: WalletState): WriteGate => {
  switch (state.status) {
    case "unavailable":
      return {
        ok: false,
        reason:
          "No injected wallet is available in this browser. This build talks to an injected wallet and nothing else.",
      };
    case "connecting":
      return { ok: false, reason: "Waiting for your wallet to answer." };
    case "disconnected":
      return { ok: false, reason: "Connect a wallet to sign this." };
    case "connected":
      break;
  }
  const verdict = networkVerdict(state);
  if (verdict === "wrong") {
    return {
      ok: false,
      reason: `Your wallet is on ${networkLabel(state.chainId)} and this contract is on ${CHAIN_NAME}.`,
    };
  }
  if (verdict === "unknown") {
    return {
      ok: false,
      reason: `Your wallet has not reported which network it is on, so this build will not sign. It expects ${CHAIN_NAME}.`,
    };
  }
  return { ok: true, reason: null };
};

/** A provider error, in words. Codes are kept, because a code is the only part a wallet agrees on. */
export const refusalMessage = (error: unknown): string => {
  if (typeof error === "object" && error !== null) {
    const code = (error as { code?: unknown }).code;
    if (code === 4001) return "You declined the request in your wallet. Nothing was sent.";
    if (code === -32002) {
      return "Your wallet already has a pending request for this site. Open it and answer that one.";
    }
    if (code === 4902) {
      return `Your wallet does not have ${CHAIN_NAME} configured, so it could not switch to it.`;
    }
  }
  if (error instanceof Error && error.message.trim().length > 0) return error.message;
  return "The wallet returned no reason.";
};
