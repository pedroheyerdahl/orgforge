from datetime import datetime, timezone

from source_actions import SourceAction, replay_actions
from source_locators import iter_locator_dates, rebase_source_locators


def _action(
    system: str,
    object_id: str,
    observed_at: str,
    payload: dict,
    *,
    revision: int = 1,
    operation: str = "create",
) -> SourceAction:
    return SourceAction(
        source_system=system,
        object_id=object_id,
        revision=revision,
        operation=operation,
        observed_at=observed_at,
        effective_at=observed_at,
        truth_event_ids=("EVT-LOCATOR",),
        payload=payload,
    )


def test_rebases_dated_paths_ids_and_filenames_to_stable_create_date():
    create = _action(
        "zoom",
        "zoom_2026-09-03_abcd1234",
        "2026-01-05T10:00:00+00:00",
        {
            "meeting_id": "zoom_2026-09-03_abcd1234",
            "source_path": "zoom/2026-09-03/zoom_2026-09-03_abcd1234.md",
            "transcript": "The September 3 discussion remains visible as prose.",
            "files": [
                {
                    "id": "file-1",
                    "name": "meeting-notes-2026-09-03.txt",
                }
            ],
        },
    )
    update = _action(
        "zoom",
        create.object_id,
        "2026-01-08T10:00:00+00:00",
        {
            **create.payload,
            "status": "processed",
        },
        revision=2,
        operation="update",
    )
    redelivery = _action(
        "zoom",
        create.object_id,
        "2026-01-09T10:00:00+00:00",
        update.payload,
        revision=2,
        operation="redeliver",
    )

    rebased = rebase_source_locators([create, update, redelivery])

    assert {action.object_id for action in rebased} == {
        "zoom_2026-01-05_abcd1234"
    }
    assert all(
        action.payload["meeting_id"] == "zoom_2026-01-05_abcd1234"
        for action in rebased
    )
    assert all(
        action.payload["source_path"]
        == "zoom/2026-01-05/zoom_2026-01-05_abcd1234.md"
        for action in rebased
    )
    assert all(
        action.payload["files"][0]["name"]
        == "meeting-notes-2026-01-05.txt"
        for action in rebased
    )
    assert "September 3" in rebased[0].payload["transcript"]
    assert rebased[1].payload_sha256 == rebased[2].payload_sha256
    assert list(iter_locator_dates(rebased[0]))
    replay_actions(rebased)


def test_rebases_source_partition_dates_without_changing_non_path_business_ids():
    observed = "2026-02-11T09:30:00+00:00"
    actions = [
        _action(
            "slack",
            "slack-msg-stable",
            observed,
            {
                "client_msg_id": "slack-msg-stable",
                "source_path": "slack/channels/engineering/2026-08-14.json",
                "text": "The 2026-08-14 customer commitment remains quoted here.",
                "ts": f"{datetime.fromisoformat(observed).timestamp():.6f}",
            },
        ),
        _action(
            "email",
            "<stable-message@example.test>",
            observed,
            {
                "message_id": "<stable-message@example.test>",
                "source_path": "emails/outbound/2026-08-14/message.eml",
                "raw_eml": "Subject: 2026-08-14 commitment\n\nKeep this body unchanged.\n",
            },
        ),
    ]

    rebased = rebase_source_locators(actions)

    assert {action.object_id for action in rebased} == {
        "slack-msg-stable",
        "<stable-message@example.test>",
    }
    assert all("2026-02-11" in action.payload["source_path"] for action in rebased)
    by_system = {action.source_system: action for action in rebased}
    assert "2026-08-14 customer" in by_system["slack"].payload["text"]
    assert "2026-08-14 commitment" in by_system["email"].payload["raw_eml"]
    assert all(
        locator.value.date() == datetime(2026, 2, 11, tzinfo=timezone.utc).date()
        for action in rebased
        for locator in iter_locator_dates(action)
    )
