# Source Realism Emulation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic observation-plane exporter that turns OrgForge simulation artifacts into native-ish, messy, replayable Clearweave corpora and passes a no-cost readiness gate before another paid five-day run.

**Architecture:** Keep simulation truth unchanged and adapt its exported artifacts into a `SourceAction` stream with stable object identity and revisions. Apply seeded, source-specific routine activity and presentation degradation, render final raw/inbox snapshots, write daily replay deliveries and provenance, then validate identity, temporal order, coverage, replay, source shape, messiness, privacy, run health, and spend metadata.

**Tech Stack:** Python 3.13 standard library, existing PyYAML/pytest toolchain, JSON/JSONL/Markdown/EML files, Docker Compose test runtime.

## Global Constraints

- The proprietary reference dump is inspection-only and must never become a runtime input, fixture, prompt source, committed asset, vocabulary source, or text-generation seed.
- Checked-in examples use only synthetic company data and public/common source structures.
- No LLM call may be added solely for noise, formatting, metadata, duplicate, stale, or replay behavior.
- All non-LLM mutations are deterministic for a configured seed.
- Observation noise cannot silently mutate stable IDs, timestamps, protected material facts, checksums, or truth provenance.
- The current dirty workspace contains related calibration/resilience work and is used in place with the user's explicit instruction to continue; do not discard or overwrite unrelated changes.
- The API-spend ceiling remains $25; this implementation performs no paid calibration call.

---

### Task 1: Source action contract and replay

**Files:**
- Create: `src/source_actions.py`
- Test: `tests/test_source_actions.py`

**Interfaces:**
- Produces: `SourceAction`, `write_actions(path, actions)`, `read_actions(path)`, and `replay_actions(actions)`.
- `SourceAction` fields match the approved design and serialize with `to_dict()`.

- [ ] **Step 1: Write failing contract and replay tests**

Cover create/update/redeliver/delete ordering, stable identity, revision rules, checksum preservation for redelivery, and final-state reconstruction.

- [ ] **Step 2: Run the focused tests and confirm RED**

Run: `pytest -q tests/test_source_actions.py`

Expected: import failure because `source_actions` does not exist.

- [ ] **Step 3: Implement the minimal action model**

Implement a frozen dataclass that validates operation, revision, timestamps, and required IDs. Generate deterministic action IDs from source/object/revision/operation/observed timestamp when not supplied. Replay actions in `(observed_at, action_id)` order and reject revision regressions or invalid update/delete targets.

- [ ] **Step 4: Run focused tests and confirm GREEN**

Run: `pytest -q tests/test_source_actions.py`

Expected: all source-action tests pass.

### Task 2: Seeded realism policy and source adapters

**Files:**
- Create: `src/source_realism.py`
- Create: `config/source_realism.yaml`
- Test: `tests/test_source_realism.py`

**Interfaces:**
- Consumes: `SourceAction` from Task 1.
- Produces: `RealismPolicy.load(path)`, `adapt_export(export_dir, policy, seed) -> list[SourceAction]`, `degrade_transcript(text, seed, protected_terms)`, and `messiness_features(actions)`.

- [ ] **Step 1: Write failing adapter tests**

Build a synthetic temporary OrgForge export containing Slack arrays, a Jira issue with comments, a Confluence page, a Zoom transcript, EML, Salesforce JSON, Zendesk JSON, and Git JSON. Assert durable IDs, Jira revisions, Slack native fields, deterministic output, protected-term survival, routine short/singleton activity, bot/system events, reaction/file/edit metadata, stale/redelivery behavior, transcript degradation, and no reference to the proprietary path.

- [ ] **Step 2: Run focused tests and confirm RED**

Run: `pytest -q tests/test_source_realism.py`

Expected: import failure because `source_realism` does not exist.

- [ ] **Step 3: Implement policy loading and source adaptation**

Use only the standard library plus PyYAML. Assign stable object IDs from native IDs where present and seeded hashes otherwise. Expand Jira comments into revisions, preserve EML, parse transcript turns, and create one action per mutable source object.

- [ ] **Step 4: Implement deterministic routine activity and degradation**

Add a bounded amount of low-information Slack activity, system/bot events, reactions, attachment metadata, edits, one tombstone/redelivery path, a stale issue, a tiny draft page, and transcript ASR defects. Protect configured material terms during transcript degradation.

- [ ] **Step 5: Run focused tests and confirm GREEN**

Run: `pytest -q tests/test_source_realism.py`

Expected: all realism tests pass and two runs with seed 42 serialize identically.

### Task 3: Native-ish renderers and Clearweave packaging

**Files:**
- Create: `src/source_renderers.py`
- Modify: `src/clearweave_corpus.py`
- Replace/extend: `tests/test_clearweave_corpus.py`

**Interfaces:**
- Consumes: action stream and replay state from Tasks 1–2.
- Produces: `render_raw_object(system, object_state)`, `render_inbox_object(system, object_state)`, and `export_corpus(export_dir, output_dir, seed=42)`.

- [ ] **Step 1: Write failing native-shape package tests**

Assert Slack raw output is a channel envelope with `channel/users/messages/threads/state`; Slack inbox is a channel transcript; Jira inbox is an issue export; Confluence does not receive a generic pretty-JSON wrapper; EML remains EML; daily deliveries are action JSON; manifest entries cover raw and inbox files with object/revision/operation/timestamps/truth IDs/checksums; provenance contains `source_actions.jsonl`.

- [ ] **Step 2: Run package tests and confirm RED**

Run: `pytest -q tests/test_clearweave_corpus.py`

Expected: assertions fail against the current generic JSON renderer.

- [ ] **Step 3: Implement renderer registry**

Render source-specific raw snapshots and inbox text. Group Slack replay state by channel, separate top-level messages from replies, preserve system/bot/file/reaction/edit fields, and resolve synthetic display names where available. Keep unknown binary/text sources raw-only.

- [ ] **Step 4: Rework exporter around source actions**

Write `raw/`, per-day `deliveries/`, `inbox/`, `provenance/source_actions.jsonl`, manifest, copied simulation events/resilience files, and unreviewed gold candidates. Use relative paths in provenance so packages remain movable.

- [ ] **Step 5: Run package tests and confirm GREEN**

Run: `pytest -q tests/test_clearweave_corpus.py`

Expected: all package tests pass.

### Task 4: Synthetic structural examples

**Files:**
- Create: `examples/source_realism/README.md`
- Create: `examples/source_realism/slack/channel-export.json`
- Create: `examples/source_realism/jira/issue-export.json`
- Create: `examples/source_realism/confluence/page-export.json`
- Create: `examples/source_realism/transcripts/meeting-export.json`
- Create: `examples/source_realism/email/thread.eml`
- Create: `examples/source_realism/replay/source-actions.jsonl`
- Test: `tests/test_source_examples.py`

**Interfaces:**
- Examples are documentation/fixtures only and are not runtime content templates.

- [ ] **Step 1: Write failing example-boundary tests**

Assert every example is valid UTF-8, uses the synthetic classification, contains no absolute proprietary path, has no secret-like tokens, parses where applicable, and exhibits the documented source structures.

- [ ] **Step 2: Run focused tests and confirm RED**

Run: `pytest -q tests/test_source_examples.py`

Expected: failure because examples do not exist.

- [ ] **Step 3: Add independently authored synthetic examples**

Use fictional profile data already present in OrgForge and generic source conventions. Include an unresolved Slack post, thread reply, bot event, reaction, attachment metadata, edited message, stale Jira issue, Confluence draft revision, degraded transcript, quoted email, and create/update/redeliver/delete replay actions.

- [ ] **Step 4: Run focused tests and confirm GREEN**

Run: `pytest -q tests/test_source_examples.py`

Expected: all example tests pass.

### Task 5: Corpus readiness validator and no-cost fixture pass

**Files:**
- Create: `src/corpus_validator.py`
- Create: `src/build_source_realism_fixture.py`
- Test: `tests/test_corpus_validator.py`

**Interfaces:**
- Produces: `validate_corpus(corpus_dir, require_run_health=False) -> ValidationReport`, CLI exit status, and a no-cost fixture builder that writes an OrgForge-shaped input and packages it through the production exporter.

- [ ] **Step 1: Write failing readiness tests**

Assert valid fixture passes privacy, identity, temporal, native-shape, manifest, replay, messiness, semantic-safety, and UTF-8 checks. Corrupt checksum, revision, parent relationship, or manifest coverage independently and assert a precise failure.

- [ ] **Step 2: Run focused tests and confirm RED**

Run: `pytest -q tests/test_corpus_validator.py`

Expected: import failure because validator does not exist.

- [ ] **Step 3: Implement validator and fixture builder**

Return structured check results and counts. The CLI exits nonzero on any failed required check. `--require-run-health` requires completed run status with zero unrecovered failures; fixture mode omits only that paid-run check.

- [ ] **Step 4: Run focused tests and confirm GREEN**

Run: `pytest -q tests/test_corpus_validator.py`

Expected: all validator tests pass.

- [ ] **Step 5: Build and validate a no-cost corpus**

Run:

```bash
python src/build_source_realism_fixture.py export/source-realism-fixture-input export/source-realism-fixture-corpus --seed 42
python src/corpus_validator.py export/source-realism-fixture-corpus
```

Expected: validator reports every no-cost gate passed.

### Task 6: Reduce forced conversational neatness

**Files:**
- Modify: `src/normal_day.py`
- Modify: `src/source_realism.py`
- Test: `tests/test_source_realism.py`

**Interfaces:**
- Produces: `conversation_shape_directive(seed_material) -> str`, used by Slack/Zoom generation prompts.

- [ ] **Step 1: Write failing conversation-shape tests**

Assert deterministic directives include multiple possible outcomes across seeds: resolved, unresolved, interrupted/moved elsewhere, and reaction/acknowledgement-heavy. Assert no directive requires a decision or explicit owner in every meeting.

- [ ] **Step 2: Run focused test and confirm RED**

Run: `pytest -q tests/test_source_realism.py -k conversation_shape`

Expected: failure because helper does not exist.

- [ ] **Step 3: Implement helper and integrate prompts**

Replace unconditional Zoom decision/wrap-up requirements and rigid Slack resolution behavior with the deterministic outcome directive while preserving participant/topic context and JSON output format.

- [ ] **Step 4: Run focused and normal-day tests**

Run: `pytest -q tests/test_source_realism.py tests/test_normal_day.py`

Expected: all selected tests pass.

### Task 7: Full verification and calibration readiness report

**Files:**
- Modify if needed: implementation/tests above
- Create: `docs/source-realism-calibration-runbook.md`

**Interfaces:**
- Runbook provides the exact next five-day command, packaging command, validator command, cost calculation, stop conditions, and expected output locations.

- [ ] **Step 1: Run syntax, style, and full relevant test suite**

Run:

```bash
python -m compileall -q src tests
ruff check src tests
pytest -q tests/test_source_actions.py tests/test_source_realism.py tests/test_clearweave_corpus.py tests/test_source_examples.py tests/test_corpus_validator.py tests/test_normal_day.py tests/test_llm_resilience.py tests/test_run_resilience.py
git diff --check
```

Expected: zero failures/errors.

- [ ] **Step 2: Rebuild and validate the no-cost fixture from scratch**

Use explicit fixture paths under `export/`, inspect counts and representative source shapes, and confirm the validator exits zero.

- [ ] **Step 3: Write the calibration runbook**

Document fresh-output and Mongo reset requirements, `env -u OPENAI_API_KEY`, five-day environment variables, resilience status checks, packaging with seed 42, strict validation with run health, conservative all-Sol token pricing, and the $25 stop rule.

- [ ] **Step 4: Review requirements against the approved spec**

Confirm privacy, identity, temporal integrity, native shape, coverage, replay, messiness, semantic safety, run health handling, and spend handling each have implementation and evidence.
