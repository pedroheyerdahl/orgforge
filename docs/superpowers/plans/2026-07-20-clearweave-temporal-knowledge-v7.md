# Clearweave Temporal Knowledge v7 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic 180-day v7 corpus with no future-native knowledge, genuine source lifecycles, stronger temporal knowledge errors, and validator gates that reject v6’s leakage.

**Architecture:** Add a source-aware temporal compiler that maps actions and structured payload timestamps together. Expand mutable final snapshots into create/update lifecycles before normalization, then measure policy-v4 temporal and semantic distributions before rendering a separate v7 package.

**Tech Stack:** Python 3.13, pytest, standard-library datetime/email/JSON APIs, PyYAML, existing `SourceAction` replay and corpus renderers.

## Global Constraints

- Preserve `export/calibration-semantic-realism-180d-clearweave-v6/` unchanged.
- Keep the exact target window 2026-01-01 through 2026-06-29.
- Make no OpenAI API calls.
- Do not read or copy proprietary source bodies, names, vocabulary, identifiers, or distinctive combinations.
- Historical/audit timestamps must be at or before the action that exposes them.
- Planned dates may be future relative to an action but must remain inside the manifest window.
- Maintain stable object identity, valid revisions, byte-identical redelivery, truth lineage, and manifest checksums.
- Policy-v2/v3 corpus validation remains backward compatible; new release gates apply to policy v4.

---

### Task 1: Native timestamp classification and extraction

**Files:**
- Create: `src/native_timestamps.py`
- Test: `tests/test_native_timestamps.py`

**Interfaces:**
- Produces: `iter_native_timestamps(source_system, payload) -> Iterable[NativeTimestamp]`.
- Produces: `rebase_native_timestamps(source_system, payload, mapper) -> dict[str, Any]`.
- `NativeTimestamp` exposes `path`, `value`, and `kind` where kind is `historical` or `planned`.

- [ ] Add failing tests with nested Slack, Jira, Git, Zendesk, Datadog, Salesforce, email, and transcript timestamps. Assert audit fields are historical, due/expected-close fields are planned, and arbitrary prose is ignored.
- [ ] Run `.venv/bin/pytest -q tests/test_native_timestamps.py` and verify import/behavior failure.
- [ ] Implement immutable recursive extraction with explicit source-aware field names and RFC/epoch/ISO parsing.
- [ ] Implement payload rebasing that preserves original value representation: Slack epoch remains epoch, ISO stays ISO, date-only stays date-only, and email/transcript structured headers are handled by their normalization passes.
- [ ] Run the focused test until green.

### Task 2: One action/payload window mapping

**Files:**
- Modify: `src/source_realism.py`
- Test: `tests/test_source_realism.py`

**Interfaces:**
- Produces: `build_window_mapper(actions, start_at, target_days) -> WindowMapper`.
- Updates: `normalize_observations_to_window(..., rebase_payload=True)`.

- [ ] Add a failing fixture where Slack `ts`, nested edit timestamp, Jira update/comment dates, Git review dates, Datadog timestamps, and transcript date extend outside the window. Assert every mapped historical field preserves its relative order and is no later than the containing action.
- [ ] Add a planned Salesforce close-date assertion: it may remain after create but not after 2026-06-29.
- [ ] Run the focused tests and verify current normalization fails because payloads are unchanged.
- [ ] Extract the existing calendar compression into `WindowMapper.map_datetime()` and use it for action, effective, and payload timestamps.
- [ ] Clamp/repair per-object action order after mapping, then map payload historical timestamps no later than the repaired action time.
- [ ] Re-run normalization, email, transcript, and replay tests until green.

### Task 3: Git and mutable snapshot lifecycle adapters

**Files:**
- Modify: `src/source_realism.py`
- Test: `tests/test_source_realism.py`

**Interfaces:**
- Produces: `_adapt_git_snapshot(path, export_dir, truth_map) -> list[SourceAction]`.
- Produces: source-specific mutable snapshot expansion for Jira and Zendesk tickets.

- [ ] Add a failing Git fixture containing final merged status and two timestamped comments. Assert create is open/draft with no comments, comments appear one per update, and merged status appears only in the final update.
- [ ] Add failing Jira/Zendesk assertions that create payloads omit future `updated_at`, later comments, and final status.
- [ ] Run focused lifecycle tests and verify generic snapshot adaptation fails.
- [ ] Route Git files through `_adapt_git_snapshot`; produce create, comment updates, and final-state update with strictly increasing revisions.
- [ ] Sanitize Jira creates and split Zendesk ticket activities while retaining stable source object IDs.
- [ ] Run replay and source adaptation tests until green.

### Task 4: Policy-v4 temporal validation and scorecard

**Files:**
- Modify: `src/corpus_validator.py`
- Modify: `src/realism_scorecard.py`
- Modify: `config/source_realism.yaml`
- Test: `tests/test_corpus_validator.py`
- Test: `tests/test_realism_scorecard.py`

**Interfaces:**
- Adds scorecard schema v3 `native_temporal`, expanded `slack_threads`, `knowledge_errors`, and `semantic_templates` sections.
- Validator consumes manifest `target_start`, `target_end`, and realism policy version.

- [ ] Add a validator test built from a small package with action order valid but payload-native future dates; assert failure messages name object ID and timestamp path.
- [ ] Add scorecard tests for future-native share, terminal creates, future comments, out-of-window native dates, distinct root thread sizes, and lifecycle update coverage.
- [ ] Run tests and verify v3 scorecard/validator cannot detect the fixtures.
- [ ] Implement aggregate counters and detailed validator diagnostics using `native_timestamps.py`.
- [ ] Require zero historical future-native timestamps and zero out-of-window structured dates for policy v4.
- [ ] Run validator against v6 and save evidence that policy-v4 diagnostics detect the known leakage without changing v6 compatibility.

### Task 5: Slack chronology and thread distribution

**Files:**
- Modify: `src/observation_realism.py`
- Modify: `config/source_realism.yaml`
- Test: `tests/test_observation_realism.py`

**Interfaces:**
- Policy v4 controls timestamp jitter, off-hours cadence, and thread-length mixture.

- [ ] Add failing tests that count unique create object IDs only and assert bounded all-root and threaded-only P90/max distributions, fewer than 25% of nonempty threads at any one length, rounded timestamp share below 25%, and Slack off-hours share between 5% and 25%.
- [ ] Run the Slack tests and verify v3 fails rounded seconds and clustered thread lengths.
- [ ] Apply deterministic second/microsecond jitter before deriving `ts`; preserve reply-after-root ordering and same-thread mapping.
- [ ] Replace fixed acknowledgement/long groups with a weighted 1–2, 3–8, and 9–24 reply mixture derived from root context.
- [ ] Run Slack lifecycle, scorecard, and replay tests until green.

### Task 6: Meeting and Git semantic long tails

**Files:**
- Modify: `src/observation_realism.py`
- Modify: `src/realism_scorecard.py`
- Test: `tests/test_observation_realism.py`
- Test: `tests/test_realism_scorecard.py`

**Interfaces:**
- Adds semantic scaffold concentration metrics based on normalized repeated 5-grams and section signatures.

- [ ] Add failing corpus fixtures asserting meeting median turns at least 45, P90 at least 100, selected maximum at least 160, Git review-comment maximum at least 8, and common semantic scaffold concentration below 50%.
- [ ] Run focused tests and verify v3’s 27/38 meeting shape, four-comment Git cap, and fixed scaffold fail.
- [ ] Generate a mixed meeting distribution by contextually splitting long source turns, reusing source-local terms, and adding varied interruptions/backchannels/questions without one repeated phrase family.
- [ ] Build Git bodies from optional source-derived sections and extend only a small review tail to 5–12 comments; preserve sparse median behavior.
- [ ] Add and enforce semantic scaffold metrics, then run focused tests until green.

### Task 7: Temporal knowledge-error scenarios and gold candidates

**Files:**
- Create: `src/knowledge_scenarios.py`
- Modify: `src/clearweave_corpus.py`
- Modify: `src/realism_scorecard.py`
- Test: `tests/test_knowledge_scenarios.py`
- Test: `tests/test_clearweave_corpus.py`

**Interfaces:**
- Produces: `apply_knowledge_scenarios(actions, seed) -> tuple[list[SourceAction], list[dict]]`.
- Writes: `provenance/knowledge_scenarios.jsonl` and `gold/temporal_candidates.jsonl`.

- [ ] Add failing tests for stale document, superseded owner, provisional-as-final, delayed correction, partial correction, and unresolved conflict scenarios spanning at least two sources and three days.
- [ ] Assert every scenario has machine-verifiable expected state by day, exact evidence action IDs, and `review_status: pending_human_review`.
- [ ] Run focused tests and verify no scenario layer exists.
- [ ] Implement deterministic scenarios using existing truth-linked anchors; source artifacts carry natural source content while labels stay in provenance/gold.
- [ ] Add policy-v4 minimum counts and verify temporal replay exposes the expected changing state.

### Task 8: Generate, package, and verify v7

**Files:**
- Create: `export/calibration-temporal-knowledge-180d-clearweave-v7/`
- Create: `export/calibration-temporal-knowledge-180d-clearweave-v7/README.md`
- Modify: `docs/orgforge-corpus-realism-handoff.md`

**Interfaces:**
- Consumes frozen `export/calibration-realism-180d/`, seed 42, 180 days, target start 2026-01-01.

- [ ] Run the complete test suite and require zero failures.
- [ ] Run an in-memory v7 diagnostic and require zero policy-v4 temporal/semantic gate failures before writing package files.
- [ ] Generate v7 without exposing `OPENAI_API_KEY`; preserve any failed output for diagnosis rather than deleting it.
- [ ] Run `src/corpus_validator.py <v7> --require-run-health` and require every check to pass.
- [ ] Independently scan all action payload timestamps and require zero historical timestamps after their action, zero structured dates outside the window, and zero future comments/final state in creates.
- [ ] Spot-check Git, Jira, Slack, Zoom, and Zendesk create/update sequences.
- [ ] Write the package README explaining final snapshots, incremental replay, temporal guarantees, scenario labels, and the pending-human-review limitation.
- [ ] Update the realism handoff with v6/v7 metrics and run `git diff --check`.

## Self-review

- Spec coverage: the release-blocking chronology defect is covered by Tasks 1–4; Slack, meeting, Git, and knowledge-error findings are covered by Tasks 5–7; packaging is Task 8.
- Placeholder scan: no deferred implementation placeholders remain.
- Type consistency: all lifecycle output remains `SourceAction`; shared timestamp APIs are defined in Task 1 and consumed by Tasks 2 and 4.
- Scope: no source-business regeneration, proprietary fitting, paid generation, or false human-review claim.
