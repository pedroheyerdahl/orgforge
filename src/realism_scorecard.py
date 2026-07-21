"""Aggregate, privacy-safe realism metrics for synthetic observation actions."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, time, timezone
from email import policy as email_policy
from email.parser import Parser
import math
import re
from statistics import median
from typing import Any, Iterable

from source_actions import SourceAction, replay_actions
from native_timestamps import iter_native_timestamps
from source_locators import iter_locator_dates


def _share(count: int, total: int) -> float:
    return round(count / total, 6) if total else 0.0


def _percentile(values: list[int], percentile: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(percentile * len(ordered)) - 1))
    return int(ordered[index])


def _duplicate_share(values: list[str]) -> float:
    counts = Counter(values)
    return _share(sum(count for count in counts.values() if count > 1), len(values))


def _normalized_words(value: str) -> list[str]:
    return re.findall(r"[a-z]+", value.casefold())


def _dominant_ngram_share(values: list[str], size: int) -> float:
    counts: Counter[tuple[str, ...]] = Counter()
    for value in values:
        words = _normalized_words(value)
        counts.update(
            set(tuple(words[index : index + size]) for index in range(len(words) - size + 1))
        )
    return _share(max(counts.values(), default=0), len(values))


def build_realism_scorecard(
    actions: Iterable[SourceAction],
    *,
    schema_version: int = 2,
    inbox_counts: dict[str, int] | None = None,
    window_start: str | None = None,
    window_end: str | None = None,
    knowledge_scenarios: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    ordered = sorted(actions, key=lambda item: (item.observed_at, item.action_id))
    delivery_days = Counter(action.observed_at[:10] for action in ordered)

    slack = [
        action
        for action in ordered
        if action.source_system == "slack" and action.operation == "create"
    ]
    word_counts = [len(str(action.payload.get("text", "")).split()) for action in slack]
    def slack_thread_key(action: SourceAction, timestamp: str) -> tuple[str, str]:
        channel = str(
            action.payload.get("channel_id")
            or action.payload.get("channel_name")
            or "unknown-channel"
        )
        return channel, timestamp

    root_keys = {
        slack_thread_key(action, str(action.payload.get("ts", "")) or action.object_id): 1
        for action in slack
        if not action.payload.get("thread_ts")
        or str(action.payload.get("thread_ts")) == str(action.payload.get("ts", ""))
    }
    roots: dict[tuple[str, str], int] = dict(root_keys)
    for action in slack:
        ts = str(action.payload.get("ts", ""))
        thread_ts = str(action.payload.get("thread_ts", ""))
        if thread_ts and thread_ts != ts:
            key = slack_thread_key(action, thread_ts)
            roots[key] = roots.get(key, 0) + 1
    orphan_replies = sum(key not in root_keys for key, count in roots.items() if count > 0)
    terminal = (".", "!", "?")

    try:
        state = replay_actions(ordered)
    except ValueError:
        state = {}
    meeting_states = [
        value for (system, _object_id), value in state.items() if system == "zoom" and not value["deleted"]
    ]
    meeting_turns = []
    short_turns = 0
    filler_turns = 0
    total_turns = 0
    turn_pattern = re.compile(r"^\*\*\[[^\]]+\]\s+[^:]+:\*\*\s*(.*)$")
    for value in meeting_states:
        turns = []
        for line in str(value["payload"].get("transcript", "")).splitlines():
            match = turn_pattern.match(line.strip())
            if match:
                turns.append(match.group(1))
        meeting_turns.append(len(turns))
        for turn in turns:
            words = turn.split()
            total_turns += 1
            short_turns += len(words) <= 5
            filler_turns += bool(re.search(r"\b(?:um|uh|yeah|sorry|i mean|mm-hm)\b", turn, re.I))

    git_states = [
        value for (system, _object_id), value in state.items() if system == "git" and not value["deleted"]
    ]
    statuses = Counter(str(value["payload"].get("status", "unknown")) for value in git_states)
    comment_counts = [len(value["payload"].get("comments", []) or []) for value in git_states]

    scorecard = {
        "schema_version": schema_version,
        "actions": len(ordered),
        "delivery": {
            "active_days": len(delivery_days),
            "max_daily_actions": max(delivery_days.values(), default=0),
            "max_daily_share": _share(max(delivery_days.values(), default=0), len(ordered)),
            "first_day": min(delivery_days, default=None),
            "last_day": max(delivery_days, default=None),
        },
        "slack": {
            "messages": len(slack),
            "median_words": float(median(word_counts)) if word_counts else 0.0,
            "p90_words": _percentile(word_counts, 0.90),
            "short_message_share": _share(sum(value <= 5 for value in word_counts), len(slack)),
            "no_terminal_punctuation_share": _share(
                sum(not str(action.payload.get("text", "")).rstrip().endswith(terminal) for action in slack),
                len(slack),
            ),
            "link_share": _share(sum("https://" in str(action.payload.get("text", "")) for action in slack), len(slack)),
            "mention_share": _share(sum("@" in str(action.payload.get("text", "")) for action in slack), len(slack)),
            "code_share": _share(sum("`" in str(action.payload.get("text", "")) for action in slack), len(slack)),
            "reaction_share": _share(sum(bool(action.payload.get("reactions")) for action in slack), len(slack)),
            "file_share": _share(sum(bool(action.payload.get("files")) for action in slack), len(slack)),
            "edited_share": _share(sum(bool(action.payload.get("edited")) for action in slack), len(slack)),
            "bot_system_share": _share(
                sum(bool(action.payload.get("bot_id") or action.payload.get("subtype")) for action in slack),
                len(slack),
            ),
            "p90_thread_messages": _percentile(list(roots.values()), 0.90),
            "max_thread_messages": max(roots.values(), default=0),
            "orphan_reply_groups": orphan_replies,
        },
        "meetings": {
            "meetings": len(meeting_states),
            "median_turns": float(median(meeting_turns)) if meeting_turns else 0.0,
            "p90_turns": _percentile(meeting_turns, 0.90),
            "short_turn_share": _share(short_turns, total_turns),
            "filler_turn_share": _share(filler_turns, total_turns),
        },
        "git": {
            "objects": len(git_states),
            "statuses": dict(sorted(statuses.items())),
            "zero_or_one_comment_share": _share(sum(value <= 1 for value in comment_counts), len(comment_counts)),
            "max_comments": max(comment_counts, default=0),
            "checklist_share": _share(sum("- [ ]" in str(value["payload"].get("body", "")) for value in git_states), len(git_states)),
            "link_share": _share(sum("https://" in str(value["payload"].get("body", "")) for value in git_states), len(git_states)),
        },
    }
    if schema_version < 2:
        return scorecard

    temporal_by_source: dict[str, dict[str, Any]] = {}
    source_groups: dict[str, list[SourceAction]] = defaultdict(list)
    inverted = 0
    for action in ordered:
        source_groups[action.source_system].append(action)
        observed = datetime.fromisoformat(action.observed_at.replace("Z", "+00:00"))
        effective = datetime.fromisoformat(action.effective_at.replace("Z", "+00:00"))
        inverted += observed < effective
    for source, source_actions in sorted(source_groups.items()):
        timestamps = [
            datetime.fromisoformat(action.observed_at.replace("Z", "+00:00"))
            for action in source_actions
        ]
        temporal_by_source[source] = {
            "actions": len(source_actions),
            "active_days": len({value.date() for value in timestamps}),
            "weekend_share": _share(sum(value.weekday() >= 5 for value in timestamps), len(timestamps)),
            "offhours_share": _share(
                sum(value.hour < 8 or value.hour >= 19 for value in timestamps),
                len(timestamps),
            ),
        }

    slack_texts = [str(action.payload.get("text", "")).strip() for action in slack]
    routine_slack = [action for action in slack if action.payload.get("synthetic_routine")]
    routine_texts = [str(action.payload.get("text", "")).strip() for action in routine_slack]
    root_timestamps = {
        slack_thread_key(action, str(action.payload.get("ts", "")))
        for action in slack
        if not action.payload.get("thread_ts")
        or str(action.payload.get("thread_ts")) == str(action.payload.get("ts"))
    }
    active_threads: Counter[tuple[str, str]] = Counter()
    thread_channels: dict[str, set[str]] = defaultdict(set)
    for action in slack:
        thread_ts = str(action.payload.get("thread_ts", ""))
        if thread_ts and thread_ts != str(action.payload.get("ts", "")):
            key = slack_thread_key(action, thread_ts)
            active_threads[key] += 1
            thread_channels[thread_ts].add(key[0])
    active_thread_sizes = [count + 1 for count in active_threads.values()]
    final_slack_states = [
        value for (system, _object_id), value in state.items() if system == "slack" and not value["deleted"]
    ]
    scorecard["slack"].update(
        {
            "exact_duplicate_share": _duplicate_share(slack_texts),
            "routine_messages": len(routine_slack),
            "routine_share": _share(len(routine_slack), len(slack)),
            "routine_duplicate_share": _duplicate_share(routine_texts),
            "question_share": _share(sum("?" in text for text in slack_texts), len(slack_texts)),
            "block_share": _share(sum(bool(action.payload.get("blocks")) for action in slack), len(slack)),
            "attachment_share": _share(sum(bool(action.payload.get("attachments")) for action in slack), len(slack)),
            "empty_system_share": _share(
                sum(
                    not str(action.payload.get("text", "")).strip()
                    or action.payload.get("subtype") in {"channel_join", "channel_leave", "message_deleted"}
                    for action in slack
                ),
                len(slack),
            ),
            "edited_share": _share(
                sum(bool(value["payload"].get("edited")) for value in final_slack_states),
                len(final_slack_states),
            ),
            "p90_thread_messages": _percentile(active_thread_sizes, 0.90),
            "max_thread_messages": max(active_thread_sizes, default=0),
            "orphan_reply_groups": sum(root not in root_timestamps for root in active_threads),
            "cross_channel_thread_ts_collisions": sum(
                len(channels) > 1 for channels in thread_channels.values()
            ),
            "all_root_p90_distinct_messages": _percentile(list(roots.values()), 0.90),
            "threaded_only_p90_distinct_messages": _percentile(active_thread_sizes, 0.90),
            "max_distinct_thread_messages": max(roots.values(), default=0),
            "thread_size_histogram": {
                str(size): count
                for size, count in sorted(Counter(active_thread_sizes).items())
            },
            "dominant_thread_size_share": _share(
                max(Counter(active_thread_sizes).values(), default=0),
                len(active_thread_sizes),
            ),
            "rounded_timestamp_share": _share(
                sum(
                    str(action.payload.get("ts", "")).split(".", 1)[-1].rstrip("0") == ""
                    for action in slack
                ),
                len(slack),
            ),
        }
    )

    meeting_word_counts: list[int] = []
    meeting_speakers: list[int] = []
    meeting_questions = 0
    meeting_bodies: list[str] = []
    stock_clarification_patterns = (
        "part include the other environment",
        "which timestamp are we comparing",
        "treating that as final or still provisional",
    )
    stock_clarification_occurrences = 0
    meetings_with_stock_clarification = 0
    speaker_pattern = re.compile(r"^\*\*\[[^\]]+\]\s+([^:]+):\*\*\s*(.*)$")
    for value in meeting_states:
        speakers: set[str] = set()
        meeting_has_stock_clarification = False
        for line in str(value["payload"].get("transcript", "")).splitlines():
            match = speaker_pattern.match(line.strip())
            if not match:
                continue
            speakers.add(match.group(1))
            body = match.group(2)
            lowered_body = body.casefold()
            matches = sum(
                pattern in lowered_body for pattern in stock_clarification_patterns
            )
            stock_clarification_occurrences += matches
            meeting_has_stock_clarification |= bool(matches)
            meeting_bodies.append(body.strip())
            meeting_word_counts.append(len(body.split()))
            meeting_questions += "?" in body
        meeting_speakers.append(len(speakers))
        meetings_with_stock_clarification += meeting_has_stock_clarification
    scorecard["meetings"].update(
        {
            "median_words_per_turn": float(median(meeting_word_counts)) if meeting_word_counts else 0.0,
            "p90_words_per_turn": _percentile(meeting_word_counts, 0.90),
            "question_turn_share": _share(meeting_questions, len(meeting_word_counts)),
            "exact_duplicate_turn_share": _duplicate_share(meeting_bodies),
            "p90_speakers": _percentile(meeting_speakers, 0.90),
            "dominant_normalized_prefix_count": max(
                Counter(
                    " ".join(_normalized_words(body)[:6])
                    for body in meeting_bodies
                    if len(_normalized_words(body)) >= 6
                ).values(),
                default=0,
            ),
            "stock_clarification_family_occurrences": stock_clarification_occurrences,
            "meetings_with_stock_clarification": meetings_with_stock_clarification,
        }
    )

    git_titles = [str(value["payload"].get("title", "")).strip() for value in git_states]
    git_bodies = [str(value["payload"].get("body", "")).strip() for value in git_states]
    nonempty_body_words = [len(body.split()) for body in git_bodies if body]
    scorecard["git"].update(
        {
            "duplicate_title_share": _duplicate_share(git_titles),
            "duplicate_body_share": _duplicate_share(git_bodies),
            "median_body_words": float(median(nonempty_body_words)) if nonempty_body_words else 0.0,
            "routine_share": _share(
                sum(bool(value["payload"].get("synthetic_routine")) for value in git_states),
                len(git_states),
            ),
            "dominant_normalized_fivegram_share": _dominant_ngram_share(
                git_bodies, 5
            ),
        }
    )

    git_create_times: dict[str, datetime] = {}
    terminal_lifecycle_days: list[int] = []
    for action in ordered:
        if action.source_system != "git":
            continue
        observed = datetime.fromisoformat(action.observed_at.replace("Z", "+00:00"))
        if action.operation == "create":
            git_create_times[action.object_id] = observed
        elif (
            action.operation == "update"
            and str(action.payload.get("status", "")).casefold() in {"merged", "closed"}
            and action.object_id in git_create_times
        ):
            terminal_lifecycle_days.append(
                int((observed - git_create_times[action.object_id]).total_seconds() // 86400)
            )
    scorecard["git"]["terminal_lifecycle_p90_days"] = _percentile(
        terminal_lifecycle_days, 0.90
    )
    scorecard["git"]["terminal_lifecycles"] = len(terminal_lifecycle_days)

    operation_counts = Counter(action.operation for action in ordered)
    slack_update_objects = {
        action.object_id
        for action in ordered
        if action.source_system == "slack" and action.operation == "update"
    }
    displayed_edit_objects = {
        object_id
        for (system, object_id), value in state.items()
        if system == "slack" and value["payload"].get("edited")
    }

    truth_by_source: dict[str, dict[str, Any]] = {}
    event_objects: dict[str, set[tuple[str, str]]] = defaultdict(set)
    event_days: dict[str, set[str]] = defaultdict(set)
    event_sources: dict[str, set[str]] = defaultdict(set)
    for source, source_actions in sorted(source_groups.items()):
        truth_by_source[source] = {
            "actions": len(source_actions),
            "linked_share": _share(
                sum(bool(action.truth_event_ids) for action in source_actions),
                len(source_actions),
            ),
        }
        for action in source_actions:
            for event_id in action.truth_event_ids:
                event_objects[event_id].add((source, action.object_id))
                event_days[event_id].add(action.observed_at[:10])
                event_sources[event_id].add(source)

    email_states = [
        value for (system, _object_id), value in state.items() if system == "email" and not value["deleted"]
    ]
    email_messages = []
    email_subjects = []
    for value in email_states:
        message = Parser(policy=email_policy.default).parsestr(
            str(value["payload"].get("raw_eml", ""))
        )
        email_messages.append(message)
        email_subjects.append(
            re.sub(
                r"^(?:(?:re|fwd?)\s*:\s*)+",
                "",
                str(message.get("Subject") or "").strip(),
                flags=re.I,
            ).casefold()
        )
    subject_counts = Counter(email_subjects)
    parseable_dates = 0
    for message in email_messages:
        try:
            parseable_dates += bool(message.get("Date") and message["Date"].datetime)
        except (AttributeError, TypeError, ValueError):
            pass
    unthreaded_duplicates = sum(
        subject_counts[subject] > 1
        and not (message.get("In-Reply-To") or message.get("References"))
        for subject, message in zip(email_subjects, email_messages)
    )

    total_inbox = sum((inbox_counts or {}).values())
    scorecard.update(
        {
            "temporal": {
                "observed_before_effective_share": _share(inverted, len(ordered)),
                "by_source": temporal_by_source,
            },
            "lifecycle": {
                "operations": dict(sorted(operation_counts.items())),
                "redelivery_share": _share(operation_counts["redeliver"], len(ordered)),
                "delete_share": _share(operation_counts["delete"], len(ordered)),
                "slack_revision_backed_edit_share": _share(
                    len(displayed_edit_objects & slack_update_objects),
                    len(displayed_edit_objects),
                ),
            },
            "email": {
                "messages": len(email_messages),
                "parseable_date_share": _share(parseable_dates, len(email_messages)),
                "threaded_share": _share(
                    sum(bool(message.get("In-Reply-To") or message.get("References")) for message in email_messages),
                    len(email_messages),
                ),
                "routing_header_share": _share(
                    sum(
                        all(message.get(name) for name in ("Delivered-To", "Return-Path", "Received"))
                        for message in email_messages
                    ),
                    len(email_messages),
                ),
                "attachment_share": _share(
                    sum(
                        any(part.get_content_disposition() == "attachment" for part in message.walk())
                        for message in email_messages
                    ),
                    len(email_messages),
                ),
                "duplicate_subject_share": _duplicate_share(email_subjects),
                "unthreaded_duplicate_subject_share": _share(
                    unthreaded_duplicates, len(email_messages)
                ),
            },
            "truth": {
                "by_source": truth_by_source,
                "events": len(event_objects),
                "deep_events": sum(
                    len(event_objects[event_id]) >= 5
                    and len(event_days[event_id]) >= 3
                    and len(event_sources[event_id]) >= 2
                    for event_id in event_objects
                ),
            },
            "inbox": {
                "files": total_inbox,
                "by_source": dict(sorted((inbox_counts or {}).items())),
                "datadog_share": _share((inbox_counts or {}).get("datadog", 0), total_inbox),
            },
        }
    )
    if schema_version >= 3:
        scenario_counts = Counter(
            str(item.get("scenario_type", "unknown"))
            for item in (knowledge_scenarios or [])
        )
        scorecard["knowledge_errors"] = {
            "scenarios": len(knowledge_scenarios or []),
            "by_type": dict(sorted(scenario_counts.items())),
            "pending_human_review": sum(
                item.get("review_status") == "pending_human_review"
                for item in (knowledge_scenarios or [])
            ),
            "source_systems": sorted(
                {
                    str(source)
                    for item in (knowledge_scenarios or [])
                    for source in item.get("source_systems", [])
                }
            ),
            "source_combinations": len(
                {
                    tuple(item.get("source_systems", []))
                    for item in (knowledge_scenarios or [])
                }
            ),
            "distinct_evidence_counts": len(
                {
                    len(item.get("evidence_action_ids", []))
                    for item in (knowledge_scenarios or [])
                }
            ),
            "distinct_observed_day_counts": len(
                {
                    len(item.get("observed_days", []))
                    for item in (knowledge_scenarios or [])
                }
            ),
            "distinct_durations": len(
                {
                    int(item.get("duration_days", 0))
                    for item in (knowledge_scenarios or [])
                }
            ),
            "unresolved": sum(
                item.get("resolution_state") == "unresolved"
                for item in (knowledge_scenarios or [])
            ),
        }
        declared_start = (
            datetime.combine(
                datetime.fromisoformat(window_start).date(), time.min, tzinfo=timezone.utc
            )
            if window_start
            else None
        )
        declared_end = (
            datetime.combine(
                datetime.fromisoformat(window_end).date(), time.max, tzinfo=timezone.utc
            )
            if window_end
            else None
        )
        future_historical = 0
        outside_window = 0
        native_total = 0
        terminal_creates = 0
        locator_date_mismatches = 0
        locator_dates_outside_window = 0
        native_by_source: dict[str, Counter[str]] = defaultdict(Counter)
        create_dates: dict[tuple[str, str], Any] = {}
        for action in ordered:
            key = (action.source_system, action.object_id)
            observed_date = datetime.fromisoformat(
                action.observed_at.replace("Z", "+00:00")
            ).date()
            if action.operation == "create" or key not in create_dates:
                create_dates.setdefault(key, observed_date)
        terminal_states = {
            "git": {"merged", "closed"},
            "jira": {"done", "closed", "resolved"},
            "zendesk": {"closed", "solved"},
        }
        for action in ordered:
            observed_at = datetime.fromisoformat(action.observed_at.replace("Z", "+00:00"))
            key = (action.source_system, action.object_id)
            for native in iter_native_timestamps(action.source_system, action.payload):
                native_total += 1
                native_by_source[action.source_system]["timestamps"] += 1
                if native.kind == "historical" and native.value > observed_at:
                    future_historical += 1
                    native_by_source[action.source_system]["future_historical"] += 1
                if (
                    declared_start is not None
                    and declared_end is not None
                    and not declared_start <= native.value <= declared_end
                ):
                    outside_window += 1
                    native_by_source[action.source_system]["outside_window"] += 1
            for locator in iter_locator_dates(action):
                native_by_source[action.source_system]["locator_dates"] += 1
                if locator.value.date() != create_dates[key]:
                    locator_date_mismatches += 1
                    native_by_source[action.source_system]["locator_date_mismatches"] += 1
                if (
                    declared_start is not None
                    and declared_end is not None
                    and not declared_start <= locator.value <= declared_end
                ):
                    locator_dates_outside_window += 1
                    native_by_source[action.source_system][
                        "locator_dates_outside_window"
                    ] += 1
            if (
                action.operation == "create"
                and str(action.payload.get("status", "")).casefold()
                in terminal_states.get(action.source_system, set())
            ):
                terminal_creates += 1
                native_by_source[action.source_system]["terminal_creates"] += 1
        scorecard["native_temporal"] = {
            "timestamps": native_total,
            "future_historical_timestamps": future_historical,
            "outside_window_timestamps": outside_window,
            "terminal_creates": terminal_creates,
            "locator_date_mismatches": locator_date_mismatches,
            "locator_dates_outside_window": locator_dates_outside_window,
            "by_source": {
                source: dict(sorted(values.items()))
                for source, values in sorted(native_by_source.items())
            },
        }
    return scorecard


def validate_realism_scorecard(scorecard: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    schema_version = int(scorecard.get("schema_version", 1))
    release_scale = scorecard.get("actions", 0) >= 5000
    delivery = scorecard.get("delivery", {})
    if scorecard.get("actions", 0) >= 200 and delivery.get("max_daily_share", 1.0) > 0.50:
        errors.append(f"delivery concentration too high: {delivery.get('max_daily_share')}")

    slack = scorecard.get("slack", {})
    if slack.get("messages", 0) >= 200:
        if slack.get("short_message_share", 0.0) < 0.08:
            errors.append("short Slack message share is below 8%")
        if slack.get("short_message_share", 1.0) > 0.30 and (
            schema_version < 2 or release_scale
        ):
            errors.append("short Slack message share exceeds 30%")
        if slack.get("no_terminal_punctuation_share", 0.0) < 0.40:
            errors.append("Slack punctuation remains uniformly polished")
        if slack.get("reaction_share", 0.0) < 0.08:
            errors.append("Slack reaction share is below 8%")
        if slack.get("file_share", 0.0) < 0.025:
            errors.append("Slack file share is below 2.5%")
        if slack.get("edited_share", 0.0) < 0.02:
            errors.append("Slack edited share is below 2%")
        if slack.get("link_share", 0.0) < 0.05:
            errors.append("Slack link share is below 5%")
        if slack.get("mention_share", 0.0) < 0.08 and (
            schema_version < 2 or release_scale
        ):
            errors.append("Slack mention share is below 8%")
        if slack.get("p90_thread_messages", 0) < 5:
            errors.append("Slack thread P90 remains below 5 messages")

    meetings = scorecard.get("meetings", {})
    if meetings.get("meetings", 0) >= 10:
        if meetings.get("median_turns", 0) < 6:
            errors.append("meeting median remains below 6 turns")
        if meetings.get("short_turn_share", 0.0) < 0.12:
            errors.append("meeting short-turn share is below 12%")
        if meetings.get("filler_turn_share", 0.0) < 0.15:
            errors.append("meeting filler share is below 15%")

    git = scorecard.get("git", {})
    if git.get("objects", 0) >= 20:
        statuses = set(git.get("statuses", {}))
        if not {"draft", "open", "merged", "closed"} <= statuses:
            errors.append("Git lifecycle lacks draft/open/merged/closed states")
        if git.get("zero_or_one_comment_share", 0.0) < 0.60:
            errors.append("Git comments remain too uniformly dense")
        if git.get("checklist_share", 0.0) < 0.05:
            errors.append("Git checklist share is below 5%")
        if git.get("link_share", 0.0) < 0.05:
            errors.append("Git link share is below 5%")
    if schema_version < 2:
        return errors

    temporal = scorecard.get("temporal", {})
    if temporal.get("observed_before_effective_share", 0.0) > 0.02:
        errors.append("observed before effective share exceeds 2%")
    for source, values in temporal.get("by_source", {}).items():
        if source == "datadog":
            continue
        if values.get("actions", 0) < 100:
            continue
        if values.get("weekend_share", 0.0) > 0.15:
            errors.append(f"{source} weekend share exceeds 15%")
        if values.get("offhours_share", 0.0) > 0.40:
            errors.append(f"{source} off-hours share exceeds 40%")

    if slack.get("messages", 0) >= 200:
        if release_scale and slack.get("exact_duplicate_share", 0.0) < 0.05:
            errors.append("Slack exact duplicate share is below 5%")
        if release_scale and slack.get("exact_duplicate_share", 1.0) > 0.15:
            errors.append("Slack exact duplicate share exceeds 15%")
        if release_scale and slack.get("routine_share", 1.0) > 0.35:
            errors.append("Slack routine share exceeds 35%")
        if release_scale and slack.get("routine_duplicate_share", 1.0) > 0.25:
            errors.append("Slack routine exact duplicate share exceeds 25%")
        if not 0.10 <= slack.get("question_share", 0.0) <= 0.30:
            errors.append("Slack question share is outside 10-30%")
        if slack.get("no_terminal_punctuation_share", 0.0) > 0.75:
            errors.append("Slack no-terminal punctuation share exceeds 75%")
        if slack.get("block_share", 0.0) < 0.01:
            errors.append("Slack block share is below 1%")
        if slack.get("attachment_share", 0.0) < 0.005:
            errors.append("Slack attachment share is below 0.5%")

    if release_scale and meetings.get("meetings", 0) >= 20:
        if not 8 <= meetings.get("median_words_per_turn", 0) <= 25:
            errors.append("meeting median words per turn is outside 8-25")
        if meetings.get("p90_words_per_turn", 0) < 30:
            errors.append("meeting P90 words per turn is below 30")
        if not 0.10 <= meetings.get("short_turn_share", 0.0) <= 0.40:
            errors.append("meeting short-turn share is outside 10-40%")
        if not 0.08 <= meetings.get("question_turn_share", 0.0) <= 0.30:
            errors.append("meeting question-turn share is outside 8-30%")
        if meetings.get("exact_duplicate_turn_share", 1.0) > 0.15:
            errors.append("meeting exact duplicate turn share exceeds 15%")
        if meetings.get("p90_speakers", 0) < 5:
            errors.append("meeting speaker P90 is below 5")

    if git.get("objects", 0) >= 20:
        if git.get("duplicate_title_share", 1.0) > 0.20:
            errors.append("Git duplicate title share exceeds 20%")
        if git.get("duplicate_body_share", 1.0) > 0.25:
            errors.append("Git duplicate body share exceeds 25%")
        if git.get("median_body_words", 0) < 50:
            errors.append("Git median body length is below 50 words")
        if release_scale and git.get("routine_share", 1.0) > 0.30:
            errors.append("Git routine share exceeds 30%")

    lifecycle = scorecard.get("lifecycle", {})
    if release_scale:
        if lifecycle.get("redelivery_share", 0.0) < 0.005:
            errors.append("lifecycle redelivery share is below 0.5%")
        if lifecycle.get("delete_share", 0.0) < 0.001:
            errors.append("lifecycle delete share is below 0.1%")
        if lifecycle.get("slack_revision_backed_edit_share", 0.0) < 0.80:
            errors.append("Slack displayed edits are not revision-backed")

    email = scorecard.get("email", {})
    if email.get("messages", 0) >= 100:
        if email.get("parseable_date_share", 0.0) < 0.98:
            errors.append("email parseable date share is below 98%")
        if email.get("threaded_share", 0.0) < 0.20:
            errors.append("email threaded share is below 20%")
        if email.get("routing_header_share", 0.0) < 0.80:
            errors.append("email routing-header share is below 80%")
        if email.get("attachment_share", 0.0) < 0.03:
            errors.append("email attachment share is below 3%")
        if email.get("unthreaded_duplicate_subject_share", 1.0) > 0.15:
            errors.append("email unexplained duplicate-subject share exceeds 15%")

    truth = scorecard.get("truth", {})
    minimum_truth = {"slack": 0.10, "email": 0.10, "git": 0.30, "zendesk": 0.20}
    for source, minimum in minimum_truth.items():
        values = truth.get("by_source", {}).get(source, {})
        if release_scale and values.get("actions", 0) >= 100 and values.get("linked_share", 0.0) < minimum:
            errors.append(f"{source} truth lineage share is below {minimum:.0%}")
    if scorecard.get("actions", 0) >= 5000 and truth.get("deep_events", 0) < 20:
        errors.append("deep truth event count is below 20")

    inbox = scorecard.get("inbox", {})
    if inbox.get("files", 0) >= 1000 and inbox.get("datadog_share", 0.0) > 0.25:
        errors.append("Datadog inbox share exceeds 25%")
    if schema_version >= 3:
        native_temporal = scorecard.get("native_temporal", {})
        if native_temporal.get("future_historical_timestamps", 1) != 0:
            errors.append("future native historical timestamps remain")
        if native_temporal.get("outside_window_timestamps", 1) != 0:
            errors.append("native timestamps remain outside declared window")
        if native_temporal.get("terminal_creates", 1) != 0:
            errors.append("terminal source states remain in create actions")
        if native_temporal.get("locator_date_mismatches", 1) != 0:
            errors.append("source locator date mismatch remains")
        if native_temporal.get("locator_dates_outside_window", 1) != 0:
            errors.append("source locator dates remain outside declared window")
        if release_scale:
            slack_temporal = scorecard.get("temporal", {}).get("by_source", {}).get(
                "slack", {}
            )
            if slack.get("rounded_timestamp_share", 1.0) > 0.25:
                errors.append("Slack rounded timestamp share exceeds 25%")
            if not 0.05 <= slack_temporal.get("offhours_share", 0.0) <= 0.25:
                errors.append("Slack off-hours share is outside 5-25%")
            if slack.get("max_distinct_thread_messages", 0) < 12:
                errors.append("Slack distinct-message thread maximum is below 12")
            if meetings.get("meetings", 0) >= 20:
                if meetings.get("median_turns", 0) < 45:
                    errors.append("meeting median remains below 45 turns")
                if meetings.get("p90_turns", 0) < 100:
                    errors.append("meeting P90 remains below 100 turns")
            if git.get("objects", 0) >= 20 and git.get("max_comments", 0) < 8:
                errors.append("Git review-comment maximum is below 8")
            knowledge_errors = scorecard.get("knowledge_errors", {})
            required_scenarios = {
                "stale_document",
                "superseded_owner",
                "provisional_as_final",
                "delayed_correction",
                "partial_correction",
                "unresolved_conflict",
            }
            for scenario_type in sorted(required_scenarios):
                if knowledge_errors.get("by_type", {}).get(scenario_type, 0) < 3:
                    errors.append(
                        f"knowledge scenario {scenario_type} has fewer than 3 examples"
                    )
    if schema_version >= 4 and release_scale:
        thread_histogram = slack.get("thread_size_histogram", {})
        if int(thread_histogram.get("4", 0)) < 1:
            errors.append("Slack has no four-message threads")
        if slack.get("dominant_thread_size_share", 1.0) > 0.20:
            errors.append("Slack dominant thread size exceeds 20%")
        if meetings.get("meetings", 0) >= 20 and meetings.get(
            "dominant_normalized_prefix_count", 10**9
        ) > 100:
            errors.append("meeting normalized phrase family exceeds 100 turns")
        if meetings.get("meetings", 0) >= 20 and meetings.get(
            "stock_clarification_family_occurrences", 10**9
        ) != 0:
            errors.append("stock meeting clarification families remain")
        if git.get("objects", 0) >= 20:
            if git.get("dominant_normalized_fivegram_share", 1.0) > 0.50:
                errors.append("Git semantic scaffold exceeds 50%")
            if git.get("terminal_lifecycles", 0) >= 10 and git.get(
                "terminal_lifecycle_p90_days", 0
            ) < 14:
                errors.append("Git terminal lifecycle P90 is below 14 days")
        datadog_days = temporal.get("by_source", {}).get("datadog", {}).get(
            "active_days", 0
        )
        if delivery.get("active_days", 0) >= 160 and datadog_days < delivery.get(
            "active_days", 0
        ):
            errors.append("Datadog is not active on every declared delivery day")
        knowledge_errors = scorecard.get("knowledge_errors", {})
        if knowledge_errors.get("source_systems", []) != [
            "confluence", "email", "git", "jira", "slack", "zendesk"
        ]:
            errors.append("knowledge scenarios do not cover all six source systems")
        if knowledge_errors.get("source_combinations", 0) < 8:
            errors.append("knowledge scenario source combinations remain too uniform")
        if knowledge_errors.get("distinct_evidence_counts", 0) < 4:
            errors.append("knowledge scenario evidence counts remain too uniform")
        if knowledge_errors.get("distinct_observed_day_counts", 0) < 3:
            errors.append("knowledge scenario observed-day counts remain too uniform")
        if knowledge_errors.get("distinct_durations", 0) < 6:
            errors.append("knowledge scenario durations remain too uniform")
        if knowledge_errors.get("unresolved", 0) < 3:
            errors.append("knowledge scenarios lack unresolved conflicts")
    return errors
