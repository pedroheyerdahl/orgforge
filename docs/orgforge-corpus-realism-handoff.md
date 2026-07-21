# OrgForge corpus realism: diagnostic and implementation handoff

## Consolidated generation process — 2026-07-20

The iterative v5-v8.1 repairs are now part of a supported project workflow,
not a sequence of manual corpus patches:

- `config/clearweave_180d.yaml` freezes the validated 180-day release settings.
- `src/build_clearweave_corpus.py` stages, packages, validates, reports, and
  safely promotes a corpus without making model calls.
- `src/corpus_validator.py` is the release gate for chronology, replay,
  source-visible controls, reference integrity, realism, run health, and spend.
- `docs/source-realism-calibration-runbook.md` is the current operator path.

The per-version sections below remain useful engineering history. Operators do
not need to replay those individual repair passes.

## v8.1 repair status — 2026-07-20

The post-v8 reference-integrity, meeting-language, and Slack-scoring review is implemented in `export/calibration-reference-integrity-180d-clearweave-v8.1`.

- All 118 knowledge evidence references resolve to final action IDs. All 24 scenarios have exact source/day agreement, all corrected scenarios have valid correction actions, and provenance/gold sidecars are identical.
- A required `knowledge_reference_integrity` validator check enforces those relationships for policy-v5 packages.
- The three reported meeting clarification families fell from 697 combined occurrences across 161 meetings to zero. Meeting median/P90 depth remains 65/200 turns.
- Slack thread aggregation now uses `(channel identity, thread_ts)`. Threaded P90/max are 15/28, matching an independent raw-action audit; 58 cross-channel timestamp collisions are reported separately.

Temporal candidates remain pending human review even though their references and expected-state structure are now valid.

## v8 implementation status — 2026-07-20

The five remaining incremental realism items from the v7 review are implemented in `export/calibration-distribution-realism-180d-clearweave-v8` and enforced by policy-v5 / scorecard-schema-v4 release gates.

- Knowledge errors now vary category counts, evidence counts, observed days, durations, resolution states, and source combinations across Confluence, Slack, Jira, email, Git, and Zendesk. The 24 generated candidates include 15 source combinations and eight unresolved outcomes; labels remain provenance-only and pending human review.
- Pull-request bodies are compositional rather than one shared scaffold. Dominant normalized five-gram coverage is 17.97%, and terminal lifecycle P90 is 28 days.
- Meeting continuation language uses a compositional opening grammar. The dominant normalized six-word prefix occurs nine times while median/P90 depth remains 65/200 turns.
- Slack thread sizes now include a smooth middle and long tail. There are 97 four-message threads, and the dominant distinct-message size accounts for 14.43% of threaded roots.
- Datadog is active on all 180 declared days.

The required validator checks pass across 125,662 actions, 120,036 replayed objects, 103,283 raw/inbox artifacts, and 228,956 UTF-8 files. The installed Clearweave package should be treated as manual-UAT quality, not frozen benchmark gold, until the gold candidates receive human review.

**Prepared:** 2026-07-20
**Target:** the completed 180-day OrgForge corpus used by Clearweave
**Priority order:** knowledge-quality failures first, ingestion/replay failures second, user-trust failures third

## Executive summary

The existing synthetic Apex Athletics corpus is useful as a clean volume and cross-source continuity corpus. It is large enough to exercise throughput, contains many linked project arcs, and is not merely a collection of unrelated documents. Its central weakness is observation realism: activity is too coordinated, prose is too complete, source envelopes are too uniform, timestamps are too regular, meetings are too concise, pull requests are too consistently successful, and contradictions are too explicitly announced.

The proprietary comparison corpus shows a different texture. Information is surrounded by short acknowledgements, automation, links, code, reactions, incomplete messages, edits, stalled work, long silences, tangents, and source-specific metadata. Important facts emerge in fragments across time and systems. Contradictions often appear as quiet changes in scope, estimates, status, or confidence rather than messages labelled as corrections.

OrgForge should therefore keep its existing truth simulation and add a tracked **observation-realism second pass** over the complete 180-day run. The second pass should preserve major simulated facts and causal chains while changing how those facts are observed: source-native structure, lifecycle events, routine dirt, uneven delivery, partial disclosure, stale observations, secondary drift, and unresolved conflicts.

The scalable implementation is a ledger-driven, incremental harness:

```text
inventory -> measure -> plan actions -> stage -> validate -> apply -> record
```

It should operate in resumable batches, use deterministic seeds and stable object identities, retain content-addressed originals, and distinguish structural mutations from semantic observation mutations. Most volume and metadata changes should be deterministic. Model calls should be reserved for selected conversational and prose transformations, cached, and validated before application.

## Scope and privacy boundary

The comparison used one local synthetic snapshot and one local proprietary
reference snapshot. Their machine-specific paths are intentionally omitted.

The proprietary corpus was used only to measure generic structural and behavioral properties. No proprietary source body, identifier, filename, repository name, distinctive vocabulary, or wording should become:

- a generation prompt;
- a runtime input;
- a checked-in fixture;
- a vocabulary or topic seed;
- an exact target fingerprint; or
- a rewritten synthetic artifact.

Permitted learnings are generic patterns: length distributions, thread depth, timing irregularity, optional-field sparsity, lifecycle behavior, source-native features, conversational incompleteness, and the way evidence becomes dispersed.

The proprietary corpus is not a universal gold standard. It is dominated by Slack and GitHub material, has a narrower source mix than the synthetic company, and includes transformed exports. All suggested targets should be treated as broad bands, not values to reproduce exactly.

## Comparison methodology

The review was read-only. It included:

1. File inventory, extensions, byte volume, depth, UTF-8 validity, line endings, size outliers, hidden files, exact duplicate hashes, and JSON parseability.
2. Logical-record extraction for Slack messages, emails, Jira objects, pull requests, support messages, Markdown documents, and transcripts.
3. Date and timestamp analysis, including active days, source overlap, weekend/after-hours activity, timestamp precision, and collisions.
4. Source-native structural analysis: key-set diversity, threading, reactions, files, attachments, edits, bots, system subtypes, email headers, PR states, comments, labels, links, and checklists.
5. Language-shape analysis: message and turn lengths, acknowledgements, fragments, punctuation, questions, filler language, corrections, reversals, disagreement, code, links, and mentions.
6. Cross-source continuity analysis using synthetic business identifiers and repository-qualified issue/PR links.
7. Aggregate contradiction proxies. These are diagnostic heuristics, not semantic truth labels.

All numbers describe the inspected snapshots and may change when the corpus is regenerated.

## Corpus-level findings

### Inventory and source mix

| Measure | Synthetic corpus | Proprietary corpus |
|---|---:|---:|
| Files | 3,988 | 6,396 |
| Bytes | 9.3 MB | 226.7 MB |
| Markdown/text files | 297 | 6,342 |
| Markdown/text share by file | 7.4% | 99.2% |
| Nominal source classes | 11 | Primarily Slack, GitHub, and transcripts |

The synthetic corpus has excellent nominal breadth: Slack, email, Jira, Confluence, Zoom, Git, Zendesk, Salesforce, Datadog, invoices, and NPS. Several sources are very thin, however: invoices, NPS, Salesforce, and Datadog contribute little narrative depth.

For Clearweave's text-oriented MVP, only 214 Confluence documents and 83 Zoom transcripts were directly useful as Markdown in the inspected copy. OrgForge's completed corpus should continue producing a readable `inbox/` projection for every supported source while keeping native-ish objects in `raw/` and lifecycle actions in `deliveries/`.

### File-system texture

| Measure | Synthetic | Proprietary |
|---|---:|---:|
| Invalid UTF-8 files | 0 | 1 |
| Files containing CRLF | 0 | 1,347 |
| Hidden files | 0 | 11 |
| Files under 100 bytes | 0 | 5 |
| Files over 1 MB | 1 | 28 |
| Exact duplicate-file excess | 6.7% | 0.02% |

All 2,521 synthetic JSON files parsed successfully. Clean parseability is desirable, but total uniformity makes the folder feel manufactured. The exact duplicate excess was concentrated in Zendesk: 267 extra files across 21 duplicate groups. This is blunt repetition, not realistic operational noise.

The realism pass should add controlled variation—line endings, tiny stubs, oversized exports, sparse records, machine-generated boilerplate, unsupported attachment metadata, and a very small quarantined malformed set—without making the main corpus unusable.

## Chronology and organizational behavior

The synthetic timeline is over-orchestrated.

### Synthetic Slack timing

- 8,496 messages across 97 active days from 2026-01-01 through 2026-05-15.
- No weekend Slack messages.
- Approximately 0.04% outside 08:00–19:00.
- 79.7% of timestamps land on second `00`.
- 26.6% of messages reuse an exact timestamp.
- 35.1% of timestamps fall on a five-minute grid.

### Proprietary Slack timing

- Approximately 99,700 distinct messages across 516 observed active days.
- Approximately 4.8% on weekends.
- Approximately 24.6% before 08:00 or after 19:00 in UTC. This is a directional comparison because the company's local timezone was not inferred.
- Approximately 1.65% land on second `00`.
- Approximately 0.7% reuse an exact timestamp.
- Approximately 20.4% fall on a five-minute grid.

### Cross-source daily coordination

- 95.1% of synthetic active days contain activity from at least two source classes.
- 74 synthetic days contain five or more source classes.
- 58.6% of proprietary active days contain at least two observed source classes.
- The proprietary snapshot contains no five-source days because its source mix is much narrower.

The issue is not simply that synthetic systems are active on the same day. It is that almost every workday appears deliberately populated across systems. Real organizations have source-specific quiet periods, project bursts, delayed write-ups, work that moves to one system and never returns, and important decisions that remain absent from the expected system.

## Slack diagnostics

### Scale and structural diversity

| Measure | Synthetic Slack | Proprietary Slack |
|---|---:|---:|
| Messages | 8,496 | ~99,700 |
| Observed users | 57 | 166 |
| Distinct message key sets | 4 | 745 |
| Distinct message keys | 12 | 102 |
| Median words/message | 32 | 15 |
| P90 words/message | 47 | 53 |
| Messages of 1–5 words | 1.1% | 14.6% |
| Empty-text messages | 0% | 1.6% |
| Acknowledgement-only messages | 0% | 1.4% |
| Messages without terminal punctuation | 20.1% | 64.9% |
| Messages containing URLs | 0.2% | 19.8% |
| Messages containing mentions | 2.7% | 17.7% |
| Messages containing code formatting | 0.6% | 6.3% |

The synthetic median is too close to its P90: messages cluster around a polished 30–50-word paragraph. The proprietary set contains both many tiny turns and a long tail of highly detailed messages.

### Threading

| Measure | Synthetic | Proprietary |
|---|---:|---:|
| Median messages/thread | 1 | 1 |
| P90 messages/thread | 1 | 10 |
| P99 messages/thread | 3 | 32 |
| Maximum observed thread | 16 | 120 |

Singleton activity is normal in both corpora, but synthetic Slack lacks the middle and long tail. Its files may contain several sequential messages while the message-level root/thread identifiers still behave as separate singletons.

### Native Slack artifacts

| Feature | Synthetic message share | Proprietary message share |
|---|---:|---:|
| Blocks | 0% | 93.6% |
| Reactions | 0% | 20.4% |
| Attachments | 0% | 9.5% |
| Files | 0% | 8.2% |
| Edited messages | 0% | 5.6% |
| System subtypes | 0% | 3.8% |
| Bot messages | 0% | 7.2% |

These fields should not be applied uniformly. Their sparsity, combinations, and source-specific payloads are part of the realism.

### Behavioral interpretation

Synthetic Slack includes casual content, but it reads as conspicuously inserted complete conversations. Real dirt is often less entertaining and more operational:

- acknowledgements and reaction-only closure;
- repeated requests for the same link;
- bot notifications no one answers;
- references to missing screenshots or private documents;
- threads that stop after a promise to investigate;
- corrections made by editing rather than announcing a correction;
- code, stack traces, pasted identifiers, and machine output;
- questions answered in another channel or source;
- duplicated delivery and cross-posting;
- messages whose meaning depends on earlier context.

## Transcript and meeting diagnostics

After excluding two non-transcript Markdown files, the comparison covered 83 synthetic and 78 proprietary transcripts.

| Measure | Synthetic meetings | Proprietary meetings |
|---|---:|---:|
| Median turns/meeting | 16 | 122 |
| P90 turns/meeting | 21 | 242 |
| Median speakers/meeting | 3 | 3 |
| P90 speakers/meeting | 4 | 10 |
| Median words/turn | 30 | 13 |
| P90 words/turn | 44 | 93 |
| Turns of 1–5 words | 1.4% | 28.7% |
| Turns containing filler | 10.5% | 36.8% |
| Turns containing a question | 15.4% | 18.7% |
| Turns containing contractions | 32.2% | 51.6% |

Synthetic meetings are uniformly compact and information-dense. Speakers take turns delivering complete paragraphs, discuss the intended issue, and usually reach an intelligible endpoint. Natural meetings combine:

- very short backchannels with occasional long monologues;
- repetition while participants align on terminology;
- interruptions, restarts, and “go ahead” exchanges;
- audio or screen-sharing housekeeping;
- partial recollection and uncertainty;
- side topics that consume several turns;
- absent stakeholders and deferred decisions;
- decisions that are revised after the call;
- action items implied rather than summarized;
- minor meetings with little durable information.

The second pass must use a mixture. Making all meetings 120 turns would create a new uniformity.

## Pull-request diagnostics

The synthetic Git source contained 80 pull-request objects. The proprietary activity export contained 4,219 pull-request-like objects.

| Measure | Synthetic PRs | Proprietary PRs |
|---|---:|---:|
| Open | 5 | 395 |
| Merged/closed | 75 merged | 3,824 closed |
| Median body words | 64 | 119 |
| P90 body words | 72 | 332 |
| Median comments | 2 | 0 |
| P90 comments | 3 | 1 |
| Maximum comments | 5 | 27 |
| Median comment words | 36 | 23 |
| P90 comment words | 51 | 118 |
| Median lifespan | Same day | 0.2 days |
| P90 lifespan | Same day | 18.9 days |
| Bodies with checklists | 0% | 15.1% |
| Bodies with multiple template sections | 100% | 59.8% |
| Bodies with links | 0% | 36.6% |
| Bodies with issue references | 11.2% | 23.2% |
| Review comments containing code | 5.6% | 15.4% |
| Review comments containing questions | 7.1% | 22.9% |

Synthetic PRs are too successful and too symmetrical: nearly all merge, bodies occupy a narrow size band, every body follows a multi-section template, reviews consistently contain two or three substantive comments, and creation-to-resolution time is effectively zero.

A realistic distribution needs many no-comment PRs, quick bot-only changes, trivial merges, drafts, stale reviews, closed-without-merge work, reopened work, long review tails, review disagreement, requested changes that are only partly addressed, CI failures, links, and code-specific questions.

## Email diagnostics

The proprietary reference did not contain a comparable email corpus, so these findings rely on standard email structure rather than a direct content comparison.

The synthetic corpus contained 1,168 email files:

- every file used the same small header set;
- every file was declared `multipart/alternative` but contained only a plain-text part;
- no attachments;
- no `Message-ID`;
- no `In-Reply-To`;
- no `References`;
- no `Received` or routing headers;
- approximately 97.5% used a bare ISO timestamp in `Date`, which standards-aware email parsing rejected as a normal RFC date.

Email realism requires RFC 5322 dates, stable message and thread identities, quoting depth, forwarding, signatures, auto-generated mail, bounces, HTML alternatives, optional routing headers, attachment metadata, and uneven participation. These should be source observations, not uniformly added decoration.

## Project continuity and information depth

The synthetic corpus is not shallow. Explicit synthetic identifiers produced the following graph:

- 782 unique anchors;
- 380 present in at least two artifacts;
- 362 present on at least two dates;
- 358 present in at least two source classes;
- 222 present in at least three source classes;
- 174 “deep” anchors present in at least five artifacts, on at least three dates, and in at least two sources.

For multi-source synthetic anchors:

- median of four artifacts;
- median of three source classes;
- median of four distinct days;
- median calendar span of 21 days;
- P90 calendar span of 105 days.

The proprietary comparison produced 2,042 multi-source repository-qualified issue/PR links and 441 deep links under the same minimum-artifact/day/source rule. Its median multi-source anchor also appeared in four artifacts, but across two source classes and two distinct days, with a median span of 32 days and a much longer tail.

Conclusion: OrgForge already generates enough cross-source project depth. The realism pass should not primarily create more project IDs. It should make existing arcs uneven and partially observable:

- only some systems mention the identifier directly;
- one system uses an old name;
- a later discussion omits the original ticket;
- an official page lags behind a PR or support thread;
- a decision appears in a meeting before being formalized;
- some work has no clean completion artifact;
- long gaps and late reopenings occur;
- minor related work remains orphaned.

## Noise and contradiction findings

The synthetic corpus contains disagreement but often over-signals it.

### Slack phrase rates per 10,000 messages

| Marker | Synthetic | Proprietary |
|---|---:|---:|
| “Actually” | 113.0 | 156.7 |
| Explicit “correction” | 20.0 | 1.9 |
| “To clarify”/“clarification” | 95.3 | 7.9 |
| Explicit disagreement/rejection | 101.2 | 26.6 |
| Reversal/supersession language | 4.7 | 34.5 |
| Admission such as “my mistake” | 0 | 1.2 |
| “Scratch that”/“never mind” | 0 | 4.1 |

Synthetic Slack therefore contains more authored conflict signals but fewer organic reversals. It says that something is a clarification or disagreement instead of simply presenting a later incompatible detail.

At the broader marker level, synthetic Slack contained more negation and explicit disagreement, while the proprietary set contained more hedging, links, code, short messages, edits, and source-native activity.

The realism target is not “more contradictions” in the abstract. It is a better mixture:

1. **Temporal replacement:** an earlier estimate or process genuinely changes later.
2. **Scope mismatch:** both statements can be correct for different customer tiers, platforms, dates, or environments.
3. **Simultaneous disagreement:** two actors hold incompatible views with no authority resolution.
4. **Stale documentation:** a page remains unchanged after implementation or policy changes.
5. **Provisional decision:** a meeting sounds decisive but the work is later reversed.
6. **Incorrect correction:** someone confidently posts an update that is itself wrong.
7. **Partial correction:** one field changes while another stale implication remains.
8. **Quiet reversal:** status, code, or behavior changes without explicit correction language.
9. **Reopening:** resolved work becomes relevant again after new evidence.
10. **Unresolved absence:** the evidence needed to decide never appears.

Every deliberate semantic conflict should remain separately attributable to actors, sources, timestamps, and truth events. The observation pass must never silently rewrite canonical truth.

## Overall assessment

| Dimension | Assessment |
|---|---|
| Volume and throughput | Strong |
| Nominal source breadth | Strong |
| Cross-source project depth | Strong |
| Chronological naturalness | Weak |
| Source-native structure | Weak |
| Conversational realism | Weak |
| PR lifecycle realism | Weak |
| Organic noise | Weak |
| Semantic contradiction coverage | Present but scripted |
| Suitability as final realism evaluation corpus | Not yet sufficient |

## Proposed OrgForge solution

### Existing OrgForge work to extend

At the time of this review, OrgForge already contained active source-realism work. The receiving agent should inspect and extend it rather than introduce a parallel harness. Relevant files included:

- `src/source_actions.py` — source-object action identity, revision, operation, and replay concepts;
- `src/source_realism.py` — export adaptation, realism policy, conversation shapes, and deterministic presentation changes;
- `src/source_renderers.py` — source-native raw and readable inbox renderers;
- `src/clearweave_corpus.py` — corpus packaging into raw, deliveries, inbox, provenance, and candidate gold data;
- `src/corpus_validator.py` — integrity and realism validation;
- `config/source_realism.yaml` — versioned realism controls;
- `docs/source-realism-calibration-runbook.md` — fixture, packaging, and validation workflow;
- existing source-realism tests and synthetic examples.

That work already expresses the correct truth-plane/observation-plane separation and includes deterministic additions such as short messages, bots, system events, reactions, files, edits, redeliveries, tombstones, stale records, tiny drafts, transcript degradation, and corrections.

The remaining work is to make the system **broad, incremental, distribution-aware, and semantically deep** over the completed 180-day corpus:

- persist per-file and per-action state rather than treating realism as one monolithic export;
- support resumable batches and targeted replanning;
- calibrate whole-corpus distributions rather than merely ensuring that each feature appears once;
- deepen speech and writing transformations;
- coordinate subtle changes across existing project arcs;
- validate protected facts and secondary drift explicitly;
- measure before/after realism without copying the proprietary corpus's fingerprint.

The OrgForge working tree also contained active, uncommitted implementation work during inspection. Preserve and audit that work before editing overlapping files.

### Architectural boundary

Keep two planes:

1. **Truth plane:** stable entities, major facts, causal chains, intended project outcomes, effective dates, and protected values.
2. **Observation plane:** source objects, revisions, deliveries, edits, redeliveries, tombstones, partial views, stale values, presentation damage, and deliberate conflicting observations.

The completed 180-day simulation is the truth-plane input. The realism harness creates and mutates observation-plane artifacts. It may obscure, duplicate, delay, scatter, or contradict truth through attributable observations, but it may not mutate protected truth silently.

### Incremental tracked harness

The second pass should behave like a resumable data-migration system:

```text
inventory -> analyze -> plan -> stage -> validate -> apply -> record
```

Recommended commands:

```bash
orgforge realism inventory <180-day-export>
orgforge realism measure <corpus-id>
orgforge realism plan <corpus-id> --max-files 250 --max-arcs 10
orgforge realism apply <batch-id>
orgforge realism validate <batch-id>
orgforge realism status <corpus-id>
orgforge realism rollback <batch-id>
orgforge realism finalize <corpus-id>
```

The exact CLI names may follow existing OrgForge conventions. The required behavior matters more than naming.

### Ledger model

Use SQLite or an append-only JSONL ledger plus indexed state. Each action should record at least:

```text
action_id
corpus_id
batch_id
target_path
source_system
object_id
revision
mutation_pass
mutation_type
policy_version
prompt_version, when applicable
model, when applicable
deterministic_seed
original_hash
expected_input_hash
result_hash
protected_fact_ids
truth_event_ids
cross_source_dependencies
status
validation_result
created_at
applied_at
```

Properties:

- An action is idempotent.
- A changed input hash invalidates planned but unapplied work.
- A policy or mutator version change marks only affected actions for replanning.
- Dependent cross-source actions apply as one validated batch.
- Interrupted runs resume without repeating completed actions.
- Original bytes are retained once in a content-addressed object store.
- Logs contain IDs and aggregate metrics, never source bodies.

### Pass ordering

#### Pass 1: identity and source-native structure

- Stable source object IDs independent of filenames.
- Revisions, create/update/delete/redeliver operations, and effective versus observed times.
- Optional-field sparsity and native envelopes.
- Thread parents, references, attachments, links, and status histories.
- Raw, inbox, delivery, provenance, and candidate-gold representations remain separate.

#### Pass 2: timing and delivery behavior

- Non-grid seconds and realistic collision rates.
- Some weekend and after-hours observations without making them universal.
- Bursty project activity and source-specific quiet periods.
- Delayed documentation and asynchronous follow-up.
- Repeated exports and redeliveries distinguishable from real updates.
- Long gaps, late reopenings, and abandoned work.

#### Pass 3: routine activity and operational dirt

- Deterministic low-information Slack messages, reactions, bot events, reminders, join/leave events, attachment metadata, CI output, retry notices, status transitions, and sparse comments.
- Orphan records, tiny drafts, incomplete templates, machine boilerplate, and missing optional fields.
- This pass should supply most volume without model calls.

#### Pass 4: language and speech realism

- Shorten and fragment selected Slack prose.
- Split over-complete messages into turns when the source context permits.
- Add backchannels, silence, uncertainty, missing context, and moved-elsewhere endings.
- Expand selected important meetings while adding many small low-value meetings.
- Add false starts, interruptions, repetition, tangents, contractions, filler, and uneven speaker participation.
- Preserve important terms, values, IDs, and attribution.
- Use model calls only for artifacts that need genuine discourse transformation.

#### Pass 5: cross-source information dispersion

Select existing high-value project arcs and create coordinated observation bundles:

- Slack mention before ticket creation;
- meeting discussion with provisional values;
- PR implementation with different terminology;
- stale Confluence page;
- later support or customer evidence;
- secondary estimate drift;
- delayed or missing formal update;
- reopened work after an apparent resolution.

These bundles must use existing synthetic entities and truth events. They should not create a second independent business simulation.

#### Pass 6: contradiction and ambiguity

Create the ten contradiction types listed earlier, prioritizing subtle and unresolved cases. Record the intended relationship only in provenance/gold candidates, never in the ingested source text.

#### Pass 7: packaging and validation

Write source-native raw artifacts, replayable deliveries, readable Clearweave inbox files, provenance, checksums, run health, and an unreviewed candidate set.

## Source-specific mutation requirements

### Slack

Use broad target bands rather than exact proprietary values:

- Median message length: approximately 15–22 words.
- 1–5-word messages: approximately 10–18%.
- No terminal punctuation: approximately 50–70%.
- Mentions: approximately 10–20%.
- Synthetic/internal links: approximately 5–20% depending on channel.
- Code or log fragments: approximately 3–8% in technical channels.
- Reactions: approximately 10–25%.
- Edited messages: approximately 3–8%.
- Bot/system activity: approximately 3–10%.
- File or attachment metadata: approximately 5–12%.
- P90 thread length: approximately 8–15 messages, with a much longer sparse tail.

Do not apply these globally. Engineering channels, DMs, support channels, executive channels, and social channels should differ.

### Meetings and transcripts

Use a mixture:

- Minor syncs: 5–40 turns.
- Typical working meetings: 40–150 turns.
- Long reviews or planning sessions: 150–300+ turns.
- Median turn length generally 10–20 words, with both very short backchannels and long explanations.
- Approximately 15–35% of turns may be 1–5 words.
- Filler/disfluency should appear in roughly 20–40% of turns for raw transcripts, less in manually cleaned notes.
- Speaker counts should have a long tail; not every meeting needs many participants.

Meeting completion shapes should include resolved, unresolved, moved elsewhere, interrupted, and acknowledgement-heavy outcomes.

### Pull requests and Git activity

- Preserve major merged implementation outcomes.
- Add drafts, stale work, closed-without-merge work, reopens, bot-only maintenance, and trivial PRs.
- Most items should have zero or one human comment; retain a sparse long tail of detailed reviews.
- Create lifespan variation from minutes to many weeks; target a P90 on the order of 10–30 days rather than same-day resolution for every item.
- Mix free-form bodies, sparse descriptions, templates, checklists, links, issue references, code excerpts, generated sections, and missing descriptions.
- Review behavior should include questions, nits, requested changes, partial responses, CI failures, approval after revision, stale approval, and conflicting reviewers.

### Email

- RFC-compliant dates and stable `Message-ID` values.
- `In-Reply-To` and `References` for threads.
- Plain, HTML, and multipart mixtures.
- Quote depth, forwards, signatures, aliases, auto-generated messages, bounces, and occasional malformed-but-readable mail.
- Attachment metadata without requiring binary bodies.
- Long silence and thread drift.

### Jira and Confluence

- Jira changelogs, comments, links, status drift, reopenings, duplicates, incomplete fields, stale assignees, and abandoned items.
- Confluence revisions, draft/tiny/long document mixtures, inconsistent templates, comments, links, attachments, and stale published pages.
- Do not make every ticket have a completion artifact or every page have a uniform heading schema.

### CRM, support, and operational systems

- Sparse fields, ownership changes, duplicated customers/tickets, merges, delayed updates, machine activities, corrected invoices, redelivered exports, out-of-order observations, and isolated telemetry anomalies.
- These sources should sometimes provide decisive evidence and often provide only weak context.

## Model-use policy

Use deterministic logic for:

- timing;
- object identity and revisions;
- metadata and optional fields;
- reactions, bots, status events, and redelivery;
- source envelopes;
- low-information routine messages;
- formatting and presentation degradation;
- attachment metadata;
- replay and packaging.

Use a language model selectively for:

- splitting polished Slack prose into coherent multi-actor exchanges;
- expanding important meetings;
- creating uneven PR review conversations;
- expressing secondary uncertainty and scope drift;
- scattering an existing truth event across source perspectives.

Every model task should receive synthetic context only, protected facts, allowed-change fields, target discourse shape, and output schema. Cache results by input hash, policy version, prompt version, model, and seed. Reject outputs that alter protected facts, introduce unknown sensitive material, or break source identity.

## Validation gates

### Privacy

- No runtime dependency on the proprietary directory.
- No proprietary text, identifiers, filenames, or vocabulary in prompts, fixtures, or output.
- Checked-in fixtures remain independently authored synthetic examples.

### Identity and replay

- Stable object identities across revisions.
- Redelivery preserves revision and content hash.
- Update increments revision.
- Delete follows create and produces a tombstone.
- Ordered delivery replay reconstructs final expected state.
- Interrupted application resumes idempotently.

### Temporal integrity

- Parent messages precede replies.
- Created time does not follow update/delete time.
- Effective and observed time differences are intentional.
- Timestamps are not uniformly gridded.
- Weekend/after-hours activity remains plausible for the synthetic organization.

### Semantic integrity

- Protected major facts survive all transformations.
- Every deliberate contradiction is separately attributable.
- Secondary drift is restricted to declared fields.
- No observation-plane mutation silently changes canonical truth.
- Cross-source bundles retain truth-event provenance.

### Native shape

- Each supported source uses its renderer.
- Unknown sources remain raw-only rather than receiving invented generic Markdown.
- Inbox files preserve important source conventions and evidence coordinates.

### Realism scorecard

Report aggregate distributions for:

- source volume and long-tail concentration;
- activity by day/hour/source;
- Slack length, threading, artifacts, and punctuation;
- meeting turns, speakers, turn lengths, fillers, and completion shapes;
- PR state, lifespan, comments, templates, links, and review features;
- object revisions, redeliveries, tombstones, stale age, and missing fields;
- cross-source anchor depth and span;
- duplicate, update, contradiction, and unresolved-case counts.

Target bands are warnings during calibration and hard gates only after human review confirms that optimizing them does not create metric-shaped artificiality.

### Logging and reports

- Never log source bodies or model outputs by default.
- Report paths, IDs, hashes, counts, metric distributions, validation codes, and cost.
- Preserve failed staged output for diagnosis without applying it.

## Rollout for the completed 180-day corpus

### Phase 0: freeze and inventory

1. Assign a corpus ID to the completed run.
2. Hash every input artifact and truth/provenance file.
3. Record the truth schema and protected-fact extraction version.
4. Produce the baseline realism scorecard.

### Phase 1: no-cost deterministic fixture

Run all deterministic passes against a small synthetic fixture that exercises every source and mutation type. Verify identity, replay, rollback, privacy, and semantic protections.

### Phase 2: representative five-day slice

Select five non-contiguous days containing ordinary work, a high-signal incident/project arc, quiet periods, and cross-source activity. Run the full pipeline, including selective language transformations. Human-review a small sample from every source.

### Phase 3: representative 30-day slice

Use several weeks with different project intensity. Calibrate distributions, model cost, batch size, failure recovery, and cross-source consistency. Confirm that the output no longer reads uniformly polished.

### Phase 4: full 180-day application

- Process by bounded batch, for example 250 files and up to 10 coordinated arcs.
- Checkpoint after every batch.
- Validate before applying.
- Stop on privacy, identity, replay, semantic, or temporal failure.
- Allow isolated language-generation failures to remain pending rather than applying partial bundles.

### Phase 5: final review and packaging

1. Run the strict validator and realism scorecard.
2. Compare baseline and final distributions.
3. Spot-check cross-source arcs, not only random files.
4. Review subtle contradiction cases for preserved ambiguity.
5. Package `raw/`, `deliveries/`, `inbox/`, `provenance/`, and unreviewed `gold/` candidates.

## Evaluation priorities for Clearweave

### Priority 1: knowledge-quality failures

The finished corpus must contain enough attributable cases to test whether Clearweave:

- mistakes recency for authority;
- collapses scoped facts incorrectly;
- treats provisional decisions as settled;
- misses quiet supersession;
- resolves simultaneous disagreement without review;
- follows a stale document over newer implementation evidence;
- accepts an incorrect correction;
- merges merely related claims as duplicates;
- drops evidence when canonical state changes; or
- publishes unresolved knowledge as certain.

### Priority 2: ingestion and replay failures

Test immutable revisions, redelivery, changed bytes under the same external revision, deletion/tombstones, retry, interrupted batches, out-of-order observations, attachment metadata, malformed inputs, and exact replay.

### Priority 3: user-trust failures

The corpus should let a user encounter:

- articles built from scattered evidence;
- conflicting records with understandable scope and dates;
- source excerpts that explain why the system is uncertain;
- corrections that preserve prior versions;
- review queues that distinguish missing evidence from disagreement; and
- irrelevant dirt that does not dominate retrieval.

## Definition of done

The 180-day realism pass is complete only when:

1. Every input file is inventoried and every output is represented in a manifest.
2. Every mutation action is idempotent, attributable, and replayable.
3. The full final state can be reconstructed from ordered deliveries.
4. Protected facts and truth-event links pass semantic validation.
5. Required source-native features appear with non-uniform, plausible distributions.
6. Slack, meeting, and PR distributions no longer exhibit the pristine patterns documented in this report.
7. Important project arcs remain deep but are less synchronously and explicitly linked.
8. The corpus includes reviewed examples of all ten contradiction/ambiguity types.
9. The pipeline can stop, resume, replan changed inputs, and roll back a batch.
10. Logs and committed files contain no proprietary content or source bodies.
11. A human cross-source spot-check finds no uniform “generated corporate prose” pattern.
12. Clearweave can ingest the `inbox/` projection without a special OrgForge-specific path.

## Recommended first implementation slice

Build the ledger, protected-fact contract, and three source adapters first:

1. Slack;
2. meetings/transcripts;
3. pull requests/Git activity.

These sources showed the clearest diagnostic gaps and provide the strongest basis for cross-source knowledge scenarios. The first vertical slice should:

- inventory one representative project arc;
- plan coordinated Slack, meeting, and PR mutations;
- apply them to staged files;
- validate identity, chronology, protected facts, and target distributions;
- record the batch;
- replay and roll it back;
- render the result into Clearweave-compatible inbox files.

Once this slice is reliable, extend the same action and validation contracts to email, Jira, Confluence, support, CRM, and operational exports. Avoid writing separate one-off mutators without the common ledger and semantic-safety boundary.

## Final recommendation

Do not regenerate the business from scratch and do not optimize for maximum dirt. Preserve the strong parts of OrgForge—the 180-day causal simulation, stable entities, and cross-source project graph—and make the observation plane realistically incomplete.

The desired corpus should feel less like an omniscient narrator distributing a project update to every system and more like an organization leaving imperfect traces: some automated, some stale, some conversational, some wrong, some duplicated, and only partially reconcilable.

## Implemented v5 package (2026-07-20)

The deterministic observation-realism pass has been applied to the frozen literal 180-day simulation export. It did not regenerate the underlying business and made no additional OpenAI API calls.

- Package: `export/calibration-realism-180d-clearweave-v5/`
- Window: 2026-01-01 through 2026-06-29 (180 days)
- Manifest entries: 193,648 raw/inbox artifacts
- Replay stream: 141,910 delivery actions across 180 daily delivery folders
- Realism ledger: 40,493 attributable mutations under policy version 2
- Total files: 335,567; disk size: approximately 1.6 GB
- Strict validation: all required identity/replay, coverage, native-shape, privacy, realism, run-health, spend, temporal, semantic-safety, and UTF-8 checks passed
- Test suite: 324 tests passed

The current package is ready for Clearweave ingestion, replay, scale, and retrieval stress testing. `raw/` contains source-shaped current-state artifacts, `deliveries/` contains the ordered daily change stream, and `inbox/` is the Clearweave-MVP text projection of those artifacts. `provenance/` contains the manifest, events, realism ledger, scorecard, and validation inputs.

This does not satisfy the human-review portions of the definition of done by itself. A frozen gold subset with reviewed evidence spans, sensitivity decisions, and examples of all ten contradiction/ambiguity types still needs human labeling before this corpus should be treated as a definitive Clearweave quality benchmark.

## Implemented semantic-realism v6 package (2026-07-20)

The v5 engineering package was subsequently audited for semantic realism. That review found that replay and scale behavior were sound but the generated observation surface was still dominated by timestamp inversion, repeated Slack routine text, four-word meeting fragments, duplicated PR templates, shallow lifecycle behavior, weak email transport/thread structure, sparse truth lineage, and a Datadog-heavy text inbox.

Version 6 corrects those failures deterministically from the same frozen source simulation. It makes no OpenAI API calls and does not read the proprietary comparison corpus.

- Package: `export/calibration-semantic-realism-180d-clearweave-v6/`
- Package README: `export/calibration-semantic-realism-180d-clearweave-v6/README.md`
- Window: 2026-01-01 through 2026-06-29; 174 active delivery days within 180 calendar days
- Manifest entries: 102,995 raw/inbox artifacts
- Semantic inbox: 6,357 files, including a deterministic 1,000-file Datadog sample
- Replay stream: 120,497 delivery actions replaying into 116,916 source objects
- Realism ledger: 18,720 attributable mutations under policy version 3
- Total files validated: 223,502; disk size: approximately 1.1 GB
- Strict validation: all required checks passed
- Test suite: 335 tests passed

### Verified v6 improvements

| Measure | Audited v5 behavior | Verified v6 |
| --- | ---: | ---: |
| Observed before effective | 79.1% | 0.0% |
| Slack exact duplicate share | 61.3% | 9.7% |
| Slack routine share | 65.3% | 27.3% |
| Slack routine duplicate share | 91.7% | 23.2% |
| Slack short-message share | — | 19.8% |
| Slack thread-size P90 | — | 8 messages |
| Meeting median words per turn | 4 | 19 |
| Meeting exact duplicate-turn share | 45.5% | 5.0% |
| Meeting question-turn share | 2.6% | 30.0% |
| Git duplicate title share | 61.9% | 0.0% |
| Git objects with zero or one comment | — | 90.6% |
| Email parseable dates | — | 100% |
| Email threaded share | — | 80.2% |
| Redeliveries | 14 | 626 |
| Deletes | 1 | 352 |
| Deep truth events | 0 | 544 |
| Datadog share of text inbox | 94.3% | 15.7% |

The v6 package passed identity replay, manifest and checksum coverage, native shape, temporal integrity, source messiness, semantic safety, policy-v3 realism, privacy, UTF-8, run-health, and spend-ceiling checks. The validator replayed all 120,497 actions and decoded all 223,502 files without a required failure.

The remaining limitation is unchanged in kind: `gold/candidates.jsonl` is unreviewed. Version 6 is suitable for ingestion, replay, retrieval, connector, and scale testing, but a frozen human-labeled subset is still required before using it as a definitive precision/recall or answer-quality benchmark.

## Implemented temporal-knowledge v7 package (2026-07-20)

A subsequent payload-native chronology audit found that v6's action ordering was valid while many create payloads still exposed later native timestamps, comments, or final state. The policy-v3 validator did not inspect those nested source timestamps. Version 7 fixes that release-blocking gap without regenerating the business or making OpenAI API calls.

- Package: `export/calibration-temporal-knowledge-180d-clearweave-v7/`
- Package README: `export/calibration-temporal-knowledge-180d-clearweave-v7/README.md`
- Window: 2026-01-01 through 2026-06-29; 177 active days
- Manifest entries: 103,045 raw/inbox artifacts
- Semantic inbox: 6,382 files
- Replay stream: 122,872 actions replaying into 117,581 objects
- Realism ledger: 20,081 attributed mutations under policy version 4
- Temporal knowledge scenarios: 24, with four examples across each of six scenario types
- Total files validated: 225,929; disk size: approximately 1.1 GB
- Strict validation: all required checks passed
- Test suite: 347 tests passed

### Verified v7 temporal contract

An independent scan of all 122,872 actions and 143,256 structured native timestamps found:

| Check | Result |
| --- | ---: |
| Historical native timestamps after observation | 0 |
| Structured native timestamps outside the declared window | 0 |
| Future nested comment timestamps | 0 |
| Git/Jira/Zendesk terminal creates | 0 |
| Git/Jira/Zendesk creates containing comments | 0 |
| Zoom date headers outside the window | 0 |

Mutable source snapshots are now lifecycle streams: 202 Git creates have 602 updates, 589 Jira creates have 1,493 updates, and 1,024 Zendesk creates have 1,024 updates. Slack retains 1,087 updates, 646 redeliveries, and 387 deletes. Native create payloads contain only create-time state; later comments, review activity, status changes, edits, corrections, and terminal state arrive later.

Version 7 also widens the surface distributions: meetings have a 63-turn median and 195-turn P90, Git review depth reaches nine comments while 90.1% of final PRs have zero or one, and Slack has 0.18% rounded timestamps with a distinct-message thread maximum of 35.

`provenance/knowledge_scenarios.jsonl` and `gold/temporal_candidates.jsonl` provide exact evidence action IDs and expected state by day for stale-document, superseded-owner, provisional-as-final, delayed-correction, partial-correction, and unresolved-conflict cases. They are deliberately marked `pending_human_review`; v7 is now suitable for deterministic temporal development and spot checks, but still does not claim to be a human-reviewed benchmark.

## Implemented v7.1 locator sanitization (2026-07-20)

The v7 follow-up audit found 4,909 create payloads whose native timestamps were correct but whose `source_path` still contained July–September dates. Path-derived Zoom object IDs, meeting IDs, and filenames could carry the same contradiction. Raw artifacts also exposed generator and evaluation controls.

Version 7.1 adds stable create-date aliases for source paths, path-derived IDs, meeting IDs, and filename metadata. It also projects raw/inbox payloads through a source-visible boundary that removes internal generator, staleness, scenario, correction, and source-path controls while preserving the source prose that implies those conditions.

The independent staged-package audit inspected 20,048 locator dates and found zero create-date mismatches, zero locator dates outside the window, zero filesystem path dates outside the window, and zero raw/inbox control leaks. Policy-v4 validation now enforces these conditions alongside native timestamp and lifecycle integrity.

Version 7.1 is conditionally ready for broad manual UAT, temporal reasoning, ingestion, replay, retrieval, and load testing. The gold labels remain pending human review, and broader scenario diversity plus remaining PR/meeting/Slack/Datadog texture improvements remain incremental follow-up work rather than release blockers.
