# Clearweave Semantic Realism v6 Design

## Status and intent

This design responds to the independent v5 corpus review. The review's measurements were reproduced against the local v5 package and are treated as release-blocking for semantic and knowledge-quality use. V5 remains immutable and valid for throughput, packaging, and replay testing.

V6 will be generated deterministically from the same frozen `calibration-realism-180d` simulation. It will make no OpenAI API calls and will not read the proprietary comparison corpus. The purpose is to improve the observation plane without changing simulated business truth.

## Verified v5 failures

- 79.09% of actions have `observed_at < effective_at` because only `observed_at` is remapped.
- Source cadence is flattened into similar 24/7 distributions by continuous timestamp compression.
- Slack exact-text duplication is 61.92%; 65.34% of messages are routine additions and 91.82% of those additions duplicate text.
- Meeting exact-turn duplication is 45.75%, median turn length is four words, and questions are 2.62% of turns.
- Git title duplication is 61.86%; one title accounts for most generated PRs.
- Only 1.97% of actions carry truth-event lineage, with no deep multi-object/multi-day/multi-source truth event.
- Lifecycle observations include only 14 redeliveries, one deletion, and one Slack update.
- Email has 2.07% parseable dates, no thread/routing/attachment structure, and high unexplained subject duplication.
- Datadog is 94.28% of the final semantic inbox.

## Architecture

The v6 pass stays within the existing source-action architecture:

1. `source_realism.py` adapts the frozen export, constructs exact truth-lineage indexes, repairs email transport structure, and remaps both timestamps using a source-aware cadence.
2. `observation_realism.py` applies policy-v3 observation mutations. It changes existing semantic surfaces conservatively, generates bounded context-derived activity, and emits real update/redelivery/delete actions.
3. `realism_scorecard.py` computes schema-v2 quality metrics with upper and lower bounds. It measures inversion, cadence, duplicate concentration, routine share, discourse shape, lifecycle depth, email structure, lineage, and inbox source balance.
4. `clearweave_corpus.py` keeps full raw and delivery coverage while limiting Datadog only in the final semantic `inbox/` projection.
5. `corpus_validator.py` requires schema-v2 gates for policy-v3 packages while preserving compatibility with v5.

## Temporal model

Normalization calculates the original lag as `observed_at - effective_at`. When an observation is mapped into the target window, its effective time is shifted by the identical offset, preserving that lag exactly. Revision order remains monotonic per source object.

Calendar mapping preserves time of day instead of multiplying continuous seconds. Datadog remains continuously distributed. Human-work systems use deterministic source-specific cadence: mostly weekdays and 08:00–19:00, with bounded off-hours/weekend activity for Slack, email, support, and Git. A validator gate rejects observed/effective inversion above 2% overall, similar cadence across every source, excessive human-system weekend share, and excessive human-system off-hours share.

## Slack model

The policy-v2 bulk reply generator is replaced with bounded thread enrichment. It selects fewer roots, derives context tokens from each root, and composes replies from varied conversational moves: clarification, partial confirmation, uncertainty, correction, handoff, timing, environment scope, and short acknowledgement. Combinations include source-local context and stable per-object details so long replies do not repeat exactly. A small natural set of acknowledgements may repeat.

Existing non-routine messages receive conservative surface changes that do not remove identifiers or factual clauses: punctuation variation, casing, line breaks, hedges, corrections, and question-shaped follow-ups. Blocks, attachments, empty/system-only records, reactions, files, mentions, and links occur at bounded rates.

Selected single-revision messages produce actual lifecycle actions: initial create, later update with `edited`, occasional byte-identical redelivery, and rare tombstone. Decorative edit fields without a corresponding update are rejected by the scorecard.

## Meeting model

Transcripts are segmented at sentence and discourse boundaries, not every fixed number of words. Long turns split into 25–60-word contributions; short backchannels remain a minority. Added turns are conditioned on nearby language and include clarification questions, scope checks, disagreement, deferral, and correction. A deterministic attendee pool expands larger meetings without changing attributed factual statements.

The pass preserves all original text tokens that carry material facts and identifiers. Gates require useful turn-length distributions, question presence, speaker diversity, and low exact-turn duplication.

## Git model

Routine PR count is reduced sharply. New PRs are derived from nearby Jira/Slack/Git anchors, with varied titles, 60–160-word bodies, optional checklists/links, and sparse context-specific comments. Existing empty PR bodies receive procedural context tied to their own title and identifiers. Four lifecycle states remain present without requiring hundreds of templated objects.

## Truth lineage

The truth index recognizes exact artifact IDs, causal-chain IDs, source-relative paths, Slack thread/root IDs, message IDs, Jira keys, PR IDs, and email source paths. An action receives an event ID only through an exact identifier/path match; broad topic-word matching is forbidden. Thread replies inherit the root's verified lineage. Generated mundane records remain unlinked unless derived from a linked source object.

The scorecard reports per-source lineage and deep event coverage. A deep event spans at least five source objects, three observed dates, and two source systems.

## Email model

EML is parsed with the standard library and reserialized without rewriting message bodies. ISO dates become RFC 5322 dates. Missing Message-ID, MIME-Version, Delivered-To, Return-Path, and Received headers are added deterministically. Messages are grouped by normalized subject and participant direction; chronological followers receive `In-Reply-To` and `References`. A bounded minority receives metadata-only synthetic attachments through valid MIME parts.

The validator distinguishes intentional threaded subject reuse from unexplained duplicate subjects.

## Datadog semantic profile

Raw Datadog artifacts and all delivery actions remain complete for scale and replay tests. The final `inbox/datadog/` projection is deterministically capped at 1,000 records so machine telemetry cannot dominate semantic ingestion. The manifest records the inbox profile and sample limit. V5 remains the recommended full-volume text-ingestion package.

## Policy-v3 release gates

- Overall observed-before-effective share: at most 2%.
- Human-system weekend share: at most 15% per source; off-hours share: at most 40% per source.
- Slack exact duplicate share: 5–15%; routine share: at most 35%; routine duplicate share: at most 25%.
- Slack question share: 10–30%; no-terminal-punctuation share: 45–75%.
- Meetings: median 8–25 words/turn; P90 at least 30 words; short-turn share 15–40%; questions 8–30%; exact duplicates at most 15%.
- Git duplicate-title share at most 20%; duplicate-body share at most 25%; median non-empty body at least 50 words; routine objects at most 30%.
- Lifecycle: at least 0.5% redeliveries, 0.1% deletions, and actual revision actions for at least 80% of displayed Slack edits.
- Email: at least 98% parseable dates, 20% threaded messages, 80% routing headers, 3% attachments, and at most 15% unexplained duplicate subjects.
- Truth lineage: Slack at least 10%, email at least 10%, Git at least 30%, support at least 20%, and at least 20 deep events.
- Datadog: at most 25% of final inbox files while raw and delivery coverage remain complete.

Broad bands are intentionally used instead of matching one proprietary corpus. All gates are computed only from synthetic output.

## Safety and compatibility

- V5 is never overwritten or deleted.
- V6 transformations are deterministic and idempotent for a fixed seed.
- Every action remains replayable under existing lifecycle rules.
- Material identifiers, truth links, classification, and checksums remain attributable.
- V5 policy-v2 scorecards continue to validate under their existing gates.
- Failed v6 staged output is preserved for diagnosis and is not presented as ready.

## Definition of done

V6 is ready for Clearweave semantic calibration only when all policy-v3 gates pass, the strict validator exits successfully, the complete repository test suite passes, and a v5/v6 comparison shows that improvements come from lower concentration and richer semantic surfaces rather than bulk template dilution. Human-reviewed gold labeling remains a separate requirement for definitive quality claims.
