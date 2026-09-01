# Quorum Clean

Grant-round reviewer screening that gates voting weight rather than money.

Built on GenLayer as a single Intelligent Contract plus a Next.js client. There is no
backend, no database, no indexer and no scheduled worker: every piece of evidence is
fetched inside consensus by the contract itself, and every state transition is a button
anyone may press.

Submission record: [`docs/SUBMISSION.md`](docs/SUBMISSION.md)

## Status

Current status: the contract, fixture register, round matrix, wallet-gated write rail, and
deterministic read decoders are wired. A canonical StudioNet deployment is **NOT PROVEN LIVE**
until a current-source contract address, finalized deployment transaction, source parity, schema
parity, and re-readable evidence are recorded in `DEPLOYMENT.json` and `evidence/studionet.json`.

The repository contains three deliberately separate proof layers: frontend tests, static contract
audit checks in `tests/static`, and genuine GenVM Direct Mode execution tests in `tests/direct`.
Static checks are not presented as Direct Mode.

## Layout

```
contracts/QuorumClean.py     the whole product
src/app                     Next.js routes
src/components              interface
src/lib/genlayer            client plumbing, shared across the three builds
tests/static                AST/source policy checks
tests/direct                executed contract tests, run with pytest on gltest
tests/e2e                   Playwright, run against the deployed origin
```

## Verify

```
npm run verify
```

Runs frontend tests, static checks, executed Direct Mode tests, the em dash check, typecheck,
lint and the production build, in that order. Deployment and live-evidence verification are
separate and fail closed when no canonical deployment is recorded.

The repository is self-contained; Direct Mode uses `tests/direct` and does not require a
workspace sibling.
