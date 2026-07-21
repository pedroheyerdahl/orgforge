# Observation Realism V5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the frozen 180-day OrgForge truth export into a distribution-aware, realistically incomplete Clearweave v5 observation corpus without changing protected business facts.

**Architecture:** Add a deterministic observation-realism engine between source adaptation and replay. It mutates only observation payloads/timing, emits an append-only mutation ledger and scorecard, preserves stable source identities and truth-event links, and leaves the frozen literal export untouched. Packaging continues to produce native snapshots, readable documents, daily replay actions, provenance, and gold candidates.

**Tech Stack:** Python 3.12, dataclasses, hashlib/random/json, existing OrgForge `SourceAction` replay model, pytest, Docker Compose.

## Global Constraints

- Never read proprietary source content at runtime or copy proprietary text, identifiers, filenames, vocabulary, or exact fingerprints.
- Preserve `synthetic_non_confidential` classification, stable object identity, truth-event links, and protected major facts.
- Use deterministic seeds for every mutation; no paid model call is required for v5.
- Redelivery preserves revision and payload; updates increment revision; ordered replay must reconstruct final state.
- Distribution gates use broad synthetic bands and reject Day-1 concentration, uniformly polished Slack, uniformly short meetings, and uniformly successful Git activity.
- The frozen input remains `export/calibration-realism-180d`; output is a new `export/calibration-realism-180d-clearweave-v5` directory.

---

### Task 1: Distribution-aware timeline normalization

**Files:**
- Modify: `src/source_realism.py`
- Test: `tests/test_source_realism.py`

**Interfaces:**
- Consumes: `normalize_observations_to_window(actions, start_at, target_days)`
- Produces: the same function with monotonic linear time compression and deterministic delivery jitter.

- [ ] Add a failing test with actions spanning beyond the target window and assert they occupy multiple target days, remain ordered, and preserve revision order.
- [ ] Run the focused test and confirm the current Day-1 fallback fails it.
- [ ] Replace out-of-window Day-1 placement with deterministic monotonic compression from the observed source range into the target range, reserving small deterministic jitter.
- [ ] Run focused and full source-realism tests.

### Task 2: Deterministic observation-realism engine and ledger

**Files:**
- Create: `src/observation_realism.py`
- Create: `tests/test_observation_realism.py`
- Modify: `config/source_realism.yaml`

**Interfaces:**
- Produces: `ObservationMutation`, `ObservationRealismPolicy`, and `apply_observation_realism(actions, policy, seed) -> tuple[list[SourceAction], list[ObservationMutation]]`.
- Mutators operate on Slack, Zoom, Git, Jira/Confluence, email, and operational records without changing object IDs or truth-event IDs.

- [ ] Add failing tests proving deterministic output, stable truth links, valid replay, ledger hash attribution, and nonuniform Slack/meeting/Git transformations.
- [ ] Implement policy loading and stable hash-based selection.
- [ ] Implement Slack variation: punctuation damage, short acknowledgements, sparse reactions/files/edits/bot metadata, links/mentions/code fragments, and additional threaded replies.
- [ ] Implement transcript variation: turn splitting, backchannels, filler, interruptions, and mixed meeting sizes while preserving original words.
- [ ] Implement Git variation for unprotected/routine PR observations: drafts, stale/closed states, sparse comments, links, checklists, CI and review questions.
- [ ] Implement sparse optional-field and envelope variation for other sources.
- [ ] Emit one content-hash mutation-ledger record per changed or added action.
- [ ] Run focused tests and replay every transformed fixture.

### Task 3: Realism scorecard and strict gates

**Files:**
- Create: `src/realism_scorecard.py`
- Create: `tests/test_realism_scorecard.py`
- Modify: `src/corpus_validator.py`
- Modify: `tests/test_corpus_validator.py`

**Interfaces:**
- Produces: `build_realism_scorecard(actions) -> dict` and `validate_realism_scorecard(scorecard) -> list[str]`.
- Validator consumes packaged `provenance/realism_scorecard.json` and `provenance/realism_ledger.jsonl`.

- [ ] Add failing tests for Slack length/punctuation/native fields/thread depth, transcript turn mixture, Git lifecycle mixture, temporal concentration, and ledger presence.
- [ ] Implement scorecard metrics without reading source bodies outside the synthetic corpus.
- [ ] Implement broad hard gates that detect the known pristine patterns and a single-day delivery concentration above 50%.
- [ ] Integrate the realism check into strict corpus validation.
- [ ] Run scorecard and validator tests.

### Task 4: Packaging integration and less-uniform readable projection

**Files:**
- Modify: `src/clearweave_corpus.py`
- Modify: `src/source_renderers.py`
- Modify: `tests/test_clearweave_corpus.py`
- Create: `tests/test_source_renderers.py`

**Interfaces:**
- Packaging calls `apply_observation_realism` after normalization/augmentation and before replay.
- Writes `provenance/realism_ledger.jsonl` and `provenance/realism_scorecard.json`.
- Readable projection remains `inbox/` for compatibility; naming changes are outside this realism pass.

- [ ] Add failing packaging tests for ledger/scorecard provenance and deterministic output.
- [ ] Add failing renderer tests requiring multiple Jira/record document shapes and preservation of evidence-bearing fields.
- [ ] Integrate the realism engine and provenance writers.
- [ ] Introduce deterministic source-specific rendering variants instead of one universal Markdown template.
- [ ] Run packaging, renderer, and validator tests.

### Task 5: Generate and validate v5

**Files:**
- Output: `export/calibration-realism-180d-clearweave-v5/`

**Interfaces:**
- Consumes the frozen literal export and policy version 2.
- Produces a complete replayable v5 package.

- [ ] Run the exporter with seed 42, target start `2026-01-01`, and 180 target days.
- [ ] Run strict validation with run-health required.
- [ ] Verify all 180 delivery days exist, no day contains more than half of all actions, and ordered replay reconstructs final state.
- [ ] Compare v4 and v5 scorecards and document material realism improvements.

### Task 6: Final repository verification

**Files:**
- Modify: `docs/orgforge-corpus-realism-handoff.md` only if implementation status needs an appended result section.

**Interfaces:**
- Produces fresh test, validation, and package evidence.

- [ ] Run the complete Dockerized pytest suite.
- [ ] Run `git diff --check`.
- [ ] Re-read the handoff definition of done and report satisfied versus intentionally deferred human-review requirements.
- [ ] Preserve v4 until v5 passes; remove no corpus without a separate cleanup request.
