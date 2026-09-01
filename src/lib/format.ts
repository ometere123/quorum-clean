/**
 * Display helpers. Every one of them is allowed to say "unreadable" and none of them invents a
 * value, because a formatter that guesses is the cheapest possible way to fabricate a fact.
 */

import { FULL_WEIGHT_BP } from "./contract-types.ts";

const WEI_PER_GEN = 10n ** 18n;

/** Wei decimal string to a GEN figure. Returns the raw string back if it is not a number. */
export const formatGen = (wei: string): string => {
  const trimmed = wei.trim();
  if (!/^\d+$/.test(trimmed)) return trimmed.length > 0 ? trimmed : "unrecorded";
  const value = BigInt(trimmed);
  const whole = value / WEI_PER_GEN;
  const fraction = value % WEI_PER_GEN;
  if (fraction === 0n) return `${whole.toString()} GEN`;
  const decimals = fraction.toString().padStart(18, "0").replace(/0+$/, "");
  return `${whole.toString()}.${decimals} GEN`;
};

/** A GEN amount typed by a person to wei. `null` when the input is not a plain decimal. */
export const genToWei = (input: string): string | null => {
  const trimmed = input.trim();
  if (!/^\d+(\.\d{1,18})?$/.test(trimmed)) return null;
  const [whole, fraction = ""] = trimmed.split(".");
  const padded = fraction.padEnd(18, "0");
  return (BigInt(whole) * WEI_PER_GEN + BigInt(padded)).toString();
};

/**
 * A basis point figure, in the two encodings that matter, never as a percentage of anything.
 *
 * The number and the word travel together everywhere in this product. `10000` alone cannot tell a
 * reviewer who was screened and found clean from a reviewer nobody looked at, so the number is
 * never shown without the status beside it.
 */
export const formatBp = (bp: string | number | null): string => {
  if (bp === null) return "no change";
  const value = typeof bp === "number" ? bp : Number(bp.trim());
  if (!Number.isFinite(value)) return "unreadable";
  return value.toLocaleString("en-GB");
};

/** Basis points as a share of full weight, in whole basis points. Never rounded to a percentage. */
export const bpOfFull = (bp: string | number): string => {
  const value = typeof bp === "number" ? bp : Number(bp.trim());
  if (!Number.isFinite(value)) return "unreadable";
  return `${value.toLocaleString("en-GB")} of ${FULL_WEIGHT_BP.toLocaleString("en-GB")}`;
};

/** A count of things, with its unit. Counts, never rates, because a rate hides a denominator. */
export const formatCount = (raw: string | number | null, unit: string, plural?: string): string => {
  if (raw === null) return `unreadable ${plural ?? `${unit}s`}`;
  const value = typeof raw === "number" ? raw : Number(raw.trim());
  if (!Number.isFinite(value)) return `unreadable ${plural ?? `${unit}s`}`;
  const word = value === 1 ? unit : plural ?? `${unit}s`;
  return `${value.toLocaleString("en-GB")} ${word}`;
};

/** First and last of a hex string, for a rail or a table cell. The full value is always elsewhere. */
export const shortenHex = (value: string, lead = 6, tail = 4): string => {
  const trimmed = value.trim();
  if (trimmed.length <= lead + tail + 1) return trimmed;
  return `${trimmed.slice(0, lead)}…${trimmed.slice(-tail)}`;
};

/**
 * A timestamp the contract wrote, shown as it was written when it cannot be parsed.
 *
 * The contract stores whatever string it was given, so this must survive a value that is not a
 * date without turning it into "Invalid Date".
 */
export const displayTime = (raw: string): string => {
  const trimmed = raw.trim();
  if (trimmed.length === 0) return "unrecorded";
  const asNumber = /^\d+$/.test(trimmed) ? Number(trimmed) : Number.NaN;
  const date = Number.isFinite(asNumber)
    ? new Date(asNumber > 1e12 ? asNumber : asNumber * 1000)
    : new Date(trimmed);
  if (Number.isNaN(date.getTime())) return trimmed;
  return date.toISOString().replace("T", " ").slice(0, 16) + " UTC";
};

/** A short label for a participant, for a matrix axis where 34px is the whole budget. */
export const axisLabel = (label: string, addr: string): string => {
  const trimmed = label.trim();
  if (trimmed.length > 0) return trimmed;
  return shortenHex(addr, 6, 4);
};

/** An ORCID, in the grouped form the register prints it in. Left alone if it is not one. */
export const formatOrcid = (raw: string): string => {
  const digits = raw.replace(/[^0-9Xx]/g, "").toUpperCase();
  if (digits.length !== 16) return raw.trim();
  return `${digits.slice(0, 4)}-${digits.slice(4, 8)}-${digits.slice(8, 12)}-${digits.slice(12)}`;
};
