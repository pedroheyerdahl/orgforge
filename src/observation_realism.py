"""Deterministic observation-plane realism mutations for synthetic corpora."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import yaml

from source_actions import SourceAction


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _bucket(seed: int, *parts: Any, modulus: int = 10_000) -> int:
    material = "|".join((str(seed), *(str(part) for part in parts)))
    return int.from_bytes(hashlib.sha256(material.encode("utf-8")).digest()[:8], "big") % modulus


def _clone(value: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


@dataclass(frozen=True)
class ObservationRealismPolicy:
    version: int = 5
    slack_punctuation_damage_pct: int = 48
    slack_reaction_pct: int = 15
    slack_file_pct: int = 5
    slack_edit_pct: int = 5
    slack_redelivery_pct: int = 3
    slack_link_pct: int = 10
    slack_mention_pct: int = 12
    slack_code_pct: int = 4
    slack_question_pct: int = 14
    slack_block_pct: int = 3
    slack_attachment_pct: int = 2
    slack_ack_thread_pct: int = 2
    slack_ordinary_thread_pct: int = 4
    slack_long_thread_pct: int = 1
    transcript_chunk_words: int = 42
    transcript_backchannel_pct: int = 12
    routine_git_interval_days: int = 14

    @classmethod
    def load(cls, path: Path) -> "ObservationRealismPolicy":
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        values = raw.get("observation_realism", {}) or {}
        known = {field.name for field in cls.__dataclass_fields__.values()}
        return cls(**{key: value for key, value in values.items() if key in known})


@dataclass(frozen=True)
class ObservationMutation:
    action_id: str
    mutation_type: str
    source_system: str
    object_id: str
    revision: int
    policy_version: int
    deterministic_seed: int
    original_hash: str
    result_hash: str
    truth_event_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["truth_event_ids"] = list(self.truth_event_ids)
        return value


def _slack_payload(payload: dict[str, Any], object_id: str, revision: int, policy: ObservationRealismPolicy, seed: int) -> dict[str, Any]:
    result = _clone(payload)
    text = str(result.get("text", ""))
    key = (object_id, revision)
    if (
        result.get("synthetic_routine")
        and 0 < len(text.split()) <= 5
        and _bucket(seed, *key, "routine-short-context", modulus=100) < 30
    ):
        try:
            native_day = datetime.fromtimestamp(
                float(result.get("ts", "")), tz=timezone.utc
            )
            text = f"{text} — {native_day.strftime('%b')} {native_day.day} export"
        except (TypeError, ValueError, OSError):
            pass
    if text and _bucket(seed, *key, "punctuation", modulus=100) < policy.slack_punctuation_damage_pct:
        text = text.rstrip()
        if text.endswith((".", "!", "?")):
            text = text[:-1]
    elif text and not text.rstrip().endswith((".", "!", "?")) and _bucket(
        seed, *key, "punctuation-restore", modulus=100
    ) < 35:
        text = text.rstrip() + "."
    if text and "https://" not in text and _bucket(seed, *key, "link", modulus=100) < policy.slack_link_pct:
        text += f" https://wiki.apexathletics.io/notes/{object_id[:16]}"
    if text and "@" not in text and _bucket(seed, *key, "mention", modulus=100) < policy.slack_mention_pct:
        text = "@ops " + text
    if text and "`" not in text and _bucket(seed, *key, "code", modulus=100) < policy.slack_code_pct:
        text += " `retry_state=unknown`"
    if text and "?" not in text and _bucket(seed, *key, "question", modulus=100) < policy.slack_question_pct:
        text = text.rstrip(".!") + " — is that still current?"
    result["text"] = text
    if _bucket(seed, *key, "reaction", modulus=100) < policy.slack_reaction_pct:
        result["reactions"] = [{"name": "eyes", "count": 1 + _bucket(seed, *key, "reaction-count", modulus=3), "users": ["UOBS001"]}]
    if _bucket(seed, *key, "file", modulus=100) < policy.slack_file_pct:
        result["files"] = [{"id": f"F{_bucket(seed, *key, 'file-id', modulus=10**8):08d}", "name": "trace.txt", "mimetype": "text/plain", "size": 300 + _bucket(seed, *key, "file-size", modulus=9000)}]
    if _bucket(seed, *key, "block", modulus=100) < policy.slack_block_pct:
        result["blocks"] = [{"type": "section", "block_id": f"context-{object_id[:12]}", "text": {"type": "mrkdwn", "text": text or " "}}]
    if _bucket(seed, *key, "attachment", modulus=100) < policy.slack_attachment_pct:
        result["attachments"] = [{"id": f"A{_bucket(seed, *key, 'attachment-id', modulus=10**8):08d}", "fallback": text[:120] or "system event", "color": "#8b8b8b"}]
    return result


_TURN = re.compile(
    r"\*\*\[([^\]]+)\]\s+([^:]+):\*\*\s*(.*?)(?=\s+\*\*\[[^\]]+\]|$)",
    re.S,
)


def _expand_transcript(text: str, object_id: str, policy: ObservationRealismPolicy, seed: int) -> str:
    parsed = [
        (timestamp, speaker, " ".join(body.split()))
        for timestamp, speaker, body in _TURN.findall(text)
    ]
    if not parsed:
        return text
    speakers = list(dict.fromkeys(speaker for _time, speaker, _body in parsed))
    roster = ("Morgan", "Deepa", "Jenna", "Tom", "Vince", "Sarah", "Hanna", "Miki")
    target_speakers = min(7, max(5, len(speakers)))
    speaker_pool = list(speakers)
    for person in roster:
        if person not in speaker_pool and len(speaker_pool) < target_speakers:
            speaker_pool.append(person)

    fillers = ("um,", "uh,", "yeah,", "sorry—", "I mean,", "so,")
    backchannels = ("yeah", "right", "mm-hm", "got it", "one sec", "go ahead")
    evidence_origins = (
        "My queue sample",
        "The ticket history",
        "Support's client trace",
        "The handoff note",
        "This morning's dashboard",
        "The attached revision",
        "The gateway output",
        "The owner note",
        "The fallback log",
        "The deployment record",
        "Support's test result",
        "The cached report",
    )
    evidence_findings = (
        "covers one route, not the adjacent request",
        "has an older owner field",
        "shows a narrower client scope",
        "omits the deployed revision",
        "diverges on the fallback result",
        "predates the drained queue",
        "contains an unreported warning",
        "matches after excluding the cache",
        "does not identify the setting owner",
        "points at an earlier export",
        "supports only the narrow fix",
        "predates the owner response",
    )
    evidence_actions = (
        "I will attach both records",
        "the owner can confirm the build",
        "we can test the older client",
        "I will keep the queue capture",
        "support can add the request ID",
        "the rollout note can stay narrow",
        "we can separate cached and live results",
        "I will request another run",
        "the client can stay in its ticket",
        "we can record the handoff gap",
        "the timeline can carry both observations",
        "I will verify the linked export",
    )
    evidence_questions = (
        "Can the owner add the build ID?",
        "Should support attach the second trace?",
        "Who can rerun the fallback path?",
        "Do we have a same-revision capture?",
        "Can cached and live stay separate?",
        "Should the handoff name the open route?",
        "Who has the matching deployment record?",
        "Can the ticket retain both observations?",
    )

    def meeting_move(context: str, move_index: int, phase: str) -> str:
        bucket = _bucket(seed, object_id, move_index, phase, "meeting-move")
        origin = evidence_origins[bucket % len(evidence_origins)]
        finding = evidence_findings[(bucket // 13) % len(evidence_findings)]
        if bucket % 4 == 0:
            next_step = evidence_questions[(bucket // 29) % len(evidence_questions)]
        else:
            next_step = evidence_actions[(bucket // 31) % len(evidence_actions)] + "."
        return f"{origin} for {context} {finding}. {next_step}"

    def discourse_chunks(body: str, turn_index: int) -> list[str]:
        limit = max(48, policy.transcript_chunk_words) + _bucket(
            seed, object_id, turn_index, "chunk-limit", modulus=21
        )
        sentences = re.split(r"(?<=[.!?])\s+", body.strip())
        chunks: list[str] = []
        current: list[str] = []
        for sentence in sentences:
            words = sentence.split()
            while len(words) > limit:
                if current:
                    chunks.append(" ".join(current))
                    current = []
                cut = limit
                for index in range(min(limit, len(words) - 1), max(20, limit - 12), -1):
                    if words[index - 1].endswith((",", ";", ":")):
                        cut = index
                        break
                chunks.append(" ".join(words[:cut]))
                words = words[cut:]
            if current and len(current) + len(words) > limit:
                chunks.append(" ".join(current))
                current = []
            current.extend(words)
        if current:
            chunks.append(" ".join(current))
        return chunks or [body.strip()]

    output: list[str] = []
    added_turn = 0
    for turn_index, (timestamp, speaker, body) in enumerate(parsed):
        chunks = discourse_chunks(body, turn_index)
        for chunk_index, chunk in enumerate(chunks):
            prefix = ""
            if _bucket(seed, object_id, turn_index, chunk_index, "filler", modulus=100) < 18:
                prefix = fillers[_bucket(seed, object_id, turn_index, chunk_index, "filler-choice", modulus=len(fillers))] + " "
            output.append(f"**[{timestamp}] {speaker}:** {prefix}{chunk}".rstrip())
        context_words = [
            word.casefold()
            for word in re.findall(r"[A-Za-z0-9_-]{4,}", body)
            if word.casefold() not in {"that", "this", "with", "from", "still", "have", "should", "would"}
        ]
        identifiers = re.findall(
            r"\b(?:[A-Z]{2,8}-\d+|PR-\d+|\d+)\b",
            body,
        )
        context_parts = [
            *(f"case {value}" if value.isdigit() else value for value in identifiers[:1]),
            *context_words[:3],
        ]
        context = " ".join(context_parts[:4]) or f"turn {turn_index + 1}"
        short_context = (
            f"case {identifiers[0]}"
            if identifiers and identifiers[0].isdigit()
            else identifiers[0]
            if identifiers
            else " ".join(context_words[:2])
        )
        listener = speaker_pool[(turn_index + added_turn + 1) % len(speaker_pool)]
        if turn_index % 4 == 1 or _bucket(seed, object_id, turn_index, "question", modulus=100) < 14:
            reply = meeting_move(context, turn_index, "response")
            output.append(f"**[{timestamp}] {listener}:** {reply}")
            added_turn += 1
        if turn_index % 5 == 0 or _bucket(seed, object_id, turn_index, "backchannel", modulus=100) < policy.transcript_backchannel_pct:
            listener = speaker_pool[(turn_index + added_turn + 2) % len(speaker_pool)]
            reply = backchannels[_bucket(seed, object_id, turn_index, "backchannel-choice", modulus=len(backchannels))]
            if short_context:
                reply = f"{reply} — {short_context}"
            output.append(f"**[{timestamp}] {listener}:** {reply}")
            added_turn += 1
    while len(output) < 6:
        timestamp, _speaker, body = parsed[len(output) % len(parsed)]
        context_words = re.findall(r"[A-Za-z0-9_-]{4,}", body)
        context = " ".join(context_words[:2]).casefold() or f"turn {len(output) + 1}"
        speaker = speaker_pool[len(output) % len(speaker_pool)]
        move = meeting_move(context, len(output), "minimum-turn")
        output.append(f"**[{timestamp}] {speaker}:** {move}")
    length_bucket = _bucket(seed, object_id, "meeting-length", modulus=100)
    if length_bucket < 60:
        target_turns = 42 + _bucket(seed, object_id, "ordinary-turns", modulus=25)
    elif length_bucket < 80:
        target_turns = 82 + _bucket(seed, object_id, "medium-turns", modulus=49)
    else:
        target_turns = 160 + _bucket(seed, object_id, "long-turns", modulus=61)
    while len(output) < target_turns:
        extension_index = len(output)
        timestamp, _source_speaker, body = parsed[extension_index % len(parsed)]
        identifiers = re.findall(r"\b(?:[A-Z]{2,8}-\d+|PR-\d+|\d+)\b", body)
        words = [
            word.casefold()
            for word in re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,}", body)
            if word.casefold()
            not in {"that", "this", "with", "from", "still", "before", "after"}
        ]
        context = " ".join([*identifiers[:1], *words[:3]]) or f"segment {extension_index}"
        move = meeting_move(context, extension_index, "continuation")
        pass_names = (
            "first", "second", "third", "fourth", "fifth", "sixth", "seventh",
            "eighth", "ninth", "tenth", "eleventh", "twelfth", "thirteenth",
            "fourteenth", "fifteenth", "sixteenth", "seventeenth", "eighteenth",
            "nineteenth", "twentieth", "twenty-first", "twenty-second", "twenty-third",
            "twenty-fourth", "twenty-fifth", "twenty-sixth", "twenty-seventh",
            "twenty-eighth", "twenty-ninth", "thirtieth", "thirty-first",
            "thirty-second", "thirty-third", "thirty-fourth", "thirty-fifth",
            "thirty-sixth", "thirty-seventh", "thirty-eighth", "thirty-ninth", "fortieth",
        )
        pass_index = min(extension_index // len(parsed), len(pass_names) - 1)
        pass_name = pass_names[pass_index]
        perspectives = (
            "screen", "console", "ticket", "export", "timeline", "client", "gateway", "queue",
            "runtime", "document", "dashboard", "incident", "handoff", "review", "support", "release",
        )
        evidence_forms = (
            "note", "log", "trace", "snapshot", "thread", "revision", "result", "record",
            "branch", "report", "capture", "status", "entry", "summary", "output", "view",
        )
        perspective = perspectives[_bucket(seed, object_id, "meeting-perspective", modulus=len(perspectives))]
        evidence_form = evidence_forms[_bucket(seed, object_id, "meeting-evidence", modulus=len(evidence_forms))]
        if extension_index % 6 == 1:
            fragments = ("checking", "found it", "one moment", "same record", "noted", "I see it")
            fragment = fragments[
                _bucket(seed, object_id, extension_index, "short-fragment", modulus=len(fragments))
            ]
            move = f"{fragment} — {context.split()[0]} {perspective}-{evidence_form}"
        elif extension_index % 7 == 0:
            source_excerpt = " ".join(body.split()[:36])
            move = f"{move} The source excerpt reads: {source_excerpt} This is the {pass_name} pass through that record."
        else:
            move += f" — {perspective} {evidence_form}"
        if (
            not re.search(r"\b(?:um|uh|yeah|sorry|i mean|mm-hm)\b", move, re.I)
            and _bucket(seed, object_id, extension_index, "continuation-filler", modulus=100) < 20
        ):
            filler = fillers[
                _bucket(
                    seed,
                    object_id,
                    extension_index,
                    "continuation-filler-choice",
                    modulus=len(fillers),
                )
            ]
            move = f"{filler} {move}"
        if extension_index % 9 == 0:
            move += f" [pass {extension_index // 9 + 1}]"
        speaker = speaker_pool[
            _bucket(seed, object_id, extension_index, "continuation-speaker", modulus=len(speaker_pool))
        ]
        output.append(f"**[{timestamp}] {speaker}:** {move}")
    if policy.version >= 5:
        directions = ("from", "against", "inside", "beside", "after", "before", "under", "around")
        evidence = ("console", "ticket", "timeline", "record", "capture", "handoff", "review", "export")
        qualifiers = ("available", "archived", "adjacent", "current", "earlier", "partial", "scoped", "unverified")
        diversified: list[str] = []
        for line_index, line in enumerate(output):
            match = re.match(r"^(\*\*\[[^]]+\]\s+[^:]+:\*\*\s*)(.*)$", line)
            if not match or len(match.group(2).split()) < 6:
                diversified.append(line)
                continue
            marker_bucket = _bucket(seed, object_id, line_index, "meeting-opening")
            marker = (
                f"{directions[marker_bucket % len(directions)]} "
                f"{evidence[(marker_bucket // 8) % len(evidence)]}-"
                f"{qualifiers[(marker_bucket // 64) % len(qualifiers)]} evidence"
            )
            diversified.append(f"{match.group(1)}{marker}: {match.group(2)}")
        output = diversified
    return "\n".join(output).rstrip() + "\n"


def _compose_git_body(title: str, object_id: str, seed: int) -> str:
    """Compose varied source-like PR prose without a corpus-wide scaffold."""

    focus = re.sub(r"[^A-Za-z0-9 _-]+", " ", title).strip() or object_id
    contexts = (
        "The change follows a mismatch found while comparing the client trace with the recorded handoff.",
        "This branch came out of a support reproduction whose result differed between two environments.",
        "A narrow runtime check exposed behavior that the current ticket wording does not fully describe.",
        "The owner review found that the exported state and the deployed path were not using the same revision.",
        "During release verification, the fallback response diverged from the primary path without a clear alert.",
        "A customer report reopened this path after the earlier fix appeared correct in only one client.",
        "The latest queue sample made an old assumption visible in the surrounding retry code.",
        "An operational follow-up identified a boundary condition absent from the original implementation note.",
    )
    changes = (
        "The patch limits its edits to the decision boundary and leaves neighboring cleanup for a separate review.",
        "Only the affected adapter and its direct verification path move here; broader naming work stays out.",
        "The implementation keeps the existing interface while making the ambiguous state explicit at the call site.",
        "This update separates primary and fallback handling so each result can be inspected independently.",
        "The branch records the source revision beside the check and avoids changing unrelated defaults.",
        "The code preserves the current rollout switch and narrows the condition that selects the older behavior.",
        "The adjustment is intentionally local, with no migration or retrospective rewrite of stored records.",
        "The modified path now retains enough context for reviewers to distinguish cached and current results.",
    )
    checks = (
        "Verification should cover a warm request, a cold retry, and one unsupported client before approval.",
        "Reviewers can compare the captured timestamp, environment, and owner note against the attached run.",
        "The useful check is whether both client paths report the same revision after a clean restart.",
        "Please reproduce once with the feature enabled and once with the previous setting retained.",
        "The test plan keeps the queue state visible and records which export supplied each expected value.",
        "Confirm the primary case first, then inspect the adjacent fallback without inferring from the newest comment.",
        "A passing unit test is not sufficient here; the deployment trace must identify the evaluated revision.",
        "Before merge, validate the older client and preserve any unresolved result as a follow-up issue.",
    )
    cautions = (
        "Known gap: ownership for the legacy environment remains provisional until the next handoff.",
        "The available evidence does not settle the mobile fallback, so that case remains explicitly open.",
        "No claim is made about historical exports; this only changes behavior observed after deployment.",
        "If the support reproduction differs again, pause rollout and keep both observations in the record.",
        "The cached path may still show the previous value for one cycle and should not be treated as a regression alone.",
        "A separate configuration discrepancy remains outside this pull request and has its own owner.",
        "The rollback is the existing switch; do not substitute a data rewrite during incident response.",
        "One client combination lacks direct evidence and should stay unresolved rather than inherit the primary result.",
    )
    bucket = _bucket(seed, object_id, "git-body")
    orderings = (
        (contexts, changes, checks, cautions),
        (checks, contexts, cautions, changes),
        (changes, cautions, contexts, checks),
        (cautions, checks, changes, contexts),
    )
    sections = orderings[bucket % len(orderings)]
    paragraphs = [
        group[(bucket // (11 + position * 6) + position * 3) % len(group)]
        for position, group in enumerate(sections)
    ]
    headings = ("Context", "Change", "Verification", "Open edge")
    rendered = [f"## {headings[(position + bucket) % len(headings)]}\n\n{paragraph}"
                for position, paragraph in enumerate(paragraphs)]
    rendered.insert(1, f"Review focus: {focus}.")
    return "\n\n".join(rendered)


def _transform_payload(action: SourceAction, policy: ObservationRealismPolicy, seed: int) -> tuple[dict[str, Any], str]:
    payload = _clone(action.payload)
    if action.source_system == "slack":
        return _slack_payload(payload, action.object_id, action.revision, policy, seed), "slack_texture"
    if action.source_system == "zoom" and payload.get("transcript"):
        payload["transcript"] = _expand_transcript(str(payload["transcript"]), action.object_id, policy, seed)
        payload["transcript_degraded"] = True
        return payload, "transcript_discourse"
    if action.source_system == "git":
        body = str(payload.get("body", "")).strip()
        if policy.version >= 5 or not body:
            title = str(payload.get("title") or action.object_id)
            body = _compose_git_body(title, action.object_id, seed)
        if "- [ ]" not in body and _bucket(
            seed, action.object_id, "git-checklist", modulus=100
        ) < 12:
            body += "\n\n- [ ] verify the fallback path\n- [x] keep the change isolated"
        if "https://" not in body and _bucket(
            seed, action.object_id, "git-link", modulus=100
        ) < 12:
            body += f"\n\nhttps://git.apexathletics.io/pulls/{action.object_id}"
        payload["body"] = body

        comments = list(payload.get("comments", []) or [])
        comment_bucket = _bucket(seed, action.object_id, "git-comment-density", modulus=100)
        if len(comments) >= 8 and comment_bucket >= 80:
            comments = comments[-12:]
        elif comment_bucket < 65:
            comments = []
        elif comment_bucket < 85:
            comments = comments[-1:]
        elif comment_bucket < 90:
            comments = comments[-4:]
        else:
            comments = comments[-12:]
        payload["comments"] = comments
        return payload, "git_source_texture"
    if action.source_system in {"jira", "confluence", "zendesk", "salesforce", "datadog"}:
        if _bucket(seed, action.source_system, action.object_id, "sparse", modulus=100) < 8:
            for key in ("assignee", "owner", "priority", "labels", "description"):
                if key in payload and _bucket(seed, action.object_id, key, modulus=2) == 0:
                    payload.pop(key, None)
            return payload, "optional_field_sparsity"
    return payload, "unchanged"


def _new_slack_actions(actions: list[SourceAction], policy: ObservationRealismPolicy, seed: int) -> list[SourceAction]:
    additions: list[SourceAction] = []
    roots = [action for action in actions if action.source_system == "slack" and action.operation == "create" and not action.payload.get("thread_ts")]
    existing_replies: Counter[str] = Counter(
        str(action.payload.get("thread_ts"))
        for action in actions
        if action.source_system == "slack"
        and action.operation == "create"
        and action.payload.get("thread_ts")
    )
    short_texts = ("ok", "looking", "same here", "not sure", "later today", "+1", "which link?", "one sec")
    thread_moves = (
        "I only checked {context}; does that match the same scope?",
        "for {context}, I would keep this provisional until the other path reports back",
        "the note about {context} may be one revision behind — which result are you using?",
        "I can verify {context} after the current job finishes, but not the adjacent case",
        "does {context} include the change from earlier, or is that still the cached result?",
        "I saw {context} in one place and a different state elsewhere; I am checking the timestamp",
        "small correction on {context}: I checked the first path, not the fallback path",
        "leaving {context} unresolved for now; the owner in the older thread has not replied",
        "which environment produced the {context} result? mine does not show enough detail",
        "the {context} link opens, but the status on it is not clearly final",
    )
    corpus_end = max(
        (datetime.fromisoformat(action.observed_at.replace("Z", "+00:00")) for action in actions),
        default=datetime.max.replace(tzinfo=timezone.utc),
    )
    for root in roots:
        group = _bucket(seed, root.object_id, "thread-group", modulus=100)
        root_ts = str(root.payload.get("ts", ""))
        current_reply_count = existing_replies.get(root_ts, 0)
        if policy.version >= 5 and current_reply_count:
            shape = _bucket(seed, root.object_id, "existing-thread-shape", modulus=100)
            target_messages = (
                2 + _bucket(seed, root.object_id, "existing-thread-ordinary", modulus=9)
                if shape < 90
                else 11 + _bucket(seed, root.object_id, "existing-thread-tail", modulus=17)
            )
            count = max(0, target_messages - 1 - current_reply_count)
            if count == 0:
                continue
        elif policy.version >= 5 and group < policy.slack_ack_thread_pct:
            count = 1 + _bucket(seed, root.object_id, "thread-ack-length", modulus=2)
        elif policy.version >= 5 and group < policy.slack_ack_thread_pct + policy.slack_ordinary_thread_pct:
            count = 3 + _bucket(seed, root.object_id, "thread-ordinary-length", modulus=7)
        elif policy.version >= 5 and group < policy.slack_ack_thread_pct + policy.slack_ordinary_thread_pct + policy.slack_long_thread_pct:
            count = 10 + _bucket(seed, root.object_id, "thread-long-tail", modulus=18)
        elif policy.version < 5 and group < policy.slack_ack_thread_pct:
            count = 1
        elif policy.version < 5 and group < policy.slack_ack_thread_pct + policy.slack_long_thread_pct:
            tail = _bucket(seed, root.object_id, "thread-length-shape", modulus=100)
            count = 4 if tail < 60 else 6 if tail < 80 else 12 + _bucket(seed, root.object_id, "thread-long-tail", modulus=3)
        else:
            continue
        try:
            numeric_root_ts = float(root_ts)
        except (TypeError, ValueError):
            numeric_root_ts = datetime.fromisoformat(root.observed_at.replace("Z", "+00:00")).timestamp()
        base_time = datetime.fromisoformat(root.observed_at.replace("Z", "+00:00"))
        identifiers = re.findall(r"\b(?:[A-Z]{2,8}-\d+|PR-\d+|[A-Za-z]+DB|\d{3,})\b", str(root.payload.get("text", "")))
        words = [
            word.casefold()
            for word in re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,}", str(root.payload.get("text", "")))
            if word.casefold() not in {"that", "this", "with", "from", "still", "uses", "previous", "value", "have", "after"}
        ]
        context_parts = list(dict.fromkeys([*identifiers, *words]))[:4]
        context = " ".join(context_parts) or f"case {root.object_id[-6:]}"
        short_context = " ".join(context_parts[:2]) or root.object_id[-6:]
        for index in range(count):
            object_hash = hashlib.sha256(f"{seed}|{root.object_id}|reply|{index}".encode("utf-8")).hexdigest()[:20]
            object_id = f"slack-realism-{object_hash}"
            when = base_time + timedelta(seconds=37 + index * 83 + _bucket(seed, object_id, "seconds", modulus=29))
            if count == 1:
                acknowledgement = short_texts[
                    _bucket(seed, object_id, "text", modulus=len(short_texts))
                ]
                text = f"{acknowledgement} {short_context}"
            elif index < 5 and index % 4 != 1:
                text = f"{short_texts[_bucket(seed, object_id, 'text', modulus=len(short_texts))]} {short_context}"
            else:
                move_index = (
                    _bucket(seed, root.object_id, "thread-text-sequence", modulus=len(thread_moves))
                    + index
                ) % len(thread_moves)
                text = thread_moves[move_index].format(context=context)
                perspectives = ("console", "ticket", "timeline", "client", "queue", "gateway", "export", "runtime")
                perspective = perspectives[
                    _bucket(seed, root.object_id, index, "thread-perspective", modulus=len(perspectives))
                ]
                text += f" — from the {perspective} view"
            if not text.endswith("?") and _bucket(seed, object_id, "terminal", modulus=100) >= 52:
                text += "."
            if when > corpus_end:
                break
            payload: dict[str, Any] = {
                "type": "message",
                "channel_id": root.payload.get("channel_id", ""),
                "channel_name": root.payload.get("channel_name", "general"),
                "user": f"UOBS{index % 7:03d}",
                "user_profile": {"display_name": ("Miki", "Hanna", "Tom", "Jenna", "Vince", "Deepa", "Morgan")[index % 7]},
                "text": text,
                "ts": f"{numeric_root_ts + 37 + index * 83:.6f}",
                "thread_ts": root_ts,
                "client_msg_id": object_id,
                "synthetic_routine": not bool(current_reply_count),
                "synthetic_unresolved": index + 1 == count and count > 1,
            }
            if index == 0 and _bucket(seed, root.object_id, "bot", modulus=100) < 12:
                payload.update({"subtype": "bot_message", "bot_id": "BOBSMON", "user": "UBUILDMON", "user_profile": {"display_name": "Build Monitor"}, "text": f"workflow check for {context} completed with warnings [{object_hash[:5]}]"})
            if index % 7 == 2:
                payload["reactions"] = [{"name": "thumbsup", "count": 1, "users": ["UOBS001"]}]
            if index % 11 == 3:
                payload["files"] = [{"id": f"F{object_hash[:8]}", "name": "screenshot.png", "mimetype": "image/png", "size": 18422}]
            if index % 13 == 5:
                payload["text"] += f" https://wiki.apexathletics.io/notes/{object_hash[:8]}"
            if index % 10 == 6:
                payload["text"] = "@ops " + payload["text"]
            if _bucket(seed, object_id, "ephemeral", modulus=100) < 6:
                payload["synthetic_ephemeral"] = True
            additions.append(SourceAction(source_system="slack", object_id=object_id, revision=1, operation="create", observed_at=when.isoformat(), effective_at=when.isoformat(), truth_event_ids=root.truth_event_ids, payload=payload))
    return additions


def _slack_lifecycle_actions(
    actions: list[SourceAction],
    policy: ObservationRealismPolicy,
    seed: int,
) -> list[tuple[SourceAction, str, str]]:
    """Create real Slack revisions, retries, and tombstones for stable objects."""
    history = Counter((action.source_system, action.object_id) for action in actions)
    corpus_end = max(
        (datetime.fromisoformat(action.observed_at.replace("Z", "+00:00")) for action in actions),
        default=datetime.max.replace(tzinfo=timezone.utc),
    )
    lifecycle: list[tuple[SourceAction, str, str]] = []
    for create in actions:
        key = (create.source_system, create.object_id)
        if (
            create.source_system != "slack"
            or create.operation != "create"
            or history[key] != 1
        ):
            continue
        current = create
        current_time = datetime.fromisoformat(create.observed_at.replace("Z", "+00:00"))
        force_edit = bool(create.payload.get("edited"))
        wants_edit = force_edit or _bucket(
            seed, create.object_id, "lifecycle-edit", modulus=100
        ) < policy.slack_edit_pct
        if wants_edit:
            update_time = current_time + timedelta(
                seconds=45 + _bucket(seed, create.object_id, "edit-delay", modulus=900)
            )
            if update_time <= corpus_end:
                payload = _clone(current.payload)
                payload["edited"] = {
                    "user": payload.get("user", ""),
                    "ts": f"{update_time.timestamp():.6f}",
                }
                update = SourceAction(
                    source_system="slack",
                    object_id=current.object_id,
                    revision=current.revision + 1,
                    operation="update",
                    observed_at=update_time.isoformat(),
                    effective_at=update_time.isoformat(),
                    truth_event_ids=current.truth_event_ids,
                    payload=payload,
                )
                lifecycle.append((update, "slack_revision_edit", current.payload_sha256))
                current = update
                current_time = update_time
        wants_redelivery = _bucket(
            seed, create.object_id, "lifecycle-redelivery", modulus=100
        ) < policy.slack_redelivery_pct
        if wants_redelivery:
            redelivery_time = current_time + timedelta(
                seconds=30 + _bucket(seed, create.object_id, "redelivery-delay", modulus=600)
            )
            if redelivery_time <= corpus_end:
                redelivery = SourceAction(
                    source_system="slack",
                    object_id=current.object_id,
                    revision=current.revision,
                    operation="redeliver",
                    observed_at=redelivery_time.isoformat(),
                    effective_at=current.effective_at,
                    truth_event_ids=current.truth_event_ids,
                    payload=current.payload,
                )
                lifecycle.append((redelivery, "slack_redelivery", ""))
                current_time = redelivery_time
        if create.payload.get("synthetic_ephemeral"):
            delete_time = current_time + timedelta(
                seconds=60 + _bucket(seed, create.object_id, "delete-delay", modulus=1200)
            )
            if delete_time <= corpus_end:
                payload = {
                    **_clone(current.payload),
                    "text": "This message was deleted.",
                    "subtype": "tombstone",
                    "deleted_ts": f"{delete_time.timestamp():.6f}",
                }
                delete = SourceAction(
                    source_system="slack",
                    object_id=current.object_id,
                    revision=current.revision + 1,
                    operation="delete",
                    observed_at=delete_time.isoformat(),
                    effective_at=delete_time.isoformat(),
                    truth_event_ids=current.truth_event_ids,
                    payload=payload,
                )
                lifecycle.append((delete, "slack_tombstone", current.payload_sha256))
    return lifecycle


def _routine_git_actions(actions: list[SourceAction], policy: ObservationRealismPolicy, seed: int) -> list[SourceAction]:
    if not actions:
        return []
    start = min(datetime.fromisoformat(action.observed_at.replace("Z", "+00:00")) for action in actions)
    end = max(datetime.fromisoformat(action.observed_at.replace("Z", "+00:00")) for action in actions)
    span_days = (end.date() - start.date()).days
    if span_days < 60:
        return []
    additions: list[SourceAction] = []
    count = min(48, max(24, span_days // max(1, policy.routine_git_interval_days)))
    people = ("Hanna", "Miki", "Tom", "Jenna", "Vince", "Deepa")
    anchors = [
        action
        for action in actions
        if action.operation == "create" and action.source_system in {"jira", "slack", "git", "confluence"}
    ] or list(actions)
    title_moves = ("clarify", "guard", "verify", "separate", "trace", "narrow", "document", "stabilize")
    focus_moves = ("fallback state", "revision check", "client scope", "retry boundary", "export timing", "handoff path")
    comment_moves = (
        "does the {anchor} evidence cover the fallback path?",
        "one check is still pending for {anchor}",
        "can we keep the revision used for {anchor} in the description?",
        "the narrow path looks fine; I have not checked the adjacent case",
    )
    for index in range(count):
        created = start + timedelta(days=index * span_days / max(count - 1, 1), hours=8 + index % 9)
        object_id = f"PR-REAL-{index:04d}"
        anchor = anchors[_bucket(seed, object_id, "anchor", modulus=len(anchors))]
        anchor_label = str(
            anchor.payload.get("title")
            or anchor.payload.get("subject")
            or anchor.payload.get("text")
            or anchor.object_id
        ).strip().splitlines()[0][:72]
        anchor_id = anchor.object_id
        final_kind = index % 4
        initial_status = "draft" if final_kind == 0 else "open"
        title = (
            ("wip: " if initial_status == "draft" else "")
            + f"{title_moves[index % len(title_moves)]} {anchor_id.lower()} "
            + f"{focus_moves[(index * 3) % len(focus_moves)]} #{index + 1}"
        )
        body_parts = [_compose_git_body(f"{title}: {anchor_label}", object_id, seed)]
        if index % 3 == 0:
            body_parts.append(f"- [ ] verify {anchor_id} against the fallback path\n- [x] keep the change isolated")
        if index % 4 == 0:
            body_parts.append(f"https://git.apexathletics.io/pulls/{object_id}")
        wants_comment = index % 5 not in {0, 1, 2}
        payload = {"pr_id": object_id, "title": title, "body": "\n\n".join(body_parts), "status": initial_status, "author": people[index % len(people)], "created_at": created.isoformat(), "comments": [], "synthetic_routine": True, "source_anchor": {"source_system": anchor.source_system, "object_id": anchor_id}}
        create = SourceAction(source_system="git", object_id=object_id, revision=1, operation="create", observed_at=created.isoformat(), effective_at=created.isoformat(), truth_event_ids=anchor.truth_event_ids, payload=payload)
        additions.append(create)
        current_payload = payload
        current_revision = 1
        if wants_comment:
            review_time = created + timedelta(
                minutes=18 + _bucket(seed, object_id, "review-delay", modulus=73)
            )
            if review_time <= end:
                current_revision += 1
                current_payload = {
                    **payload,
                    "updated_at": review_time.isoformat(),
                    "comments": [
                        {
                            "author": people[(index + 1) % len(people)],
                            "timestamp": review_time.isoformat(),
                            "text": comment_moves[index % len(comment_moves)].format(anchor=anchor_id),
                        }
                    ],
                }
                additions.append(SourceAction(source_system="git", object_id=object_id, revision=current_revision, operation="update", observed_at=review_time.isoformat(), effective_at=review_time.isoformat(), truth_event_ids=anchor.truth_event_ids, payload=current_payload))
        if final_kind in {2, 3}:
            lifecycle_bucket = _bucket(seed, object_id, "lifespan-shape", modulus=100)
            if lifecycle_bucket < 30:
                lifespan_days = 1 + _bucket(seed, object_id, "lifespan-short", modulus=5)
            elif lifecycle_bucket < 75:
                lifespan_days = 7 + _bucket(seed, object_id, "lifespan-medium", modulus=14)
            else:
                lifespan_days = 18 + _bucket(seed, object_id, "lifespan-long", modulus=18)
            lifespan = timedelta(days=lifespan_days, hours=2 + index % 7)
            resolved = created + lifespan
            if resolved <= end:
                status = "merged" if final_kind == 2 else "closed"
                additions.append(SourceAction(source_system="git", object_id=object_id, revision=current_revision + 1, operation="update", observed_at=resolved.isoformat(), effective_at=resolved.isoformat(), truth_event_ids=anchor.truth_event_ids, payload={**current_payload, "status": status, "updated_at": resolved.isoformat(), "merged_at": resolved.isoformat() if status == "merged" else None}))
    return additions


def _stretch_git_terminal_lifecycles(
    actions: list[SourceAction],
    policy: ObservationRealismPolicy,
    seed: int,
) -> list[SourceAction]:
    """Move last terminal snapshots into a realistic long tail within the window."""

    if policy.version < 5 or not actions:
        return actions
    corpus_end = max(
        datetime.fromisoformat(action.observed_at.replace("Z", "+00:00"))
        for action in actions
    )
    by_object: dict[str, list[SourceAction]] = {}
    for action in actions:
        if action.source_system == "git":
            by_object.setdefault(action.object_id, []).append(action)
    replacements: dict[str, SourceAction] = {}
    for object_id, history in by_object.items():
        history.sort(key=lambda item: (item.observed_at, item.action_id))
        create = next((item for item in history if item.operation == "create"), None)
        terminal = next(
            (
                item
                for item in reversed(history)
                if item.operation == "update"
                and str(item.payload.get("status", "")).casefold() in {"merged", "closed"}
            ),
            None,
        )
        if create is None or terminal is None or terminal is not history[-1]:
            continue
        created_at = datetime.fromisoformat(create.observed_at.replace("Z", "+00:00"))
        current_at = datetime.fromisoformat(terminal.observed_at.replace("Z", "+00:00"))
        shape = _bucket(seed, object_id, "terminal-lifecycle-shape", modulus=100)
        if shape < 45:
            target_days = 2 + _bucket(seed, object_id, "terminal-short", modulus=7)
        elif shape < 80:
            target_days = 10 + _bucket(seed, object_id, "terminal-medium", modulus=11)
        else:
            target_days = 21 + _bucket(seed, object_id, "terminal-long", modulus=15)
        target_at = created_at + timedelta(days=target_days, hours=2 + shape % 6)
        if target_at <= current_at or target_at > corpus_end:
            continue
        payload = _clone(terminal.payload)
        for key in ("updated_at", "merged_at", "closed_at"):
            if key in payload and payload[key] is not None:
                payload[key] = target_at.isoformat()
        replacements[terminal.action_id] = SourceAction(
            source_system=terminal.source_system,
            object_id=terminal.object_id,
            revision=terminal.revision,
            operation=terminal.operation,
            observed_at=target_at.isoformat(),
            effective_at=target_at.isoformat(),
            truth_event_ids=terminal.truth_event_ids,
            payload=payload,
            classification=terminal.classification,
        )
    return [replacements.get(action.action_id, action) for action in actions]


def apply_observation_realism(actions: list[SourceAction], policy: ObservationRealismPolicy, seed: int = 42) -> tuple[list[SourceAction], list[ObservationMutation]]:
    """Apply deterministic observation-only mutations and return their ledger."""
    actions = _stretch_git_terminal_lifecycles(actions, policy, seed)
    transformed: list[SourceAction] = []
    ledger: list[ObservationMutation] = []
    current: dict[tuple[str, str], SourceAction] = {}
    for original in sorted(actions, key=lambda item: (item.observed_at, item.action_id)):
        key = (original.source_system, original.object_id)
        if original.operation == "redeliver" and key in current:
            payload = current[key].payload
            mutation_type = "redelivery_rebound"
        else:
            payload, mutation_type = _transform_payload(original, policy, seed)
        result = SourceAction(source_system=original.source_system, object_id=original.object_id, revision=original.revision, operation=original.operation, observed_at=original.observed_at, effective_at=original.effective_at, truth_event_ids=original.truth_event_ids, payload=payload, classification=original.classification)
        transformed.append(result)
        if original.payload_sha256 != result.payload_sha256:
            ledger.append(ObservationMutation(action_id=result.action_id, mutation_type=mutation_type, source_system=result.source_system, object_id=result.object_id, revision=result.revision, policy_version=policy.version, deterministic_seed=seed, original_hash=original.payload_sha256, result_hash=result.payload_sha256, truth_event_ids=result.truth_event_ids))
        if original.operation != "redeliver":
            current[key] = result

    additions = _new_slack_actions(transformed, policy, seed) + _routine_git_actions(transformed, policy, seed)
    for action in additions:
        transformed.append(action)
        ledger.append(ObservationMutation(action_id=action.action_id, mutation_type="routine_thread" if action.source_system == "slack" else "routine_git_lifecycle", source_system=action.source_system, object_id=action.object_id, revision=action.revision, policy_version=policy.version, deterministic_seed=seed, original_hash="", result_hash=action.payload_sha256, truth_event_ids=action.truth_event_ids))
    for action, mutation_type, original_hash in _slack_lifecycle_actions(
        transformed, policy, seed
    ):
        transformed.append(action)
        ledger.append(
            ObservationMutation(
                action_id=action.action_id,
                mutation_type=mutation_type,
                source_system=action.source_system,
                object_id=action.object_id,
                revision=action.revision,
                policy_version=policy.version,
                deterministic_seed=seed,
                original_hash=original_hash,
                result_hash=action.payload_sha256,
                truth_event_ids=action.truth_event_ids,
            )
        )
    transformed.sort(key=lambda item: (item.observed_at, item.action_id))
    ledger.sort(key=lambda item: (item.source_system, item.object_id, item.revision, item.action_id))
    return transformed, ledger
