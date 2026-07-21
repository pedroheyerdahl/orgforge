# Clearweave v8 Distribution Realism Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and install a deterministic 180-day v8 corpus that removes the five remaining generator-shaped realism patterns without regressing v7.1 temporal integrity.

**Architecture:** Introduce deterministic distribution helpers at the existing knowledge, observation, and source-realism layers, then expose semantic and distribution metrics in scorecard schema 4. Build into staging and promote only after strict validation.

**Tech Stack:** Python 3, pytest, YAML, JSON/JSONL, existing OrgForge corpus pipeline.

## Global Constraints

- Do not call an LLM or read proprietary source bodies.
- Preserve the declared 180-day window and all v7.1 native timestamp and locator invariants.
- Keep generator controls and expected labels out of raw and inbox artifacts.
- Use deterministic seed-based sampling and stable object identities.
- Replace the installed Clearweave corpus only after staged strict validation passes.

---

### Task 1: Heterogeneous knowledge scenarios

**Files:**
- Modify: `tests/test_knowledge_scenarios.py`
- Modify: `src/knowledge_scenarios.py`

**Interfaces:**
- Consumes: `apply_knowledge_scenarios(actions: list[SourceAction], seed: int)`
- Produces: the same tuple return type with varied source-native evidence arcs and provenance labels.

- [ ] Add tests asserting varied category counts, evidence counts, durations, day counts, source combinations, all six target systems, and unresolved arcs without final corrections.
- [ ] Run the focused test and confirm it fails against the fixed six-by-four loop.
- [ ] Implement the deterministic scenario planner and source-specific action builders.
- [ ] Run the focused test and confirm it passes.

### Task 2: PR, meeting, and Slack distribution realism

**Files:**
- Modify: `tests/test_observation_realism.py`
- Modify: `src/observation_realism.py`
- Modify: `config/source_realism.yaml`

**Interfaces:**
- Consumes: `apply_observation_realism(actions, policy, seed)`
- Produces: policy-v5 actions with compositional PR bodies and meeting turns, smooth Slack thread lengths, and stretched Git terminal lifecycles.

- [ ] Add tests for PR normalized five-gram concentration and lifecycle P90, meeting normalized-prefix concentration, and Slack thread-size smoothness.
- [ ] Run the focused tests and confirm each fails for the intended v7 behavior.
- [ ] Implement compositional text generation, terminal update scheduling, and broad thread-size sampling.
- [ ] Run the focused tests and confirm they pass.

### Task 3: Continuous Datadog activity

**Files:**
- Modify: `tests/test_source_realism.py`
- Modify: `src/source_realism.py`

**Interfaces:**
- Consumes: `augment_actions_to_span(actions, target_days, seed)`
- Produces: at least one Datadog action on every declared day.

- [ ] Add a test asserting 180 distinct Datadog observation days.
- [ ] Run it and confirm the current 150-day behavior fails.
- [ ] Add deterministic daily low-volume activity records.
- [ ] Run the test and confirm it passes.

### Task 4: Scorecard schema 4 gates

**Files:**
- Modify: `tests/test_realism_scorecard.py`
- Modify: `tests/test_clearweave_corpus.py`
- Modify: `src/realism_scorecard.py`
- Modify: `src/clearweave_corpus.py`
- Modify: `src/corpus_validator.py`

**Interfaces:**
- Consumes: final actions, replay state, scenario labels, declared window.
- Produces: scorecard schema 4 and policy-v5 release errors for all five dimensions.

- [ ] Add failing tests for each new metric and gate plus policy/schema versioning.
- [ ] Implement normalized n-gram helpers, lifecycle and distribution metrics, and release gates.
- [ ] Run focused scorecard/exporter/validator tests and confirm they pass.

### Task 5: Staged v8 build and installation

**Files:**
- Create: `export/calibration-distribution-realism-180d-clearweave-v8/`
- Replace after validation: `<clearweave-checkout>/sources/`
- Modify: `docs/orgforge-corpus-realism-handoff.md`

**Interfaces:**
- Consumes: current 180-day source export and policy-v5 pipeline.
- Produces: canonical v8 package and byte-identical installed Clearweave corpus.

- [ ] Run all focused tests and then the complete test suite.
- [ ] Build v8 in a fresh staging directory without API calls.
- [ ] Run strict validation and independently inspect all five metrics plus chronology and raw-control leakage.
- [ ] Update the package README and handoff with measured v8 results and the remaining human-review limitation.
- [ ] Promote the staged package to canonical v8 and replace Clearweave `sources` with a recoverable backup boundary.
- [ ] Re-run strict installed validation and compare canonical/installed manifest checksums.
