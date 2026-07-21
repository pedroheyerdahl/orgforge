"""Deterministic cross-source temporal knowledge-error scenarios."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
from typing import Any

from source_actions import SourceAction


SCENARIO_TYPES = (
    "stale_document",
    "superseded_owner",
    "provisional_as_final",
    "delayed_correction",
    "partial_correction",
    "unresolved_conflict",
)

_TYPE_COUNTS = (3, 4, 5, 3, 4, 5)
_SOURCE_COMBINATIONS = (
    ("confluence", "slack"),
    ("jira", "slack", "email"),
    ("git", "jira"),
    ("zendesk", "email", "slack"),
    ("confluence", "git", "jira"),
    ("email", "zendesk"),
    ("slack", "git", "confluence", "jira"),
    ("zendesk", "jira", "email"),
    ("git", "slack", "email"),
    ("confluence", "zendesk", "slack"),
    ("jira", "email", "git", "zendesk"),
    ("slack", "confluence", "email"),
)
_DURATIONS = (2, 4, 7, 11, 16, 22, 28)
_SCOPES = (
    "mobile retry queue",
    "gateway timeout",
    "renewal handoff",
    "device export",
    "fallback routing",
    "support escalation",
    "release ownership",
    "client sync window",
)


def _slack_ts(value: datetime) -> str:
    return f"{value.timestamp():.6f}"


def _action_key(action: SourceAction) -> tuple[str, str, int, str]:
    return (
        action.source_system,
        action.object_id,
        action.revision,
        action.operation,
    )


def _payload(
    source: str,
    object_id: str,
    when: datetime,
    scope: str,
    scenario_type: str,
    evidence_index: int,
    *,
    revision: int = 1,
    correction: bool = False,
) -> dict[str, Any]:
    stance = (
        "The current record does not establish which environment produced the result",
        "The owner named in the earlier handoff has not confirmed the adjacent client",
        "The latest observation covers the primary path but leaves the fallback open",
        "The timestamp on the available export predates the change discussed elsewhere",
        "The operational state and the written note disagree on a material detail",
        "The evidence is useful for triage but is not sufficient to call the decision final",
    )[(evidence_index + len(scope)) % 6]
    if correction:
        stance = (
            f"Follow-up evidence narrows the {scope} discrepancy, but preserves the older observation in history. "
            "The primary path is now confirmed; any client or fallback not named here remains unresolved"
        )
    prose = (
        f"{stance}. This observation concerns {scope}. "
        "Review the source timestamp and scope before using it as the current organizational answer."
    )

    if source == "slack":
        return {
            "type": "message",
            "channel_id": "CKNOWLEDGE",
            "channel_name": "project-ops",
            "user": ("UMIKI", "UHANNA", "UTOM", "UJENNA")[evidence_index % 4],
            "user_profile": {
                "display_name": ("Miki", "Hanna", "Tom", "Jenna")[evidence_index % 4]
            },
            "text": prose,
            "ts": _slack_ts(when if revision == 1 else when - timedelta(days=1)),
            "client_msg_id": object_id,
            **({"edited": {"ts": _slack_ts(when)}} if revision > 1 else {}),
        }
    if source == "confluence":
        return {
            "page_id": object_id,
            "status": "current",
            "version": revision,
            "title": f"{scope.title()} operating notes",
            "body": prose,
        }
    if source == "jira":
        return {
            "id": object_id,
            "title": f"Confirm {scope} ({object_id[-6:]})",
            "description": prose,
            "status": "In Progress" if revision == 1 else "Needs Verification",
            "created_at": (when - timedelta(days=max(0, revision - 1))).isoformat(),
            "updated_at": when.isoformat(),
            "comments": [] if revision == 1 else [{"author": "Miki", "created": when.isoformat(), "text": prose}],
        }
    if source == "email":
        message_id = f"<{object_id.lower()}@apexathletics.io>"
        return {
            "message_id": message_id,
            "subject": f"Re: {scope}",
            "raw_eml": (
                "From: hanna@apexathletics.io\n"
                "To: ops@apexathletics.io\n"
                f"Date: {when.strftime('%a, %d %b %Y %H:%M:%S +0000')}\n"
                f"Message-ID: {message_id}\n"
                f"Subject: Re: {scope}\n"
                "X-Data-Classification: synthetic_non_confidential\n\n"
                f"{prose}\n"
            ),
        }
    if source == "git":
        return {
            "pr_id": object_id,
            "title": f"Verify {scope} evidence ({object_id[-6:]})",
            "body": prose,
            "status": "open",
            "author": "Deepa",
            "created_at": (when - timedelta(days=max(0, revision - 1))).isoformat(),
            "updated_at": when.isoformat(),
            "comments": [] if revision == 1 else [{"author": "reviewer", "timestamp": when.isoformat(), "text": prose}],
        }
    if source == "zendesk":
        return {
            "id": object_id,
            "subject": f"Question about {scope}",
            "status": "open",
            "created_at": (when - timedelta(days=max(0, revision - 1))).isoformat(),
            "updated_at": when.isoformat(),
            "comments": [{"author": "requester", "timestamp": when.isoformat(), "text": prose}],
        }
    raise ValueError(f"unsupported knowledge scenario source: {source}")


def apply_knowledge_scenarios(
    actions: list[SourceAction],
    seed: int = 42,
) -> tuple[list[SourceAction], list[dict[str, Any]]]:
    """Add varied source-native evidence arcs and provenance-only labels."""

    if actions:
        start = min(
            datetime.fromisoformat(action.observed_at.replace("Z", "+00:00"))
            for action in actions
        ).replace(hour=9, minute=0, second=0, microsecond=0)
    else:
        start = datetime(2026, 1, 1, 9, tzinfo=timezone.utc)

    output = list(actions)
    scenarios: list[dict[str, Any]] = []
    scenario_index = 0
    for type_index, scenario_type in enumerate(SCENARIO_TYPES):
        for occurrence in range(_TYPE_COUNTS[type_index]):
            scenario_id = f"KNOW-{scenario_type.upper().replace('_', '-')}-{occurrence + 1:02d}"
            event_id = "EVT-" + hashlib.sha256(
                f"{seed}|temporal-evidence|{scenario_index}".encode("utf-8")
            ).hexdigest()[:16]
            base = start + timedelta(days=4 + scenario_index * 5)
            duration = _DURATIONS[(scenario_index * 3 + occurrence) % len(_DURATIONS)]
            evidence_count = 3 + (scenario_index % 5)
            day_count = 2 + (scenario_index % 5)
            day_offsets = [
                round(slot * duration / max(1, day_count - 1))
                for slot in range(day_count)
            ]
            combination = _SOURCE_COMBINATIONS[scenario_index % len(_SOURCE_COMBINATIONS)]
            scope = _SCOPES[(scenario_index + seed) % len(_SCOPES)]
            unresolved = scenario_type == "unresolved_conflict" or scenario_index % 9 == 0
            evidence: list[SourceAction] = []
            first_source = combination[0]
            first_object = f"KNOW-{first_source.upper()}-{scenario_index:03d}-00"

            for evidence_index in range(evidence_count):
                is_last = evidence_index == evidence_count - 1
                correction = is_last and not unresolved
                source = first_source if correction else combination[evidence_index % len(combination)]
                object_id = first_object if correction else f"KNOW-{source.upper()}-{scenario_index:03d}-{evidence_index:02d}"
                revision = 2 if correction else 1
                slot = min(day_count - 1, round(evidence_index * (day_count - 1) / max(1, evidence_count - 1)))
                when = base + timedelta(days=day_offsets[slot], hours=(evidence_index * 2) % 7, minutes=occurrence * 3)
                action = SourceAction(
                    source_system=source,
                    object_id=object_id,
                    revision=revision,
                    operation="update" if correction else "create",
                    observed_at=when.isoformat(),
                    effective_at=when.isoformat(),
                    truth_event_ids=(event_id,),
                    payload=_payload(
                        source,
                        object_id,
                        when,
                        scope,
                        scenario_type,
                        evidence_index,
                        revision=revision,
                        correction=correction,
                    ),
                )
                evidence.append(action)

            output.extend(evidence)
            observed_days = sorted({action.observed_at[:10] for action in evidence})
            expected = {
                day: (
                    "conflict_remains_unresolved"
                    if unresolved and day == observed_days[-1]
                    else "scoped_or_misleading_evidence_visible"
                    if day != observed_days[0]
                    else "initial_observation_only"
                )
                for day in observed_days
            }
            correction_action = evidence[-1].action_id if not unresolved else None
            scenarios.append(
                {
                    "scenario_id": scenario_id,
                    "scenario_type": scenario_type,
                    "review_status": "pending_human_review",
                    "resolution_state": "unresolved" if unresolved else "partially_corrected",
                    "source_systems": list(dict.fromkeys(action.source_system for action in evidence)),
                    "observed_days": observed_days,
                    "duration_days": duration,
                    "evidence_action_ids": [action.action_id for action in evidence],
                    "correction_action_id": correction_action,
                    "_evidence_keys": [list(_action_key(action)) for action in evidence],
                    "_correction_key": (
                        list(_action_key(evidence[-1])) if not unresolved else None
                    ),
                    "shared_or_misleading_evidence": scenario_index % 3 != 1,
                    "expected_state_by_day": expected,
                }
            )
            scenario_index += 1

    output.sort(key=lambda action: (action.observed_at, action.action_id))
    return output, scenarios


def finalize_knowledge_scenarios(
    scenarios: list[dict[str, Any]],
    actions: list[SourceAction],
) -> list[dict[str, Any]]:
    """Resolve scenario evidence against final action identities and metadata."""

    final_by_key = {_action_key(action): action for action in actions}
    finalized: list[dict[str, Any]] = []
    for original in scenarios:
        scenario = dict(original)
        evidence_keys = [tuple(value) for value in scenario.pop("_evidence_keys", [])]
        if not evidence_keys:
            raise ValueError(f"scenario {scenario.get('scenario_id')} has no stable evidence keys")
        try:
            evidence = [final_by_key[key] for key in evidence_keys]
        except KeyError as exc:
            raise ValueError(
                f"scenario {scenario.get('scenario_id')} evidence key missing after transforms: {exc.args[0]}"
            ) from exc
        correction_key_value = scenario.pop("_correction_key", None)
        correction = (
            final_by_key.get(tuple(correction_key_value))
            if correction_key_value is not None
            else None
        )
        if correction_key_value is not None and correction is None:
            raise ValueError(
                f"scenario {scenario.get('scenario_id')} correction key missing after transforms"
            )
        observed_days = sorted({action.observed_at[:10] for action in evidence})
        unresolved = scenario.get("resolution_state") == "unresolved"
        scenario["evidence_action_ids"] = [action.action_id for action in evidence]
        scenario["correction_action_id"] = correction.action_id if correction else None
        scenario["source_systems"] = list(
            dict.fromkeys(action.source_system for action in evidence)
        )
        scenario["observed_days"] = observed_days
        scenario["duration_days"] = (
            datetime.fromisoformat(observed_days[-1]).date()
            - datetime.fromisoformat(observed_days[0]).date()
        ).days
        scenario["expected_state_by_day"] = {
            day: (
                "conflict_remains_unresolved"
                if unresolved and day == observed_days[-1]
                else "scoped_or_misleading_evidence_visible"
                if day != observed_days[0]
                else "initial_observation_only"
            )
            for day in observed_days
        }
        finalized.append(scenario)
    return finalized
