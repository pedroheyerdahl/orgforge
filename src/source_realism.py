"""Deterministic source adaptation and presentation realism.

This module consumes only OrgForge's synthetic export. It intentionally has no
configuration or code path that reads an external reference corpus.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email import policy as email_policy
from email.parser import Parser
from email.utils import format_datetime, getaddresses
import hashlib
import json
from pathlib import Path
import random
import re
from typing import Any, Iterable

import yaml

from native_timestamps import rebase_native_timestamps
from source_actions import CLASSIFICATION, SourceAction


SYSTEMS = {
    "confluence": "confluence",
    "jira": "jira",
    "slack": "slack",
    "git": "git",
    "emails": "email",
    "email": "email",
    "zoom": "zoom",
    "salesforce": "salesforce",
    "zendesk": "zendesk",
    "datadog": "datadog",
    "invoices": "invoices",
    "nps": "nps",
}


@dataclass(frozen=True)
class RealismPolicy:
    version: int = 1
    classification: str = CLASSIFICATION
    routine_activity_per_channel: int = 7
    ensure_calibration_features: bool = True
    stale_age_days: int = 120
    redelivery_rate: float = 0.12
    semantic_inbox_datadog_limit: int = 1000
    transcript_disfluency_rate: float = 0.12
    transcript_punctuation_damage_rate: float = 0.18
    transcript_repeated_fragment_rate: float = 0.08

    @classmethod
    def load(cls, path: Path) -> "RealismPolicy":
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        transcript = raw.get("transcript", {})
        policy = cls(
            version=int(raw.get("version", 1)),
            classification=str(raw.get("classification", CLASSIFICATION)),
            routine_activity_per_channel=int(raw.get("routine_activity_per_channel", 7)),
            ensure_calibration_features=bool(raw.get("ensure_calibration_features", True)),
            stale_age_days=int(raw.get("stale_age_days", 120)),
            redelivery_rate=float(raw.get("redelivery_rate", 0.12)),
            semantic_inbox_datadog_limit=int(
                raw.get("semantic_inbox_datadog_limit", 1000)
            ),
            transcript_disfluency_rate=float(transcript.get("disfluency_rate", 0.12)),
            transcript_punctuation_damage_rate=float(
                transcript.get("punctuation_damage_rate", 0.18)
            ),
            transcript_repeated_fragment_rate=float(
                transcript.get("repeated_fragment_rate", 0.08)
            ),
        )
        if policy.classification != CLASSIFICATION:
            raise ValueError(f"realism policy classification must be {CLASSIFICATION!r}")
        if policy.routine_activity_per_channel < 0:
            raise ValueError("routine_activity_per_channel cannot be negative")
        return policy


def conversation_shape_directive(seed_material: str) -> str:
    """Choose a reproducible conversational outcome without forcing closure."""

    digest = hashlib.sha256(seed_material.encode("utf-8")).digest()
    shape = digest[0] % 4
    directives = (
        "resolved: the group reaches one provisional decision, but the exchange can still contain doubt, caveats, or an incomplete follow-up",
        "unresolved: the exchange ends with an open question or missing information; do not add a summary, decision, or owner just to make it feel complete",
        "moved_elsewhere: participants stop before resolving the topic because the work moves to a ticket, document, later call, or another person",
        "acknowledgement_heavy: keep the exchange sparse; some turns can be a short acknowledgement, fragment, correction, or promise to look later rather than a substantive answer",
    )
    return directives[shape]


def _stable_id(prefix: str, *parts: Any, length: int = 16) -> str:
    joined = "|".join(str(part) for part in parts)
    digest = hashlib.sha256(joined.encode("utf-8")).hexdigest()[:length]
    return f"{prefix}{digest}"


def _stable_bucket(*parts: Any, modulus: int) -> int:
    joined = "|".join(str(part) for part in parts)
    return int.from_bytes(
        hashlib.sha256(joined.encode("utf-8")).digest()[:8], "big"
    ) % modulus


def _parse_datetime(value: Any, fallback: datetime | None = None) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)) or (
        isinstance(value, str) and re.fullmatch(r"\d{9,12}(?:\.\d+)?", value.strip())
    ):
        try:
            parsed = datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            parsed = fallback or datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    elif value:
        text = str(value).strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            text += "T12:00:00+00:00"
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            parsed = fallback or datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    else:
        parsed = fallback or datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso(value: Any, fallback: datetime | None = None) -> str:
    return _parse_datetime(value, fallback).isoformat()


def _slack_ts(value: Any, fallback: datetime | None = None) -> str:
    parsed = _parse_datetime(value, fallback)
    return f"{parsed.timestamp():.6f}"


def _relative_source_path(path: Path, export_dir: Path) -> str:
    return path.relative_to(export_dir).as_posix()


def _native_id(value: dict[str, Any], fallback: str) -> str:
    for key in ("message_id", "id", "Id", "pr_id", "ticket_id", "page_id", "uuid"):
        if value.get(key) not in (None, ""):
            return str(value[key])
    return fallback


def _payload_timestamp(value: dict[str, Any], fallback: datetime) -> str:
    for key in (
        "updated_at",
        "LastModifiedDate",
        "created_at",
        "created",
        "date",
        "timestamp",
        "ts",
    ):
        if value.get(key):
            return _iso(value[key], fallback)
    return fallback.isoformat()


def _truth_ids_for_export(export_dir: Path) -> dict[str, tuple[str, ...]]:
    path = export_dir / "simulation_events.jsonl"
    if not path.exists():
        return {}
    mapping: dict[str, list[str]] = {}
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for number, line in enumerate(fh, start=1):
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            event_id = str(
                event.get("event_id")
                or event.get("mongo_id")
                or _stable_id("sim-event-", number, line)
            )
            values = list((event.get("artifact_ids") or {}).values())
            causal_chain = (event.get("facts") or {}).get("causal_chain", []) or []
            values.extend(causal_chain if isinstance(causal_chain, list) else [])
            for artifact_id in values:
                if not isinstance(artifact_id, str) or not artifact_id:
                    continue
                keys = {artifact_id.strip(), artifact_id.strip().replace("\\", "/")}
                marker = f"/{export_dir.name}/"
                normalized = artifact_id.strip().replace("\\", "/")
                if marker in normalized:
                    keys.add(normalized.split(marker, 1)[1])
                for key in keys:
                    if key:
                        mapping.setdefault(key, []).append(event_id)
    return {key: tuple(dict.fromkeys(values)) for key, values in mapping.items()}


def _truth_ids_for_keys(
    truth_map: dict[str, tuple[str, ...]],
    *keys: Any,
) -> tuple[str, ...]:
    event_ids: list[str] = []
    for key in keys:
        if key in (None, ""):
            continue
        normalized = str(key).strip().replace("\\", "/")
        event_ids.extend(truth_map.get(normalized, ()))
    return tuple(dict.fromkeys(event_ids))


def _adapt_slack(
    export_dir: Path,
    truth_map: dict[str, tuple[str, ...]],
) -> tuple[list[SourceAction], dict[str, list[SourceAction]]]:
    actions: list[SourceAction] = []
    by_channel: dict[str, list[SourceAction]] = {}
    current: dict[str, SourceAction] = {}
    slack_root = export_dir / "slack" / "channels"
    if not slack_root.exists():
        return actions, by_channel

    for path in sorted(slack_root.rglob("*.json")):
        relative = path.relative_to(slack_root)
        channel = relative.parts[0] if len(relative.parts) > 1 else "general"
        try:
            records = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(records, list):
            continue
        channel_id = _stable_id("C", channel, length=10).upper()
        for index, record in enumerate(records, start=1):
            if not isinstance(record, dict):
                continue
            observed_at = _parse_datetime(record.get("ts") or record.get("date"))
            user_name = str(record.get("user") or "unknown-user")
            user_id = str(record.get("user_id") or _stable_id("U", user_name, length=10).upper())
            object_id = _native_id(
                record,
                _stable_id(
                    "slack-msg-",
                    channel,
                    observed_at.isoformat(),
                    user_name,
                    record.get("text"),
                    index,
                ),
            )
            payload: dict[str, Any] = {
                "type": "message",
                "channel_id": channel_id,
                "channel_name": channel,
                "user": user_id,
                "user_profile": {"display_name": user_name},
                "text": str(record.get("text", "")),
                "ts": _slack_ts(record.get("ts") or record.get("date")),
                "client_msg_id": str(record.get("client_msg_id") or object_id),
                "source_path": _relative_source_path(path, export_dir),
            }
            root_value = record.get("thread_ts")
            if root_value:
                payload["thread_ts"] = _slack_ts(root_value)
            for key in (
                "subtype",
                "bot_id",
                "bot_profile",
                "blocks",
                "attachments",
                "files",
                "reactions",
                "edited",
                "metadata",
            ):
                if key in record:
                    payload[key] = record[key]
            previous = current.get(object_id)
            if previous is None:
                operation = "create"
                revision = 1
                effective_at = observed_at
            else:
                previous_observed = _parse_datetime(previous.observed_at)
                if observed_at <= previous_observed:
                    observed_at = previous_observed + timedelta(microseconds=1)
                if payload == previous.payload:
                    operation = "redeliver"
                    revision = previous.revision
                    effective_at = _parse_datetime(previous.effective_at)
                    payload = previous.payload
                else:
                    operation = "update"
                    revision = previous.revision + 1
                    effective_at = observed_at
            action = SourceAction(
                source_system="slack",
                object_id=object_id,
                revision=revision,
                operation=operation,
                observed_at=observed_at.isoformat(),
                effective_at=effective_at.isoformat(),
                truth_event_ids=_truth_ids_for_keys(
                    truth_map,
                    object_id,
                    record.get("message_id"),
                    record.get("thread_id"),
                    record.get("root_id"),
                    record.get("thread_ts"),
                    _relative_source_path(path, export_dir),
                ),
                payload=payload,
            )
            actions.append(action)
            by_channel.setdefault(channel, []).append(action)
            current[object_id] = action
    return actions, by_channel


def _adapt_jira(
    export_dir: Path,
    truth_map: dict[str, tuple[str, ...]],
) -> list[SourceAction]:
    actions: list[SourceAction] = []
    jira_root = export_dir / "jira"
    if not jira_root.exists():
        return actions
    for path in sorted(jira_root.rglob("*.json")):
        try:
            issue = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(issue, dict):
            continue
        object_id = _native_id(issue, path.stem)
        created_at = _parse_datetime(issue.get("created_at") or issue.get("created"))
        final_status = str(issue.get("status", "To Do"))
        base = dict(issue)
        comments = list(base.pop("comments", []) or [])
        for field in ("updated", "updated_at", "resolved_at", "closed_at"):
            base.pop(field, None)
        base["status"] = "To Do" if final_status != "To Do" else final_status
        base["comments"] = []
        base["source_path"] = _relative_source_path(path, export_dir)
        truth_ids = _truth_ids_for_keys(
            truth_map,
            object_id,
            _relative_source_path(path, export_dir),
        )
        actions.append(
            SourceAction(
                source_system="jira",
                object_id=object_id,
                revision=1,
                operation="create",
                observed_at=created_at.isoformat(),
                effective_at=created_at.isoformat(),
                truth_event_ids=truth_ids,
                payload=base,
            )
        )
        current = base
        revision = 1
        last_time = created_at
        for comment in sorted(
            (item for item in comments if isinstance(item, dict)),
            key=lambda item: _parse_datetime(
                item.get("created") or item.get("updated") or item.get("date"), created_at
            ),
        ):
            comment_time = _parse_datetime(
                comment.get("created") or comment.get("updated") or comment.get("date"),
                last_time + timedelta(seconds=1),
            )
            if comment_time <= last_time:
                comment_time = last_time + timedelta(seconds=1)
            revision += 1
            current = {**current, "comments": [*current.get("comments", []), comment]}
            actions.append(
                SourceAction(
                    source_system="jira",
                    object_id=object_id,
                    revision=revision,
                    operation="update",
                    observed_at=comment_time.isoformat(),
                    effective_at=comment_time.isoformat(),
                    truth_event_ids=truth_ids,
                    payload=current,
                )
            )
            last_time = comment_time
        if final_status != current.get("status") or issue.get("updated_at"):
            final_time = _parse_datetime(issue.get("updated_at"), last_time + timedelta(seconds=1))
            if final_time <= last_time:
                final_time = last_time + timedelta(seconds=1)
            revision += 1
            current = {**issue, "comments": comments, "source_path": _relative_source_path(path, export_dir)}
            actions.append(
                SourceAction(
                    source_system="jira",
                    object_id=object_id,
                    revision=revision,
                    operation="update",
                    observed_at=final_time.isoformat(),
                    effective_at=final_time.isoformat(),
                    truth_event_ids=truth_ids,
                    payload=current,
                )
            )
    return actions


def degrade_transcript(
    text: str,
    seed: int,
    protected_terms: Iterable[str] = (),
) -> str:
    """Apply bounded ASR-like defects while preserving protected terms."""

    rng = random.Random(seed)
    protected: dict[str, str] = {}
    working = text
    for index, term in enumerate(sorted(set(protected_terms), key=len, reverse=True)):
        if term and term in working:
            token = f"ZXPROTECTED{index}ZX"
            working = working.replace(term, token)
            protected[token] = term

    words = working.split()
    if words:
        insert_at = min(len(words), max(1, rng.randrange(1, min(len(words), 6) + 1)))
        words.insert(insert_at, rng.choice(("um", "uh", "like")))
    working = " ".join(words)
    if ". " in working:
        working = working.replace(". ", rng.choice(("... ", " ")), 1)
    elif working.endswith("."):
        working = working[:-1]
    if len(words) > 10 and rng.random() < 0.75:
        fragment = " ".join(words[2:5])
        working += f" {fragment}"

    for token, term in protected.items():
        working = working.replace(token, term)
    return working


def _adapt_markdown_or_email(
    path: Path,
    export_dir: Path,
    system: str,
    truth_map: dict[str, tuple[str, ...]],
    seed: int,
) -> SourceAction:
    text = path.read_text(encoding="utf-8", errors="replace")
    relative = _relative_source_path(path, export_dir)
    object_id = path.stem
    fallback = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    payload: dict[str, Any]
    observed = fallback

    if system == "email":
        message = Parser(policy=email_policy.default).parsestr(text)
        object_id = str(message.get("Message-ID") or _stable_id("email-", relative, text))
        observed = _parse_datetime(message.get("Date"), fallback)
        payload = {
            "message_id": object_id,
            "subject": str(message.get("Subject") or ""),
            "raw_eml": text,
            "source_path": relative,
        }
    elif system == "zoom":
        date_match = re.search(r"\b20\d{2}-\d{2}-\d{2}\b", text)
        observed = _parse_datetime(date_match.group(0) if date_match else None, fallback)
        protected = tuple(sorted(set(re.findall(r"\b[A-Z][A-Za-z0-9]+DB\b", text))))
        degraded = degrade_transcript(text, seed=int(_stable_id("", seed, relative), 16), protected_terms=protected)
        payload = {
            "meeting_id": object_id,
            "provider": "zoom",
            "transcript": degraded,
            "transcript_variant": "machine",
            "transcript_degraded": degraded != text,
            "source_path": relative,
        }
    else:
        id_match = re.search(r"\*\*ID:\*\*\s*([^\s]+)", text)
        date_match = re.search(r"\b20\d{2}-\d{2}-\d{2}\b", text)
        object_id = id_match.group(1) if id_match else object_id
        observed = _parse_datetime(date_match.group(0) if date_match else None, fallback)
        payload = {
            "page_id": object_id,
            "status": "current",
            "version": 1,
            "body": text,
            "source_path": relative,
        }

    return SourceAction(
        source_system=system,
        object_id=object_id,
        revision=1,
        operation="create",
        observed_at=observed.isoformat(),
        effective_at=observed.isoformat(),
        truth_event_ids=_truth_ids_for_keys(truth_map, object_id, relative),
        payload=payload,
    )


def _adapt_generic_json(
    path: Path,
    export_dir: Path,
    system: str,
    truth_map: dict[str, tuple[str, ...]],
) -> list[SourceAction]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    values = raw if isinstance(raw, list) else [raw]
    actions: list[SourceAction] = []
    fallback = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    for index, value in enumerate(values, start=1):
        if not isinstance(value, dict):
            value = {"value": value}
        object_id = _native_id(
            value,
            _stable_id(
                f"{system}-",
                _relative_source_path(path, export_dir),
                index,
                value,
            ),
        )
        observed = _payload_timestamp(value, fallback)
        payload = {**value, "source_path": _relative_source_path(path, export_dir)}
        actions.append(
            SourceAction(
                source_system=system,
                object_id=object_id,
                revision=1,
                operation="create",
                observed_at=observed,
                effective_at=observed,
                truth_event_ids=_truth_ids_for_keys(
                    truth_map,
                    object_id,
                    _relative_source_path(path, export_dir),
                ),
                payload=payload,
            )
        )
    return actions


def _adapt_git_snapshot(
    path: Path,
    export_dir: Path,
    truth_map: dict[str, tuple[str, ...]],
) -> list[SourceAction]:
    """Expand a final pull-request snapshot into a chronological lifecycle."""

    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(snapshot, dict):
        return _adapt_generic_json(path, export_dir, "git", truth_map)

    object_id = _native_id(snapshot, path.stem)
    relative = _relative_source_path(path, export_dir)
    truth_ids = _truth_ids_for_keys(truth_map, object_id, relative)
    created = _parse_datetime(snapshot.get("created_at") or snapshot.get("created"))
    final_status = str(snapshot.get("status") or "open").casefold()
    initial_status = "draft" if final_status == "draft" else "open"
    comments = [item for item in snapshot.get("comments", []) or [] if isinstance(item, dict)]
    base = dict(snapshot)
    base["status"] = initial_status
    base["comments"] = []
    base["source_path"] = relative
    for field in ("updated", "updated_at", "merged_at", "closed_at", "resolved_at"):
        base.pop(field, None)

    actions = [
        SourceAction(
            source_system="git",
            object_id=object_id,
            revision=1,
            operation="create",
            observed_at=created.isoformat(),
            effective_at=created.isoformat(),
            truth_event_ids=truth_ids,
            payload=base,
        )
    ]
    current = base
    revision = 1
    last_time = created
    ordered_comments = sorted(
        comments,
        key=lambda item: _parse_datetime(
            item.get("timestamp") or item.get("created_at") or item.get("date"),
            created,
        ),
    )
    for comment in ordered_comments:
        comment_time = _parse_datetime(
            comment.get("timestamp") or comment.get("created_at") or comment.get("date"),
            last_time + timedelta(seconds=1),
        )
        if comment_time <= last_time:
            comment_time = last_time + timedelta(seconds=1)
        revision += 1
        current = {**current, "comments": [*current.get("comments", []), comment]}
        actions.append(
            SourceAction(
                source_system="git",
                object_id=object_id,
                revision=revision,
                operation="update",
                observed_at=comment_time.isoformat(),
                effective_at=comment_time.isoformat(),
                truth_event_ids=truth_ids,
                payload=current,
            )
        )
        last_time = comment_time

    final_fields = ("updated_at", "updated", "merged_at", "closed_at", "resolved_at")
    needs_final = final_status != initial_status or any(snapshot.get(field) for field in final_fields)
    if needs_final:
        final_time = _parse_datetime(
            next((snapshot[field] for field in final_fields if snapshot.get(field)), None),
            last_time + timedelta(seconds=1),
        )
        if final_time <= last_time:
            final_time = last_time + timedelta(seconds=1)
        revision += 1
        final_payload = {
            **snapshot,
            "comments": comments,
            "source_path": relative,
        }
        actions.append(
            SourceAction(
                source_system="git",
                object_id=object_id,
                revision=revision,
                operation="update",
                observed_at=final_time.isoformat(),
                effective_at=final_time.isoformat(),
                truth_event_ids=truth_ids,
                payload=final_payload,
            )
        )
    return actions


def _adapt_zendesk_ticket_snapshot(
    path: Path,
    export_dir: Path,
    truth_map: dict[str, tuple[str, ...]],
) -> list[SourceAction]:
    """Expand a final Zendesk ticket snapshot into visible revisions."""

    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(snapshot, dict):
        return _adapt_generic_json(path, export_dir, "zendesk", truth_map)
    object_id = _native_id(snapshot, path.stem)
    relative = _relative_source_path(path, export_dir)
    truth_ids = _truth_ids_for_keys(truth_map, object_id, relative)
    created = _parse_datetime(snapshot.get("created_at") or snapshot.get("created"))
    final_status = str(snapshot.get("status") or "open")
    comments = [item for item in snapshot.get("comments", []) or [] if isinstance(item, dict)]
    base = dict(snapshot)
    base["status"] = "open"
    base["comments"] = []
    base["source_path"] = relative
    for field in ("updated", "updated_at", "closed_at", "resolved_at"):
        base.pop(field, None)
    actions = [
        SourceAction(
            source_system="zendesk",
            object_id=object_id,
            revision=1,
            operation="create",
            observed_at=created.isoformat(),
            effective_at=created.isoformat(),
            truth_event_ids=truth_ids,
            payload=base,
        )
    ]
    current = base
    revision = 1
    last_time = created
    for comment in sorted(
        comments,
        key=lambda item: _parse_datetime(
            item.get("timestamp") or item.get("created_at") or item.get("date"),
            created,
        ),
    ):
        comment_time = _parse_datetime(
            comment.get("timestamp") or comment.get("created_at") or comment.get("date"),
            last_time + timedelta(seconds=1),
        )
        if comment_time <= last_time:
            comment_time = last_time + timedelta(seconds=1)
        revision += 1
        current = {**current, "comments": [*current.get("comments", []), comment]}
        actions.append(
            SourceAction(
                source_system="zendesk",
                object_id=object_id,
                revision=revision,
                operation="update",
                observed_at=comment_time.isoformat(),
                effective_at=comment_time.isoformat(),
                truth_event_ids=truth_ids,
                payload=current,
            )
        )
        last_time = comment_time
    if final_status.casefold() != "open" or snapshot.get("updated_at"):
        final_time = _parse_datetime(
            snapshot.get("resolved_at")
            or snapshot.get("closed_at")
            or snapshot.get("updated_at"),
            last_time + timedelta(seconds=1),
        )
        if final_time <= last_time:
            final_time = last_time + timedelta(seconds=1)
        revision += 1
        actions.append(
            SourceAction(
                source_system="zendesk",
                object_id=object_id,
                revision=revision,
                operation="update",
                observed_at=final_time.isoformat(),
                effective_at=final_time.isoformat(),
                truth_event_ids=truth_ids,
                payload={**snapshot, "comments": comments, "source_path": relative},
            )
        )
    return actions


def _adapt_jsonl(
    path: Path,
    export_dir: Path,
    system: str,
    truth_map: dict[str, tuple[str, ...]],
) -> list[SourceAction]:
    """Adapt JSONL snapshots while preserving repeated source-object identity."""

    relative = path.relative_to(export_dir)
    actions: list[SourceAction] = []
    current: dict[str, SourceAction] = {}
    fallback = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for number, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                value = {"raw_line": line.rstrip("\n")}
            if not isinstance(value, dict):
                value = {"value": value}
            object_id = _native_id(value, _stable_id(f"{system}-", relative, number))
            payload = {**value, "source_path": relative.as_posix()}
            observed = _parse_datetime(_payload_timestamp(value, fallback))
            previous = current.get(object_id)
            if previous is None:
                operation = "create"
                revision = 1
                effective = observed
            else:
                previous_observed = _parse_datetime(previous.observed_at)
                if observed <= previous_observed:
                    observed = previous_observed + timedelta(microseconds=1)
                if payload == previous.payload:
                    operation = "redeliver"
                    revision = previous.revision
                    effective = _parse_datetime(previous.effective_at)
                    payload = previous.payload
                else:
                    operation = "update"
                    revision = previous.revision + 1
                    effective = observed
            action = SourceAction(
                source_system=system,
                object_id=object_id,
                revision=revision,
                operation=operation,
                observed_at=observed.isoformat(),
                effective_at=effective.isoformat(),
                truth_event_ids=_truth_ids_for_keys(
                    truth_map,
                    object_id,
                    relative.as_posix(),
                ),
                payload=payload,
            )
            actions.append(action)
            current[object_id] = action
    return actions


def _routine_slack_actions(
    by_channel: dict[str, list[SourceAction]],
    seed: int,
) -> list[SourceAction]:
    channels = sorted(by_channel) or ["general"]
    channel = channels[0]
    existing = sorted(by_channel.get(channel, []), key=lambda action: action.observed_at)
    base = _parse_datetime(existing[-1].observed_at if existing else "2026-01-02T09:00:00+00:00")
    channel_id = _stable_id("C", channel, length=10).upper()
    rng = random.Random(seed)

    def create_message(offset: int, suffix: str, **payload_fields: Any) -> SourceAction:
        when = base + timedelta(minutes=offset)
        object_id = _stable_id("slack-msg-", seed, channel, suffix)
        payload = {
            "type": "message",
            "channel_id": channel_id,
            "channel_name": channel,
            "user": _stable_id("U", payload_fields.pop("display_name", "Hanna"), length=10).upper(),
            "text": payload_fields.pop("text", ""),
            "ts": _slack_ts(when),
            "client_msg_id": object_id,
            "synthetic_routine": True,
            **payload_fields,
        }
        return SourceAction(
            source_system="slack",
            object_id=object_id,
            revision=1,
            operation="create",
            observed_at=when.isoformat(),
            effective_at=when.isoformat(),
            payload=payload,
        )

    short = create_message(1, "short", text=rng.choice(("ok", "yep", "looking")))
    unresolved = create_message(
        2,
        "unresolved",
        text="anyone know who owns the retry copy?",
        synthetic_unresolved=True,
    )
    bot = create_message(
        3,
        "bot",
        display_name="Build Monitor",
        text="build completed with warnings",
        subtype="bot_message",
        bot_id=_stable_id("B", channel, length=10).upper(),
        blocks=[{"type": "section", "block_id": "synthetic-build-summary"}],
    )
    system = create_message(
        4,
        "join",
        text="a new teammate joined the channel",
        subtype="channel_join",
    )
    file_message = create_message(
        5,
        "file",
        text="logs from the retry check",
        files=[
            {
                "id": _stable_id("F", channel, seed, length=10).upper(),
                "name": "retry-check.txt",
                "mimetype": "text/plain",
                "size": 1842,
            }
        ],
    )

    actions = [short, unresolved, bot, system, file_message]
    target = existing[0] if existing else short
    update_time = base + timedelta(minutes=6)
    updated_payload = {
        **target.payload,
        "text": target.payload.get("text", "") + " (edited)",
        "edited": {
            "user": target.payload.get("user", ""),
            "ts": _slack_ts(update_time),
        },
        "reactions": [{"name": "eyes", "count": 2, "users": ["USYN001", "USYN002"]}],
    }
    updated = SourceAction(
        source_system="slack",
        object_id=target.object_id,
        revision=target.revision + 1,
        operation="update",
        observed_at=update_time.isoformat(),
        effective_at=update_time.isoformat(),
        truth_event_ids=target.truth_event_ids,
        payload=updated_payload,
    )
    redelivery_time = base + timedelta(minutes=7)
    redelivery = SourceAction(
        source_system="slack",
        object_id=updated.object_id,
        revision=updated.revision,
        operation="redeliver",
        observed_at=redelivery_time.isoformat(),
        effective_at=updated.effective_at,
        truth_event_ids=updated.truth_event_ids,
        payload=updated.payload,
    )
    doomed = create_message(8, "doomed", text="uploaded the wrong trace")
    tombstone_time = base + timedelta(minutes=9)
    tombstone = SourceAction(
        source_system="slack",
        object_id=doomed.object_id,
        revision=2,
        operation="delete",
        observed_at=tombstone_time.isoformat(),
        effective_at=tombstone_time.isoformat(),
        payload={
            **doomed.payload,
            "text": "This message was deleted.",
            "subtype": "tombstone",
            "deleted_ts": _slack_ts(tombstone_time),
        },
    )
    actions.extend((updated, redelivery, doomed, tombstone))
    return actions


def _calibration_edge_actions(
    actions: list[SourceAction],
    policy: RealismPolicy,
) -> list[SourceAction]:
    if actions:
        start = min(_parse_datetime(action.observed_at) for action in actions)
    else:
        start = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    stale_effective = start - timedelta(days=policy.stale_age_days)
    stale_issue = SourceAction(
        source_system="jira",
        object_id="SYN-STALE-001",
        revision=1,
        operation="create",
        observed_at=start.isoformat(),
        effective_at=stale_effective.isoformat(),
        payload={
            "id": "SYN-STALE-001",
            "title": "Recheck the old export note",
            "status": "To Do",
            "created_at": stale_effective.isoformat(),
            "updated_at": stale_effective.isoformat(),
            "stale_record": True,
            "comments": [],
        },
    )
    tiny_draft = SourceAction(
        source_system="confluence",
        object_id="CONF-SYN-DRAFT-001",
        revision=1,
        operation="create",
        observed_at=(start + timedelta(minutes=1)).isoformat(),
        effective_at=(start + timedelta(minutes=1)).isoformat(),
        payload={
            "page_id": "CONF-SYN-DRAFT-001",
            "status": "draft",
            "version": 1,
            "title": "retry notes",
            "body": "check mobile too\n\nlink was in the thread somewhere",
            "tiny_draft": True,
        },
    )
    correction = SourceAction(
        source_system="confluence",
        object_id="CONF-SYN-CORRECTION-001",
        revision=1,
        operation="create",
        observed_at=(start + timedelta(minutes=2)).isoformat(),
        effective_at=(start + timedelta(minutes=2)).isoformat(),
        payload={
            "page_id": "CONF-SYN-CORRECTION-001",
            "status": "current",
            "version": 1,
            "title": "Correction to retry note",
            "body": "The earlier note used the previous client wording.",
            "supersedes": ["CONF-SYN-DRAFT-001"],
        },
    )
    return [stale_issue, tiny_draft, correction]


def augment_actions_to_span(
    actions: list[SourceAction],
    target_days: int,
    seed: int = 42,
    start_at: datetime | None = None,
) -> list[SourceAction]:
    """Add deterministic source-native workload across a requested calendar span.

    LLM output remains the semantic anchor. These records supply the mundane
    volume, retries, partial updates, and cross-system drift that dominate real
    exports without paying for prose generation on every simulated day.
    """
    if target_days < 1:
        raise ValueError("target_days must be positive")
    if start_at is not None:
        start = _parse_datetime(start_at)
    elif actions:
        start = min(_parse_datetime(action.observed_at) for action in actions)
    else:
        start = datetime(2026, 1, 1, 9, tzinfo=timezone.utc)
    start = start.replace(hour=9, minute=0, second=0, microsecond=0)
    channels = ("engineering", "product", "support", "random")
    people = ("Morgan", "Sarah", "Deepa", "Tom", "Jenna", "Vince")
    topics = (
        "mobile retry state",
        "TitanDB timeout",
        "campaign handoff",
        "device sync queue",
        "customer export",
        "capacity warning",
    )
    short_text = ("ok", "looking", "same here", "not sure", "later today", "+1")
    routine_text = (
        "I can check the older client after the current deploy finishes",
        "the status in this export still looks one update behind",
        "not sure that dashboard includes the change from this morning",
        "I only verified web and the mobile path still needs a pass",
        "the link in the earlier thread is returning the previous value",
        "can someone confirm which environment that result came from",
    )
    expanded = list(actions)

    def add(
        system: str,
        object_id: str,
        revision: int,
        operation: str,
        when: datetime,
        payload: dict[str, Any],
        *,
        effective_at: datetime | None = None,
    ) -> SourceAction:
        action = SourceAction(
            source_system=system,
            object_id=object_id,
            revision=revision,
            operation=operation,
            observed_at=when.isoformat(),
            effective_at=(effective_at or when).isoformat(),
            payload=payload,
        )
        expanded.append(action)
        return action

    for day_index in range(target_days):
        day = start + timedelta(days=day_index)
        channel = channels[day_index % len(channels)]
        topic = topics[day_index % len(topics)]
        export_context = f" for {topic}; I was looking at the {day.strftime('%b %d')} export"
        root_id = _stable_id("slack-load-", seed, day_index, "root")
        root_time = day + timedelta(minutes=7 + day_index % 23)
        root_payload = {
            "type": "message",
            "channel_id": _stable_id("C", channel, length=10).upper(),
            "channel_name": channel,
            "user": _stable_id("U", people[day_index % len(people)], length=10).upper(),
            "user_profile": {"display_name": people[day_index % len(people)]},
            "text": short_text[day_index % len(short_text)]
            if day_index % 5 == 1
            else routine_text[day_index % len(routine_text)] + export_context,
            "ts": _slack_ts(root_time),
            "client_msg_id": root_id,
            "synthetic_routine": True,
        }
        if day_index % 11 == 0:
            root_payload["reactions"] = [
                {"name": "eyes", "count": 1, "users": ["ULOAD001"]}
            ]
        root = add("slack", root_id, 1, "create", root_time, root_payload)
        reply_time = root_time + timedelta(minutes=2)
        add(
            "slack",
            _stable_id("slack-load-", seed, day_index, "reply"),
            1,
            "create",
            reply_time,
            {
                **root_payload,
                "user": _stable_id(
                    "U", people[(day_index + 1) % len(people)], length=10
                ).upper(),
                "user_profile": {
                    "display_name": people[(day_index + 1) % len(people)]
                },
                "text": short_text[(day_index + 2) % len(short_text)]
                if day_index % 4 == 0
                else routine_text[(day_index + 2) % len(routine_text)] + export_context,
                "ts": _slack_ts(reply_time),
                "thread_ts": root_payload["ts"],
                "client_msg_id": _stable_id(
                    "slack-load-", seed, day_index, "reply"
                ),
            },
        )
        ack_time = root_time + timedelta(minutes=3)
        add(
            "slack",
            _stable_id("slack-load-", seed, day_index, "ack"),
            1,
            "create",
            ack_time,
            {
                **root_payload,
                "user": _stable_id(
                    "U", people[(day_index + 4) % len(people)], length=10
                ).upper(),
                "user_profile": {
                    "display_name": people[(day_index + 4) % len(people)]
                },
                "text": short_text[(day_index + 4) % len(short_text)]
                if day_index % 3 == 0
                else routine_text[(day_index + 4) % len(routine_text)] + export_context,
                "ts": _slack_ts(ack_time),
                "client_msg_id": _stable_id(
                    "slack-load-", seed, day_index, "ack"
                ),
                "synthetic_unresolved": day_index % 5 == 0,
            },
        )
        if day_index % 9 == 0:
            bot_time = root_time + timedelta(minutes=4)
            add(
                "slack",
                _stable_id("slack-load-", seed, day_index, "bot"),
                1,
                "create",
                bot_time,
                {
                    **root_payload,
                    "user": "UBUILDMON",
                    "user_profile": {"display_name": "Build Monitor"},
                    "text": f"workflow completed with warnings [{day_index + 1:03d}]",
                    "ts": _slack_ts(bot_time),
                    "subtype": "bot_message",
                    "bot_id": "BLOADMON",
                    "client_msg_id": _stable_id(
                        "slack-load-", seed, day_index, "bot"
                    ),
                },
            )
        if day_index % 17 == 0:
            add(
                "slack",
                root.object_id,
                root.revision,
                "redeliver",
                root_time + timedelta(hours=2),
                root.payload,
                effective_at=root_time,
            )

        if day_index % 3 == 0:
            issue_id = f"LOAD-{1000 + day_index:04d}"
            created = day + timedelta(hours=1)
            issue = {
                "id": issue_id,
                "title": f"Check {topic}",
                "description": "Observed:\n\nExpected:\n\nEnvironment: unknown",
                "status": "To Do",
                "assignee": people[(day_index + 2) % len(people)],
                "created_at": created.isoformat(),
                "updated_at": created.isoformat(),
                "comments": [],
            }
            add("jira", issue_id, 1, "create", created, issue)
            if day_index + 1 < target_days:
                updated = day + timedelta(days=1, hours=2)
                add(
                    "jira",
                    issue_id,
                    2,
                    "update",
                    updated,
                    {
                        **issue,
                        "status": "In Progress" if day_index % 6 else "To Do",
                        "updated_at": updated.isoformat(),
                        "comments": [
                            {
                                "author": people[(day_index + 3) % len(people)],
                                "created": updated.isoformat(),
                                "text": "could not reproduce on the other client",
                            }
                        ],
                    },
                )

        if day_index % 7 == 0:
            page_id = f"CONF-LOAD-{day_index:04d}"
            page_time = day + timedelta(hours=3)
            page = {
                "page_id": page_id,
                "title": f"{topic} notes",
                "status": "draft" if day_index % 14 == 0 else "current",
                "version": 1,
                "body": (
                    f"## notes\n\n{topic} looked enabled in the morning export.\n\n"
                    "todo: confirm owner; link was in slack"
                ),
                "contradiction_group": f"load-{day_index:04d}",
            }
            add("confluence", page_id, 1, "create", page_time, page)
            if day_index + 3 < target_days:
                revised = day + timedelta(days=3, hours=3)
                add(
                    "confluence",
                    page_id,
                    2,
                    "update",
                    revised,
                    {
                        **page,
                        "status": "current",
                        "version": 2,
                        "body": (
                            f"## correction\n\nEarlier note was stale: {topic} was disabled "
                            "for the affected client. No final owner yet."
                        ),
                        "supersedes_version": 1,
                    },
                )

        if day_index % 4 == 0:
            message_id = f"<load-{day_index:04d}@apexathletics.io>"
            mail_time = day + timedelta(hours=4)
            add(
                "email",
                message_id,
                1,
                "create",
                mail_time,
                {
                    "message_id": message_id,
                    "subject": f"re: {topic}",
                    "raw_eml": (
                        f"From: {people[day_index % len(people)].lower()}@apexathletics.io\n"
                        "To: ops@apexathletics.io\n"
                        f"Date: {mail_time.strftime('%a, %d %b %Y %H:%M:%S +0000')}\n"
                        f"Message-ID: {message_id}\nSubject: re: {topic}\n"
                        "X-Data-Classification: synthetic_non_confidential\n\n"
                        "Checking whether this is still expected. The forwarded note had the old value.\n"
                    ),
                },
            )

        if day_index % 10 == 0:
            meeting_time = day + timedelta(hours=5)
            add(
                "zoom",
                f"zoom-load-{day_index:04d}",
                1,
                "create",
                meeting_time,
                {
                    "meeting_id": f"zoom-load-{day_index:04d}",
                    "provider": "zoom",
                    "transcript_variant": "machine",
                    "transcript_degraded": True,
                    "transcript": (
                        f"**[14:00:03] {people[day_index % len(people)]}:** um {topic} "
                        "is still mixed across clients\n"
                        f"**[14:01:19] {people[(day_index + 1) % len(people)]}:** "
                        "yeah I need to check the old export"
                    ),
                },
            )

        if day_index % 5 == 0:
            ticket_id = f"ZD-LOAD-{day_index:04d}"
            ticket_time = day + timedelta(hours=6)
            ticket_payload = {
                "id": ticket_id,
                "subject": topic,
                "status": "open",
                "created_at": ticket_time.isoformat(),
                "comments": [],
            }
            add(
                "zendesk",
                ticket_id,
                1,
                "create",
                ticket_time,
                ticket_payload,
            )
            ticket_comment_time = ticket_time + timedelta(minutes=23)
            add(
                "zendesk",
                ticket_id,
                2,
                "update",
                ticket_comment_time,
                {
                    **ticket_payload,
                    "updated_at": ticket_comment_time.isoformat(),
                    "comments": [
                        {
                            "author": "customer",
                            "timestamp": ticket_comment_time.isoformat(),
                            "text": "is this expected?",
                        }
                    ],
                },
            )

        if day_index % 6 == 0:
            pr_time = day + timedelta(hours=7)
            pr_id = f"PR-LOAD-{day_index:04d}"
            pr_payload = {
                "pr_id": pr_id,
                "title": f"adjust {topic} for run {day_index:03d}",
                "status": "open" if day_index % 12 else "draft",
                "created_at": pr_time.isoformat(),
                "comments": [],
            }
            add(
                "git",
                pr_id,
                1,
                "create",
                pr_time,
                pr_payload,
            )
            review_time = pr_time + timedelta(minutes=31)
            add(
                "git",
                pr_id,
                2,
                "update",
                review_time,
                {
                    **pr_payload,
                    "updated_at": review_time.isoformat(),
                    "comments": [
                        {
                            "author": "ci",
                            "timestamp": review_time.isoformat(),
                            "text": "one check pending",
                        }
                    ],
                },
            )

        if True:
            alert_time = day + timedelta(hours=8)
            add(
                "datadog",
                f"DD-LOAD-{day_index:04d}",
                1,
                "create",
                alert_time,
                {
                    "id": f"DD-LOAD-{day_index:04d}",
                    "title": (
                        f"{topic} above warning threshold"
                        if day_index % 3 == 1
                        else f"{topic} daily activity sample"
                    ),
                    "timestamp": alert_time.isoformat(),
                    "status": "Warn" if day_index % 3 == 1 else "OK",
                },
            )

        if day_index % 9 == 0:
            sf_time = day + timedelta(hours=9)
            add(
                "salesforce",
                f"006LOAD{day_index:04d}",
                1,
                "create",
                sf_time,
                {
                    "Id": f"006LOAD{day_index:04d}",
                    "Name": f"Device pilot follow-up {day_index:04d}",
                    "StageName": "Discovery",
                    "LastModifiedDate": sf_time.isoformat(),
                    "NextStep": "waiting on customer reply",
                },
            )

        if day_index % 21 == 0:
            nps_time = day + timedelta(hours=10)
            add(
                "nps",
                f"NPS-LOAD-{day_index:04d}",
                1,
                "create",
                nps_time,
                {
                    "id": f"NPS-LOAD-{day_index:04d}",
                    "date": nps_time.date().isoformat(),
                    "score": 6 + day_index % 4,
                    "comment": f"setup was fine; {topic} was confusing",
                },
            )

    return sorted(expanded, key=lambda action: (action.observed_at, action.action_id))


def normalize_observations_to_window(
    actions: list[SourceAction],
    start_at: datetime,
    target_days: int,
) -> list[SourceAction]:
    """Map observations into a target window while preserving source chronology."""
    start = _parse_datetime(start_at).replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=target_days) - timedelta(microseconds=1)
    parsed = [_parse_datetime(action.observed_at) for action in actions]
    active_end = max((value for value in parsed if value >= start), default=start)
    compress_active = active_end > end
    source_span_days = max((active_end.date() - start.date()).days, 1)
    bootstrap_days = max(1, min(14, target_days))
    last_by_object: dict[tuple[str, str], datetime] = {}
    slack_ts_by_object: dict[tuple[str, str], str] = {}
    slack_root_ts: dict[str, str] = {}
    normalized: list[SourceAction] = []

    def map_window_datetime(value: datetime) -> datetime:
        value = _parse_datetime(value)
        if value < start:
            return start
        if not compress_active:
            return min(value, end)
        source_day = max(0, (value.date() - start.date()).days)
        target_day = round(source_day * (target_days - 1) / source_span_days)
        mapped = (start + timedelta(days=target_day)).replace(
            hour=value.hour,
            minute=value.minute,
            second=value.second,
            microsecond=value.microsecond,
        )
        return min(mapped, end)

    def apply_cadence(action: SourceAction, value: datetime) -> datetime:
        if action.source_system == "datadog":
            return value
        cadence_identity = (
            action.payload.get("thread_ts") or action.payload.get("ts") or action.object_id
            if action.source_system == "slack"
            else action.object_id
        )
        digest = hashlib.sha256(
            f"cadence|{action.source_system}|{cadence_identity}|{action.revision}".encode(
                "utf-8"
            )
        ).digest()
        soft = action.source_system in {"slack", "email", "git", "zendesk"}
        weekend_keep_pct = 12 if soft else 5
        offhours_keep_pct = 35 if soft else 12
        if value.weekday() >= 5 and digest[0] % 100 >= weekend_keep_pct:
            shifted = value + timedelta(days=7 - value.weekday())
            if shifted > end:
                shifted = value - timedelta(days=value.weekday() - 4)
            value = shifted
        if (value.hour < 8 or value.hour >= 19) and digest[1] % 100 >= offhours_keep_pct:
            value = value.replace(
                hour=8 + digest[2] % 11,
                minute=digest[3] % 60,
                second=digest[4] % 60,
                microsecond=0,
            )
        if action.source_system == "slack":
            if digest[5] % 100 < 10:
                value = value.replace(
                    hour=6 if digest[6] % 2 == 0 else 19 + digest[7] % 4,
                )
            value = value.replace(
                second=1 + digest[8] % 59,
                microsecond=int.from_bytes(digest[9:12], "big") % 1_000_000,
            )
        return value

    for action in sorted(actions, key=lambda item: (item.observed_at, item.revision, item.action_id)):
        original_observed = _parse_datetime(action.observed_at)
        original_effective = _parse_datetime(action.effective_at)
        observed_effective_delta = original_observed - original_effective
        observed = original_observed
        if original_observed < start:
            digest = hashlib.sha256(
                f"{action.source_system}|{action.object_id}".encode("utf-8")
            ).digest()
            day_offset = int.from_bytes(digest[:2], "big") % bootstrap_days
            seconds = int.from_bytes(digest[2:6], "big") % (12 * 60 * 60)
            observed = start + timedelta(days=day_offset, hours=7, seconds=seconds)
        elif compress_active:
            observed = map_window_datetime(original_observed)
        observed = apply_cadence(action, observed)
        key = (action.source_system, action.object_id)
        previous = last_by_object.get(key)
        if previous is not None and observed <= previous:
            observed = previous + timedelta(microseconds=1)
        if observed > end:
            observed = end
        last_by_object[key] = observed
        effective = observed - observed_effective_delta
        payload = rebase_native_timestamps(
            action.source_system,
            action.payload,
            map_window_datetime,
            historical_ceiling=observed,
            window_start=start,
            window_end=end,
        )
        if action.source_system == "slack":
            original_ts = str(action.payload.get("ts", ""))
            if action.operation == "create":
                mapped_ts = f"{observed.timestamp():.6f}"
                slack_ts_by_object[key] = mapped_ts
                if original_ts:
                    slack_root_ts[original_ts] = mapped_ts
            if key in slack_ts_by_object:
                payload["ts"] = slack_ts_by_object[key]
            original_thread = str(action.payload.get("thread_ts", ""))
            if original_thread:
                payload["thread_ts"] = slack_root_ts.get(
                    original_thread,
                    str(payload.get("thread_ts", original_thread)),
                )
        elif action.source_system == "zoom" and payload.get("transcript"):
            payload["transcript"] = re.sub(
                r"(?i)(\*\*Date:\*\*\s*)\d{4}-\d{2}-\d{2}",
                rf"\g<1>{observed.date().isoformat()}",
                str(payload["transcript"]),
            )
        normalized.append(
            SourceAction(
                source_system=action.source_system,
                object_id=action.object_id,
                revision=action.revision,
                operation=action.operation,
                observed_at=observed.isoformat(),
                effective_at=effective.isoformat(),
                truth_event_ids=action.truth_event_ids,
                payload=payload,
                classification=action.classification,
            )
        )
    return sorted(normalized, key=lambda action: (action.observed_at, action.action_id))


def normalize_email_observations(
    actions: list[SourceAction],
    seed: int = 42,
) -> list[SourceAction]:
    """Normalize email transport metadata without changing non-email actions."""
    ordered = sorted(actions, key=lambda action: (action.observed_at, action.action_id))
    threads: dict[tuple[str, str], list[str]] = {}
    subject_threads: dict[str, list[str]] = {}
    current_payload: dict[str, dict[str, Any]] = {}
    normalized: list[SourceAction] = []

    def set_header(message: Any, name: str, value: str) -> None:
        if message.get_all(name):
            del message[name]
        message[name] = value

    for action in ordered:
        if action.source_system != "email":
            normalized.append(action)
            continue
        if action.operation == "redeliver" and action.object_id in current_payload:
            payload = current_payload[action.object_id]
        else:
            payload = json.loads(json.dumps(action.payload, ensure_ascii=False, default=str))
            message = Parser(policy=email_policy.default).parsestr(
                str(payload.get("raw_eml", ""))
            )
            observed = _parse_datetime(action.observed_at)
            raw_message_id = str(message.get("Message-ID") or "").strip()
            if "@" not in raw_message_id:
                local = _stable_id("message-", seed, action.object_id, length=24)
                raw_message_id = f"<{local}@apexathletics.io>"
            elif not raw_message_id.startswith("<"):
                raw_message_id = f"<{raw_message_id.strip('<>')}>"
            set_header(message, "Message-ID", raw_message_id)
            set_header(message, "Date", format_datetime(observed))

            from_addresses = [address for _name, address in getaddresses([str(message.get("From") or "")]) if address]
            to_addresses = [
                address
                for _name, address in getaddresses(
                    [str(message.get("To") or ""), str(message.get("Cc") or "")]
                )
                if address
            ]
            sender = from_addresses[0] if from_addresses else "unknown@apexathletics.io"
            recipient = to_addresses[0] if to_addresses else "archive@apexathletics.io"
            if not message.get("Delivered-To"):
                message["Delivered-To"] = recipient
            if not message.get("Return-Path"):
                message["Return-Path"] = f"<{sender}>"
            if not message.get("Received"):
                route_id = _stable_id("route-", seed, action.object_id, length=12)
                message["Received"] = (
                    f"from mail-{route_id}.synthetic.internal by mx.apexathletics.io "
                    f"with ESMTPS id {route_id}; {format_datetime(observed)}"
                )
            if not message.get("MIME-Version"):
                message["MIME-Version"] = "1.0"
            if not message.get("Content-Type"):
                message.set_type("text/plain")
                message.set_param("charset", "utf-8")

            subject = re.sub(
                r"^(?:(?:re|fwd?)\s*:\s*)+",
                "",
                str(message.get("Subject") or payload.get("subject") or "").strip(),
                flags=re.I,
            ).casefold()
            participants = tuple(sorted(set(from_addresses + to_addresses)))
            participant_key = (subject, "participants:" + "|".join(participants))
            truth_keys = [
                (subject, f"truth:{event_id}") for event_id in action.truth_event_ids
            ]
            references = threads.get(participant_key)
            if references is None:
                references = next(
                    (threads[key] for key in truth_keys if key in threads),
                    None,
                )
            if references is None:
                subject_references = subject_threads.get(subject, [])
                references = (
                    subject_references
                    if subject_references
                    and _stable_bucket(seed, action.object_id, "subject-thread-fallback", modulus=100) < 55
                    else []
                )
            threads[participant_key] = references
            for key in truth_keys:
                threads[key] = references
            if references and not message.get("In-Reply-To"):
                message["In-Reply-To"] = references[-1]
            if references and not message.get("References"):
                message["References"] = " ".join(references[-20:])
            references.append(raw_message_id)
            subject_threads.setdefault(subject, []).append(raw_message_id)

            attachment_bucket = int.from_bytes(
                hashlib.sha256(
                    f"email-attachment|{seed}|{action.object_id}".encode("utf-8")
                ).digest()[:4],
                "big",
            ) % 100
            if attachment_bucket < 10 and not message.get("X-OrgForge-Attachment"):
                attachment_id = _stable_id("context-", seed, action.object_id, length=12)
                message.add_attachment(
                    f"synthetic diagnostic context {attachment_id}\n",
                    subtype="plain",
                    filename=f"{attachment_id}.txt",
                )
                message["X-OrgForge-Attachment"] = "synthetic"

            payload["message_id"] = raw_message_id
            payload["subject"] = str(message.get("Subject") or payload.get("subject") or "")
            payload["raw_eml"] = message.as_string(policy=email_policy.default)
        result = SourceAction(
            source_system=action.source_system,
            object_id=action.object_id,
            revision=action.revision,
            operation=action.operation,
            observed_at=action.observed_at,
            effective_at=action.effective_at,
            truth_event_ids=action.truth_event_ids,
            payload=payload,
            classification=action.classification,
        )
        normalized.append(result)
        if action.operation != "redeliver":
            current_payload[action.object_id] = payload
    return sorted(normalized, key=lambda action: (action.observed_at, action.action_id))


def adapt_export(
    export_dir: Path,
    policy: RealismPolicy,
    seed: int = 42,
) -> list[SourceAction]:
    """Adapt an OrgForge export into a deterministic source-action stream."""

    export_dir = export_dir.resolve()
    truth_map = _truth_ids_for_export(export_dir)
    actions, slack_by_channel = _adapt_slack(export_dir, truth_map)
    actions.extend(_adapt_jira(export_dir, truth_map))

    for path in sorted(item for item in export_dir.rglob("*") if item.is_file()):
        relative = path.relative_to(export_dir)
        if not relative.parts or relative.parts[0] in {"slack", "jira", "provenance"}:
            continue
        if path.name in {"simulation.log", "simulation_events.jsonl"}:
            continue
        system = SYSTEMS.get(relative.parts[0].lower())
        if not system:
            continue
        suffix = path.suffix.lower()
        if suffix in {".md", ".txt", ".eml"}:
            actions.append(
                _adapt_markdown_or_email(path, export_dir, system, truth_map, seed)
            )
        elif suffix == ".json":
            if system == "git":
                actions.extend(_adapt_git_snapshot(path, export_dir, truth_map))
            elif system == "zendesk" and len(relative.parts) > 1 and relative.parts[1] == "tickets":
                actions.extend(_adapt_zendesk_ticket_snapshot(path, export_dir, truth_map))
            else:
                actions.extend(_adapt_generic_json(path, export_dir, system, truth_map))
        elif suffix == ".jsonl":
            actions.extend(_adapt_jsonl(path, export_dir, system, truth_map))

    if policy.ensure_calibration_features:
        actions.extend(_routine_slack_actions(slack_by_channel, seed))
        actions.extend(_calibration_edge_actions(actions, policy))

    return sorted(actions, key=lambda action: (action.observed_at, action.action_id))


def messiness_features(actions: Iterable[SourceAction]) -> dict[str, int]:
    counts = {
        "short_messages": 0,
        "singleton_messages": 0,
        "bot_messages": 0,
        "system_messages": 0,
        "messages_with_reactions": 0,
        "messages_with_files": 0,
        "edited_messages": 0,
        "redeliveries": 0,
        "tombstones": 0,
        "stale_records": 0,
        "tiny_drafts": 0,
        "transcript_degraded": 0,
        "corrections": 0,
    }
    system_subtypes = {"channel_join", "channel_leave", "channel_topic", "channel_name"}
    for action in actions:
        payload = action.payload
        if action.operation == "redeliver":
            counts["redeliveries"] += 1
        if action.operation == "delete" or payload.get("subtype") == "tombstone":
            counts["tombstones"] += 1
        if payload.get("stale_record"):
            counts["stale_records"] += 1
        if payload.get("tiny_draft") or (
            action.source_system == "confluence"
            and payload.get("status") == "draft"
            and len(str(payload.get("body", ""))) < 500
        ):
            counts["tiny_drafts"] += 1
        if payload.get("transcript_degraded"):
            counts["transcript_degraded"] += 1
        if payload.get("supersedes"):
            counts["corrections"] += 1
        if action.source_system != "slack":
            continue
        text = str(payload.get("text", ""))
        if len(text) < 40:
            counts["short_messages"] += 1
        if payload.get("synthetic_unresolved"):
            counts["singleton_messages"] += 1
        if payload.get("bot_id") or payload.get("subtype") == "bot_message":
            counts["bot_messages"] += 1
        if payload.get("subtype") in system_subtypes:
            counts["system_messages"] += 1
        if payload.get("reactions"):
            counts["messages_with_reactions"] += 1
        if payload.get("files"):
            counts["messages_with_files"] += 1
        if payload.get("edited"):
            counts["edited_messages"] += 1
    return counts
