/**
 * Guards the exact class of bug a prior audit found live: the frontend calling a contract method
 * name that does not exist (`screening_bond`, `get_appeal`), while `verify-schema.mjs` only ever
 * checked a hand-picked subset that happened to exclude both.
 *
 * Two assertions close that gap from both directions:
 *   1. every method name literally referenced by `src/` also appears in `REQUIRED_METHODS`
 *      (config.ts) and in `scripts/verify-schema.mjs`'s own required list — so a call to a
 *      nonexistent method can no longer pass CI silently;
 *   2. every method in those two required lists actually exists on `contracts/QuorumClean.py`
 *      as a real `@gl.public.view` / `@gl.public.write[.payable]` method — so a typo in the
 *      required list itself cannot pass CI either.
 *
 * This is a plain-text scan, not a TypeScript parser: it looks for the method name as a quoted
 * string literal anywhere under `src/`. That is sufficient here because every call site in this
 * codebase passes a literal string (`call("list_rounds", [])`, `functionName="screen"`,
 * `submit("appeal", ...)`) — nothing constructs a method name dynamically.
 */

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));

function listFiles(dir, exts) {
  const out = [];
  for (const entry of readdirSync(dir)) {
    const full = path.join(dir, entry);
    const stat = statSync(full);
    if (stat.isDirectory()) {
      out.push(...listFiles(full, exts));
    } else if (exts.some((ext) => entry.endsWith(ext))) {
      out.push(full);
    }
  }
  return out;
}

function contractMethods() {
  const source = readFileSync(path.join(ROOT, "contracts", "QuorumClean.py"), "utf8");
  const names = new Set();
  const pattern = /@gl\.public\.(?:view|write(?:\.payable)?)\s*\n\s*def (\w+)\(/g;
  for (const match of source.matchAll(pattern)) names.add(match[1]);
  return names;
}

function methodsReferencedIn(files) {
  const real = contractMethods();
  const found = new Set();
  for (const file of files) {
    const text = readFileSync(file, "utf8");
    for (const name of real) {
      // Word-bounded quoted literal, e.g. "screen" or 'round_summary' — not a substring hit
      // inside an unrelated identifier.
      const re = new RegExp(`["']${name}["']`);
      if (re.test(text)) found.add(name);
    }
  }
  return found;
}

test("every contract method the frontend calls is a real method on the contract", () => {
  const real = contractMethods();
  assert.ok(real.size >= 14, `expected the contract to expose its public methods, found ${real.size}`);
  const srcFiles = listFiles(path.join(ROOT, "src"), [".ts", ".tsx"]);
  const referenced = methodsReferencedIn(srcFiles);
  const bogus = [...referenced].filter((name) => !real.has(name));
  assert.deepEqual(bogus, [], `frontend references contract method(s) that do not exist: ${bogus.join(", ")}`);
});

test("REQUIRED_METHODS (config.ts) covers every method the frontend actually calls", async () => {
  const { REQUIRED_METHODS } = await import("../src/lib/genlayer/config.ts");
  const srcFiles = listFiles(path.join(ROOT, "src"), [".ts", ".tsx"]);
  const referenced = methodsReferencedIn(srcFiles);
  const required = new Set(REQUIRED_METHODS);
  const uncovered = [...referenced].filter((name) => !required.has(name));
  assert.deepEqual(
    uncovered,
    [],
    `frontend calls method(s) not in REQUIRED_METHODS, so a broken call to them would pass ` +
      `schema verification silently: ${uncovered.join(", ")}`,
  );
});

test("REQUIRED_METHODS (config.ts) and verify-schema.mjs's own list are real contract methods and agree", () => {
  const real = contractMethods();
  const configSource = readFileSync(path.join(ROOT, "src", "lib", "genlayer", "config.ts"), "utf8");
  const scriptSource = readFileSync(path.join(ROOT, "scripts", "verify-schema.mjs"), "utf8");

  const extractRequired = (text) => {
    const block = /REQUIRED_METHODS\s*(?::\s*[^=]+)?=\s*\[([^\]]*)\]|const required = \[([^\]]*)\]/.exec(text);
    assert.ok(block, "could not find a required-methods array literal");
    const body = block[1] ?? block[2];
    return [...body.matchAll(/["']([\w]+)["']/g)].map((m) => m[1]);
  };

  const fromConfig = extractRequired(configSource);
  const fromScript = extractRequired(scriptSource);

  for (const name of fromConfig) {
    assert.ok(real.has(name), `REQUIRED_METHODS names "${name}", which is not a real contract method`);
  }
  for (const name of fromScript) {
    assert.ok(real.has(name), `verify-schema.mjs names "${name}", which is not a real contract method`);
  }

  assert.deepEqual(
    [...fromConfig].sort(),
    [...fromScript].sort(),
    "REQUIRED_METHODS (config.ts) and verify-schema.mjs's required list have drifted apart",
  );
});
