import json
from pathlib import Path

from source_actions import read_actions, replay_actions


EXAMPLES = Path("examples/source_realism")


def test_examples_are_synthetic_private_safe_and_parseable():
    expected = {
        "slack/channel-export.json",
        "jira/issue-export.json",
        "confluence/page-export.json",
        "transcripts/meeting-export.json",
        "email/thread.eml",
        "replay/source-actions.jsonl",
    }
    files = {path.relative_to(EXAMPLES).as_posix() for path in EXAMPLES.rglob("*") if path.is_file()}

    assert expected <= files
    for relative in expected:
        text = (EXAMPLES / relative).read_text(encoding="utf-8")
        assert "synthetic_non_confidential" in text
        assert "Downloads/sources" not in text
        assert "xoxp-" not in text
        assert "sk-" not in text
        if relative.endswith(".json"):
            json.loads(text)


def test_examples_demonstrate_source_shape_and_replay_behavior():
    slack = json.loads((EXAMPLES / "slack/channel-export.json").read_text())
    jira = json.loads((EXAMPLES / "jira/issue-export.json").read_text())
    confluence = json.loads((EXAMPLES / "confluence/page-export.json").read_text())
    meeting = json.loads((EXAMPLES / "transcripts/meeting-export.json").read_text())
    email = (EXAMPLES / "email/thread.eml").read_text()
    actions = read_actions(EXAMPLES / "replay/source-actions.jsonl")
    state = replay_actions(actions)

    assert set(slack) == {"classification", "channel", "users", "messages", "threads", "state"}
    assert any(item.get("subtype") == "bot_message" for item in slack["messages"])
    assert any(item.get("edited") for item in slack["messages"])
    assert any(item.get("reactions") for item in slack["messages"])
    assert any(item.get("files") for item in slack["messages"])
    assert slack["threads"]
    assert jira["fields"]["stale_record"] is True
    assert jira["changelog"]
    assert confluence["status"] == "draft"
    assert confluence["version"]["number"] >= 1
    assert meeting["variants"]["machine"] != meeting["variants"]["corrected"]
    assert "In-Reply-To:" in email and "> " in email
    assert any(action.operation == "redeliver" for action in actions)
    assert state[("jira", "SYN-EX-9")]["revision"] == 3
    assert state[("slack", "slack-msg-example-deleted")]["deleted"] is True
