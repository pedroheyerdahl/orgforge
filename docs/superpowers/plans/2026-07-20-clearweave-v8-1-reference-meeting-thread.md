# Clearweave v8.1 Reference, Meeting, and Thread Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce and install a v8.1 corpus whose knowledge sidecars reference final actions, whose meetings omit the three stock prompt families, and whose Slack metrics are channel-scoped.

**Architecture:** Preserve stable scenario action keys through observation transforms and resolve them immediately before sidecar output. Replace fixed meeting phrase lists with a deterministic composer, and key every scorecard thread aggregation by channel plus timestamp. Enforce all three contracts in tests and the corpus validator.

**Tech Stack:** Python 3, pytest, JSON/JSONL, existing OrgForge corpus pipeline.

## Global Constraints

- No API calls and no proprietary source content.
- Preserve the 2026-01-01 through 2026-06-29 window and all v8 chronology gates.
- Keep evaluation controls out of raw and inbox artifacts.
- Build and validate a clean package before replacing Clearweave sources.

---

### Task 1: Finalize and validate scenario references

**Files:** `src/knowledge_scenarios.py`, `src/clearweave_corpus.py`, `src/corpus_validator.py`, `tests/test_knowledge_scenarios.py`, `tests/test_clearweave_corpus.py`, `tests/test_corpus_validator.py`

- [ ] Add failing tests proving transformed scenario IDs are stale and malformed sidecars fail validation.
- [ ] Add stable evidence keys and a finalization function that resolves final actions and recomputes derived metadata.
- [ ] Add the required validator check and make focused tests pass.

### Task 2: Replace meeting phrase families

**Files:** `src/observation_realism.py`, `src/realism_scorecard.py`, `tests/test_observation_realism.py`, `tests/test_realism_scorecard.py`

- [ ] Add a failing corpus-scale test for the three reported prompt families.
- [ ] Replace fixed question and continuation lists with deterministic compositional turns.
- [ ] Add scorecard counts and a zero-occurrence schema-v4 release gate.

### Task 3: Scope Slack thread metrics by channel

**Files:** `src/realism_scorecard.py`, `tests/test_realism_scorecard.py`

- [ ] Add a failing test with identical root timestamps in different channels.
- [ ] Key all thread aggregates by channel identity and timestamp.
- [ ] Verify maximum, histogram, P90, orphan, and collision metrics.

### Task 4: Rebuild and promote v8.1

**Files:** `export/calibration-reference-integrity-180d-clearweave-v8.1/`, `<clearweave-checkout>/sources/`, package README, realism handoff.

- [ ] Run the full test suite and build a fresh local package.
- [ ] Run independent reference, meeting-family, and channel-thread audits plus the full validator.
- [ ] Promote with a recoverable v8 backup, verify byte parity, and validate the installed package.
