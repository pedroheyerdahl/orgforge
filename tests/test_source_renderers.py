import json

from source_renderers import (
    render_jira_markdown,
    render_raw_object,
    render_record_markdown,
    render_slack_channel,
    source_visible_payload,
)


def test_jira_renderer_uses_multiple_source_document_shapes_without_losing_evidence():
    documents = []
    for index in range(40):
        documents.append(
            render_jira_markdown(
                {
                    "id": f"ENG-{100 + index}",
                    "title": f"Retry investigation {index}",
                    "status": "In Progress",
                    "description": "The older client still needs verification.",
                    "comments": [
                        {
                            "author": "Hanna",
                            "created": "2026-01-02T10:00:00Z",
                            "text": "Web is covered; mobile is pending.",
                        }
                    ],
                }
            )
        )

    first_line_shapes = {document.splitlines()[0].split(" ", 1)[0] for document in documents}
    assert len(first_line_shapes) >= 3
    assert all("In Progress" in document for document in documents)
    assert all("older client" in document for document in documents)
    assert all("mobile is pending" in document for document in documents)


def test_record_renderer_uses_multiple_shapes_and_preserves_fields():
    documents = [
        render_record_markdown(
            "datadog",
            {
                "id": f"DD-{index:03d}",
                "title": f"Latency monitor {index}",
                "status": "Warn",
                "description": "One shard is above the warning threshold.",
            },
        )
        for index in range(40)
    ]

    first_line_shapes = {document.splitlines()[0].split(" ", 1)[0] for document in documents}
    assert len(first_line_shapes) >= 3
    assert all("Warn" in document for document in documents)
    assert all("warning threshold" in document for document in documents)


def test_source_visible_payload_recursively_removes_generator_and_gold_controls():
    payload = {
        "title": "Retry ownership notes",
        "body": "The owner changed after the handoff; fallback is unresolved.",
        "status": "current",
        "synthetic_routine": True,
        "synthetic_unresolved": True,
        "synthetic_ephemeral": True,
        "source_anchor": {"source_system": "jira", "object_id": "ENG-1"},
        "contradiction_group": "load-0001",
        "transcript_degraded": True,
        "tiny_draft": True,
        "correction_scope": "partial",
        "supersedes": ["src-action-old"],
        "supersedes_version": 1,
        "stale_record": True,
        "source_path": "confluence/2026-01-05/page.md",
        "comments": [
            {
                "text": "fallback still needs review",
                "synthetic_routine": True,
            }
        ],
    }

    visible = source_visible_payload(payload)

    assert visible == {
        "title": "Retry ownership notes",
        "body": "The owner changed after the handoff; fallback is unresolved.",
        "status": "current",
        "comments": [{"text": "fallback still needs review"}],
    }


def test_raw_renderers_do_not_expose_internal_controls():
    git_state = {
        "source_system": "git",
        "object_id": "PR-42",
        "revision": 2,
        "deleted": False,
        "last_observed_at": "2026-01-05T10:00:00+00:00",
        "effective_at": "2026-01-05T10:00:00+00:00",
        "truth_event_ids": [],
        "payload": {
            "pr_id": "PR-42",
            "title": "Guard retry state",
            "status": "open",
            "synthetic_routine": True,
            "source_anchor": {"source_system": "jira", "object_id": "ENG-1"},
        },
    }
    _suffix, raw_git = render_raw_object("git", git_state)
    slack = render_slack_channel(
        "engineering",
        [
            {
                **git_state,
                "source_system": "slack",
                "object_id": "msg-1",
                "payload": {
                    "type": "message",
                    "channel_id": "CENG",
                    "channel_name": "engineering",
                    "user": "UHANNA",
                    "text": "looking",
                    "ts": "1767607201.123456",
                    "synthetic_routine": True,
                    "synthetic_unresolved": True,
                },
            }
        ],
    )

    assert "synthetic_routine" not in json.loads(raw_git)
    assert "source_anchor" not in json.loads(raw_git)
    assert "synthetic_routine" not in slack["messages"][0]
    assert "synthetic_unresolved" not in slack["messages"][0]
