# Clearweave Semantic Realism v6 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a deterministic 180-day v6 corpus that passes semantic-realism gates for chronology, diversity, discourse, lineage, lifecycle, email structure, and source balance.

**Architecture:** Preserve the existing `SourceAction` replay contract. Correct adaptation and timestamp mapping at the source, apply bounded policy-v3 observation mutations, measure schema-v2 quality distributions, then render a full raw/replay package with a sampled semantic inbox.

**Tech Stack:** Python 3.11, pytest, PyYAML, Python standard-library email/parser APIs, Docker Compose, JSON/JSONL/EML/Markdown.

## Global Constraints

- Do not read or copy proprietary source content, names, vocabulary, or identifiers.
- Do not make OpenAI API calls; v6 is derived deterministically from the frozen 180-day export.
- Do not overwrite or delete v5.
- Preserve stable source identity, action replay, classification, truth attribution, and manifest checksums.
- Policy-v2 packages remain backward compatible.
- Write each behavioral test before production code and observe the expected failure.

---

### Task 1: Correct temporal normalization and source cadence

**Files:**
- Modify: `src/source_realism.py`
- Test: `tests/test_source_realism.py`
- Test: `tests/test_realism_scorecard.py`

**Interfaces:**
- Consumes: `normalize_observations_to_window(actions, start_at, target_days)`.
- Produces: mapped actions that preserve each original `observed_at - effective_at` delta and deterministic source-aware cadence.

- [ ] Add a failing test with stale, same-time, and future-effective actions; assert the original timestamp delta is preserved exactly after mapping.
- [ ] Add a failing test with human-system and Datadog actions; assert human-system timestamps stay within bounded weekday/work-hour distributions while Datadog remains continuous.
- [ ] Run `pytest -q tests/test_source_realism.py -k normalization` and confirm the new tests fail because effective times are unchanged and cadence is flattened.
- [ ] Replace continuous-second compression with calendar-day mapping that preserves time of day, shifts both timestamps by the same offset, and applies deterministic source cadence without violating per-object revision order.
- [ ] Run the focused tests and existing replay-order tests until green.

### Task 2: Expand exact truth-lineage matching

**Files:**
- Modify: `src/source_realism.py`
- Test: `tests/test_source_realism.py`

**Interfaces:**
- Consumes: `simulation_events.jsonl`, source-relative paths, source object IDs, Slack thread/root IDs, causal-chain IDs.
- Produces: exact event-ID sets attached to adapted actions without fuzzy topic matching.

- [ ] Extend the synthetic fixture with one event linking Jira, PR, Slack thread, and email path identifiers.
- [ ] Add failing assertions that Jira, Git, every message in the matching Slack thread, and the matching email carry the event ID while unrelated records remain unlinked.
- [ ] Run the focused lineage test and confirm Slack/email assertions fail under exact-object-only lookup.
- [ ] Build a normalized exact-key event index from artifact values, causal chains, source-relative path tails, and thread IDs.
- [ ] Update source adapters to query all source-specific exact keys and inherit verified root lineage into generated replies.
- [ ] Run source-realism and replay tests until green.

### Task 3: Repair and thread EML deterministically

**Files:**
- Modify: `src/source_realism.py`
- Modify: `src/source_renderers.py` only if serialization requires it
- Test: `tests/test_source_realism.py`
- Test: `tests/test_source_renderers.py`

**Interfaces:**
- Consumes: adapted email `raw_eml`, object identity, observed timestamp, normalized subject and participants.
- Produces: RFC 5322 EML with stable Message-ID, parseable Date, routing headers, thread headers, and bounded valid attachments.

- [ ] Add a three-message fixture with ISO dates, repeated normalized subject, no IDs, and no routing headers.
- [ ] Add failing assertions for parseable dates, unique stable Message-IDs, `In-Reply-To`, `References`, routing headers, body preservation, and a valid attachment in the deterministic selected message.
- [ ] Run focused email tests and confirm they fail on missing transport/thread structure.
- [ ] Add an email-normalization pass using standard-library email parsing and generation; group only exact normalized-subject/participant threads and preserve bodies.
- [ ] Run focused tests until green, including raw/inbox EML preservation.

### Task 4: Replace Slack template dilution with contextual activity and real lifecycle actions

**Files:**
- Modify: `src/observation_realism.py`
- Modify: `config/source_realism.yaml`
- Test: `tests/test_observation_realism.py`

**Interfaces:**
- Consumes: policy-v3 rates and existing Slack roots/actions.
- Produces: bounded context-derived replies, conservative non-routine texture, blocks/attachments/system records, updates, redeliveries, deletions, and a complete mutation ledger.

- [ ] Replace the v2 volume assertions with failing distribution tests for exact duplication, routine share, question share, punctuation upper bound, blocks, attachments, and empty/system records.
- [ ] Add failing lifecycle assertions: displayed edits correspond to update actions, redeliveries are byte-identical same-revision actions, and tombstones are revisioned deletes.
- [ ] Run `pytest -q tests/test_observation_realism.py -k slack` and confirm v2 fails on duplication, routine concentration, and lifecycle depth.
- [ ] Implement context extraction and combinatorial conversational moves; reduce selected roots and thread lengths; allow only short acknowledgements to repeat naturally.
- [ ] Convert selected single-revision creates into valid create/update/redeliver/delete sequences while preserving truth IDs and ordering.
- [ ] Run Slack-focused and replay tests until green.

### Task 5: Replace mechanical meeting expansion and templated PR generation

**Files:**
- Modify: `src/observation_realism.py`
- Modify: `config/source_realism.yaml`
- Test: `tests/test_observation_realism.py`

**Interfaces:**
- Consumes: source transcript turns and nearby Jira/Slack/Git context.
- Produces: discourse-boundary transcript transformations and a small varied PR lifecycle set.

- [ ] Add failing transcript tests for median/P90 word length, question share, duplicate-turn cap, factual-token preservation, and speaker diversity.
- [ ] Add failing PR tests for routine-object cap, unique title/body concentration, median body length, all lifecycle states, sparse comments, checklists, and links.
- [ ] Run focused tests and confirm fixed-word chunking and fixed PR templates fail.
- [ ] Segment transcripts at sentences/clauses into 25–60-word contributions; add bounded context-derived questions, disagreement, correction, and backchannels.
- [ ] Replace the 210-object PR routine generator with a small context-derived set and enrich existing empty bodies without changing identifiers or statuses.
- [ ] Run meeting/Git tests and replay validation until green.

### Task 6: Add schema-v2 scorecard and strict upper-bound gates

**Files:**
- Modify: `src/realism_scorecard.py`
- Modify: `src/corpus_validator.py`
- Test: `tests/test_realism_scorecard.py`
- Test: `tests/test_corpus_validator.py`

**Interfaces:**
- Produces: scorecard schema version 2 with temporal, cadence, diversity, lifecycle, email, lineage, and inbox-balance metrics.
- Preserves: schema-v1/policy-v2 validation behavior.

- [ ] Add failing unit tests for each policy-v3 release gate from the design specification, including excessive upper bounds and missing lineage/lifecycle behavior.
- [ ] Run scorecard/validator tests and confirm the scorecard lacks required fields.
- [ ] Implement privacy-safe counters: exact duplicate concentration, routine concentration, questions, blocks/attachments, turn words/speakers, PR body/title diversity, operation shares, revision-backed edits, parseable/threaded email, per-source truth share, deep truth events, and observed/effective inversion.
- [ ] Require schema-v2 gates only for manifest realism policy version 3 or higher.
- [ ] Run focused scorecard and validator tests until green.

### Task 7: Create the sampled semantic inbox profile

**Files:**
- Modify: `src/clearweave_corpus.py`
- Modify: `config/source_realism.yaml`
- Test: `tests/test_clearweave_corpus.py`

**Interfaces:**
- Consumes: full replayed source-object state.
- Produces: complete `raw/` and `deliveries/`, complete manifest coverage, and a deterministic `inbox/datadog/` sample capped at 1,000 files.

- [ ] Add a failing package test with more Datadog objects than the configured limit; assert raw/delivery counts remain complete and inbox selection is deterministic.
- [ ] Run the focused package test and confirm all Datadog records are currently emitted to inbox.
- [ ] Add a representation-aware final-object writer that always writes raw but samples Datadog only for inbox using stable object hashing.
- [ ] Record `inbox_profile` and `datadog_inbox_limit` in the manifest.
- [ ] Run package, manifest-coverage, and validator tests until green.

### Task 8: Generate and verify v6

**Files:**
- Create generated package: `export/calibration-semantic-realism-180d-clearweave-v6/`
- Create generated package README: `export/calibration-semantic-realism-180d-clearweave-v6/README.md`
- Modify: `docs/orgforge-corpus-realism-handoff.md`

**Interfaces:**
- Consumes: frozen `export/calibration-realism-180d/` and policy-v3 code.
- Produces: validated v6 package and a v5/v6 comparison.

- [ ] Run all focused tests, then `pytest -q tests` in Docker; require zero failures.
- [ ] Generate v6 with target start `2026-01-01`, 180 days, fixed seed 42, and observation realism enabled; do not expose `OPENAI_API_KEY` to the container.
- [ ] Run the strict corpus validator with `--require-run-health`; preserve failed output and stop packaging if any required gate fails.
- [ ] Compare v5 and v6 temporal, Slack, meeting, Git, email, lifecycle, truth, and source-balance metrics.
- [ ] Add a self-contained README explaining `raw/`, `inbox/`, `deliveries/`, `provenance/`, `gold/`, profile selection, and limitations.
- [ ] Update the realism handoff with verified results and retain the human-reviewed-gold limitation.
- [ ] Run `git diff --check`, verify package file counts/size/manifest/ledger, and report exact paths.

## Self-review

- Spec coverage: all eight independent review priorities map to Tasks 1–7; generation and verification are Task 8.
- Placeholder scan: no deferred implementation placeholders are present.
- Type consistency: all tasks retain `SourceAction`, existing exporter entry points, and policy-version compatibility.
- Scope: v6 observation realism only; no business regeneration, proprietary fitting, paid generation, or human gold labeling.
