"""Stable source-observation actions and deterministic replay."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


OPERATIONS = frozenset({"create", "update", "delete", "redeliver"})
CLASSIFICATION = "synthetic_non_confidential"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _validate_timestamp(value: str) -> None:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid ISO-8601 timestamp: {value!r}") from exc


@dataclass(frozen=True)
class SourceAction:
    source_system: str
    object_id: str
    revision: int
    operation: str
    observed_at: str
    effective_at: str
    payload: dict[str, Any]
    truth_event_ids: tuple[str, ...] = field(default_factory=tuple)
    action_id: str = ""
    classification: str = CLASSIFICATION

    def __post_init__(self) -> None:
        if not self.source_system or not self.object_id:
            raise ValueError("source_system and object_id are required")
        if self.operation not in OPERATIONS:
            raise ValueError(f"invalid source operation: {self.operation!r}")
        if self.revision < 1:
            raise ValueError("revision must be at least 1")
        _validate_timestamp(self.observed_at)
        _validate_timestamp(self.effective_at)
        if self.classification != CLASSIFICATION:
            raise ValueError(f"classification must be {CLASSIFICATION!r}")
        object.__setattr__(self, "truth_event_ids", tuple(self.truth_event_ids))
        if not self.action_id:
            identity = "|".join(
                (
                    self.source_system,
                    self.object_id,
                    str(self.revision),
                    self.operation,
                    self.observed_at,
                    self.payload_sha256,
                )
            )
            digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
            object.__setattr__(self, "action_id", f"src-action-{digest}")

    @property
    def payload_sha256(self) -> str:
        return _sha256(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "classification": self.classification,
            "source_system": self.source_system,
            "object_id": self.object_id,
            "revision": self.revision,
            "operation": self.operation,
            "observed_at": self.observed_at,
            "effective_at": self.effective_at,
            "truth_event_ids": list(self.truth_event_ids),
            "payload_sha256": self.payload_sha256,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SourceAction":
        action = cls(
            action_id=str(value.get("action_id", "")),
            classification=str(value.get("classification", CLASSIFICATION)),
            source_system=str(value["source_system"]),
            object_id=str(value["object_id"]),
            revision=int(value["revision"]),
            operation=str(value["operation"]),
            observed_at=str(value["observed_at"]),
            effective_at=str(value["effective_at"]),
            truth_event_ids=tuple(str(item) for item in value.get("truth_event_ids", [])),
            payload=dict(value.get("payload", {})),
        )
        supplied_digest = value.get("payload_sha256")
        if supplied_digest and supplied_digest != action.payload_sha256:
            raise ValueError(f"payload checksum mismatch for {action.action_id}")
        return action


def write_actions(path: Path, actions: Iterable[SourceAction]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for action in actions:
            fh.write(json.dumps(action.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")


def read_actions(path: Path) -> list[SourceAction]:
    actions: list[SourceAction] = []
    with path.open("r", encoding="utf-8") as fh:
        for number, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            try:
                actions.append(SourceAction.from_dict(json.loads(line)))
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ValueError(f"invalid source action at {path}:{number}: {exc}") from exc
    return actions


def replay_actions(actions: Iterable[SourceAction]) -> dict[tuple[str, str], dict[str, Any]]:
    """Replay actions into final source-object state, validating lifecycle rules."""

    state: dict[tuple[str, str], dict[str, Any]] = {}
    for action in sorted(actions, key=lambda item: (item.observed_at, item.action_id)):
        key = (action.source_system, action.object_id)
        current = state.get(key)

        if action.operation == "create":
            if current is not None:
                raise ValueError(f"create targets existing object {key}")
            if action.revision != 1:
                raise ValueError(f"create for {key} must use revision 1")
        elif action.operation == "redeliver":
            if current is None:
                raise ValueError(f"redelivery targets missing object {key}")
            if action.revision != current["revision"]:
                raise ValueError(
                    f"redelivery for {key} expected revision {current['revision']}, got {action.revision}"
                )
            if action.payload_sha256 != current["payload_sha256"]:
                raise ValueError(f"redelivery payload changed for {key}")
            current["last_action_id"] = action.action_id
            current["last_observed_at"] = action.observed_at
            current["redelivery_count"] += 1
            continue
        else:
            if current is None:
                raise ValueError(f"{action.operation} targets missing object {key}")
            expected_revision = current["revision"] + 1
            if action.revision != expected_revision:
                raise ValueError(
                    f"{action.operation} for {key} expected revision {expected_revision}, got {action.revision}"
                )
            if current["deleted"]:
                raise ValueError(f"{action.operation} targets deleted object {key}")

        state[key] = {
            "source_system": action.source_system,
            "object_id": action.object_id,
            "revision": action.revision,
            "payload": action.payload,
            "payload_sha256": action.payload_sha256,
            "deleted": action.operation == "delete",
            "truth_event_ids": list(action.truth_event_ids),
            "last_action_id": action.action_id,
            "last_observed_at": action.observed_at,
            "effective_at": action.effective_at,
            "redelivery_count": 0,
        }

    return state
