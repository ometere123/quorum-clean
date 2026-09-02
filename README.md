# Quorum Clean

Grant-round reviewer screening that gates voting weight rather than money.

Built on GenLayer as a single Intelligent Contract plus a Next.js client. There is no
backend, no database, no indexer and no scheduled worker: every piece of evidence is
fetched inside consensus by the contract itself, and every state transition is a button
anyone may press.

Submission record: [`docs/SUBMISSION.md`](docs/SUBMISSION.md)

## Status

Current status: the contract, fixture register, round matrix, wallet-gated write rail, and
deterministic read decoders are wired. Canonical StudioNet deployment:
`0x96FDeDdab60F6381af442b226672360760D07ff3` (finalized, GenVM SUCCESS, source/schema parity
recorded). Representative payable live exercises remain explicitly limited in the evidence record.
Live app: https://quorum-clean.vercel.app

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
tests/e2e                   Playwright, run against a served production build or explicit E2E_BASE_URL
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
