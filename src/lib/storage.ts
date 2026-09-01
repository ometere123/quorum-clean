/**
 * Local storage for the transaction rail.
 *
 * The rail is a convenience, not a source of truth: every hash in it is re-read from the node,
 * and a hash that cannot be re-read is shown as unreadable rather than as its last known state.
 */

import { normalizeStoredTransactions } from "./transaction-state.ts";
import type { StoredTransaction, TxStage } from "./contract-types.ts";

const KEY = "quorum-clean:transactions:v1";

/** How many to keep. A rail is a rail, not a history. */
const CAP = 24;

/**
 * Anything that is not exactly a stored transaction is dropped rather than coerced.
 *
 * A malformed entry that gets patched up here would show up in the rail as a transaction that
 * does not exist, which is worse than a shorter rail.
 */
const isStoredTransaction = (value: unknown): value is StoredTransaction => {
  if (typeof value !== "object" || value === null) return false;
  const record = value as Record<string, unknown>;
  return (
    typeof record.hash === "string" &&
    record.hash.length > 0 &&
    typeof record.label === "string" &&
    typeof record.createdAt === "string" &&
    typeof record.status === "string"
  );
};

export const readTransactions = (): StoredTransaction[] => {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    const kept = parsed.filter(isStoredTransaction).map((tx) => ({
      ...tx,
      status: tx.status.toUpperCase() as TxStage,
    }));
    return normalizeStoredTransactions(kept).slice(0, CAP);
  } catch {
    return [];
  }
};

export const writeTransactions = (transactions: readonly StoredTransaction[]): void => {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(KEY, JSON.stringify(transactions.slice(0, CAP)));
  } catch {
    // A full or blocked storage is not worth an error surface. The rail degrades to this session.
  }
};
