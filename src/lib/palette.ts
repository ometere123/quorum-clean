/**
 * The palette, with its contrast measured rather than estimated.
 *
 * `src/app/globals.css` states three ratios in a comment and says this file holds the figures.
 * It does, and `tests/palette.test.mjs` recomputes them from the hex values, so a token added
 * later cannot skip the check and a figure cannot drift away from the colour it describes.
 *
 * The ratios are not decoration. Each one imposes a constraint that the components obey, and the
 * constraint is written next to the number so it travels with it.
 */

export type SwatchRole =
  /** Text at any size, including 11px labels. */
  | "text"
  /** Glyphs, fills, and labels at 18px and above. Never small text. */
  | "glyph-and-large"
  /** Fill only. Never carries text at any size. */
  | "fill-only"
  /** Rules, edges, and the placeholder inside an empty cell. Never text. */
  | "rule-only";

export type Swatch = {
  token: string;
  hex: string;
  /** Recorded ratio against `--field`, to two places. */
  ratio: number;
  role: SwatchRole;
  /** The rule this ratio imposes, in words, because a bare number is not a constraint. */
  constraint: string;
};

export const FIELD = "#f1f1ee";

/**
 * Contrast against the poster ground.
 *
 * Blue is the only accent that may set text. Red lands just under the 4.5 line, which is why the
 * system names a conflict in ink beside a red mark rather than in red. Ochre is nowhere near it.
 */
export const SWATCHES: readonly Swatch[] = [
  {
    token: "--ink",
    hex: "#1b1b1b",
    ratio: 15.22,
    role: "text",
    constraint: "Carries all body text, all headings and all record type.",
  },
  {
    token: "--blue",
    hex: "#2c5f8a",
    ratio: 5.96,
    role: "text",
    constraint:
      "The only accent that may carry text. Used for the cleared mark and for links in prose.",
  },
  {
    token: "--red",
    hex: "#c8402f",
    ratio: 4.39,
    role: "glyph-and-large",
    constraint:
      "Under 4.5, so it is used for the conflict glyph, cell fills and the refusal edge only. Where a conflict is named in words, the word is set in ink beside the mark.",
  },
  {
    token: "--ochre",
    hex: "#d9a335",
    ratio: 2.01,
    role: "fill-only",
    constraint:
      "Fill only, at any size. A glyph sitting on an ochre fill is set in ink, because ink on ochre measures 7.58 and the field colour on ochre measures 2.01.",
  },
  {
    token: "--ink-70",
    hex: "#5b5b5a",
    ratio: 6.01,
    role: "text",
    constraint: "The label grey. Passes at 11px, which is the smallest type in the system.",
  },
  {
    token: "--ink-55",
    hex: "#7b7b7a",
    ratio: 3.74,
    role: "rule-only",
    constraint:
      "Under 4.5, so no component sets readable text in it. It marks rules and the inside of an empty cell, where there is nothing to read.",
  },
];

/** Contrast of a glyph on a filled cell, which is a different measurement from the same ink on the ground. */
export const ON_FILL: readonly { fill: string; glyph: string; ratio: number; note: string }[] = [
  {
    fill: "--red",
    glyph: "--field",
    ratio: 4.39,
    note: "A shape rather than text, so the 3:1 floor for graphical objects is the one that applies.",
  },
  {
    fill: "--blue",
    glyph: "--field",
    ratio: 5.96,
    note: "Clears the text floor as well, so a word may sit on a blue fill if one ever needs to.",
  },
  {
    fill: "--ochre",
    glyph: "--ink",
    ratio: 7.58,
    note: "The reason the glyph on ochre is ink and not the field colour.",
  },
];

/** The floor that applies to text. */
export const TEXT_FLOOR = 4.5;

/** The floor that applies to a glyph, a rule or any other non-text mark. */
export const GRAPHIC_FLOOR = 3;

const channel = (value: number): number => {
  const srgb = value / 255;
  return srgb <= 0.04045 ? srgb / 12.92 : ((srgb + 0.055) / 1.055) ** 2.4;
};

/** Relative luminance per WCAG 2.1, from a `#rrggbb` string. */
export const luminance = (hex: string): number => {
  const clean = hex.replace("#", "").trim();
  if (!/^[0-9a-fA-F]{6}$/.test(clean)) {
    throw new Error(`not a six digit hex colour: ${hex}`);
  }
  const r = channel(Number.parseInt(clean.slice(0, 2), 16));
  const g = channel(Number.parseInt(clean.slice(2, 4), 16));
  const b = channel(Number.parseInt(clean.slice(4, 6), 16));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};

/** WCAG contrast ratio between two opaque colours. */
export const contrastRatio = (a: string, b: string): number => {
  const la = luminance(a);
  const lb = luminance(b);
  const lighter = Math.max(la, lb);
  const darker = Math.min(la, lb);
  return (lighter + 0.05) / (darker + 0.05);
};
