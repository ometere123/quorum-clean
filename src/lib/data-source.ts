import { DATA_MODE } from "./genlayer/config.ts";
import * as live from "./live-reads.ts";
import { MOCK_BOND_WEI, MOCK_ROUNDS, MOCK_SCREENINGS, MOCK_STATS, MOCK_SUMMARIES } from "./mock-data.ts";
import { available, notFound, type ReadResult } from "./genlayer/read-result.ts";
import type { Appeal, ContractStats, Round, RoundSummary, Screening } from "./contract-types.ts";

export const isLive = DATA_MODE === "live";
export const sourceLabel = isLive ? "LIVE CONTRACT" : "BUNDLED FIXTURES";

export const rounds = (): Promise<ReadResult<Round[]>> =>
  isLive ? live.rounds() : Promise.resolve(available(MOCK_ROUNDS));

export const summary = (id: string): Promise<ReadResult<RoundSummary>> =>
  isLive ? live.summary(id) : Promise.resolve(MOCK_SUMMARIES[id] ? available(MOCK_SUMMARIES[id]) : notFound());

export const screenings = (id: string): Promise<ReadResult<Screening[]>> =>
  isLive ? live.screenings(id) : Promise.resolve(available(MOCK_SCREENINGS[id] ?? []));

export const appeal = (id: string): Promise<ReadResult<Appeal>> =>
  isLive ? live.appeal(id) : Promise.resolve(notFound());

export const stats = (): Promise<ReadResult<ContractStats>> =>
  isLive ? live.stats() : Promise.resolve(available(MOCK_STATS));

export const bond = (): Promise<ReadResult<string>> =>
  isLive ? live.bond() : Promise.resolve(available(MOCK_BOND_WEI));
