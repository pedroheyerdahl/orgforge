# Clearweave corpus pipeline design

**Date:** 2026-07-20

## Goal

Turn the proven Clearweave corpus transformations and release gates into one
repeatable OrgForge build command. The command must reproduce the 180-day
package contract without adding model calls, publish no generated corpus to
Git, and never replace a usable destination with a failed build.

## Chosen approach

Add a thin orchestration layer around the existing `export_corpus()` and
`validate_corpus()` APIs. This preserves the implementation that produced the
validated v8.1 package while removing the error-prone sequence of hand-written
commands.

A documentation-only recipe would leave ordering and promotion mistakes
possible. A broad package refactor would put already-validated transformation
logic at unnecessary risk. The orchestration layer is the smallest change that
makes the process reproducible.

## Public interface

The supported command is:

```bash
uv run python src/build_clearweave_corpus.py \
  <orgforge-export> \
  <finished-corpus> \
  --profile config/clearweave_180d.yaml \
  --replace
```

The versioned YAML profile owns the build inputs that should not drift between
runs: seed, target start, target duration, observation-realism mode, Datadog
inbox limit, strict run-health requirement, and expected realism-policy
version.

`--replace` is required when the destination already exists. Replacement is
atomic from the caller's perspective and leaves no permanent backup folder.

## Build flow

1. Load and validate the profile before writing output.
2. Resolve and validate source and destination paths.
3. Build the entire package in a temporary sibling directory.
4. Run the complete corpus validator against the staged package.
5. Confirm the generated manifest uses the profile's expected realism policy.
6. Write `provenance/build_report.json` with profile, source, corpus counts,
   and validation results.
7. Validate the staged package again with the report present.
8. Promote the staged directory to the destination only after every required
   check passes.

The pipeline makes no LLM/API calls. It transforms an existing OrgForge source
export deterministically.

## Failure behavior

- Invalid profiles and unsafe path relationships fail before generation.
- An existing destination is never touched unless `--replace` was supplied.
- Failed validation never replaces the destination.
- Failed staging output is removed by default; `--keep-failed` retains it for
  diagnosis and reports its exact path.
- If promotion fails after moving an existing destination aside, the original
  destination is restored before the error is returned.
- Temporary rollback directories are deleted after successful promotion. No
  backup corpus is retained.

## Package contract

The orchestrator preserves the established package layout:

- `raw/`: native-ish final source objects;
- `deliveries/`: daily create/update/delete/redelivery actions for replay;
- `inbox/`: source-specific text projections for text ingestion;
- `provenance/`: manifest, action stream, realism ledger, scorecard, scenarios,
  source-run evidence, and build report;
- `gold/`: frozen candidates awaiting human review.

The established exporter order remains authoritative: adapt source data,
normalize the declared window, add workload, rebase locators, inject knowledge
scenarios, normalize email, apply observation realism, finalize references,
replay, render, score, and manifest.

## Verification

Tests must prove profile validation, refusal to overwrite without authorization,
non-promotion on validation failure, atomic successful replacement, report
creation, and an end-to-end no-cost fixture build. The full OrgForge test suite
must pass before publication. The new orchestrator receives the complete Ruff
rule set; newly added legacy-policy modules receive correctness lint while the
repository's existing line-length backlog remains separate maintenance work.

## Publication boundary

Commit source, tests, configuration, examples, and documentation only. Exclude
`.env`, credentials, simulation exports, generated corpus packages, caches, and
logs. Push the branch to the user's personal GitHub fork. Do not push to
`tenurehq/orgforge` and do not create a pull request.
