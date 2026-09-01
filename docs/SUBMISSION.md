# Quorum Clean submission record

## Thesis and boundary

Quorum Clean produces an auditable conflict-of-interest screening record for review rounds. GenLayer
is necessary because ORCID, OpenAlex and GitHub are live, heterogeneous public sources and identity
resolution can be ambiguous. Deterministic code owns round windows, registration, scope freezing,
source gates, status transitions, appeals, bonds and weights. Consensus retrieves and normalizes
source evidence; bounded prompts may classify only already-admitted evidence. `CLEAR` means no
evidenced tie was found in answering sources, not that independence was proved.

## Trust boundary

GitHub repositories and organisations are operator-declared scope. The contract freezes that scope
when screening begins; it cannot independently discover every repository or private affiliation.
This declaration is therefore an explicit integration trust boundary, not a trustless fact.

## Deployment and verification

`DEPLOYMENT.json` and `evidence/studionet.json` are the canonical records only after they contain a
finalized transaction, final Git commit, source SHA-256/byte count, schema parity and re-readable
state. Otherwise the status is **NOT PROVEN LIVE**.

```text
npm ci
npm run verify
python -m pytest tests/static -q
python -m pytest tests/direct -q
npm run verify:deployment
npm run verify:schema
```

The source-level contract shape and adversarial policy checks are **PROVEN STATIC**, not Direct
Mode. The executed contract lifecycle suite is **PROVEN DIRECT** only for the cases it actually
runs through the GenVM SDK. Live identities must
be public test identities or ethically appropriate examples; the system must never label a real
person conflicted from an unverified fixture. Live source outage, ambiguity, appeal and funded
refusal branches are **NOT PROVEN LIVE** unless evidence lists finalized hashes and stored state.

## Reviewer walkthrough

1. Start at `/` in fixture mode and read the explicit fixture banner.
2. Inspect `contracts/QuorumClean.py` for the frozen-scope and source-admission gates.
3. Run typecheck, lint, frontend tests, direct tests, compile, GenVM lint and production build.
4. Switch to live mode only with an explicit deployed address and verify finality, schema and
   source parity before accepting any result.
