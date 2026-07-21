# Clearweave v7.1 locator and native-output sanitization design

**Date:** 2026-07-20
**Status:** Approved for implementation

## Goal

Remove visible timeline contradictions from date-bearing paths and path-derived identifiers, and prevent generator/evaluation controls from leaking into native raw or inbox artifacts, without changing the business simulation or widening the work into another realism rebuild.

## Verified defect

The v7 action timeline and native timestamp fields are correct, but 4,909 create payloads retain post-window dates in `source_path`: 4,098 Slack, 599 email, 175 Zendesk, and 37 Zoom. Zoom object IDs, `meeting_id` values, and rendered filenames can carry the same stale dates. Raw source renderers also expose internal fields such as `synthetic_routine`, `correction_scope`, and `supersedes`.

The root cause is that normalization treats paths and identities as opaque strings, while raw renderers serialize the complete internal payload.

## Locator rebasing

Add a deterministic post-normalization locator pass. For each `(source_system, object_id)` history, the create action's rebased observation date is authoritative.

- Replace full ISO date tokens in `source_path` with the create date.
- Replace full ISO date tokens in path-derived object IDs and matching native ID fields, including `meeting_id`, with the create date.
- Reuse the same object alias across every revision and redelivery.
- Rebase date tokens in filename metadata without rewriting free prose.
- Preserve revisions, operations, truth-event links, and byte-identical redelivery behavior.
- Run this pass before knowledge scenarios so gold evidence action IDs are calculated from final identities.

## Native-output boundary

Internal controls remain available in provenance actions and scorecard construction but are removed from rendered raw/inbox payloads. The renderer recursively drops:

- `synthetic_routine`, `synthetic_unresolved`, and `synthetic_ephemeral`;
- `source_anchor`, `contradiction_group`, `transcript_degraded`, and `tiny_draft`;
- `correction_scope`, `supersedes`, and `supersedes_version`;
- `stale_record` and internal `source_path`.

The source content that implies staleness or correction remains. Only explicit generation/evaluation controls are removed.

## Validation

Policy v4 gains release checks for:

- source-path date tokens matching the create action's date;
- date-bearing path-derived identity tokens matching the create date;
- no post-window date token in source locators or filename metadata;
- no forbidden control key in raw or inbox artifacts.

Older policy versions remain readable. Tests must first reproduce the current leakage, then pass after implementation.

## Packaging

Regenerate the canonical OrgForge v7 folder from the frozen source export with no API calls, validate it, and replace `<clearweave-checkout>/sources` only after the staged package passes. Preserve the prior Clearweave copy until replacement is verified. Scenario diversification, PR semantic templates, Slack thread quantization, meeting phrase reuse, and Datadog coverage remain incremental follow-up work.
