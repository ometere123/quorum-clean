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
const required = [
  "create_round",
  "register_participant",
  "request_screening",
  "screen",
  "appeal",
  "adjudicate_appeal",
  "lock_round",
  "get_weight",
  "get_screening",
  "list_screenings",
  "round_summary",
  "stats",
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
