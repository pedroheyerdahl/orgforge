# Clearweave Corpus Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide one safe, profile-driven command that packages and validates a Clearweave corpus before atomically promoting it.

**Architecture:** A focused `corpus_pipeline` module owns profile parsing, staging, validation, reporting, and promotion. A minimal CLI delegates to that module, while the existing exporter and validator remain unchanged and authoritative.

**Tech Stack:** Python 3.13, PyYAML, pathlib, pytest, existing OrgForge exporter and validator.

## Global Constraints

- The packaging pipeline must make zero model or API calls.
- Existing destinations require explicit `--replace` authorization.
- Failed builds must not modify an existing destination.
- Successful replacement must leave no permanent backup directory.
- Generated corpora, credentials, `.env`, logs, and caches must not be committed.
- Publish only to the user's personal fork; do not open a pull request.

---

### Task 1: Profile-driven pipeline

**Files:**
- Create: `tests/test_corpus_pipeline.py`
- Create: `src/corpus_pipeline.py`
- Create: `config/clearweave_180d.yaml`

**Interfaces:**
- Consumes: `clearweave_corpus.export_corpus(Path, Path, ...)` and `corpus_validator.validate_corpus(Path, require_run_health=...)`.
- Produces: `CorpusBuildProfile.load(path)` and `build_corpus(source_dir, output_dir, profile, replace=False, keep_failed=False)`.

- [ ] **Step 1: Write failing profile and overwrite-safety tests**

Add tests that load the committed profile, reject invalid dates/durations, and
assert an existing destination is refused before the exporter is called when
`replace=False`.

- [ ] **Step 2: Run the focused tests and verify the missing module failure**

Run: `uv run pytest tests/test_corpus_pipeline.py -q`

Expected: collection fails because `corpus_pipeline` does not exist.

- [ ] **Step 3: Implement profile parsing and preflight checks**

Create an immutable profile dataclass with strict required keys and ISO-date,
positive-duration, positive-policy-version, and non-negative-limit checks.
Reject identical, nested, missing-source, and unauthorized-existing paths before
creating a staging directory.

- [ ] **Step 4: Run the focused tests**

Run: `uv run pytest tests/test_corpus_pipeline.py -q`

Expected: the profile and preflight tests pass.

- [ ] **Step 5: Write failing validation and promotion tests**

Add tests using injected exporter/validator callables to prove that a failed
validation leaves the destination untouched, a successful build writes a report
and replaces the destination, and no rollback/staging directory remains.

- [ ] **Step 6: Implement staging, reporting, and rollback-safe promotion**

Build into a temporary sibling, validate, check the manifest policy version,
write `provenance/build_report.json`, validate again, and promote with restoration
of the previous destination if the final rename fails.

- [ ] **Step 7: Run the focused tests**

Run: `uv run pytest tests/test_corpus_pipeline.py -q`

Expected: all pipeline tests pass.

### Task 2: Public CLI and real fixture proof

**Files:**
- Modify: `tests/test_corpus_pipeline.py`
- Create: `src/build_clearweave_corpus.py`

**Interfaces:**
- Consumes: `CorpusBuildProfile.load()` and `build_corpus()`.
- Produces: the command `uv run python src/build_clearweave_corpus.py SOURCE OUTPUT --profile PROFILE [--replace] [--keep-failed]`.

- [ ] **Step 1: Write a failing end-to-end fixture test**

Use `build_source_realism_fixture.build_fixture_input()` as source input and a
small temporary profile. Assert that the real exporter and validator produce a
promoted package with `raw`, `deliveries`, `inbox`, `provenance`, `gold`, and a
passing build report.

- [ ] **Step 2: Run the focused test and verify failure**

Run: `uv run pytest tests/test_corpus_pipeline.py -q`

Expected: failure because the complete orchestration or CLI entry point is not
yet present.

- [ ] **Step 3: Implement the CLI**

Parse paths and flags, load the profile, invoke the pipeline, print the build
report as JSON, and return a nonzero exit code with a concise error on failure.

- [ ] **Step 4: Run focused tests and CLI help**

Run: `uv run pytest tests/test_corpus_pipeline.py -q`

Run: `uv run python src/build_clearweave_corpus.py --help`

Expected: tests pass and help documents all required arguments and safety flags.

### Task 3: Consolidated documentation and publication audit

**Files:**
- Modify: `README.md`
- Modify: `docs/source-realism-calibration-runbook.md`
- Modify: `docs/orgforge-corpus-realism-handoff.md`

**Interfaces:**
- Consumes: the committed profile and CLI.
- Produces: one current command, package-layout explanation, two-phase generation model, quality gates, and privacy/publication boundaries.

- [ ] **Step 1: Update documentation**

Document semantic simulation versus deterministic packaging, the one-command
build, folder meanings, strict versus fixture validation, build-report fields,
and safe replacement behavior. Mark historical per-version plans as provenance,
not required operator steps.

- [ ] **Step 2: Run documentation and secret scans**

Run: `rg -n "OPENAI_API_KEY=.+|xox[baprs]-|/Users/.+/Downloads/sources" README.md docs config src tests`

Expected: no credential values or proprietary source paths in new publication
content; generic forbidden-pattern tests may appear in validator test/code only.

- [ ] **Step 3: Run complete verification**

Run: `uv run pytest -q`

Run: `uv run ruff check src/corpus_pipeline.py src/build_clearweave_corpus.py tests/test_corpus_pipeline.py`

Run correctness lint for the newly added corpus modules and tests with the
repository's legacy line-length and `zip(strict=...)` backlog excluded.

Run: `git diff --check`

Expected: zero test failures, zero new-pipeline lint errors, zero correctness
errors in newly added corpus files, and zero whitespace errors.

- [ ] **Step 4: Audit and commit the intended change set**

Inspect `git status`, staged paths, ignored exports, and staged diffs. Commit all
task-related corpus-generation improvements while excluding `.env`, generated
exports, logs, caches, and unrelated user files.

- [ ] **Step 5: Publish to the personal fork only**

Resolve the authenticated GitHub username, create or reuse that account's fork,
add a distinct fork remote, push `codex/consolidate-corpus-pipeline`, and verify
the remote branch. Do not invoke any pull-request command.
