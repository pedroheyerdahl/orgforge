"""Package OrgForge observations as a replayable Clearweave source corpus."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
from typing import Any

from knowledge_scenarios import apply_knowledge_scenarios, finalize_knowledge_scenarios
from observation_realism import ObservationRealismPolicy, apply_observation_realism
from realism_scorecard import build_realism_scorecard
from source_actions import SourceAction, replay_actions, write_actions
from source_locators import rebase_source_locators
from source_realism import (
    RealismPolicy,
    adapt_export,
    augment_actions_to_span,
    normalize_email_observations,
    normalize_observations_to_window,
)
from source_renderers import (
    json_text,
    render_inbox_object,
    render_raw_object,
    render_slack_channel,
    render_slack_markdown,
)


CLASSIFICATION = "synthetic_non_confidential"


def _safe_name(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._@+-]+", "-", value).strip("-.")
    return clean[:160] or "artifact"


def _write_text(path: Path, content: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest_entry(
    output_dir: Path,
    path: Path,
    representation: str,
    state: dict[str, Any],
    source_system: str | None = None,
    object_id: str | None = None,
) -> dict[str, Any]:
    payload = state["payload"]
    return {
        "classification": CLASSIFICATION,
        "representation": representation,
        "path": path.relative_to(output_dir).as_posix(),
        "source_system": source_system or state["source_system"],
        "object_id": object_id or state["object_id"],
        "revision": state["revision"],
        "operation": "delete" if state["deleted"] else "update" if state["revision"] > 1 else "create",
        "observed_at": state["last_observed_at"],
        "effective_at": state["effective_at"],
        "truth_event_ids": state["truth_event_ids"],
        "source_path": payload.get("source_path", ""),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _write_deliveries(output_dir: Path, actions: list[SourceAction]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for action in actions:
        delivery_day = action.observed_at[:10]
        relative = Path("deliveries") / delivery_day / action.source_system / f"{action.action_id}.json"
        path = output_dir / relative
        digest = _write_text(path, json.dumps(action.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")
        entries.append(
            {
                "action_id": action.action_id,
                "delivery_day": delivery_day,
                "source_system": action.source_system,
                "object_id": action.object_id,
                "revision": action.revision,
                "operation": action.operation,
                "path": relative.as_posix(),
                "payload_sha256": action.payload_sha256,
                "sha256": digest,
            }
        )
    return entries


def _write_slack(
    output_dir: Path,
    slack_states: list[dict[str, Any]],
    manifest_entries: list[dict[str, Any]],
) -> None:
    by_channel: dict[str, list[dict[str, Any]]] = {}
    for state in slack_states:
        channel = str(state["payload"].get("channel_name") or "unknown-channel")
        by_channel.setdefault(channel, []).append(state)

    for channel, states in sorted(by_channel.items()):
        envelope = render_slack_channel(channel, states)
        raw_path = output_dir / "raw" / "slack" / "channels" / f"{_safe_name(channel)}.json"
        inbox_path = output_dir / "inbox" / "slack" / "channels" / f"{_safe_name(channel)}.md"
        _write_text(raw_path, json_text(envelope))
        _write_text(inbox_path, render_slack_markdown(envelope))
        last = max(states, key=lambda item: (item["last_observed_at"], item["last_action_id"]))
        merged = {
            **last,
            "revision": max(item["revision"] for item in states),
            "deleted": False,
            "truth_event_ids": sorted(
                {event_id for item in states for event_id in item["truth_event_ids"]}
            ),
            "payload": {
                "channel_name": channel,
                "source_path": "slack/channels",
            },
        }
        channel_id = f"slack-channel:{channel}"
        manifest_entries.append(
            _manifest_entry(output_dir, raw_path, "raw", merged, "slack", channel_id)
        )
        manifest_entries.append(
            _manifest_entry(output_dir, inbox_path, "inbox", merged, "slack", channel_id)
        )


def _write_final_objects(
    output_dir: Path,
    state: dict[tuple[str, str], dict[str, Any]],
    manifest_entries: list[dict[str, Any]],
    *,
    datadog_inbox_limit: int | None = None,
    seed: int = 42,
) -> None:
    slack_states = [value for (system, _), value in state.items() if system == "slack"]
    _write_slack(output_dir, slack_states, manifest_entries)

    datadog_inbox_ids: set[str] | None = None
    if datadog_inbox_limit is not None:
        candidates = [
            object_id
            for (system, object_id), object_state in state.items()
            if system == "datadog" and not object_state["deleted"]
        ]
        candidates.sort(
            key=lambda object_id: hashlib.sha256(
                f"semantic-inbox|{seed}|{object_id}".encode("utf-8")
            ).hexdigest()
        )
        datadog_inbox_ids = set(candidates[: max(0, datadog_inbox_limit)])

    for (system, object_id), object_state in sorted(state.items()):
        if system == "slack":
            continue
        suffix, raw_content = render_raw_object(system, object_state)
        raw_path = output_dir / "raw" / system / f"{_safe_name(object_id)}{suffix}"
        _write_text(raw_path, raw_content)
        manifest_entries.append(_manifest_entry(output_dir, raw_path, "raw", object_state))

        if object_state["deleted"]:
            continue
        if system == "datadog" and datadog_inbox_ids is not None and object_id not in datadog_inbox_ids:
            continue
        inbox_suffix, inbox_content = render_inbox_object(system, object_state)
        inbox_path = output_dir / "inbox" / system / f"{_safe_name(object_id)}{inbox_suffix}"
        _write_text(inbox_path, inbox_content)
        manifest_entries.append(_manifest_entry(output_dir, inbox_path, "inbox", object_state))


def _copy_provenance(export_dir: Path, output_dir: Path) -> None:
    provenance = output_dir / "provenance"
    events = export_dir / "simulation_events.jsonl"
    if events.exists():
        shutil.copyfile(events, provenance / "events.jsonl")
    else:
        (provenance / "events.jsonl").write_text("", encoding="utf-8")
    runtime_log = export_dir / "simulation.log"
    if runtime_log.exists():
        shutil.copyfile(runtime_log, provenance / "simulation.log")
    for filename in ("run_status.json", "llm_resilience.jsonl", "resume_checkpoint.json"):
        source = export_dir / "provenance" / filename
        if source.exists():
            shutil.copyfile(source, provenance / filename)


def _write_gold(
    output_dir: Path,
    manifest_entries: list[dict[str, Any]],
    knowledge_scenarios: list[dict[str, Any]] | None = None,
) -> None:
    gold = output_dir / "gold"
    gold.mkdir(parents=True, exist_ok=True)
    candidates = [
        {
            "classification": CLASSIFICATION,
            "source_system": entry["source_system"],
            "object_id": entry["object_id"],
            "inbox_file": entry["path"],
            "labels": None,
            "review_status": "unreviewed",
        }
        for entry in manifest_entries
        if entry["representation"] == "inbox"
    ][:25]
    (gold / "candidates.jsonl").write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in candidates),
        encoding="utf-8",
    )
    (gold / "temporal_candidates.jsonl").write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n"
            for item in (knowledge_scenarios or [])
        ),
        encoding="utf-8",
    )
    (gold / "README.md").write_text(
        "# Gold slice\n\n"
        "`candidates.jsonl` contains unlabeled static-search candidates. "
        "`temporal_candidates.jsonl` contains generated expected state-by-day "
        "labels for deliberate knowledge-error scenarios. Those temporal labels "
        "remain `pending_human_review` until a reviewer freezes the evaluation slice.\n",
        encoding="utf-8",
    )


def export_corpus(
    export_dir: Path,
    output_dir: Path,
    seed: int = 42,
    target_days: int | None = None,
    target_start: str | None = None,
    observation_realism: bool = False,
    datadog_inbox_limit: int | None = None,
) -> dict[str, Any]:
    export_dir = export_dir.resolve()
    output_dir = output_dir.resolve()
    for name in ("raw", "deliveries", "inbox", "provenance", "gold"):
        (output_dir / name).mkdir(parents=True, exist_ok=True)

    policy_path = Path(__file__).resolve().parents[1] / "config" / "source_realism.yaml"
    policy = RealismPolicy.load(policy_path)
    if observation_realism and datadog_inbox_limit is None:
        datadog_inbox_limit = policy.semantic_inbox_datadog_limit
    actions = adapt_export(export_dir, policy=policy, seed=seed)
    knowledge_scenarios: list[dict[str, Any]] = []
    if target_days is not None:
        start_at = (
            datetime.fromisoformat(target_start).replace(tzinfo=timezone.utc)
            if target_start
            else None
        )
        if start_at is not None:
            actions = normalize_observations_to_window(actions, start_at, target_days)
        actions = augment_actions_to_span(
            actions,
            target_days=target_days,
            seed=seed,
            start_at=start_at,
        )
        if start_at is not None:
            actions = normalize_observations_to_window(actions, start_at, target_days)
            actions = rebase_source_locators(actions)
    if observation_realism and target_days is not None and target_days >= 160:
        actions, knowledge_scenarios = apply_knowledge_scenarios(actions, seed=seed)
    actions = normalize_email_observations(actions, seed=seed)
    realism_policy = None
    realism_ledger = []
    if observation_realism:
        realism_policy = ObservationRealismPolicy.load(policy_path)
        actions, realism_ledger = apply_observation_realism(
            actions,
            realism_policy,
            seed=seed,
        )
    if knowledge_scenarios:
        knowledge_scenarios = finalize_knowledge_scenarios(
            knowledge_scenarios, actions
        )
    state = replay_actions(actions)
    write_actions(output_dir / "provenance" / "source_actions.jsonl", actions)
    (output_dir / "provenance" / "knowledge_scenarios.jsonl").write_text(
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n"
            for item in knowledge_scenarios
        ),
        encoding="utf-8",
    )
    if observation_realism:
        (output_dir / "provenance" / "realism_ledger.jsonl").write_text(
            "".join(
                json.dumps(entry.to_dict(), ensure_ascii=False, sort_keys=True) + "\n"
                for entry in realism_ledger
            ),
            encoding="utf-8",
        )
    delivery_entries = _write_deliveries(output_dir, actions)

    manifest_entries: list[dict[str, Any]] = []
    _write_final_objects(
        output_dir,
        state,
        manifest_entries,
        datadog_inbox_limit=datadog_inbox_limit if observation_realism else None,
        seed=seed,
    )
    _copy_provenance(export_dir, output_dir)

    if observation_realism and realism_policy is not None:
        inbox_counts = Counter(
            entry["source_system"]
            for entry in manifest_entries
            if entry["representation"] == "inbox"
        )
        (output_dir / "provenance" / "realism_scorecard.json").write_text(
            json.dumps(
                build_realism_scorecard(
                    actions,
                    schema_version=(
                        4
                        if realism_policy.version >= 5
                        else 3
                        if realism_policy.version >= 4
                        else 2
                        if realism_policy.version >= 3
                        else 1
                    ),
                    inbox_counts=dict(inbox_counts),
                    window_start=target_start,
                    window_end=(
                        (
                            datetime.fromisoformat(target_start).date()
                            + timedelta(days=target_days - 1)
                        ).isoformat()
                        if target_days is not None and target_start
                        else None
                    ),
                    knowledge_scenarios=knowledge_scenarios,
                ),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    manifest = {
        "corpus_id": f"orgforge-clearweave-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "classification": CLASSIFICATION,
        "source_simulation_export": export_dir.name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "target_days": target_days,
        "target_start": target_start,
        "target_end": (
            (
                datetime.fromisoformat(target_start).date()
                + timedelta(days=target_days - 1)
            ).isoformat()
            if target_days is not None and target_start
            else None
        ),
        "layout": ["raw", "deliveries", "inbox", "provenance", "gold"],
        "entries": manifest_entries,
        "deliveries": delivery_entries,
    }
    if observation_realism and realism_policy is not None:
        manifest["realism_policy_version"] = realism_policy.version
        manifest["realism_ledger_entries"] = len(realism_ledger)
        manifest["inbox_profile"] = "semantic"
        manifest["datadog_inbox_limit"] = datadog_inbox_limit
        manifest["knowledge_scenarios"] = len(knowledge_scenarios)
    (output_dir / "provenance" / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_gold(output_dir, manifest_entries, knowledge_scenarios)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--target-days", type=int)
    parser.add_argument("--target-start")
    parser.add_argument("--observation-realism", action="store_true")
    parser.add_argument("--datadog-inbox-limit", type=int)
    args = parser.parse_args()
    manifest = export_corpus(
        args.export_dir,
        args.output_dir,
        seed=args.seed,
        target_days=args.target_days,
        target_start=args.target_start,
        observation_realism=args.observation_realism,
        datadog_inbox_limit=args.datadog_inbox_limit,
    )
    print(
        f"Exported {len(manifest['entries'])} raw/inbox artifacts and "
        f"{len(manifest['deliveries'])} delivery actions to {args.output_dir}"
    )


if __name__ == "__main__":
    main()
