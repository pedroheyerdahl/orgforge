"""Source-aware structured timestamp discovery and deterministic rebasing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import copy
import re
from typing import Any, Callable, Iterable, Literal


TimestampKind = Literal["historical", "planned"]


@dataclass(frozen=True)
class NativeTimestamp:
    path: tuple[str | int, ...]
    value: datetime
    kind: TimestampKind
    raw: Any


_PLANNED_FIELDS = {
    "close_date",
    "due",
    "due_at",
    "due_date",
    "expected_at",
    "expected_close",
    "expected_close_at",
    "expected_close_date",
    "expires_at",
    "expiration_date",
    "scheduled_at",
    "scheduled_date",
    "target_date",
}

_HISTORICAL_FIELDS = {
    "closed_at",
    "created",
    "created_at",
    "date",
    "deleted_at",
    "deleted_ts",
    "edited_at",
    "effective_at",
    "event_time",
    "merged_at",
    "observed_at",
    "opened_at",
    "resolved_at",
    "sent_at",
    "started_at",
    "thread_ts",
    "time",
    "timestamp",
    "ts",
    "updated",
    "updated_at",
}

_EPOCH = re.compile(r"^\d{9,12}(?:\.\d+)?$")
_DATE_ONLY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _kind_for_field(field: str) -> TimestampKind | None:
    normalized = field.casefold().replace("-", "_")
    if normalized in _PLANNED_FIELDS or normalized.startswith(("due_", "expected_", "scheduled_", "target_")):
        return "planned"
    if normalized in _HISTORICAL_FIELDS:
        return "historical"
    if normalized.endswith(("_timestamp", "_created_at", "_updated_at", "_closed_at", "_resolved_at")):
        return "historical"
    return None


def _parse_native(value: Any) -> datetime | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if value < 100_000_000:
            return None
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None
    if not isinstance(value, str):
        return None
    text = value.strip()
    if _EPOCH.fullmatch(text):
        try:
            return datetime.fromtimestamp(float(text), tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None
    if _DATE_ONLY.fullmatch(text):
        return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def iter_native_timestamps(
    source_system: str,
    payload: dict[str, Any],
) -> Iterable[NativeTimestamp]:
    """Yield structured timestamps; prose and unrecognized fields are ignored."""

    del source_system  # Reserved for source-specific exceptions as schemas evolve.

    def visit(value: Any, path: tuple[str | int, ...]) -> Iterable[NativeTimestamp]:
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = (*path, key)
                kind = _kind_for_field(str(key))
                parsed = _parse_native(child) if kind else None
                if kind and parsed is not None:
                    yield NativeTimestamp(child_path, parsed, kind, child)
                yield from visit(child, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                yield from visit(child, (*path, index))

    return visit(payload, ())


def _render_like(raw: Any, value: datetime) -> Any:
    mapped = value.astimezone(timezone.utc)
    if isinstance(raw, int) and not isinstance(raw, bool):
        return int(mapped.timestamp())
    if isinstance(raw, float):
        return float(mapped.timestamp())
    text = str(raw)
    if _EPOCH.fullmatch(text):
        decimals = len(text.split(".", 1)[1]) if "." in text else 0
        return f"{mapped.timestamp():.{decimals}f}" if decimals else str(int(mapped.timestamp()))
    if _DATE_ONLY.fullmatch(text):
        return mapped.date().isoformat()
    if text.endswith("Z"):
        return mapped.isoformat().replace("+00:00", "Z")
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return mapped.replace(tzinfo=None).isoformat()
    return mapped.isoformat()


def rebase_native_timestamps(
    source_system: str,
    payload: dict[str, Any],
    mapper: Callable[[datetime], datetime],
    *,
    historical_ceiling: datetime | None = None,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> dict[str, Any]:
    """Return a deep-copied payload with recognized timestamp values mapped."""

    result = copy.deepcopy(payload)
    for native in iter_native_timestamps(source_system, payload):
        mapped = mapper(native.value)
        if window_start is not None and mapped < window_start:
            mapped = window_start
        if window_end is not None and mapped > window_end:
            mapped = window_end
        if (
            native.kind == "historical"
            and historical_ceiling is not None
            and mapped > historical_ceiling
        ):
            mapped = historical_ceiling
        parent: Any = result
        for part in native.path[:-1]:
            parent = parent[part]
        parent[native.path[-1]] = _render_like(native.raw, mapped)
    return result
