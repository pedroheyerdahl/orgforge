import json

import pytest

from source_actions import SourceAction, read_actions, replay_actions, write_actions


def _action(operation, revision, payload, observed_at, action_id=""):
    return SourceAction(
        source_system="jira",
        object_id="SYN-104",
        revision=revision,
        operation=operation,
        observed_at=observed_at,
        effective_at=observed_at,
        truth_event_ids=("event-synthetic-1",),
        payload=payload,
        action_id=action_id,
    )


def test_replay_reconstructs_updates_redelivery_and_delete():
    created = _action(
        "create",
        1,
        {"id": "SYN-104", "status": "To Do"},
        "2026-01-02T09:00:00+00:00",
    )
    updated = _action(
        "update",
        2,
        {"id": "SYN-104", "status": "In Progress"},
        "2026-01-03T10:00:00+00:00",
    )
    redelivered = _action(
        "redeliver",
        2,
        {"id": "SYN-104", "status": "In Progress"},
        "2026-01-04T08:00:00+00:00",
    )
    deleted = _action(
        "delete",
        3,
        {"id": "SYN-104", "deleted": True},
        "2026-01-05T11:00:00+00:00",
    )

    state = replay_actions([deleted, redelivered, created, updated])

    issue = state[("jira", "SYN-104")]
    assert issue["revision"] == 3
    assert issue["deleted"] is True
    assert issue["payload"] == {"id": "SYN-104", "deleted": True}
    assert redelivered.payload_sha256 == updated.payload_sha256


def test_replay_rejects_revision_regression_and_changed_redelivery():
    created = _action(
        "create",
        1,
        {"id": "SYN-104", "status": "To Do"},
        "2026-01-02T09:00:00+00:00",
    )
    bad_update = _action(
        "update",
        1,
        {"id": "SYN-104", "status": "Done"},
        "2026-01-03T09:00:00+00:00",
    )
    changed_redelivery = _action(
        "redeliver",
        1,
        {"id": "SYN-104", "status": "Done"},
        "2026-01-03T10:00:00+00:00",
    )

    with pytest.raises(ValueError, match="expected revision 2"):
        replay_actions([created, bad_update])

    with pytest.raises(ValueError, match="redelivery payload"):
        replay_actions([created, changed_redelivery])


def test_action_ids_are_stable_and_jsonl_round_trips(tmp_path):
    first = _action(
        "create",
        1,
        {"id": "SYN-104", "title": "Verify retry banner"},
        "2026-01-02T09:00:00+00:00",
    )
    second = _action(
        "create",
        1,
        {"id": "SYN-104", "title": "Verify retry banner"},
        "2026-01-02T09:00:00+00:00",
    )
    path = tmp_path / "source-actions.jsonl"

    write_actions(path, [first])
    loaded = read_actions(path)

    assert first.action_id == second.action_id
    assert loaded == [first]
    serialized = json.loads(path.read_text(encoding="utf-8"))
    assert serialized["classification"] == "synthetic_non_confidential"
    assert serialized["payload_sha256"] == first.payload_sha256


def test_action_rejects_invalid_operation_or_timestamp():
    with pytest.raises(ValueError, match="operation"):
        _action("overwrite", 1, {}, "2026-01-02T09:00:00+00:00")

    with pytest.raises(ValueError, match="timestamp"):
        _action("create", 1, {}, "not-a-time")
