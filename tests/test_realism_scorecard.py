from datetime import datetime, timedelta, timezone
from copy import deepcopy

from observation_realism import ObservationRealismPolicy, apply_observation_realism
from realism_scorecard import build_realism_scorecard, validate_realism_scorecard
from source_actions import SourceAction


def _message(
    index: int,
    text: str,
    step: timedelta = timedelta(hours=1),
    when: datetime | None = None,
) -> SourceAction:
    when = when or datetime(2026, 1, 1, 9, tzinfo=timezone.utc) + step * index
    return SourceAction(
        source_system="slack",
        object_id=f"msg-{index:04d}",
        revision=1,
        operation="create",
        observed_at=when.isoformat(),
        effective_at=when.isoformat(),
        truth_event_ids=(f"EVT-{index % 20:02d}",),
        payload={
            "type": "message",
            "channel_id": "CENG",
            "channel_name": "engineering",
            "user": "UHANNA",
            "text": text,
            "ts": f"{when.timestamp():.6f}",
            "client_msg_id": f"msg-{index:04d}",
        },
    )


def test_scorecard_accepts_distribution_aware_observation_pass():
    start = datetime(2026, 1, 5, tzinfo=timezone.utc)
    actions = []
    for index in range(240):
        business_index = index // 2
        calendar_day = business_index + 2 * (business_index // 5)
        when = start + timedelta(days=calendar_day, hours=9 + (index % 2) * 4)
        actions.append(
            _message(
                index,
                f"The retry path for client {index:04d} still needs another verification pass.",
                when=when,
            )
        )
    for index in range(12):
        when = start + timedelta(days=index * 14)
        turns = "\n".join(
            [
                f"**[10:00:00] Hanna:** The retry path for scenario {index} still needs another verification pass for the older client because the first export only covered web and the fallback report arrived later. We should compare timestamps before calling the status final.",
                f"**[10:02:00] Miki:** I checked scenario {index} on web, but not the older mobile build yet.",
                f"**[10:04:00] Tom:** Which environment produced fallback report {index}, and does it include the current revision?",
                f"**[10:06:00] Deepa:** Environment label {index} is missing, so I would keep the result provisional until the owner replies.",
                f"**[10:08:00] Morgan:** right on scenario {index}",
            ]
        )
        actions.append(
            SourceAction(
                source_system="zoom",
                object_id=f"zoom-{index}",
                revision=1,
                operation="create",
                observed_at=when.isoformat(),
                effective_at=when.isoformat(),
                truth_event_ids=(f"EVT-{index:02d}",),
                payload={"transcript": turns},
            )
        )
    for index in range(20):
        when = start + timedelta(days=index * 7, hours=10)
        actions.append(
            SourceAction(
                source_system="jira",
                object_id=f"LINK-{index:02d}",
                revision=1,
                operation="create",
                observed_at=when.isoformat(),
                effective_at=when.isoformat(),
                truth_event_ids=(f"EVT-{index:02d}",),
                payload={"status": "open", "title": f"Linked work {index:02d}"},
            )
        )
    actions.append(
        SourceAction(
            source_system="jira",
            object_id="END",
            revision=1,
            operation="create",
            observed_at=(start + timedelta(days=179)).isoformat(),
            effective_at=(start + timedelta(days=179)).isoformat(),
            payload={"status": "open"},
        )
    )

    transformed, _ledger = apply_observation_realism(
        actions,
        ObservationRealismPolicy(),
        seed=42,
    )
    scorecard = build_realism_scorecard(transformed)

    errors = validate_realism_scorecard(scorecard)
    assert errors == [], (errors, scorecard)
    assert scorecard["schema_version"] == 2
    assert scorecard["delivery"]["active_days"] >= 100
    assert scorecard["slack"]["short_message_share"] >= 0.08
    assert scorecard["slack"]["short_message_share"] <= 0.30
    assert scorecard["slack"]["p90_thread_messages"] >= 5
    assert scorecard["meetings"]["median_turns"] >= 6
    assert {"draft", "open", "merged", "closed"} <= set(scorecard["git"]["statuses"])
    assert scorecard["temporal"]["observed_before_effective_share"] == 0
    assert scorecard["truth"]["deep_events"] >= 20
    assert scorecard["slack"]["exact_duplicate_share"] <= 0.15
    assert scorecard["meetings"]["exact_duplicate_turn_share"] <= 0.15
    assert scorecard["meetings"]["stock_clarification_family_occurrences"] == 0
    assert scorecard["git"]["duplicate_title_share"] <= 0.20


def test_scorecard_rejects_pristine_and_day_concentrated_corpus():
    text = "This is a complete and carefully formatted corporate update with a clear conclusion."
    actions = [_message(index, text, timedelta(seconds=1)) for index in range(240)]

    scorecard = build_realism_scorecard(actions)
    errors = validate_realism_scorecard(scorecard)

    assert any("delivery concentration" in error for error in errors)
    assert any("short Slack" in error for error in errors)
    assert any("Slack punctuation" in error for error in errors)
    assert any("Slack thread" in error for error in errors)


def test_schema_v2_rejects_upper_bound_temporal_and_semantic_failures():
    start = datetime(2026, 1, 3, 2, tzinfo=timezone.utc)
    actions = []
    for index in range(6000):
        observed = start + timedelta(seconds=index)
        actions.append(
            SourceAction(
                source_system="slack",
                object_id=f"routine-{index:04d}",
                revision=1,
                operation="create",
                observed_at=observed.isoformat(),
                effective_at=(observed + timedelta(days=1)).isoformat(),
                payload={
                    "type": "message",
                    "text": "same polished routine status update.",
                    "synthetic_routine": True,
                    "ts": f"{observed.timestamp():.6f}",
                },
            )
        )

    scorecard = build_realism_scorecard(actions)
    errors = validate_realism_scorecard(scorecard)

    assert any("observed before effective" in error for error in errors)
    assert any("weekend" in error for error in errors)
    assert any("off-hours" in error for error in errors)
    assert any("exact duplicate" in error for error in errors)
    assert any("routine share" in error for error in errors)
    assert any("question share" in error for error in errors)
    assert any("punctuation" in error for error in errors)


def test_schema_v2_rejects_meeting_git_lifecycle_email_truth_and_inbox_failures():
    passing = {
        "schema_version": 2,
        "actions": 10000,
        "delivery": {"max_daily_share": 0.02},
        "temporal": {
            "observed_before_effective_share": 0.0,
            "by_source": {"slack": {"weekend_share": 0.05, "offhours_share": 0.20}},
        },
        "slack": {
            "messages": 5000,
            "routine_messages": 1000,
            "short_message_share": 0.15,
            "no_terminal_punctuation_share": 0.60,
            "question_share": 0.18,
            "exact_duplicate_share": 0.08,
            "routine_share": 0.20,
            "routine_duplicate_share": 0.10,
            "reaction_share": 0.10,
            "file_share": 0.03,
            "edited_share": 0.03,
            "link_share": 0.06,
            "mention_share": 0.09,
            "block_share": 0.02,
            "attachment_share": 0.01,
            "p90_thread_messages": 7,
        },
        "meetings": {
            "meetings": 20,
            "median_turns": 24,
            "short_turn_share": 0.25,
            "filler_turn_share": 0.20,
            "median_words_per_turn": 14,
            "p90_words_per_turn": 48,
            "question_turn_share": 0.16,
            "exact_duplicate_turn_share": 0.05,
            "p90_speakers": 6,
        },
        "git": {
            "objects": 100,
            "statuses": {"draft": 10, "open": 20, "merged": 60, "closed": 10},
            "zero_or_one_comment_share": 0.80,
            "checklist_share": 0.10,
            "link_share": 0.10,
            "duplicate_title_share": 0.05,
            "duplicate_body_share": 0.05,
            "median_body_words": 90,
            "routine_share": 0.15,
        },
        "lifecycle": {
            "redelivery_share": 0.01,
            "delete_share": 0.002,
            "slack_revision_backed_edit_share": 0.95,
        },
        "email": {
            "messages": 200,
            "parseable_date_share": 1.0,
            "threaded_share": 0.40,
            "routing_header_share": 1.0,
            "attachment_share": 0.05,
            "unthreaded_duplicate_subject_share": 0.05,
        },
        "truth": {
            "by_source": {
                "slack": {"actions": 5000, "linked_share": 0.20},
                "email": {"actions": 200, "linked_share": 0.20},
                "git": {"actions": 100, "linked_share": 0.40},
                "zendesk": {"actions": 100, "linked_share": 0.30},
            },
            "deep_events": 25,
        },
        "inbox": {"files": 10000, "datadog_share": 0.10},
    }
    assert validate_realism_scorecard(passing) == []

    broken = deepcopy(passing)
    broken["meetings"]["exact_duplicate_turn_share"] = 0.50
    broken["git"]["duplicate_title_share"] = 0.60
    broken["lifecycle"]["redelivery_share"] = 0.0
    broken["email"]["parseable_date_share"] = 0.02
    broken["truth"]["deep_events"] = 0
    broken["inbox"]["datadog_share"] = 0.94
    errors = validate_realism_scorecard(broken)

    assert any("meeting exact duplicate" in error for error in errors)
    assert any("Git duplicate title" in error for error in errors)
    assert any("redelivery" in error for error in errors)
    assert any("email parseable" in error for error in errors)
    assert any("deep truth" in error for error in errors)
    assert any("Datadog inbox" in error for error in errors)


def test_schema_v3_rejects_future_native_dates_and_terminal_creates():
    observed = datetime(2026, 1, 3, 9, tzinfo=timezone.utc)
    actions = [
        SourceAction(
            source_system="git",
            object_id="PR-FUTURE",
            revision=1,
            operation="create",
            observed_at=observed.isoformat(),
            effective_at=observed.isoformat(),
            payload={
                "status": "merged",
                "created_at": observed.isoformat(),
                "merged_at": "2026-07-10T12:00:00+00:00",
                "comments": [
                    {"timestamp": "2026-07-09T11:00:00+00:00", "text": "future"}
                ],
            },
        )
    ]

    scorecard = build_realism_scorecard(
        actions,
        schema_version=3,
        window_start="2026-01-01",
        window_end="2026-06-29",
    )
    errors = validate_realism_scorecard(scorecard)

    assert scorecard["native_temporal"]["future_historical_timestamps"] == 2
    assert scorecard["native_temporal"]["outside_window_timestamps"] == 2
    assert scorecard["native_temporal"]["terminal_creates"] == 1
    assert any("future native" in error for error in errors)
    assert any("outside declared window" in error for error in errors)
    assert any("terminal source states" in error for error in errors)


def test_schema_v3_rejects_mismatched_and_out_of_window_locator_dates():
    observed = datetime(2026, 1, 3, 9, tzinfo=timezone.utc)
    action = SourceAction(
        source_system="zoom",
        object_id="zoom_2026-09-03_abcd1234",
        revision=1,
        operation="create",
        observed_at=observed.isoformat(),
        effective_at=observed.isoformat(),
        payload={
            "meeting_id": "zoom_2026-09-03_abcd1234",
            "source_path": "zoom/2026-09-03/zoom_2026-09-03_abcd1234.md",
            "transcript": "No structured date appears in this prose.",
        },
    )

    scorecard = build_realism_scorecard(
        [action],
        schema_version=3,
        window_start="2026-01-01",
        window_end="2026-06-29",
    )
    errors = validate_realism_scorecard(scorecard)

    assert scorecard["native_temporal"]["locator_date_mismatches"] > 0
    assert scorecard["native_temporal"]["locator_dates_outside_window"] > 0
    assert any("locator date mismatch" in error for error in errors)
    assert any("locator dates remain outside" in error for error in errors)


def test_scorecard_scopes_reused_slack_thread_timestamps_by_channel():
    when = datetime(2026, 1, 2, 9, tzinfo=timezone.utc)
    root_ts = f"{when.timestamp():.6f}"
    actions = []
    for channel_index, replies in enumerate((2, 3), start=1):
        channel_id = f"C{channel_index}"
        actions.append(
            SourceAction(
                source_system="slack",
                object_id=f"root-{channel_index}",
                revision=1,
                operation="create",
                observed_at=when.isoformat(),
                effective_at=when.isoformat(),
                payload={"channel_id": channel_id, "text": "root", "ts": root_ts},
            )
        )
        for reply_index in range(replies):
            reply_time = when + timedelta(minutes=reply_index + 1)
            actions.append(
                SourceAction(
                    source_system="slack",
                    object_id=f"reply-{channel_index}-{reply_index}",
                    revision=1,
                    operation="create",
                    observed_at=reply_time.isoformat(),
                    effective_at=reply_time.isoformat(),
                    payload={
                        "channel_id": channel_id,
                        "text": "reply",
                        "ts": f"{reply_time.timestamp():.6f}",
                        "thread_ts": root_ts,
                    },
                )
            )

    scorecard = build_realism_scorecard(actions, schema_version=4)

    assert scorecard["slack"]["max_distinct_thread_messages"] == 4
    assert scorecard["slack"]["thread_size_histogram"] == {"3": 1, "4": 1}
    assert scorecard["slack"]["cross_channel_thread_ts_collisions"] == 1
