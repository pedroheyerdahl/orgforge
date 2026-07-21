# Clearweave source corpus calibration

## Goal

Use OrgForge's existing Apex Athletics simulation to produce a large, realistic source-system corpus for Clearweave. The first execution is a capped five-day calibration run; the later target is a reproducible 180-day run.

## Corpus contract

OrgForge remains the source-of-facts simulator. Its generated artifacts are exported into a Clearweave-compatible local-folder tree as UTF-8 Markdown or text, while retaining source-system conventions and messiness. The exporter must not normalize facts into Clearweave records, resolve contradictions, or remove stale and duplicate material.

The export contains:

- `inbox/<source-system>/` with source-like files for Confluence, Jira, Slack, Git, email, Zoom, Salesforce, Zendesk, Datadog, invoices, and NPS;
- `provenance/manifest.json` mapping each exported file to its source path, artifact identifier, simulation day, and timestamp;
- `provenance/events.jsonl` containing the simulation event records used to explain cross-system relationships.

The provenance directory is outside the Clearweave intake folder and is not treated as product knowledge.

## Calibration run

The CLI accepts simulation-day, output-directory, seed, and post-processing controls so calibration does not require editing the committed world configuration. The five-day run uses the OpenAI cloud preset with Luna as the worker model and Terra as the planner model. Sol is reserved for later high-value artifacts after quality and spend are measured.

The calibration output is written to a temporary directory. It must not overwrite the Clearweave repository's real intake folder.

## Cost guard

The calibration target is a $20 internal budget with a $25 hard ceiling. The runner records request and token usage when the provider exposes it and stops before starting additional work when the configured estimate reaches the safety threshold. A measured five-day result is used to extrapolate the 180-day cost before the full run is authorized.

## Verification

The exporter is tested against representative JSON, JSONL, Markdown, text, and email inputs. Verification checks that every exported file is UTF-8, every manifest entry points to an existing file, source-system directories are present, and the export contains no Clearweave canonical-record fields such as `record_id` or `supporting_record_ids`.
