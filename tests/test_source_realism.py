import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from email import policy as email_policy
from email.parser import Parser
from pathlib import Path

from source_actions import SourceAction, replay_actions
from native_timestamps import iter_native_timestamps
from source_realism import (
    RealismPolicy,
    adapt_export,
    augment_actions_to_span,
    conversation_shape_directive,
    degrade_transcript,
    messiness_features,
    normalize_email_observations,
    normalize_observations_to_window,
)


def _write_synthetic_export(root: Path) -> None:
    (root / "slack" / "channels" / "engineering").mkdir(parents=True)
    (root / "jira").mkdir()
    (root / "confluence" / "general").mkdir(parents=True)
    (root / "zoom" / "2026-01-03").mkdir(parents=True)
    (root / "emails").mkdir()
    (root / "salesforce").mkdir()
    (root / "zendesk").mkdir()
    (root / "git" / "prs").mkdir(parents=True)

    (root / "slack" / "channels" / "engineering" / "2026-01-02.json").write_text(
        json.dumps(
            [
                {
                    "message_id": "slack-msg-synthetic-001",
                    "user": "Hanna",
                    "text": "The retry banner still uses the previous timeout copy.",
                    "ts": "2026-01-02T09:05:00+00:00",
                    "date": "2026-01-02",
                    "thread_id": "slack-engineering-thread-001",
                    "root_id": "slack-engineering-thread-001",
                },
                {
                    "message_id": "slack-msg-synthetic-002",
                    "user": "Miki",
                    "text": "I can check the mobile state after standup.",
                    "ts": "2026-01-02T09:08:00+00:00",
                    "date": "2026-01-02",
                    "thread_id": "slack-engineering-thread-001",
                    "root_id": "slack-engineering-thread-001",
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
                "title": "Verify retry banner behavior",
                "description": "Confirm the existing timeout behavior on supported clients.",
                "status": "In Progress",
                "assignee": "Hanna",
                "created_at": "2026-01-02T08:00:00+00:00",
                "updated_at": "2026-01-03T14:00:00+00:00",
                "comments": [
                    {
                        "author": "Hanna",
                        "created": "2026-01-03T10:00:00+00:00",
                        "text": "Web is covered; mobile still needs a pass.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (root / "confluence" / "general" / "CONF-SYN-001.md").write_text(
        "# Retry behavior notes\n**ID:** CONF-SYN-001\n**Author:** Hanna\n**Date:** 2026-01-02\n\nThe timeout remains 30 seconds for TitanDB reads.\n",
        encoding="utf-8",
    )
    (root / "zoom" / "2026-01-03" / "meeting.md").write_text(
        "# Meeting Transcript\n**Date:** 2026-01-03\n\n**[10:00:00] Hanna:** TitanDB reads still use the existing timeout.\n\n**[10:02:00] Miki:** I need to check the mobile retry state.\n",
        encoding="utf-8",
    )
    (root / "emails" / "thread.eml").write_text(
        "From: hanna@apexathletics.io\nTo: miki@apexathletics.io\nDate: Sat, 03 Jan 2026 11:00:00 +0000\nMessage-ID: <synthetic-thread-1@apexathletics.io>\nSubject: retry copy\n\nCan you check mobile?\n",
        encoding="utf-8",
    )
    (root / "salesforce" / "opportunity.json").write_text(
        json.dumps({"Id": "006SYN001", "StageName": "Discovery", "LastModifiedDate": "2026-01-03T12:00:00+00:00"}),
        encoding="utf-8",
    )
    (root / "zendesk" / "ticket.json").write_text(
        json.dumps({"id": 4104, "status": "open", "updated_at": "2026-01-03T12:30:00+00:00"}),
        encoding="utf-8",
    )
    (root / "git" / "prs" / "PR-17.json").write_text(
        json.dumps({"pr_id": "PR-17", "status": "open", "created_at": "2026-01-03T13:00:00+00:00"}),
        encoding="utf-8",
    )


def test_adapt_export_is_deterministic_source_shaped_and_messy(tmp_path):
    export = tmp_path / "export"
    _write_synthetic_export(export)
    policy = RealismPolicy.load(Path("config/source_realism.yaml"))

    first = adapt_export(export, policy=policy, seed=42)
    second = adapt_export(export, policy=policy, seed=42)
    systems = {action.source_system for action in first}
    features = messiness_features(first)

    assert [a.to_dict() for a in first] == [a.to_dict() for a in second]
    assert {"slack", "jira", "confluence", "zoom", "email", "salesforce", "zendesk", "git"} <= systems
    assert features["short_messages"] >= 1
    assert features["singleton_messages"] >= 1
    assert features["bot_messages"] >= 1
    assert features["system_messages"] >= 1
    assert features["messages_with_reactions"] >= 1
    assert features["messages_with_files"] >= 1
    assert features["edited_messages"] >= 1
    assert features["redeliveries"] >= 1
    assert features["tombstones"] >= 1
    assert features["stale_records"] >= 1
    assert features["tiny_drafts"] >= 1
    assert features["transcript_degraded"] >= 1
    assert features["corrections"] >= 1
    assert "Downloads/sources" not in json.dumps([a.to_dict() for a in first])


def test_git_final_snapshot_becomes_create_review_updates_and_final_status(tmp_path):
    export = tmp_path / "export"
    prs = export / "git" / "prs"
    prs.mkdir(parents=True)
    (prs / "PR-42.json").write_text(
        json.dumps(
            {
                "pr_id": "PR-42",
                "title": "Guard the retry path",
                "description": "Keep the fallback state visible during rollout.",
                "status": "merged",
                "created_at": "2026-01-03T09:00:00+00:00",
                "updated_at": "2026-01-05T16:00:00+00:00",
                "merged_at": "2026-01-05T16:00:00+00:00",
                "comments": [
                    {
                        "author": "Miki",
                        "timestamp": "2026-01-04T10:00:00+00:00",
                        "text": "Which fallback did this cover?",
                    },
                    {
                        "author": "Hanna",
                        "timestamp": "2026-01-05T11:00:00+00:00",
                        "text": "Only the current client path.",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    actions = [
        action
        for action in adapt_export(
            export,
            policy=RealismPolicy(ensure_calibration_features=False),
            seed=42,
        )
        if action.source_system == "git" and action.object_id == "PR-42"
    ]

    assert [(action.operation, action.revision) for action in actions] == [
        ("create", 1),
        ("update", 2),
        ("update", 3),
        ("update", 4),
    ]
    assert actions[0].payload["status"] == "open"
    assert actions[0].payload["comments"] == []
    assert "merged_at" not in actions[0].payload
    assert "updated_at" not in actions[0].payload
    assert [len(action.payload["comments"]) for action in actions] == [0, 1, 2, 2]
    assert [action.payload["status"] for action in actions] == [
        "open",
        "open",
        "open",
        "merged",
    ]
    assert all(
        value.value <= datetime.fromisoformat(action.observed_at)
        for action in actions
        for value in iter_native_timestamps("git", action.payload)
        if value.kind == "historical"
    )
    replay_actions(actions)


def test_zendesk_final_ticket_snapshot_becomes_comment_and_resolution_updates(tmp_path):
    export = tmp_path / "export"
    tickets = export / "zendesk" / "tickets"
    tickets.mkdir(parents=True)
    (tickets / "ZD-42.json").write_text(
        json.dumps(
            {
                "ticket_id": "ZD-42",
                "subject": "Retry state is unclear",
                "status": "Solved",
                "created_at": "2026-01-03T09:00:00+00:00",
                "updated_at": "2026-01-06T15:00:00+00:00",
                "comments": [
                    {
                        "author": "Customer",
                        "timestamp": "2026-01-03T09:00:00+00:00",
                        "text": "The retry state is unclear.",
                    },
                    {
                        "author": "Support Agent",
                        "timestamp": "2026-01-05T13:00:00+00:00",
                        "text": "The older client remains under review.",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    actions = [
        action
        for action in adapt_export(
            export,
            policy=RealismPolicy(ensure_calibration_features=False),
            seed=42,
        )
        if action.source_system == "zendesk" and action.object_id == "ZD-42"
    ]

    assert [action.payload["status"] for action in actions] == [
        "open",
        "open",
        "open",
        "Solved",
    ]
    assert [len(action.payload["comments"]) for action in actions] == [0, 1, 2, 2]
    assert "updated_at" not in actions[0].payload
    assert [(action.operation, action.revision) for action in actions] == [
        ("create", 1),
        ("update", 2),
        ("update", 3),
        ("update", 4),
    ]
    replay_actions(actions)


def test_jira_comments_become_revisions_and_slack_has_native_fields(tmp_path):
    export = tmp_path / "export"
    _write_synthetic_export(export)
    actions = adapt_export(export, RealismPolicy.load(Path("config/source_realism.yaml")), seed=7)

    jira = [a for a in actions if a.source_system == "jira" and a.object_id == "SYN-104"]
    slack = [a for a in actions if a.source_system == "slack"]

    assert [a.revision for a in jira if a.operation != "redeliver"] == [1, 2, 3]
    assert "updated_at" not in jira[0].payload
    assert jira[0].payload["comments"] == []
    assert all(
        value.value <= datetime.fromisoformat(action.observed_at)
        for action in jira
        for value in iter_native_timestamps("jira", action.payload)
        if value.kind == "historical"
    )
    assert jira[-1].payload["status"] == "In Progress"
    assert all(message.payload["type"] == "message" for message in slack)
    assert all("ts" in message.payload and "channel_id" in message.payload for message in slack)
    assert any("client_msg_id" in message.payload for message in slack)
    assert any(message.payload.get("thread_ts") for message in slack)


def test_transcript_degradation_is_deterministic_and_protects_material_terms():
    source = "TitanDB returns the current athlete summary. We should verify the mobile retry state."

    first = degrade_transcript(source, seed=19, protected_terms=("TitanDB", "30 seconds"))
    second = degrade_transcript(source, seed=19, protected_terms=("TitanDB", "30 seconds"))

    assert first == second
    assert first != source
    assert "TitanDB" in first


def test_conversation_shapes_are_deterministic_and_not_always_resolved():
    first = conversation_shape_directive("day-2|slack|retry-state")
    second = conversation_shape_directive("day-2|slack|retry-state")
    shapes = {
        conversation_shape_directive(f"synthetic-shape-{index}").split(":", 1)[0]
        for index in range(80)
    }

    assert first == second
    assert {"resolved", "unresolved", "moved_elsewhere", "acknowledgement_heavy"} <= shapes
    assert "must reach" not in first.lower()
    assert "always" not in first.lower()


def test_generic_records_without_native_ids_include_full_source_path_in_identity(tmp_path):
    export = tmp_path / "export"
    first = export / "zendesk" / "comments" / "ZD-101" / "same-time.json"
    second = export / "zendesk" / "comments" / "ZD-102" / "same-time.json"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    payload = json.dumps({"author": "support", "text": "checking"})
    first.write_text(payload, encoding="utf-8")
    second.write_text(payload, encoding="utf-8")

    actions = adapt_export(
        export,
        RealismPolicy(ensure_calibration_features=False),
        seed=42,
    )

    assert len(actions) == 2
    assert len({action.object_id for action in actions}) == 2


def test_repeated_jsonl_native_ids_become_redelivery_or_update(tmp_path):
    export = tmp_path / "export"
    datadog = export / "datadog"
    datadog.mkdir(parents=True)
    alert = {
        "id": "ENG-109",
        "title": "Queue latency warning",
        "date_happened": 1767607800,
        "status": "Alert",
    }
    changed = {**alert, "status": "Recovered", "date_resolved": 1767607900}
    (datadog / "alerts.jsonl").write_text(
        "\n".join(json.dumps(value) for value in (alert, alert, changed)) + "\n",
        encoding="utf-8",
    )

    actions = adapt_export(
        export,
        RealismPolicy(ensure_calibration_features=False),
        seed=42,
    )
    repeated = [action for action in actions if action.object_id == "ENG-109"]

    assert [(action.operation, action.revision) for action in repeated] == [
        ("create", 1),
        ("redeliver", 1),
        ("update", 2),
    ]
    state = replay_actions(actions)
    assert state[("datadog", "ENG-109")]["payload"]["status"] == "Recovered"


def test_repeated_slack_message_ids_become_redelivery_or_update(tmp_path):
    export = tmp_path / "export"
    channel = export / "slack" / "channels" / "system-alerts"
    channel.mkdir(parents=True)
    message = {
        "message_id": "slack-msg-duplicate",
        "user": "Build Monitor",
        "text": "workflow completed with warnings",
        "ts": "2026-04-30T09:00:00+00:00",
    }
    edited = {**message, "text": "workflow completed", "edited": {"ts": "2026-04-30T09:01:00+00:00"}}
    (channel / "2026-04-30.json").write_text(
        json.dumps([message, message, edited]),
        encoding="utf-8",
    )

    actions = adapt_export(
        export,
        RealismPolicy(ensure_calibration_features=False),
        seed=42,
    )

    assert [(action.operation, action.revision) for action in actions] == [
        ("create", 1),
        ("redeliver", 1),
        ("update", 2),
    ]
    state = replay_actions(actions)
    assert state[("slack", "slack-msg-duplicate")]["payload"]["text"] == "workflow completed"


def test_normalization_compresses_long_timeline_across_target_window():
    source_start = datetime(2026, 1, 1, 9, tzinfo=timezone.utc)
    actions = [
        SourceAction(
            source_system="datadog",
            object_id=f"metric-{index:04d}",
            revision=1,
            operation="create",
            observed_at=(source_start + timedelta(days=index * 2)).isoformat(),
            effective_at=(source_start + timedelta(days=index * 2)).isoformat(),
            payload={"value": index},
        )
        for index in range(120)
    ]

    normalized = normalize_observations_to_window(
        actions,
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        180,
    )
    days = [action.observed_at[:10] for action in normalized]

    assert min(days) == "2026-01-01"
    assert max(days) == "2026-06-29"
    assert len(set(days)) >= 100
    assert max(days.count(day) for day in set(days)) < len(days) / 2


def test_normalization_preserves_object_revision_order():
    first = SourceAction(
        source_system="jira",
        object_id="ENG-1",
        revision=1,
        operation="create",
        observed_at="2026-08-01T09:00:00+00:00",
        effective_at="2026-08-01T09:00:00+00:00",
        payload={"status": "open"},
    )
    second = SourceAction(
        source_system="jira",
        object_id="ENG-1",
        revision=2,
        operation="update",
        observed_at="2026-09-01T09:00:00+00:00",
        effective_at="2026-09-01T09:00:00+00:00",
        payload={"status": "done"},
    )

    normalized = normalize_observations_to_window(
        [second, first],
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        180,
    )

    assert [action.revision for action in normalized] == [1, 2]
    assert normalized[0].observed_at < normalized[1].observed_at
    replay_actions(normalized)


def test_normalization_preserves_observed_effective_delta():
    source_start = datetime(2026, 7, 1, 12, tzinfo=timezone.utc)
    actions = [
        SourceAction(
            source_system="jira",
            object_id="stale-ticket",
            revision=1,
            operation="create",
            observed_at=source_start.isoformat(),
            effective_at=(source_start - timedelta(days=14, hours=3)).isoformat(),
            payload={"status": "open"},
        ),
        SourceAction(
            source_system="email",
            object_id="scheduled-email",
            revision=1,
            operation="create",
            observed_at=(source_start + timedelta(days=30)).isoformat(),
            effective_at=(source_start + timedelta(days=30, hours=2)).isoformat(),
            payload={"subject": "scheduled maintenance"},
        ),
    ]

    normalized = normalize_observations_to_window(
        actions,
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        180,
    )

    original_deltas = {
        action.object_id: datetime.fromisoformat(action.observed_at)
        - datetime.fromisoformat(action.effective_at)
        for action in actions
    }
    normalized_deltas = {
        action.object_id: datetime.fromisoformat(action.observed_at)
        - datetime.fromisoformat(action.effective_at)
        for action in normalized
    }
    assert normalized_deltas == original_deltas


def test_normalization_rebases_payload_timestamps_with_the_action_window():
    source_observed = datetime(2026, 6, 10, 10, 17, 23, tzinfo=timezone.utc)
    action = SourceAction(
        source_system="git",
        object_id="PR-TEMPORAL-1",
        revision=1,
        operation="create",
        observed_at=source_observed.isoformat(),
        effective_at=source_observed.isoformat(),
        payload={
            "created_at": "2026-06-01T09:00:00+00:00",
            "updated_at": "2026-06-20T12:00:00+00:00",
            "comments": [
                {"timestamp": "2026-06-18T11:00:00+00:00", "text": "future review"}
            ],
            "due_date": "2026-09-01",
        },
    )

    normalized = normalize_observations_to_window(
        [action], datetime(2026, 1, 1, tzinfo=timezone.utc), 180
    )[0]
    observed = datetime.fromisoformat(normalized.observed_at)
    native = list(iter_native_timestamps("git", normalized.payload))

    assert observed <= datetime(2026, 6, 29, 23, 59, 59, tzinfo=timezone.utc)
    assert all(
        value.value <= observed for value in native if value.kind == "historical"
    )
    assert all(
        datetime(2026, 1, 1, tzinfo=timezone.utc)
        <= value.value
        <= datetime(2026, 6, 29, 23, 59, 59, 999999, tzinfo=timezone.utc)
        for value in native
    )
    assert next(value.value for value in native if value.path == ("due_date",)) > observed


def test_normalization_rebases_zoom_transcript_date_header():
    action = SourceAction(
        source_system="zoom",
        object_id="zoom-native-date",
        revision=1,
        operation="create",
        observed_at="2026-09-03T10:00:00+00:00",
        effective_at="2026-09-03T10:00:00+00:00",
        payload={
            "transcript": (
                "# Meeting Transcript\n**Date:** 2026-09-03\n\n"
                "**[10:00:00] Hanna:** The retry path remains provisional.\n"
            )
        },
    )

    normalized = normalize_observations_to_window(
        [action], datetime(2026, 1, 1, tzinfo=timezone.utc), 180
    )[0]

    assert "**Date:** 2026-06-29" in normalized.payload["transcript"]
    assert "2026-09-03" not in normalized.payload["transcript"]


def test_normalization_uses_human_work_cadence_without_flattening_datadog():
    source_start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    actions = []
    for index in range(120):
        when = source_start + timedelta(days=index * 2, hours=index % 24)
        for system in ("jira", "datadog"):
            actions.append(
                SourceAction(
                    source_system=system,
                    object_id=f"{system}-{index:04d}",
                    revision=1,
                    operation="create",
                    observed_at=when.isoformat(),
                    effective_at=when.isoformat(),
                    payload={"value": index},
                )
            )

    normalized = normalize_observations_to_window(
        actions,
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        180,
    )
    by_system = {
        system: [
            datetime.fromisoformat(action.observed_at)
            for action in normalized
            if action.source_system == system
        ]
        for system in ("jira", "datadog")
    }

    jira_weekend = sum(value.weekday() >= 5 for value in by_system["jira"]) / 120
    jira_offhours = sum(value.hour < 8 or value.hour >= 19 for value in by_system["jira"]) / 120
    datadog_weekend = sum(value.weekday() >= 5 for value in by_system["datadog"]) / 120
    datadog_offhours = sum(value.hour < 8 or value.hour >= 19 for value in by_system["datadog"]) / 120

    assert jira_weekend <= 0.15
    assert jira_offhours <= 0.40
    assert datadog_weekend >= 0.20
    assert datadog_offhours >= 0.40


def test_normalization_adds_slack_timestamp_jitter_and_bounded_offhours():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    actions = []
    for index in range(240):
        when = start + timedelta(hours=9, days=index % 180)
        actions.append(
            SourceAction(
                source_system="slack",
                object_id=f"slack-jitter-{index:04d}",
                revision=1,
                operation="create",
                observed_at=when.isoformat(),
                effective_at=when.isoformat(),
                payload={
                    "type": "message",
                    "text": f"retry path {index}",
                    "ts": f"{when.timestamp():.6f}",
                },
            )
        )

    normalized = normalize_observations_to_window(actions, start, 180)
    observed = [datetime.fromisoformat(action.observed_at) for action in normalized]
    payload_times = [
        datetime.fromtimestamp(float(action.payload["ts"]), tz=timezone.utc)
        for action in normalized
    ]

    assert sum(value.second == 0 for value in payload_times) / len(payload_times) < 0.25
    offhours = sum(value.hour < 8 or value.hour >= 19 for value in observed) / len(observed)
    assert 0.05 <= offhours <= 0.25
    assert all(payload <= action for payload, action in zip(payload_times, observed))


def test_augmented_git_and_zendesk_comments_arrive_as_updates():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)

    actions = augment_actions_to_span([], target_days=180, seed=42, start_at=start)

    relevant = [
        action for action in actions if action.source_system in {"git", "zendesk"}
    ]
    assert all(
        action.payload.get("comments", []) == []
        for action in relevant
        if action.operation == "create"
    )
    assert any(
        action.operation == "update" and action.payload.get("comments")
        for action in relevant
        if action.source_system == "git"
    )
    assert any(
        action.operation == "update" and action.payload.get("comments")
        for action in relevant
        if action.source_system == "zendesk"
    )
    replay_actions(actions)


def test_augmented_datadog_is_active_on_every_declared_day():
    start = datetime(2026, 1, 1, 9, tzinfo=timezone.utc)

    actions = augment_actions_to_span([], target_days=180, seed=42, start_at=start)

    active_days = {
        action.observed_at[:10]
        for action in actions
        if action.source_system == "datadog"
    }
    assert len(active_days) == 180
    assert min(active_days) == "2026-01-01"
    assert max(active_days) == "2026-06-29"


def test_numeric_epoch_timestamps_survive_adaptation_and_span_window(tmp_path):
    export = tmp_path / "export"
    datadog = export / "datadog"
    datadog.mkdir(parents=True)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    records = [
        json.dumps(
            {
                "metric": "system.health",
                "value": index,
                "timestamp": int((start + timedelta(days=index * 3)).timestamp()),
            }
        )
        for index in range(60)
    ]
    (datadog / "metrics.jsonl").write_text("\n".join(records) + "\n", encoding="utf-8")

    adapted = adapt_export(
        export,
        RealismPolicy(ensure_calibration_features=False),
        seed=42,
    )
    normalized = normalize_observations_to_window(adapted, start, 180)

    assert len({action.observed_at[:10] for action in normalized}) >= 50


def test_span_augmentation_keeps_routine_slack_repetition_bounded():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    actions = augment_actions_to_span([], target_days=180, seed=42, start_at=start)
    texts = [
        str(action.payload.get("text", "")).strip()
        for action in actions
        if action.source_system == "slack"
        and action.operation == "create"
        and action.payload.get("synthetic_routine")
    ]
    counts = Counter(texts)
    duplicate_share = sum(count for count in counts.values() if count > 1) / len(texts)

    assert duplicate_share <= 0.35
    assert len(set(texts)) >= len(texts) * 0.65


def test_truth_lineage_matches_exact_cross_source_ids_threads_and_paths(tmp_path):
    export = tmp_path / "export"
    slack_dir = export / "slack" / "channels" / "engineering"
    slack_dir.mkdir(parents=True)
    (export / "jira").mkdir()
    (export / "git" / "prs").mkdir(parents=True)
    (export / "emails").mkdir()

    (slack_dir / "2026-01-02.json").write_text(
        json.dumps(
            [
                {
                    "message_id": "slack-linked-root",
                    "thread_id": "thread-cross-1",
                    "root_id": "thread-cross-1",
                    "user": "Hanna",
                    "text": "PR-1 follows SYN-1",
                    "ts": "2026-01-02T09:00:00+00:00",
                },
                {
                    "message_id": "slack-linked-reply",
                    "thread_id": "thread-cross-1",
                    "root_id": "thread-cross-1",
                    "thread_ts": "2026-01-02T09:00:00+00:00",
                    "user": "Miki",
                    "text": "checking",
                    "ts": "2026-01-02T09:02:00+00:00",
                },
                {
                    "message_id": "slack-unrelated",
                    "thread_id": "thread-other",
                    "root_id": "thread-other",
                    "user": "Tom",
                    "text": "lunch later?",
                    "ts": "2026-01-02T12:00:00+00:00",
                },
            ]
        ),
        encoding="utf-8",
    )
    (export / "jira" / "SYN-1.json").write_text(
        json.dumps({"id": "SYN-1", "status": "open", "created_at": "2026-01-02T08:00:00+00:00"}),
        encoding="utf-8",
    )
    (export / "git" / "prs" / "PR-1.json").write_text(
        json.dumps({"pr_id": "PR-1", "status": "open", "created_at": "2026-01-02T10:00:00+00:00"}),
        encoding="utf-8",
    )
    (export / "emails" / "thread.eml").write_text(
        "From: hanna@apexathletics.io\nTo: miki@apexathletics.io\n"
        "Date: Fri, 02 Jan 2026 11:00:00 +0000\n"
        "Message-ID: <different-native-id@apexathletics.io>\n"
        "Subject: SYN-1 follow-up\n\nPR-1 is ready for review.\n",
        encoding="utf-8",
    )
    (export / "simulation_events.jsonl").write_text(
        json.dumps(
            {
                "mongo_id": "EVT-cross-source-1",
                "artifact_ids": {
                    "jira": "SYN-1",
                    "pr": "PR-1",
                    "slack_thread": "thread-cross-1",
                    "email_path": "emails/thread.eml",
                },
                "facts": {"causal_chain": ["SYN-1", "PR-1"]},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    actions = adapt_export(
        export,
        RealismPolicy(ensure_calibration_features=False),
        seed=42,
    )
    linked = {
        (action.source_system, action.object_id): action.truth_event_ids
        for action in actions
    }

    assert linked[("jira", "SYN-1")] == ("EVT-cross-source-1",)
    assert linked[("git", "PR-1")] == ("EVT-cross-source-1",)
    assert linked[("slack", "slack-linked-root")] == ("EVT-cross-source-1",)
    assert linked[("slack", "slack-linked-reply")] == ("EVT-cross-source-1",)
    assert linked[("email", "<different-native-id@apexathletics.io>")] == (
        "EVT-cross-source-1",
    )
    assert linked[("slack", "slack-unrelated")] == ()


def test_email_normalization_repairs_headers_threads_and_attachments():
    start = datetime(2026, 1, 2, 9, tzinfo=timezone.utc)
    actions = []
    for index in range(60):
        when = start + timedelta(hours=index)
        actions.append(
            SourceAction(
                source_system="email",
                object_id=f"email-{index:03d}",
                revision=1,
                operation="create",
                observed_at=when.isoformat(),
                effective_at=when.isoformat(),
                truth_event_ids=("EVT-email-thread",),
                payload={
                    "message_id": f"email-{index:03d}",
                    "subject": "Re: Retry state",
                    "raw_eml": (
                        "From: hanna@apexathletics.io\n"
                        f"To: {'miki' if index % 2 == 0 else 'tom'}@apexathletics.io\n"
                        f"Date: {when.isoformat()}\n"
                        "Subject: Re: Retry state\n\n"
                        f"body-marker-{index}\n"
                    ),
                },
            )
        )

    normalized = normalize_email_observations(actions, seed=42)
    messages = [
        Parser(policy=email_policy.default).parsestr(action.payload["raw_eml"])
        for action in normalized
    ]

    assert len({str(message["Message-ID"]) for message in messages}) == len(messages)
    assert all(message["Date"].datetime is not None for message in messages)
    assert all(message["Delivered-To"] for message in messages)
    assert all(message["Return-Path"] for message in messages)
    assert all(message["Received"] for message in messages)
    assert not messages[0]["In-Reply-To"]
    assert all(message["In-Reply-To"] for message in messages[1:])
    assert all(message["References"] for message in messages[1:])
    for index, message in enumerate(messages):
        body = message.get_body(preferencelist=("plain",)).get_content()
        assert f"body-marker-{index}" in body
    assert any(
        any(part.get_content_disposition() == "attachment" for part in message.walk())
        for message in messages
    )
    replay_actions(normalized)


def test_email_normalization_recovers_some_subject_threads_across_recipient_changes():
    start = datetime(2026, 1, 2, 9, tzinfo=timezone.utc)
    actions = []
    for index in range(80):
        when = start + timedelta(hours=index)
        actions.append(
            SourceAction(
                source_system="email",
                object_id=f"routing-change-{index:03d}",
                revision=1,
                operation="create",
                observed_at=when.isoformat(),
                effective_at=when.isoformat(),
                payload={
                    "raw_eml": (
                        "From: alerts@apexathletics.io\n"
                        f"To: queue-{index:03d}@apexathletics.io\n"
                        "Subject: Retry queue notification\n\n"
                        f"queue marker {index}\n"
                    )
                },
            )
        )

    normalized = normalize_email_observations(actions, seed=42)
    messages = [
        Parser(policy=email_policy.default).parsestr(action.payload["raw_eml"])
        for action in normalized
    ]

    threaded = sum(bool(message["In-Reply-To"]) for message in messages)
    assert 35 <= threaded <= 55
