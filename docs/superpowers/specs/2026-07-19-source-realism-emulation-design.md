# Source realism emulation for Clearweave corpora

## Goal

Produce a large synthetic organizational corpus that preserves OrgForge's causal ground truth while making every artifact look and behave like an imperfect extraction from its source system. The corpus must support ingestion, replay, retrieval, duplicate/update handling, contradiction evaluation, and human inspection without using proprietary text or identifiers as generation material.

The next milestone is a five-day calibration export. The later target remains a reproducible 180-day corpus under the existing $25 API-spend ceiling.

## Privacy boundary

The proprietary reference dump is inspection-only and must never become a runtime input, fixture, prompt source, committed asset, vocabulary source, or text-generation seed.

Permitted learnings are generic source-system conventions and broad structural observations such as long-tailed channel volume, sparse optional fields, revision histories, bot activity, thread nesting, attachment metadata, incomplete templates, and transcript errors.

All checked-in examples must:

- use the synthetic company profile and synthetic people, systems, topics, IDs, and text;
- be authored from public/common source schemas and generic workplace archetypes;
- deliberately avoid matching proprietary filenames, counts, dates, wording, or distinctive combinations;
- carry a `synthetic_non_confidential` classification in provenance;
- be generated or hand-authored independently rather than produced by rewriting proprietary records.

No tool created for this feature may require or default to the proprietary directory.

## Architecture

OrgForge keeps two separate planes:

1. **Truth plane:** simulation events, canonical state, causal chains, stable entity IDs, and intended facts.
2. **Observation plane:** source actions, revisions, native-ish export envelopes, presentation defects, deliveries, retries, redeliveries, and tombstones.

Observation noise may obscure or duplicate truth, but it must not silently mutate truth. Deliberate contradictions must be represented as conflicting observations with separate actors, timestamps, source identities, and provenance links.

The pipeline is:

```text
simulation facts/events
  -> source action stream
  -> routine activity densifier
  -> source lifecycle mutations
  -> native-ish source renderers
  -> daily delivery/replay package
  -> raw + inbox + provenance + gold candidates
```

## Components

### Realism policy

A versioned, synthetic configuration defines broad ranges and probabilities for source activity. It includes no proprietary text or exact corpus fingerprint. The policy controls:

- heavy-tailed source/channel/object volumes;
- routine versus high-signal activity;
- singleton, short, unresolved, and abandoned interactions;
- bots, system events, reactions, attachments, edits, tombstones, and missing fields;
- stale, duplicate, redelivered, corrected, and contradictory observations;
- transcript disfluency and ASR degradation;
- document size and completion-state mixtures.

The seed makes all non-LLM mutations reproducible.

### Routine activity densifier

Most corpus scale comes from deterministic or template-driven low-information activity rather than extra LLM calls. It may create acknowledgements, reactions, join/leave events, automated alerts, reminders, status transitions, retry notifications, sparse comments, stale objects, attachment metadata, and duplicate deliveries.

The densifier operates on synthetic actors, channels, tickets, and facts already present in the truth plane. It cannot invent a new material business decision.

### Source lifecycle and identity

Each observed object has a durable source identity independent of file order. Source actions use this contract:

```json
{
  "action_id": "stable synthetic action ID",
  "source_system": "slack|jira|confluence|zoom|email|salesforce|zendesk|git|datadog|invoices|nps",
  "object_id": "durable source object ID",
  "revision": 1,
  "operation": "create|update|delete|redeliver",
  "observed_at": "ISO-8601 timestamp",
  "effective_at": "ISO-8601 timestamp",
  "truth_event_ids": ["simulation event ID"],
  "payload": {}
}
```

Updates preserve object identity, increment revision, and produce daily delivery actions. Redeliveries preserve revision and checksum. Deletes produce tombstones. Repeated exports may include unchanged records and must be distinguishable from updates.

### Source renderers

Renderers produce native-ish raw exports and readable Clearweave inbox representations.

- **Slack:** channel export envelope with channel metadata, user map, top-level messages, thread map, sync state, blocks, reactions, file metadata, edits, bots, system subtypes, tombstones, unresolved IDs, and Slack-style timestamps. The inbox contains one readable channel transcript per delivery/snapshot, not one prettified JSON record per array index.
- **Jira:** issue snapshots and change events with project key, issue type, status, labels, priority, assignee, reporter, description, comments, changelog, links, attachments, missing optional fields, stale open issues, duplicates, and reopen transitions. The inbox uses an issue-export rendering that preserves incomplete templates and comment formatting.
- **Confluence:** page snapshots and revisions with space, page ID, version, status, author/editor, timestamps, storage body, links, comments, and attachments. Content ranges from tiny notes and abandoned drafts to long polished pages. Rendering does not force every page into the same headings or metadata layout.
- **Zoom/transcripts:** provider-style meeting metadata plus transcript variants. Semantic turns are passed through deterministic ASR degradation that can add disfluencies, punctuation damage, segmentation mistakes, repeated fragments, and corrected alternate versions without changing every material fact.
- **Email:** raw RFC 5322 `.eml` with realistic headers, multipart alternatives, quote depth, signatures, forwards, auto-generated messages, and attachment metadata.
- **Salesforce/Zendesk:** source-shaped object snapshots and history with sparse custom fields, status drift, ownership changes, activities, automated updates, merges, and duplicate records.
- **Git:** repository files and pull-request/issue activity, including ordinary code/configuration, templates, generated files, bot comments, abandoned work, review state, and repetitive machine changes.
- **Datadog/invoices/NPS:** source-shaped machine events, exports, corrections, and redeliveries rather than uniformly clean summaries.

Unknown source types remain raw-only until a renderer exists; the exporter must not wrap them in an invented generic source document.

### Presentation degradation

Degradation is deterministic and source-specific. It may alter punctuation, whitespace, line endings, quoting, formatting, message segmentation, optional metadata, or transcript recognition. It must not alter stable IDs, source timestamps, checksums, provenance, or protected material facts.

Language messiness is applied selectively. Not every person misspells every message, and persona quirks cannot become rigid signatures. Conversations may remain unanswered, move to another source, end mid-topic, or receive a reaction instead of a prose response. Prompts must stop requiring every meeting to frame a goal, reach a decision, and finish with an explicit owner.

### Synthetic examples

Small examples live under `examples/source_realism/`. They demonstrate Slack, Jira, Confluence, transcript, email, and replay behavior using only synthetic company data. Tests may copy these fixtures, but runtime generation uses the same renderer APIs rather than reading examples as content templates.

### Packaging

The Clearweave package remains:

```text
corpus/
  raw/          native-ish source snapshots and exports
  deliveries/   ordered daily create/update/delete/redeliver actions
  inbox/        source-specific Markdown/text/EML rendering for the MVP
  provenance/   manifest, source actions, simulation events, checksums, run status
  gold/         small unreviewed candidate set for later human labeling
```

The manifest maps every inbox and raw file to source system, object ID, revision, operation, observation/effective timestamps, delivery day, checksum, and truth-event IDs. Provenance is not ingested as organizational knowledge.

## Cost policy

The realism layer should reduce API spend:

- routine activity, source schemas, revisions, delivery behavior, and presentation degradation are deterministic;
- the configured worker/planner model is used only for semantically important artifacts;
- no LLM call is made solely to add typos, formatting damage, metadata, reactions, bot events, duplicates, or stale records;
- the existing resilient primary/fallback wrapper remains in force;
- calibration must calculate a conservative all-fallback price ceiling before authorizing 180 days.

## Validation and calibration gate

The next five-day run is authorized only after automated tests and a no-cost local fixture export pass these checks:

1. **Privacy:** no runtime dependency on the proprietary directory and no proprietary content in committed examples.
2. **Identity:** every mutable object has a durable object ID; updates and redeliveries retain it.
3. **Temporal integrity:** file/delivery dates, source timestamps, revisions, thread parents, and delete ordering are valid.
4. **Native shape:** supported sources use their renderer instead of generic pretty-JSON Markdown.
5. **Manifest coverage:** every raw and inbox artifact is represented with checksums and source-action metadata.
6. **Replay:** applying deliveries in order reconstructs the expected final object state; unchanged redelivery is distinguishable from update.
7. **Messiness:** the fixture corpus contains short/singleton activity, bot/system events, edits, reactions, attachments, stale records, duplicates, an unresolved interaction, transcript degradation, and at least one correction/supersession.
8. **Semantic safety:** protected facts survive presentation degradation and deliberate contradictions remain separately attributable.
9. **Run health:** the simulation completes with zero unrecovered LLM failures and writes final run status/events.
10. **Spend:** measured usage and conservative extrapolation remain below the $25 hard ceiling.

After a paid five-day run passes the same identity, temporal, manifest, replay, messiness, health, and spend checks, the 180-day run can be considered.

## Out of scope

- Pixel-perfect reproduction of any proprietary exporter.
- Copying or paraphrasing proprietary workplace content.
- Downloading binary attachment bodies during the calibration milestone.
- Human-labeling the final gold set before the source corpus passes replay and integrity checks.
- Replacing Clearweave's ingestion behavior; `inbox/` remains compatible with its current text-oriented MVP.
