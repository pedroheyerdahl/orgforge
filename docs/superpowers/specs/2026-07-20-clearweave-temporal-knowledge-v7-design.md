# Clearweave temporal-knowledge corpus v7 design

**Date:** 2026-07-20
**Status:** Approved direction — fixed 180-day window with native timestamp rebasing and lifecycle expansion

## Goal

Produce a separate v7 package for 2026-01-01 through 2026-06-29 in which every observation contains only information knowable at its `observed_at`, while retaining source-native messiness, cross-source depth, replay, and v6 surface realism.

## Chosen approach

Use one deterministic temporal compiler for actions and payloads, then expand final snapshots into initial creates and chronological updates before rendering. Preserve v6 unchanged.

Rejected alternatives:

1. Expanding the package through September or November would preserve native dates but violate the requested 180-day corpus and would not fix final-state creates.
2. Regenerating the business simulation would add cost and semantic drift without addressing the exporter contract directly.

## Authoritative timeline

The action stream is authoritative. A single calendar mapping rebases source observations into the 180-day target window. The same mapping must be applied to structured native timestamps, Slack epoch timestamps, email headers, transcript headers, filenames derived during rendering, and nested activity/comment timestamps.

Timestamp fields are classified:

- Historical/audit fields: message `ts`, comment/activity timestamps, `created_at`, `updated_at`, `edited.ts`, `merged_at`, `closed_at`, `resolved_at`, transcript meeting dates, and comparable event timestamps. These must be within the declared window and no later than the action that first exposes them.
- Planning fields: due dates, expected close dates, expirations, and scheduled future work. These may be later than the containing action but must remain inside the declared window.
- Free text: dates mentioned in prose are not rewritten automatically. Structured provenance and synthetic scenario labels determine what the text is intended to represent.

For every action, payload timestamps are mapped from their original source time using the same source-to-target mapping as `observed_at`. Per-object revision order is repaired after mapping without allowing an action past the window end.

## Snapshot-to-lifecycle expansion

Source snapshots must be converted before final temporal validation:

- Jira create payloads contain the initial status, no later comments, and no final `updated_at`; comments and status changes become ordered update actions.
- Git create payloads contain draft/open status and no review comments. Each timestamped review comment becomes an update. Merged/closed state is emitted only in a later update after the latest visible review activity.
- Zendesk tickets and comments retain stable ticket/comment identity; ticket status and later activities become updates rather than future content in the create.
- Slack creates contain only create-time metadata. Edits and deletion remain revisioned actions; thread timestamps are rebased with their root.
- Generic timestamped source records are rebased recursively. Records that represent distinct immutable observations stay distinct creates.
- Redeliveries remain byte-identical same-revision actions.

No update may contain a nested comment/activity timestamp later than that update. Final-state `raw/` and `inbox/` remain replay products; daily `deliveries/` expose only the state available on each day.

## Validator and scorecard contract

Policy v4 and scorecard schema v3 add release gates for:

- every historical/audit native timestamp at or before its action time;
- every structured native date inside the manifest window;
- no create payload with a terminal Git/Jira/Zendesk state when later lifecycle evidence exists;
- no future comments, reviews, edits, or state transitions embedded in creates;
- rendered Slack roots/replies matching action-native times;
- distinct-message Slack thread distributions, excluding revisions and redeliveries;
- rounded Slack timestamp share and off-hours/weekend cadence;
- Git create/update/final-state lifecycle depth;
- minimum stale, correction, supersession, provisional, delayed-correction, partial-correction, and unresolved-conflict scenario counts;
- semantic scaffold concentration for meetings and Git, not only exact-string duplication.

Policy-v2/v3 packages remain readable; new temporal gates are mandatory only for policy v4.

## Remaining surface-realism work

v7 also addresses the non-blocking but material review findings:

- Slack gets deterministic second/microsecond jitter and a wider thread-length tail without fixed 5–8-message clusters.
- Meetings use a mixed distribution: ordinary short meetings remain, selected meetings become substantially longer, and context-derived turn construction replaces a small set of repeated clarification phrases.
- Git bodies and reviews are composed from source anchors and source-specific sections with sparse comments and a longer review tail; common semantic scaffolds are measured and capped.
- Knowledge-error scenarios are added across days and sources. Scenario truth and expected temporal state live in provenance, while source artifacts remain implicit and messy.

## Gold and evaluation boundary

v7 will produce machine-verifiable temporal scenario labels and evidence candidates under `gold/`, including expected knowable state by day. They remain marked `pending_human_review`. This supports deterministic development and spot-checking but does not claim that the benchmark is human-reviewed.

## Packaging and acceptance

The output is `export/calibration-temporal-knowledge-180d-clearweave-v7/` with the existing `raw/`, `inbox/`, `deliveries/`, `provenance/`, and `gold/` contract. v6 is never overwritten.

Acceptance requires:

1. The new temporal validator reproduces failures on v6.
2. All policy-v4 gates pass on an in-memory v7 diagnostic.
3. The complete test suite passes.
4. The generated package passes strict replay, checksum, native-shape, privacy, temporal, semantic, run-health, spend, and UTF-8 validation.
5. Manual spot checks across Git, Jira, Slack, Zoom, and Zendesk show no future information in create actions.
