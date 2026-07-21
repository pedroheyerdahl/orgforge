"""Native-ish raw and readable renderers for synthetic source objects."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any, Iterable


SOURCE_INTERNAL_KEYS = frozenset(
    {
        "synthetic_routine",
        "synthetic_unresolved",
        "synthetic_ephemeral",
        "source_anchor",
        "contradiction_group",
        "transcript_degraded",
        "tiny_draft",
        "correction_scope",
        "supersedes",
        "supersedes_version",
        "stale_record",
        "source_path",
    }
)


def source_visible_payload(value: Any) -> Any:
    """Return an immutable projection without generator/evaluation controls."""

    if isinstance(value, dict):
        return {
            key: source_visible_payload(child)
            for key, child in value.items()
            if key not in SOURCE_INTERNAL_KEYS
        }
    if isinstance(value, list):
        return [source_visible_payload(child) for child in value]
    return value


def json_text(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=False, default=str) + "\n"


def render_slack_channel(channel_name: str, states: Iterable[dict[str, Any]]) -> dict[str, Any]:
    messages: list[dict[str, Any]] = []
    threads: dict[str, list[dict[str, Any]]] = {}
    users: dict[str, str] = {}
    latest_ts = "0.000000"
    channel_id = ""

    for state in sorted(states, key=lambda item: str(item["payload"].get("ts", ""))):
        payload = source_visible_payload(state["payload"])
        profile = payload.pop("user_profile", {}) or {}
        user_id = str(payload.get("user", ""))
        if user_id:
            users[user_id] = str(profile.get("display_name") or user_id)
        channel_id = str(payload.pop("channel_id", channel_id))
        payload.pop("channel_name", None)
        latest_ts = max(latest_ts, str(payload.get("ts", latest_ts)))
        thread_ts = payload.get("thread_ts")
        if thread_ts and str(thread_ts) != str(payload.get("ts")):
            threads.setdefault(str(thread_ts), []).append(payload)
        else:
            messages.append(payload)

    messages.sort(key=lambda item: str(item.get("ts", "")))
    for replies in threads.values():
        replies.sort(key=lambda item: str(item.get("ts", "")))
    return {
        "channel": {
            "id": channel_id,
            "name": channel_name,
            "is_archived": False,
        },
        "users": users,
        "messages": messages,
        "threads": dict(sorted(threads.items())),
        "state": {
            "latest_ts": latest_ts,
            "complete": True,
            "classification": "synthetic_non_confidential",
        },
    }


def _slack_date(ts: str) -> str:
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%B %-d, %Y")
    except (TypeError, ValueError, OSError):
        return "Unknown date"


def _slack_time(ts: str) -> str:
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%b %-d, %Y, %H:%M")
    except (TypeError, ValueError, OSError):
        return str(ts)


def _slack_message_lines(message: dict[str, Any], users: dict[str, str], quote: bool = False) -> list[str]:
    prefix = "> " if quote else ""
    user_id = str(message.get("user", ""))
    name = users.get(user_id, user_id or "unknown-user")
    lines = [f"{prefix}**{name}** — _{_slack_time(str(message.get('ts', '')))}_"]
    text = str(message.get("text", ""))
    if text:
        for part in text.splitlines():
            lines.append(prefix + part)
    for file_info in message.get("files", []) or []:
        file_name = file_info.get("name") or file_info.get("title") or "file"
        lines.append(f"{prefix}📎 _{file_name}_")
    reactions = message.get("reactions", []) or []
    if reactions:
        summary = " ".join(
            f":{item.get('name', 'reaction')}: {item.get('count', 1)}" for item in reactions
        )
        lines.append(prefix + summary)
    if message.get("edited"):
        lines.append(prefix + "_(edited)_")
    return lines


def render_slack_markdown(envelope: dict[str, Any]) -> str:
    channel = envelope["channel"]
    users = envelope.get("users", {})
    messages = envelope.get("messages", [])
    threads = envelope.get("threads", {})
    lines = [f"# #{channel.get('name', 'channel')}", ""]
    if messages:
        lines.extend(
            [
                f"> {len(messages)} top-level messages; thread replies are rendered inline",
                "",
                "---",
                "",
            ]
        )
    last_date = None
    for message in messages:
        date = _slack_date(str(message.get("ts", "")))
        if date != last_date:
            lines.extend([f"## {date}", ""])
            last_date = date
        lines.extend(_slack_message_lines(message, users))
        replies = threads.get(str(message.get("ts", "")), [])
        if replies:
            lines.extend(["", f"> **Thread** ({len(replies)} replies):"])
            for reply in replies:
                lines.extend(_slack_message_lines(reply, users, quote=True))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_jira_markdown(payload: dict[str, Any]) -> str:
    issue_id = str(payload.get("id") or payload.get("key") or "issue")
    title = str(payload.get("title") or payload.get("summary") or "Untitled issue")
    variant = int(hashlib.sha256(issue_id.encode("utf-8")).hexdigest()[:4], 16) % 3
    headers = (f"# [{issue_id}] {title}", f"[{issue_id}] {title}", f"ISSUE {issue_id} — {title}")
    lines = [headers[variant], ""]
    fields = (
        ("Type", payload.get("issue_type")),
        ("Status", payload.get("status")),
        ("Priority", payload.get("priority")),
        ("Assignee", payload.get("assignee")),
        ("Reporter", payload.get("reporter")),
        ("Created", payload.get("created_at") or payload.get("created")),
        ("Updated", payload.get("updated_at") or payload.get("updated")),
        ("Labels", ", ".join(payload.get("labels", [])) if payload.get("labels") else None),
    )
    for label, value in fields:
        if value not in (None, "", []):
            if variant == 0:
                lines.append(f"**{label}:** {value}")
            elif variant == 1:
                lines.append(f"{label}: {value}")
            else:
                lines.append(f"- {label.lower()}: {value}")
    description = payload.get("description")
    if description not in (None, ""):
        heading = "## Description" if variant == 0 else "Description" if variant == 1 else "--- description ---"
        lines.extend(["", heading, "", str(description)])
    comments = payload.get("comments", []) or []
    if comments:
        heading = "## Activity" if variant == 0 else "Comments" if variant == 1 else "--- activity ---"
        lines.extend(["", heading, ""])
        for comment in comments:
            author = comment.get("author") or "unknown-user"
            created = comment.get("created") or comment.get("date") or "unknown time"
            lines.extend([f"**{author}** ({created}):", "", str(comment.get("text", "")), ""])
    if payload.get("stale_record"):
        lines.extend(["", "_No activity has been recorded on this issue for an extended period._"])
    return "\n".join(lines).rstrip() + "\n"


def render_confluence_markdown(payload: dict[str, Any]) -> str:
    body = str(payload.get("body", ""))
    if body:
        return body.rstrip() + "\n"
    title = str(payload.get("title") or payload.get("page_id") or "Untitled page")
    return f"# {title}\n"


def render_zoom_markdown(payload: dict[str, Any]) -> str:
    return str(payload.get("transcript", "")).rstrip() + "\n"


def render_record_markdown(system: str, payload: dict[str, Any]) -> str:
    object_id = payload.get("Id") or payload.get("id") or payload.get("pr_id") or "record"
    title = (
        payload.get("Name")
        or payload.get("title")
        or payload.get("subject")
        or payload.get("monitor_name")
        or str(object_id)
    )
    identity = f"{system}|{object_id}"
    variant = int(hashlib.sha256(identity.encode("utf-8")).hexdigest()[:4], 16) % 3
    headers = (f"# {title}", f"{system.upper()} EXPORT — {title}", f"[{object_id}] {title}")
    lines = [headers[variant], ""]
    for key, value in payload.items():
        if key in {"source_path", "body", "description", "comments", "activities"}:
            continue
        if value in (None, "", [], {}):
            continue
        label = key.replace("_", " ").strip().title()
        if isinstance(value, (list, dict)):
            value = json.dumps(value, ensure_ascii=False, sort_keys=True)
        if variant == 0:
            lines.append(f"**{label}:** {value}")
        elif variant == 1:
            lines.append(f"{key}={value}")
        else:
            lines.append(f"- {label}: {value}")
    for key, heading in (("description", "Description"), ("body", "Body")):
        if payload.get(key):
            section = f"## {heading}" if variant == 0 else heading if variant == 1 else f"--- {heading.lower()} ---"
            lines.extend(["", section, "", str(payload[key])])
    comments = payload.get("comments") or payload.get("activities") or []
    if comments:
        section = "## Activity" if variant == 0 else "Activity" if variant == 1 else "--- activity ---"
        lines.extend(["", section, ""])
        for item in comments:
            lines.append(str(item if not isinstance(item, dict) else item.get("text") or item))
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_raw_object(system: str, state: dict[str, Any]) -> tuple[str, str]:
    payload = source_visible_payload(state["payload"])
    if system == "email":
        return ".eml", _render_eml(state)
    return ".json", json_text(payload)


def render_inbox_object(system: str, state: dict[str, Any]) -> tuple[str, str]:
    payload = source_visible_payload(state["payload"])
    if system == "jira":
        return ".md", render_jira_markdown(payload)
    if system == "confluence":
        return ".md", render_confluence_markdown(payload)
    if system == "zoom":
        return ".md", render_zoom_markdown(payload)
    if system == "email":
        return ".eml", _render_eml(state)
    return ".md", render_record_markdown(system, payload)


def _render_eml(state: dict[str, Any]) -> str:
    """Preserve native EML while supplying a stable source ID when absent."""
    payload = state["payload"]
    raw = str(payload.get("raw_eml", ""))
    if re.search(r"(?im)^Message-ID\s*:", raw):
        return raw
    message_id = str(payload.get("message_id") or state["object_id"]).strip("<>")
    if "@" not in message_id:
        message_id = f"{message_id}@apexathletics.io"
    return f"Message-ID: <{message_id}>\n{raw}"
