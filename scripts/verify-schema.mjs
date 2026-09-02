import { createAccount, createClient } from "genlayer-js";
import { studionet } from "genlayer-js/chains";
import { existsSync, readFileSync } from "node:fs";

if (existsSync(".env.local")) {
  for (const line of readFileSync(".env.local", "utf8").split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) continue;
    const [key, ...value] = trimmed.split("=");
    process.env[key] ??= value.join("=");
  }
}

const address = process.env.NEXT_PUBLIC_QUORUM_CLEAN_CONTRACT;
// Kept identical to REQUIRED_METHODS in src/lib/genlayer/config.ts — tests/schema-parity.test.mjs
// asserts the two have not drifted apart, and that every method the frontend actually calls is
// covered here, so a call to a nonexistent method cannot pass CI silently again.
const required = [
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

if (!address) {
  console.error("NEXT_PUBLIC_QUORUM_CLEAN_CONTRACT is not set.");
  process.exit(1);
}

const client = createClient({
  chain: studionet,
  account: createAccount(),
  endpoint: process.env.NEXT_PUBLIC_GENLAYER_ENDPOINT ?? "https://studio.genlayer.com/api",
});
const schema = await client.getContractSchema(address);
const missing = required.filter((method) => !schema.methods?.[method]);
if (missing.length) {
  console.error(`Missing methods: ${missing.join(", ")}`);
  process.exit(1);
}
console.log(`Quorum Clean schema verified for ${address} (${required.length} methods).`);
