# Source-realism corpus runbook

This is the current operating procedure for generating and releasing an
OrgForge corpus for Clearweave. Historical v5-v8.1 specs and plans explain how
the realism policy evolved; they are not additional operator steps.

The process never reads a proprietary source dump. Aggregate structural
learnings are encoded in synthetic policies and tests, not copied source data,
names, identifiers, filenames, or phrases.

## The two phases

### 1. Semantic simulation

`src/flow.py` generates the synthetic organization's source-system exhaust and
ground-truth event stream. This phase can call the configured language models,
uses MongoDB for simulation state, and writes resilience, status, and usage
records into the source export.

### 2. Deterministic packaging

`src/build_clearweave_corpus.py` adapts a completed source export into the
Clearweave package. It performs timestamp/window normalization, stable identity,
lifecycle splitting, locator rebasing, knowledge scenarios, source-specific
messiness, replay rendering, scorecard generation, validation, and safe
promotion. It makes no language-model or API calls.

## Preconditions

- Python dependencies are installed with `uv sync --dev`, or the equivalent
  Docker image is built.
- Docker and MongoDB are available only if a new semantic simulation is needed.
- Provider credentials are stored in `.env`; never put them in configuration,
  commands, logs, corpus artifacts, or Git.
- `ORGFORGE_MAX_SPEND_USD` is set to the run's explicitly approved ceiling.
- Source and destination paths are distinct and neither contains the other.
- Only one simulator writes to a given Mongo database and export path.

## 1. Verify the no-cost packaging stack

Run the focused integration test. It builds a synthetic fixture through the
real exporter and complete validator without credentials or API calls:

```bash
uv run pytest tests/test_corpus_pipeline.py -q
```

For a full preflight, run:

```bash
uv run pytest -q
uv run ruff check src tests
```

Do not start a paid simulation if either command fails.

## 2. Run or resume the semantic simulation

The exact model preset is configured in `config/config.yaml`. The example below
starts a clean run while keeping the spend and unrecovered-error kill switches
explicit:

```bash
env -u OPENAI_API_KEY docker compose run --rm \
  -e ORGFORGE_MAX_DAYS=180 \
  -e ORGFORGE_OUTPUT_DIR=/app/export/source-180d \
  -e ORGFORGE_MAX_UNRECOVERED_LLM_FAILURES=3 \
  -e ORGFORGE_MAX_SPEND_USD=<approved-ceiling> \
  -e 'MONGO_URI=mongodb://mongodb:27017/?directConnection=true' \
  orgforge uv run --no-project python src/flow.py --reset --seed 42
```

The shell's `OPENAI_API_KEY` is intentionally unset for this command so Compose
loads the current value from `.env`. Leave `OPENAI_BASE_URL` unset when using
the provider's default endpoint. A usage-tier limit produces rate-limit errors,
not intermittent invalid-key errors; resilience retries only errors classified
as transient and stops at the configured failure or spend boundary.

If execution stops after a written checkpoint, use `--resume` with the same
database, output path, seed, model settings, and budget. Never combine
`--resume` with `--reset`, and never run two simulators against the same state.

## 3. Confirm source-run health

Before packaging, inspect `<source-export>/provenance/run_status.json` and
require:

- `status` is `completed`;
- `unrecovered_llm_failures` is zero;
- conservative spend is at or below `spend_ceiling_usd`;
- `simulation_events.jsonl` exists;
- the resilience ledger contains no unrecovered outcome.

Stop and diagnose the source run if any condition fails. Do not turn an
incomplete simulation into a release package.

## 4. Build and validate the package

From the OrgForge checkout, run the single supported packaging command:

```bash
uv run python src/build_clearweave_corpus.py \
  export/source-180d \
  export/clearweave-180d \
  --profile config/clearweave_180d.yaml
```

Use `--replace` only when intentionally replacing an existing destination. The
pipeline stages the complete package beside the destination, validates it,
writes `provenance/build_report.json`, validates again, and then promotes it.
Failed output does not replace the current corpus. `--keep-failed` retains the
staging path named in the error for diagnosis; the default removes it.

The 180-day profile requires:

- seed 42 and the declared 2026-01-01 through 2026-06-29 window;
- observation-realism policy v5;
- source-specific inbox rendering with a bounded Datadog projection;
- strict source-run health and authoritative budget validation;
- all corpus-validator release gates.

## 5. Understand the output

- `raw/` contains native-ish current source objects. It is not a byte-for-byte
  copy of the simulator export because lifecycle state, timestamps, identifiers,
  and source envelopes are normalized into the declared observation window.
- `deliveries/` contains one file per observed source action, grouped by day and
  system. Use it to replay what arrived, changed, was deleted, or was redelivered.
- `inbox/` is a lossy, source-specific text projection for ingestion systems
  that currently consume text or email rather than native APIs. It is not the
  source of replay truth.
- `provenance/` contains the authoritative action stream, stable references,
  checksums, manifest, realism ledger and scorecard, knowledge scenarios,
  source-run health, and build report.
- `gold/` contains candidate evaluation records. `pending_human_review` means
  they are not benchmark labels yet.

## Release gates

The build is releasable only when the command exits zero and the build report
records every required check as passing. The validator covers:

- UTF-8 and privacy controls;
- stable identities, revisions, replay, and channel-scoped Slack threads;
- native timestamps, lifecycle state, source paths, and declared-window dates;
- native source shapes and absence of generator-only controls in raw output;
- manifest coverage and checksums for raw, inbox, and deliveries;
- messiness and semantic-safety requirements;
- knowledge evidence, source, day, and correction-reference integrity;
- policy-v5 realism scorecard thresholds;
- completed source-run health and authoritative spend ceiling.

After the automated gate, manually inspect a small cross-source sample. A
passing package can support ingestion, replay, load, temporal retrieval, and
manual UAT. It is not a frozen contradiction benchmark until its gold candidates
are human reviewed.

## Publication boundary

Commit code, tests, generic synthetic configuration, examples, and docs. Never
commit `.env`, keys, provider responses, source exports, generated corpus
packages, logs, caches, or proprietary reference data. The repository's
`.gitignore` excludes normal export and environment paths, but the staged diff
must still be audited before every commit.
