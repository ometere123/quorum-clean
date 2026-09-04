"use client";

import { createClient } from "genlayer-js";
import { chain, GENLAYER_ENDPOINT } from "./config";

/**
 * Deliberately does not call the SDK's own `client.connect()`.
 *
 * That method is a MetaMask-Snap onboarding helper: after a chain check it unconditionally
 * calls `wallet_getSnaps` and, if the GenLayer signing snap is not among them, `wallet_requestSnaps`
 * to install one — a flow this app has never wanted (writes are signed by whatever ordinary
 * injected wallet the person already connected, over plain EIP-1193 methods, never a snap). A
 * wallet that does not implement `wallet_getSnaps` — most of them — throws a plain
 * `{ code, message }` object from that call, which used to abort every write before it reached
 * the contract and, formatted with `String(error)`, showed the person the literal text
 * `[object Object]` instead of a reason.
 *
 * None of what `connect()` does is needed here. `createClient` already binds `chain`, `account`
 * and `provider` at construction, which is everything a read or a write requires, and
 * `wallet.getWriteClient()` (`wallet-provider.tsx`) never reaches this function unless
 * `writeGate()` has already confirmed the wallet is on the right chain — so `connect()`'s own
 * chain-switch step would be redundant even without the snap problem.
 */
export async function createInjectedClient(address: `0x${string}`) {
  const provider = typeof window !== "undefined" ? window.ethereum : undefined;
  return createClient({ chain, endpoint: GENLAYER_ENDPOINT, account: address, provider });
}

declare global {
  interface Window {
    ethereum?: {
      request: (args: { method: string; params?: unknown[] }) => Promise<unknown>;
      on?: (event: string, listener: (...args: unknown[]) => void) => void;
      removeListener?: (event: string, listener: (...args: unknown[]) => void) => void;
    };
  }
}
