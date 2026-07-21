# Clearweave v8 Distribution Realism Design

**Status:** Approved for implementation by the user's instruction to complete all five documented incremental realism items.

## Goal

Produce a new deterministic 180-day Clearweave corpus that preserves v7.1's chronology, locator, replay, and raw-label guarantees while removing five remaining generator-shaped distributions: uniform knowledge scenarios, repeated pull-request scaffolds, repeated meeting phrase families, quantized Slack thread sizes, and missing Datadog days.

No OpenAI API calls or proprietary source content are used. The existing organization profile and source-native renderers remain authoritative.

## Design

### Knowledge scenarios

Replace the six-by-four fixed template loop with a deterministic scenario plan. The plan keeps all six error categories but varies category counts, duration, evidence count, observed-day count, source combinations, correction completeness, and resolution state. Evidence can come from Confluence, Slack, Jira, email, Git, and Zendesk; a scenario uses two to four systems and three to seven evidence actions over two to six observed days spanning two to twenty-eight days.

Some evidence is shared by multiple interpretations, some is misleading, and unresolved scenarios have no artificial final correction. Raw artifacts contain only plausible source fields and prose. Scenario type, expected state, shared-evidence flags, and review status remain in provenance and gold candidate files only.

### Pull requests

Replace the empty-body fallback paragraph with a compositional body generator. It chooses and reorders sections such as context, observed behavior, scope, verification, rollout, known gaps, links, and reviewer notes; varies prose and section count; and anchors text to the PR title/object without exposing generator controls.

Terminal Git updates are deterministically scheduled across a mixed lifecycle distribution. Long-tail PRs remain open for 18 to 35 days where the declared window allows it. Native `updated_at`, `closed_at`, and `merged_at` fields move with the observation, and action ordering remains valid. The release scorecard measures normalized repeated five-gram concentration and terminal lifecycle P90.

### Meetings

Keep the existing realistic turn-count distribution, but replace fixed continuation sentences with a compositional discourse grammar. Each inserted turn combines a stance, evidence source, scope qualifier, uncertainty or action, and meeting-specific context. The scorecard normalizes identifiers/numbers and measures dominant six-word prefix concentration so lexical substitutions cannot hide a repeated template.

### Slack threads

Replace discrete reply counts of 1, 4, 6, and 12-14 with a deterministic broad distribution: acknowledgements at one to two replies, ordinary threads at three to nine replies, and long-tail threads at ten to twenty-seven replies. Every ordinary size is reachable, no single threaded-root size may dominate, four-message threads must exist, and the long tail must remain present. Thread metrics count distinct source objects, not revisions or redeliveries.

### Datadog continuity

Emit one low-volume daily activity observation for each of the 180 declared days. Existing alerts and metrics remain unchanged; the continuity record only fills missing days and does not enter the semantic inbox beyond its existing cap. The scorecard requires 180 active Datadog days for a 180-day release.

## Versioning and validation

Observation realism policy version becomes 5 and the realism scorecard schema becomes 4. Schema 4 adds:

- knowledge scenario evidence-count, day-count, duration, source-combination, and resolution distributions;
- Git repeated-five-gram concentration and terminal-lifecycle percentiles;
- meeting normalized-prefix concentration;
- Slack threaded-root size histogram and dominant-size share;
- active days by source, including Datadog.

The v8 release gates require heterogeneous scenario shapes and all six source systems, Git semantic concentration at or below 50%, Git terminal lifecycle P90 of at least 14 days, meeting dominant normalized prefix count at or below 100, Slack four-message threads plus dominant size share at or below 20%, and 180 active Datadog days. Existing strict chronology, locator, terminal-create, raw-control, rendering, and replay checks remain in force.

## Build and replacement safety

Generate v8 into a new staged directory. Run focused tests, the full test suite, strict corpus validation, independent metric inspection, and manifest parity checks. Only then replace `<clearweave-checkout>/sources`, retaining v7.1 as the previous package. The installed corpus and canonical v8 package must have byte-identical manifests.
