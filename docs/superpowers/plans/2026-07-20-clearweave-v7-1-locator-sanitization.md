# Clearweave v7.1 Locator Sanitization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebase date-bearing source locators and prevent internal generator/evaluation controls from appearing in source-visible artifacts.

**Architecture:** Add a deterministic action-level locator alias pass after timeline normalization, and a renderer-level source-visible payload projection. Extend policy-v4 validation so stale paths/IDs and raw control leakage cannot regress.

**Tech Stack:** Python 3.13, pytest, standard-library datetime/JSON/path APIs, existing `SourceAction` replay and corpus packaging.

## Global Constraints

- Preserve the exact 2026-01-01 through 2026-06-29 window.
- Make no OpenAI API calls.
- Preserve revision order, redelivery identity, truth lineage, and checksums.
- Do not rewrite free prose or proprietary reference content.
- Keep generation controls in provenance only, never raw/inbox artifacts.
- Stage and validate before replacing Clearweave's installed `sources/` folder.

---

### Task 1: Date-bearing locator rebasing

**Files:**
- Create: `src/source_locators.py`
- Modify: `src/clearweave_corpus.py`
- Test: `tests/test_source_locators.py`

**Interfaces:**
- Produces: `rebase_source_locators(actions: list[SourceAction]) -> list[SourceAction]`.
- Produces: `iter_locator_dates(action: SourceAction) -> Iterable[LocatorDate]` for validator diagnostics.

- [ ] Write a failing test with Zoom, Slack, email, and Zendesk source paths dated after June 29; assert paths, path-derived IDs, `meeting_id`, and filename metadata use each object's create date across revisions.
- [ ] Run `.venv/bin/pytest -q tests/test_source_locators.py` and verify the missing behavior fails.
- [ ] Implement stable per-object aliases and recursive locator-field rewriting without touching prose.
- [ ] Insert the pass after the second window normalization and before knowledge-scenario generation.
- [ ] Run locator, replay, exporter, and knowledge-scenario tests until green.

### Task 2: Source-visible payload projection

**Files:**
- Modify: `src/source_renderers.py`
- Test: `tests/test_source_renderers.py`
- Test: `tests/test_clearweave_corpus.py`

**Interfaces:**
- Produces: `source_visible_payload(payload: dict[str, Any]) -> dict[str, Any]`.
- Raw and inbox renderers consume the projected payload; provenance actions remain unchanged.

- [ ] Write failing raw Slack, Git, Confluence, and Zoom tests containing nested generator/control keys.
- [ ] Assert source-visible output omits controls and preserves ordinary source fields and correction prose.
- [ ] Run focused renderer tests and verify leaked keys cause failure.
- [ ] Implement immutable recursive projection and route all raw/inbox renderers through it.
- [ ] Run renderer and package tests until green.

### Task 3: Policy-v4 regression gates

**Files:**
- Modify: `src/corpus_validator.py`
- Modify: `src/realism_scorecard.py`
- Test: `tests/test_corpus_validator.py`
- Test: `tests/test_realism_scorecard.py`

**Interfaces:**
- Adds `native_temporal.locator_date_mismatches` and `native_temporal.locator_dates_outside_window`.
- Adds a required `source_visible_controls` validator check for policy v4.

- [ ] Add failing scorecard and packaged-corpus fixtures with mismatched path/ID dates and raw control fields.
- [ ] Run focused tests and verify policy v4 currently accepts both defects.
- [ ] Count locator dates with exact object/path diagnostics and enforce zero mismatches/outside-window values.
- [ ] Scan raw/inbox JSON and Slack envelopes for forbidden control keys without treating provenance as source-visible.
- [ ] Run validator and scorecard tests until green.

### Task 4: Regenerate and install v7.1

**Files:**
- Rebuild: `export/calibration-temporal-knowledge-180d-clearweave-v7/`
- Update: `export/calibration-temporal-knowledge-180d-clearweave-v7/README.md`
- Update: `docs/orgforge-corpus-realism-handoff.md`
- Replace after validation: `<clearweave-checkout>/sources/`

**Interfaces:**
- Consumes frozen `export/calibration-realism-180d/`, seed 42, target start 2026-01-01, target days 180.

- [ ] Run the full test suite and require zero failures.
- [ ] Build to a staged sibling folder without API credentials or network calls.
- [ ] Run strict validation and an independent audit requiring zero locator mismatches and zero raw control keys.
- [ ] Write the package README and handoff metrics.
- [ ] Preserve the installed Clearweave corpus, replace it with the validated staged package, and validate the installed copy.
- [ ] Remove only superseded staged/backup folders after successful installed-copy validation.
- [ ] Run `git diff --check` and report exact package paths and remaining benchmark limitations.

## Self-review

- Spec coverage: locator dates, path-derived IDs, filenames, raw controls, validation, staged replacement, and remaining-scope boundary are each covered.
- Placeholder scan: no deferred implementation placeholders or ambiguous follow-up steps remain.
- Type consistency: locator functions consume and return `SourceAction`; renderer projection consumes and returns dictionaries.
- Scope: scenario diversity and broader semantic texture work are explicitly excluded from this surgical pass.
