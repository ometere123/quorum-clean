import { DATA_MODE } from "./genlayer/config.ts";
import * as live from "./live-reads.ts";
import { MOCK_APPEALS, MOCK_BOND_WEI, MOCK_ROUNDS, MOCK_SCREENINGS, MOCK_STATS, MOCK_SUMMARIES } from "./mock-data.ts";
import { available, notFound, type ReadResult } from "./genlayer/read-result.ts";
import type { ContractStats, Round, RoundSummary, Screening } from "./contract-types.ts";

export const isLive = DATA_MODE === "live";
export const sourceLabel = isLive ? "LIVE CONTRACT" : "BUNDLED FIXTURES";

export const rounds = (): Promise<ReadResult<Round[]>> =>
  isLive ? live.rounds() : Promise.resolve(available(MOCK_ROUNDS));

export const summary = (id: string): Promise<ReadResult<RoundSummary>> =>
  isLive ? live.summary(id) : Promise.resolve(MOCK_SUMMARIES[id] ? available(MOCK_SUMMARIES[id]) : notFound());

export const screenings = (id: string): Promise<ReadResult<Screening[]>> =>
  isLive ? live.screenings(id) : Promise.resolve(available(MOCK_SCREENINGS[id] ?? []));

/**
 * `MOCK_SCREENINGS` is keyed by round id, not screening id, so a single-screening lookup has to
 * search every round's list. Mirrors `get_screening`'s embedded appeal: the matching
 * `MOCK_APPEALS` row (by `appeal_id`), or `null`, exactly like the contract's `_appeal_dict()` /
 * `None`.
 */
export const screening = (id: string): Promise<ReadResult<Screening>> => {
  if (isLive) return live.screening(id);
  const found = Object.values(MOCK_SCREENINGS).flat().find((row) => row.id === id);
  if (!found) return Promise.resolve(notFound());
  const appeal = found.appeal_id ? MOCK_APPEALS.find((row) => row.id === found.appeal_id) ?? null : null;
  return Promise.resolve(available({ ...found, appeal }));
};

export const stats = (): Promise<ReadResult<ContractStats>> =>
  isLive ? live.stats() : Promise.resolve(available(MOCK_STATS));

export const bond = (): Promise<ReadResult<string>> =>
  isLive ? live.bond() : Promise.resolve(available(MOCK_BOND_WEI));
