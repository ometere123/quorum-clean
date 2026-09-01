# Quorum Clean

Grant-round reviewer screening that gates voting weight rather than money.

Built on GenLayer as a single Intelligent Contract plus a Next.js client. There is no
backend, no database, no indexer and no scheduled worker: every piece of evidence is
fetched inside consensus by the contract itself, and every state transition is a button
anyone may press.

Specification: `../genlayer-prds/04-reviewer-integrity-gate.md`
Design system: `../genlayer-prds/design-systems.md`

## Status

Release candidate surface: the contract, fixture register, round matrix, wallet-gated write rail,
and deterministic read decoders are wired. Live deployment verification remains environment-bound
until a contract address is configured in `.env.local`.

## Layout

```
contracts/QuorumClean.py     the whole product
src/app                     Next.js routes
src/components              interface
src/lib/genlayer            client plumbing, shared across the three builds
tests/direct                contract tests, run with pytest on gltest
tests/e2e                   Playwright, run against the deployed origin
```

## Verify

```
npm run verify
```

Runs the frontend unit tests, the contract tests, the em dash check, the type check, the
linter and the production build, in that order.

There is a second, faster test layer that does not run in CI. `_build/harness/` in the parent
workspace loads the contract against a stub SDK and replays captured HTTP responses off disk,
so a consensus path can be exercised in milliseconds without a node. It lives outside this
repository because it is shared by every build in the set.

```
python ../_build/harness/run.py quorum-clean
```
