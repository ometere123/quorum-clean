import { localnet, studionet, testnetAsimov, testnetBradbury } from "genlayer-js/chains";

export const CONTRACT_ADDRESS = process.env.NEXT_PUBLIC_QUORUM_CLEAN_CONTRACT as `0x${string}` | undefined;

export const GENLAYER_ENDPOINT =
  process.env.NEXT_PUBLIC_GENLAYER_ENDPOINT ?? "https://studio.genlayer.com/api";

export const CHAIN_NAME = (process.env.NEXT_PUBLIC_GENLAYER_CHAIN ?? "studionet") as
  | "studionet"
  | "localnet"
  | "testnetAsimov"
  | "testnetBradbury";

const CHAINS = { studionet, localnet, testnetAsimov, testnetBradbury } as const;

export const chain = CHAINS[CHAIN_NAME];

/**
 * The one switch between the bundled fixtures and the deployed contract.
 *
 * `NEXT_PUBLIC_QUORUM_CLEAN_DATA=live` (or any contract address being present) puts every read
 * and write on the chain. Unset, the app reads `src/lib/mock-data.ts`, so the whole
 * interface is explorable before a deployment exists. Nothing else in the app branches
 * on this.
 */
const requestedDataMode = process.env.NEXT_PUBLIC_QUORUM_CLEAN_DATA;
export const DATA_MODE: "live" | "fixtures" =
  requestedDataMode === "fixtures"
    ? "fixtures"
    : requestedDataMode === "live" || Boolean(CONTRACT_ADDRESS)
      ? "live"
      : "fixtures";

export const IS_LIVE = DATA_MODE === "live" && Boolean(CONTRACT_ADDRESS);

// genlayer-js's built-in chain metadata for studionet still points at
// genlayer-explorer.vercel.app, but the working StudioNet explorer is
// explorer-studio.genlayer.com. Overridden explicitly rather than trusting
// chain.blockExplorers, which is wrong for this network.
export const EXPLORER_BASE = "https://explorer-studio.genlayer.com";
export const explorerTxUrl = (hash: string) => `${EXPLORER_BASE}/tx/${hash}`;
export const explorerAddressUrl = (address: string) => `${EXPLORER_BASE}/address/${address}`;

/**
 * Every method the frontend depends on. `scripts/verify-schema.mjs` reports which are missing
 * from the live deployment, and `tests/schema-parity.test.mjs` fails CI if any string literal
 * used as a `functionName` anywhere under `src/` is absent from this list — so a call to a
 * nonexistent method (as `screening_bond` and `get_appeal` once were) can no longer go unnoticed.
 * Kept identical to the `required` array in `scripts/verify-schema.mjs`; that test also checks
 * the two have not drifted apart.
 */
export const REQUIRED_METHODS = [
  "create_round",
  "declare_github_scope",
  "register_participant",
  "request_screening",
  "screen",
  "appeal",
  "adjudicate_appeal",
  "lock_round",
  "list_rounds",
  "round_summary",
  "list_screenings",
  "get_screening",
  "ledger",
  "parameters",
];
