import hashlib
import json
from pathlib import Path

from clearweave_corpus import export_corpus


def _write_source_export(root: Path) -> None:
    (root / "slack" / "channels" / "engineering").mkdir(parents=True)
    (root / "jira").mkdir()
    (root / "confluence" / "general").mkdir(parents=True)
    (root / "zoom" / "2026-01-03").mkdir(parents=True)
    (root / "emails").mkdir()
    (root / "provenance").mkdir()

    (root / "slack" / "channels" / "engineering" / "2026-01-02.json").write_text(
        json.dumps(
            [
                {
                    "message_id": "slack-msg-synthetic-001",
                    "user": "Hanna",
                    "text": "retry banner is still stale",
                    "ts": "2026-01-02T09:05:00+00:00",
                },
                {
                    "message_id": "slack-msg-synthetic-002",
                    "user": "Miki",
                    "text": "looking",
                    "ts": "2026-01-02T09:07:00+00:00",
                    "thread_ts": "2026-01-02T09:05:00+00:00",
                },
            ]
        ),
        encoding="utf-8",
    )
    (root / "jira" / "SYN-104.json").write_text(
        json.dumps(
            {
                "id": "SYN-104",
                "title": "Verify retry banner",
                "description": "Check supported clients.",
                "status": "In Progress",
                "created_at": "2026-01-02T08:00:00+00:00",
                "updated_at": "2026-01-03T14:00:00+00:00",
                "comments": [
                    {
                        "author": "Hanna",
                        "created": "2026-01-03T10:00:00+00:00",
                        "text": "web checked; mobile pending",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (root / "confluence" / "general" / "CONF-SYN-001.md").write_text(
        "# Retry notes\n\nnot final — check the mobile thread\n",
        encoding="utf-8",
    )
    (root / "zoom" / "2026-01-03" / "meeting.md").write_text(
        "# Meeting Transcript\n**Date:** 2026-01-03\n\n**[10:00:00] Hanna:** The timeout is unchanged.\n",
        encoding="utf-8",
    )
    (root / "emails" / "thread.eml").write_text(
        "From: hanna@apexathletics.io\nTo: miki@apexathletics.io\nDate: Sat, 03 Jan 2026 11:00:00 +0000\nMessage-ID: <synthetic-thread-1@apexathletics.io>\nSubject: retry copy\n\nCan you check mobile?\n",
        encoding="utf-8",
    )
    (root / "emails" / "thread-no-id.eml").write_text(
        "From: system@apexathletics.io\nTo: ops@apexathletics.io\nDate: Sat, 03 Jan 2026 11:30:00 +0000\nSubject: generated alert\n\ncheck the queue\n",
        encoding="utf-8",
    )
    (root / "simulation_events.jsonl").write_text(
        json.dumps(
            {
                "event_id": "sim-event-synthetic-1",
                "artifact_ids": {"jira": "SYN-104"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "provenance" / "run_status.json").write_text(
        '{"status":"completed","unrecovered":0}\n', encoding="utf-8"
    )
    (root / "provenance" / "llm_resilience.jsonl").write_text(
        '{"outcome":"recovered"}\n', encoding="utf-8"
    )


def test_export_corpus_uses_native_source_shapes_and_daily_actions(tmp_path):
    source = tmp_path / "export"
    _write_source_export(source)

    output = tmp_path / "corpus"
    manifest = export_corpus(source, output, seed=42)

    slack_raw = output / "raw" / "slack" / "channels" / "engineering.json"
    slack_inbox = output / "inbox" / "slack" / "channels" / "engineering.md"
    slack_data = json.loads(slack_raw.read_text(encoding="utf-8"))

    assert set(slack_data) == {"channel", "users", "messages", "threads", "state"}
    assert slack_data["channel"]["name"] == "engineering"
    assert slack_data["messages"]
    assert slack_data["threads"]
    assert "**Thread**" in slack_inbox.read_text(encoding="utf-8")
    assert (output / "raw" / "jira" / "SYN-104.json").exists()
    assert (output / "inbox" / "jira" / "SYN-104.md").exists()
    assert (output / "raw" / "confluence" / "CONF-SYN-001.json").exists()
    assert (output / "inbox" / "confluence" / "CONF-SYN-001.md").exists()
    assert list((output / "deliveries").glob("*/*/*.json"))
    assert (output / "provenance" / "source_actions.jsonl").exists()
    assert (output / "provenance" / "events.jsonl").exists()
    assert manifest["classification"] == "synthetic_non_confidential"


def test_manifest_covers_raw_and_inbox_with_relative_paths_and_checksums(tmp_path):
    source = tmp_path / "export"
    _write_source_export(source)
    output = tmp_path / "corpus"

    manifest = export_corpus(source, output, seed=42)

    assert manifest["entries"]
    representations = {entry["representation"] for entry in manifest["entries"]}
    assert {"raw", "inbox"} <= representations
    for entry in manifest["entries"]:
        artifact = output / entry["path"]
        assert artifact.exists()
        assert not Path(entry["path"]).is_absolute()
        assert hashlib.sha256(artifact.read_bytes()).hexdigest() == entry["sha256"]
        assert entry["object_id"]
        assert entry["revision"] >= 1
        assert entry["operation"] in {"create", "update", "delete", "redeliver"}
        assert entry["observed_at"]
        assert entry["effective_at"]


def test_inbox_avoids_generic_pretty_json_and_preserves_eml(tmp_path):
    source = tmp_path / "export"
    _write_source_export(source)
    output = tmp_path / "corpus"

    export_corpus(source, output, seed=9)

    jira = (output / "inbox" / "jira" / "SYN-104.md").read_text(encoding="utf-8")
    confluence = (output / "inbox" / "confluence" / "CONF-SYN-001.md").read_text(
        encoding="utf-8"
    )
    email_files = list((output / "inbox" / "email").glob("*.eml"))

    assert "Export representation: JSON record rendered as source text" not in jira
    assert "```json" not in jira
    assert "Export representation" not in confluence
    assert email_files
    assert all(
        "Message-ID:" in path.read_text(encoding="utf-8") for path in email_files
    )
    assert "record_id" not in jira
    assert "supporting_record_ids" not in jira


def test_export_corpus_copies_resilience_provenance_and_gold_candidates(tmp_path):
    source = tmp_path / "export"
    _write_source_export(source)
    output = tmp_path / "corpus"

    export_corpus(source, output, seed=42)

    assert (output / "provenance" / "run_status.json").read_text() == (
        '{"status":"completed","unrecovered":0}\n'
    )
    assert (output / "provenance" / "llm_resilience.jsonl").read_text() == (
        '{"outcome":"recovered"}\n'
    )
    candidates = (output / "gold" / "candidates.jsonl").read_text(encoding="utf-8")
    assert "unreviewed" in candidates


def test_target_days_adds_large_replayable_cross_source_workload(tmp_path):
    source = tmp_path / "export"
    _write_source_export(source)
    output = tmp_path / "corpus"

    manifest = export_corpus(
        source,
        output,
        seed=42,
        target_days=180,
        target_start="2026-01-01",
    )
    actions = [
        json.loads(line)
        for line in (output / "provenance" / "source_actions.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    observed_days = sorted(action["observed_at"][:10] for action in actions)
    systems = {action["source_system"] for action in actions}

    assert manifest["target_days"] == 180
    assert manifest["target_start"] == "2026-01-01"
    assert manifest["target_end"] == "2026-06-29"
    assert len(actions) >= 900
    assert observed_days[0] == "2026-01-01"
    assert observed_days[-1] == "2026-06-29"
    assert (
        __import__("datetime").date.fromisoformat(observed_days[-1])
        - __import__("datetime").date.fromisoformat(observed_days[0])
    ).days >= 179
    assert {
        "slack",
        "jira",
        "confluence",
        "email",
        "zoom",
        "salesforce",
        "zendesk",
        "git",
        "datadog",
        "nps",
    } <= systems
    assert {action["operation"] for action in actions} >= {
        "create",
        "update",
        "redeliver",
        "delete",
    }


def test_observation_realism_package_writes_ledger_and_scorecard(tmp_path):
    source = tmp_path / "export"
    _write_source_export(source)
    output = tmp_path / "corpus"

    manifest = export_corpus(
        source,
        output,
        seed=42,
        target_days=180,
        target_start="2026-01-01",
        observation_realism=True,
    )

    ledger = output / "provenance" / "realism_ledger.jsonl"
    scorecard = json.loads(
        (output / "provenance" / "realism_scorecard.json").read_text(encoding="utf-8")
    )
    knowledge_scenarios = [
        json.loads(line)
        for line in (output / "provenance" / "knowledge_scenarios.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    temporal_candidates = [
        json.loads(line)
        for line in (output / "gold" / "temporal_candidates.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    final_actions = [
        json.loads(line)
        for line in (output / "provenance" / "source_actions.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    final_by_id = {item["action_id"]: item for item in final_actions}
    assert manifest["realism_policy_version"] == 5
    assert manifest["realism_ledger_entries"] > 0
    assert manifest["knowledge_scenarios"] == 24
    assert len(knowledge_scenarios) == len(temporal_candidates) == 24
    for scenario in knowledge_scenarios:
        evidence = [final_by_id[action_id] for action_id in scenario["evidence_action_ids"]]
        assert scenario["source_systems"] == list(
            dict.fromkeys(item["source_system"] for item in evidence)
        )
        assert scenario["observed_days"] == sorted(
            {item["observed_at"][:10] for item in evidence}
        )
        if scenario["resolution_state"] == "unresolved":
            assert scenario["correction_action_id"] is None
        else:
            assert scenario["correction_action_id"] in scenario["evidence_action_ids"]
    assert {
        "stale_document",
        "superseded_owner",
        "provisional_as_final",
        "delayed_correction",
        "partial_correction",
        "unresolved_conflict",
    } <= {item["scenario_type"] for item in temporal_candidates}
    assert all(
        scorecard["knowledge_errors"]["by_type"].get(name, 0) >= 3
        for name in {
            "stale_document",
            "superseded_owner",
            "provisional_as_final",
            "delayed_correction",
            "partial_correction",
            "unresolved_conflict",
        }
    )
    source_visible_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (output / "raw").rglob("*")
        if path.is_file()
    )
    assert "synthetic_routine" not in source_visible_text
    assert "correction_scope" not in source_visible_text
    assert '"supersedes"' not in source_visible_text
    assert len(ledger.read_text(encoding="utf-8").splitlines()) == manifest["realism_ledger_entries"]
    assert scorecard["delivery"]["max_daily_share"] < 0.50
    assert scorecard["slack"]["short_message_share"] >= 0.08
    assert scorecard["schema_version"] == 4
    assert scorecard["temporal"]["by_source"]["datadog"]["active_days"] == 180
    assert scorecard["slack"]["thread_size_histogram"].get("4", 0) > 0
    assert scorecard["slack"]["dominant_thread_size_share"] <= 0.20
    assert scorecard["meetings"]["dominant_normalized_prefix_count"] <= 100
    assert scorecard["git"]["dominant_normalized_fivegram_share"] <= 0.50
    assert scorecard["git"]["terminal_lifecycle_p90_days"] >= 14
    assert scorecard["knowledge_errors"]["source_systems"] == [
        "confluence", "email", "git", "jira", "slack", "zendesk"
    ]
    assert scorecard["knowledge_errors"]["distinct_evidence_counts"] >= 4
    assert scorecard["knowledge_errors"]["distinct_durations"] >= 6


def test_semantic_inbox_samples_datadog_without_reducing_raw_or_deliveries(tmp_path):
    source = tmp_path / "export"
    _write_source_export(source)
    datadog = source / "datadog"
    datadog.mkdir()
    start = __import__("datetime").datetime(2026, 1, 1, tzinfo=__import__("datetime").timezone.utc)
    (datadog / "metrics.jsonl").write_text(
        "".join(
            json.dumps(
                {
                    "id": f"metric-{index:03d}",
                    "metric": "system.health",
                    "timestamp": int((start + __import__("datetime").timedelta(hours=index)).timestamp()),
                    "value": index,
                }
            )
            + "\n"
            for index in range(10)
        ),
        encoding="utf-8",
    )

    first = tmp_path / "corpus-first"
    second = tmp_path / "corpus-second"
    first_manifest = export_corpus(
        source,
        first,
        seed=42,
        observation_realism=True,
        datadog_inbox_limit=2,
    )
    export_corpus(
        source,
        second,
        seed=42,
        observation_realism=True,
        datadog_inbox_limit=2,
    )

    assert len(list((first / "raw" / "datadog").glob("*.json"))) == 10
    assert len(list((first / "deliveries").glob("*/*/*.json"))) >= 10
    first_inbox = sorted(path.name for path in (first / "inbox" / "datadog").glob("*.md"))
    second_inbox = sorted(path.name for path in (second / "inbox" / "datadog").glob("*.md"))
    assert len(first_inbox) == 2
    assert first_inbox == second_inbox
    assert first_manifest["inbox_profile"] == "semantic"
    assert first_manifest["datadog_inbox_limit"] == 2
    scorecard = json.loads(
        (first / "provenance" / "realism_scorecard.json").read_text(encoding="utf-8")
    )
    assert scorecard["schema_version"] == 4
    assert scorecard["inbox"]["by_source"]["datadog"] == 2


def test_export_rebases_path_derived_zoom_identity_with_the_observation(tmp_path):
    source = tmp_path / "export"
    meeting_dir = source / "zoom" / "2026-09-03"
    meeting_dir.mkdir(parents=True)
    (meeting_dir / "zoom_2026-09-03_abcd1234.md").write_text(
        "# Meeting Transcript\n**Date:** 2026-09-03\n\n"
        "**[10:00:00] Hanna:** The retry path remains provisional.\n",
        encoding="utf-8",
    )
    output = tmp_path / "corpus"

    export_corpus(
        source,
        output,
        seed=42,
        target_days=180,
        target_start="2026-01-01",
        observation_realism=True,
    )

    actions = [
        json.loads(line)
        for line in (output / "provenance" / "source_actions.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    meeting = next(
        action
        for action in actions
        if action["source_system"] == "zoom"
        and "abcd1234" in action["object_id"]
    )
    expected_date = meeting["observed_at"][:10]

    assert expected_date in meeting["object_id"]
    assert expected_date in meeting["payload"]["meeting_id"]
    assert expected_date in meeting["payload"]["source_path"]
    assert "2026-09-03" not in meeting["object_id"]
