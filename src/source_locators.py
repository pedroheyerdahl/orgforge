"""Rebase source locator dates without rewriting source prose."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timezone
import re
from typing import Any, Iterable

from source_actions import SourceAction


_DATE_TOKEN = re.compile(r"(?<!\d)(20\d{2}-\d{2}-\d{2})(?!\d)")
_LOCATOR_KEYS = {
    "source_path",
    "meeting_id",
    "message_id",
    "client_msg_id",
    "pr_id",
    "ticket_id",
    "page_id",
    "uuid",
    "id",
    "Id",
    "name",
    "filename",
    "file_name",
    "title_filename",
}


@dataclass(frozen=True)
class LocatorDate:
    path: tuple[str | int, ...]
    value: datetime
    raw: str


def _parse_date(raw: str) -> datetime:
    return datetime.combine(
        datetime.fromisoformat(raw).date(), time.min, tzinfo=timezone.utc
    )


def _replace_dates(value: str, replacement: str) -> str:
    return _DATE_TOKEN.sub(replacement, value)


def _rewrite_payload(value: Any, create_date: str, key: str | None = None) -> Any:
    if isinstance(value, dict):
        return {
            child_key: _rewrite_payload(child, create_date, child_key)
            for child_key, child in value.items()
        }
    if isinstance(value, list):
        return [
            _rewrite_payload(child, create_date, key)
            for child in value
        ]
    if isinstance(value, str) and key in _LOCATOR_KEYS:
        return _replace_dates(value, create_date)
    return value


def _iter_payload_dates(
    value: Any,
    path: tuple[str | int, ...] = (),
    key: str | None = None,
) -> Iterable[LocatorDate]:
    if isinstance(value, dict):
        for child_key, child in value.items():
            yield from _iter_payload_dates(child, (*path, child_key), child_key)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _iter_payload_dates(child, (*path, index), key)
    elif isinstance(value, str) and key in _LOCATOR_KEYS:
        for match in _DATE_TOKEN.finditer(value):
            raw = match.group(1)
            yield LocatorDate(path=path, value=_parse_date(raw), raw=raw)


def iter_locator_dates(action: SourceAction) -> Iterable[LocatorDate]:
    """Yield dates embedded in source paths, identities, and filenames."""

    for match in _DATE_TOKEN.finditer(action.object_id):
        raw = match.group(1)
        yield LocatorDate(
            path=("object_id",),
            value=_parse_date(raw),
            raw=raw,
        )
    yield from _iter_payload_dates(action.payload)


def rebase_source_locators(actions: list[SourceAction]) -> list[SourceAction]:
    """Align source locator dates to each object's rebased create date."""

    ordered = sorted(actions, key=lambda action: (action.observed_at, action.action_id))
    create_dates: dict[tuple[str, str], str] = {}
    for action in ordered:
        key = (action.source_system, action.object_id)
        observed_date = datetime.fromisoformat(
            action.observed_at.replace("Z", "+00:00")
        ).date().isoformat()
        if action.operation == "create":
            create_dates.setdefault(key, observed_date)
        else:
            create_dates.setdefault(key, observed_date)

    aliases = {
        key: _replace_dates(key[1], create_date)
        for key, create_date in create_dates.items()
    }
    rebased: list[SourceAction] = []
    for action in ordered:
        key = (action.source_system, action.object_id)
        create_date = create_dates[key]
        rebased.append(
            SourceAction(
                source_system=action.source_system,
                object_id=aliases[key],
                revision=action.revision,
                operation=action.operation,
                observed_at=action.observed_at,
                effective_at=action.effective_at,
                truth_event_ids=action.truth_event_ids,
                payload=_rewrite_payload(action.payload, create_date),
                classification=action.classification,
            )
        )
    return sorted(rebased, key=lambda action: (action.observed_at, action.action_id))
