# Clearweave v8.1 Reference, Meeting, and Thread Design

**Status:** Approved by the review's required validator additions and directive to fix knowledge-reference integrity first.

## Goal

Repair the v8 knowledge-evaluation sidecars, remove the remaining repeated meeting clarification families, and make Slack thread metrics match channel-scoped raw exports without regressing chronology, replay, privacy, or source shape.

## Action-reference finalization

Knowledge scenarios are generated before observation realism because their source objects must participate in the same mutation pipeline as all other actions. Scenario records therefore retain stable evidence identities as `(source_system, object_id, revision, operation)` until every payload and timestamp transform is complete. A finalization pass resolves those identities to final action IDs, then recomputes `source_systems`, `observed_days`, `duration_days`, `correction_action_id`, and expected-state day keys from the resolved actions. Only finalized records are written to provenance and gold.

The corpus validator adds a required `knowledge_reference_integrity` check for policy-v5 packages. Every evidence ID and correction ID must exist; declared sources and dates must exactly match referenced actions; correction IDs must be included in evidence; and every non-unresolved scenario must identify a valid correction action.

## Meeting language

Replace the fixed response and continuation prompt lists with deterministic compositional moves. A turn combines meeting-specific context with independently selected evidence origin, scope, stance, uncertainty, and next action. The three reported families—other-environment inclusion, timestamp-comparison, and final-versus-provisional—must have zero occurrences. A semantic-family detector in tests and the scorecard gates their return while retaining existing depth and turn-length bands.

## Slack metrics

All thread grouping uses `(channel identity, thread_ts)`, where channel identity is `channel_id` with `channel_name` fallback. P90, maximum, histogram, orphan checks, and dominant-size share use this scoped key. A reused timestamp in another channel is not the same thread. The scorecard adds a collision count for visibility but does not treat cross-channel reuse as thread depth.

## Release process

Build a clean v8.1 package locally without API calls. Require the complete test suite, reference-integrity validator, zero stock meeting families, channel-scoped Slack metrics, canonical full validation, byte parity after promotion, and installed full validation. Keep the prior installed v8 as rollback until v8.1 passes in Clearweave.
