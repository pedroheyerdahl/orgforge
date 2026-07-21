"""Validate a packaged Clearweave corpus before a paid calibration run."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, time, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from source_actions import CLASSIFICATION, read_actions, replay_actions
from native_timestamps import iter_native_timestamps
from source_locators import iter_locator_dates
from source_renderers import SOURCE_INTERNAL_KEYS
from source_realism import messiness_features
from realism_scorecard import build_realism_scorecard, validate_realism_scorecard


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    details: str
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "required": self.required,
            "details": self.details,
        }


@dataclass(frozen=True)
class ValidationReport:
    corpus_dir: Path
    checks: dict[str, CheckResult]

    @property
    def ok(self) -> bool:
        return all(check.passed for check in self.checks.values() if check.required)

    @property
    def failed(self) -> list[str]:
        return [name for name, check in self.checks.items() if check.required and not check.passed]

    def to_dict(self) -> dict[str, Any]:
        return {
            "corpus_dir": str(self.corpus_dir),
            "ok": self.ok,
            "failed": self.failed,
            "checks": {name: check.to_dict() for name, check in self.checks.items()},
        }


def _result(name: str, errors: list[str], success: str, required: bool = True) -> CheckResult:
    return CheckResult(name, not errors, "; ".join(errors) if errors else success, required)


def _load_manifest(corpus_dir: Path) -> dict[str, Any]:
    return json.loads((corpus_dir / "provenance" / "manifest.json").read_text(encoding="utf-8"))


def _check_utf8(corpus_dir: Path) -> CheckResult:
    errors = []
    count = 0
    for path in corpus_dir.rglob("*"):
        if not path.is_file():
            continue
        count += 1
        try:
            path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"not UTF-8: {path.relative_to(corpus_dir)}")
    return _result("utf8", errors, f"{count} files decode as UTF-8")


def _check_privacy(corpus_dir: Path, manifest: dict[str, Any]) -> CheckResult:
    errors = []
    forbidden = (
        "Downloads/sources",
        "xoxp-",
        "OPENAI_API_KEY=",
    )
    if manifest.get("classification") != CLASSIFICATION:
        errors.append("manifest classification is not synthetic_non_confidential")
    for path in corpus_dir.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for fragment in forbidden:
            if fragment in text:
                errors.append(f"forbidden private/secret marker in {path.relative_to(corpus_dir)}")
    return _result("privacy", errors, "synthetic classification and private-path guard passed")


def _check_identity_replay(corpus_dir: Path) -> tuple[CheckResult, list, dict]:
    errors = []
    actions = []
    state = {}
    try:
        actions = read_actions(corpus_dir / "provenance" / "source_actions.jsonl")
        ids = [action.action_id for action in actions]
        if len(ids) != len(set(ids)):
            errors.append("duplicate action IDs")
        state = replay_actions(actions)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(str(exc))
    return _result(
        "identity_replay",
        errors,
        f"replayed {len(actions)} actions into {len(state)} objects",
    ), actions, state


def _check_knowledge_reference_integrity(
    corpus_dir: Path,
    manifest: dict[str, Any],
    actions: list,
) -> CheckResult:
    required = int(manifest.get("realism_policy_version", 0) or 0) >= 5
    if not required:
        return CheckResult(
            "knowledge_reference_integrity",
            True,
            "not required for pre-v5 corpus",
            required=False,
        )
    errors: list[str] = []
    path = corpus_dir / "provenance" / "knowledge_scenarios.jsonl"
    if not path.exists():
        return _result(
            "knowledge_reference_integrity",
            ["knowledge_scenarios.jsonl missing"],
            "",
        )
    by_id = {action.action_id: action for action in actions}
    scenarios: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            scenarios.append(json.loads(line))
        except json.JSONDecodeError as exc:
            errors.append(f"invalid scenario line {number}: {exc}")
    gold_path = corpus_dir / "gold" / "temporal_candidates.jsonl"
    if not gold_path.exists():
        errors.append("gold/temporal_candidates.jsonl missing")
    else:
        try:
            gold_scenarios = [
                json.loads(line)
                for line in gold_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            if gold_scenarios != scenarios:
                errors.append("gold temporal candidates differ from provenance scenarios")
        except json.JSONDecodeError as exc:
            errors.append(f"invalid gold temporal candidates: {exc}")
    for scenario in scenarios:
        scenario_id = str(scenario.get("scenario_id", "unknown"))
        evidence_ids = [str(value) for value in scenario.get("evidence_action_ids", [])]
        missing = [action_id for action_id in evidence_ids if action_id not in by_id]
        for action_id in missing:
            errors.append(f"{scenario_id} missing evidence action {action_id}")
        evidence = [by_id[action_id] for action_id in evidence_ids if action_id in by_id]
        actual_sources = list(dict.fromkeys(action.source_system for action in evidence))
        if not missing and scenario.get("source_systems") != actual_sources:
            errors.append(f"{scenario_id} source_systems do not match evidence actions")
        actual_days = sorted({action.observed_at[:10] for action in evidence})
        if not missing and scenario.get("observed_days") != actual_days:
            errors.append(f"{scenario_id} observed_days do not match evidence actions")
        correction_id = scenario.get("correction_action_id")
        unresolved = scenario.get("resolution_state") == "unresolved"
        if correction_id is not None and correction_id not in by_id:
            errors.append(f"{scenario_id} missing correction action {correction_id}")
        if correction_id is not None and correction_id not in evidence_ids:
            errors.append(f"{scenario_id} correction action is not included in evidence")
        if unresolved and correction_id is not None:
            errors.append(f"{scenario_id} unresolved scenario declares a correction action")
        if not unresolved and correction_id is None:
            errors.append(f"{scenario_id} corrected scenario lacks a correction action")
    return _result(
        "knowledge_reference_integrity",
        errors,
        f"resolved {sum(len(item.get('evidence_action_ids', [])) for item in scenarios)} evidence references across {len(scenarios)} scenarios",
    )


def _check_temporal(
    corpus_dir: Path,
    actions: list,
    manifest: dict[str, Any],
) -> CheckResult:
    errors = []
    observed = [action.observed_at for action in actions]
    if observed != sorted(observed):
        errors.append("source actions are not ordered by observed_at")
    slack_dir = corpus_dir / "raw" / "slack" / "channels"
    for path in slack_dir.glob("*.json") if slack_dir.exists() else []:
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"invalid Slack JSON {path.name}: {exc}")
            continue
        roots = {str(message.get("ts")) for message in envelope.get("messages", [])}
        for root_ts, replies in envelope.get("threads", {}).items():
            if root_ts not in roots:
                errors.append(f"orphan Slack thread {root_ts} in {path.name}")
            for reply in replies:
                if str(reply.get("thread_ts")) != str(root_ts):
                    errors.append(f"reply has mismatched parent in {path.name}")
                try:
                    if float(reply.get("ts", 0)) < float(root_ts):
                        errors.append(f"reply precedes parent in {path.name}")
                except (TypeError, ValueError):
                    errors.append(f"invalid Slack timestamp in {path.name}")

    if int(manifest.get("realism_policy_version", 0) or 0) >= 4:
        start_value = manifest.get("target_start")
        end_value = manifest.get("target_end")
        window_start = (
            datetime.combine(datetime.fromisoformat(str(start_value)).date(), time.min, tzinfo=timezone.utc)
            if start_value
            else None
        )
        window_end = (
            datetime.combine(datetime.fromisoformat(str(end_value)).date(), time.max, tzinfo=timezone.utc)
            if end_value
            else None
        )
        terminal_states = {
            "git": {"merged", "closed"},
            "jira": {"done", "closed", "resolved"},
            "zendesk": {"closed", "solved"},
        }
        native_errors: list[str] = []
        create_dates: dict[tuple[str, str], Any] = {}
        for action in actions:
            key = (action.source_system, action.object_id)
            observed_date = datetime.fromisoformat(
                action.observed_at.replace("Z", "+00:00")
            ).date()
            if action.operation == "create" or key not in create_dates:
                create_dates.setdefault(key, observed_date)
        for action in actions:
            observed_at = datetime.fromisoformat(action.observed_at.replace("Z", "+00:00"))
            key = (action.source_system, action.object_id)
            for native in iter_native_timestamps(action.source_system, action.payload):
                location = ".".join(str(part) for part in native.path)
                if native.kind == "historical" and native.value > observed_at:
                    native_errors.append(
                        f"future native timestamp {action.source_system}/{action.object_id}:{location}"
                    )
                if (
                    window_start is not None
                    and window_end is not None
                    and not window_start <= native.value <= window_end
                ):
                    native_errors.append(
                        f"native timestamp outside declared window {action.source_system}/{action.object_id}:{location}"
                    )
            for locator in iter_locator_dates(action):
                location = ".".join(str(part) for part in locator.path)
                if locator.value.date() != create_dates[key]:
                    native_errors.append(
                        f"locator date mismatch {action.source_system}/{action.object_id}:{location}"
                    )
                if (
                    window_start is not None
                    and window_end is not None
                    and not window_start <= locator.value <= window_end
                ):
                    native_errors.append(
                        f"locator date outside declared window {action.source_system}/{action.object_id}:{location}"
                    )
            status = str(action.payload.get("status", "")).casefold()
            if (
                action.operation == "create"
                and status in terminal_states.get(action.source_system, set())
            ):
                native_errors.append(
                    f"terminal state in create {action.source_system}/{action.object_id}:{status}"
                )
            if len(native_errors) >= 100:
                native_errors.append("additional native temporal errors omitted")
                break
        errors.extend(native_errors)
    return _result(
        "temporal_integrity",
        errors,
        "action order, native timestamps, declared window, and Slack parent timing are valid",
    )


def _check_native_shape(corpus_dir: Path) -> CheckResult:
    errors = []
    slack_dir = corpus_dir / "raw" / "slack" / "channels"
    slack_files = list(slack_dir.glob("*.json")) if slack_dir.exists() else []
    if not slack_files:
        errors.append("missing Slack channel export")
    for path in slack_files:
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"invalid Slack JSON {path.name}: {exc}")
            continue
        required = {"channel", "users", "messages", "threads", "state"}
        if set(envelope) != required:
            errors.append(f"Slack envelope keys differ in {path.name}")
    for path in (corpus_dir / "inbox").rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if "Export representation: JSON record rendered as source text" in text:
            errors.append(f"generic JSON wrapper remains in {path.relative_to(corpus_dir)}")
    email_files = list((corpus_dir / "inbox" / "email").glob("*.eml"))
    if not email_files or not all("Message-ID:" in path.read_text() for path in email_files):
        errors.append("email inbox does not preserve EML headers")
    return _result("native_shape", errors, "source-specific raw and inbox renderers detected")


def _check_source_visible_controls(
    corpus_dir: Path,
    manifest: dict[str, Any],
) -> CheckResult:
    required = int(manifest.get("realism_policy_version", 0) or 0) >= 4
    if not required:
        return CheckResult(
            "source_visible_controls",
            True,
            "not required for pre-v4 corpus",
            required=False,
        )
    errors: list[str] = []
    for root_name in ("raw", "inbox"):
        root = corpus_dir / root_name
        for path in root.rglob("*") if root.exists() else []:
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for key in SOURCE_INTERNAL_KEYS:
                patterns = (
                    f'"{key}"',
                    f"**{key.replace('_', ' ').title()}:**",
                    f"{key}=",
                )
                if any(pattern in text for pattern in patterns):
                    errors.append(
                        f"source-visible control {key} in {path.relative_to(corpus_dir)}"
                    )
                    break
            if len(errors) >= 100:
                errors.append("additional source-visible control errors omitted")
                break
        if len(errors) >= 100:
            break
    return _result(
        "source_visible_controls",
        errors,
        "raw and inbox artifacts contain no generator/evaluation controls",
        required=required,
    )


def _check_manifest_coverage(corpus_dir: Path, manifest: dict[str, Any]) -> CheckResult:
    errors = []
    entries = manifest.get("entries", [])
    declared = {str(entry.get("path")) for entry in entries}
    actual = {
        path.relative_to(corpus_dir).as_posix()
        for root in (corpus_dir / "raw", corpus_dir / "inbox")
        for path in root.rglob("*")
        if path.is_file()
    }
    uncovered = sorted(actual - declared)
    missing = sorted(declared - actual)
    if uncovered:
        errors.append(f"uncovered artifacts: {', '.join(uncovered[:5])}")
    if missing:
        errors.append(f"manifest paths missing on disk: {', '.join(missing[:5])}")
    for entry in entries:
        path = corpus_dir / str(entry.get("path"))
        if not path.exists():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != entry.get("sha256"):
            errors.append(f"checksum mismatch: {entry.get('path')}")
        if not entry.get("object_id") or int(entry.get("revision", 0)) < 1:
            errors.append(f"identity metadata missing: {entry.get('path')}")
    delivery_declared = {str(item.get("path")) for item in manifest.get("deliveries", [])}
    delivery_actual = {
        path.relative_to(corpus_dir).as_posix()
        for path in (corpus_dir / "deliveries").rglob("*.json")
    }
    if delivery_declared != delivery_actual:
        errors.append("delivery manifest coverage mismatch")
    return _result(
        "manifest_coverage",
        errors,
        f"manifest covers {len(actual)} raw/inbox artifacts and {len(delivery_actual)} deliveries",
    )


def _check_messiness(actions: list) -> CheckResult:
    features = messiness_features(actions)
    errors = [f"missing {name}" for name, count in features.items() if count < 1]
    return _result("messiness", errors, f"required features present: {json.dumps(features, sort_keys=True)}")


def _check_semantic_safety(actions: list) -> CheckResult:
    errors = []
    if any(action.classification != CLASSIFICATION for action in actions):
        errors.append("action classification mismatch")
    if any(action.payload.get("truth_mutated") for action in actions):
        errors.append("observation payload declares truth mutation")
    if not any(action.payload.get("supersedes") for action in actions):
        errors.append("correction/supersession observation missing")
    return _result("semantic_safety", errors, "observations preserve classification and explicit corrections")


def _check_realism(corpus_dir: Path, manifest: dict[str, Any], actions: list) -> CheckResult:
    version = int(manifest.get("realism_policy_version", 0) or 0)
    if version < 2:
        return CheckResult("realism", True, "not required for pre-v2 corpus", required=False)
    errors: list[str] = []
    scorecard_path = corpus_dir / "provenance" / "realism_scorecard.json"
    ledger_path = corpus_dir / "provenance" / "realism_ledger.jsonl"
    scorecard: dict[str, Any] = {}
    if not scorecard_path.exists():
        errors.append("realism_scorecard.json missing")
    else:
        try:
            scorecard = json.loads(scorecard_path.read_text(encoding="utf-8"))
            errors.extend(validate_realism_scorecard(scorecard))
            inbox_counts: dict[str, int] = {}
            inbox_root = corpus_dir / "inbox"
            if inbox_root.exists():
                for path in inbox_root.rglob("*"):
                    if not path.is_file():
                        continue
                    relative = path.relative_to(inbox_root)
                    if relative.parts:
                        source = relative.parts[0]
                        inbox_counts[source] = inbox_counts.get(source, 0) + 1
            knowledge_scenarios: list[dict[str, Any]] = []
            scenarios_path = corpus_dir / "provenance" / "knowledge_scenarios.jsonl"
            if scenarios_path.exists():
                knowledge_scenarios = [
                    json.loads(line)
                    for line in scenarios_path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
            rebuilt = build_realism_scorecard(
                actions,
                schema_version=int(scorecard.get("schema_version", 1)),
                inbox_counts=inbox_counts if int(scorecard.get("schema_version", 1)) >= 2 else None,
                window_start=manifest.get("target_start"),
                window_end=manifest.get("target_end"),
                knowledge_scenarios=knowledge_scenarios,
            )
            if scorecard != rebuilt:
                errors.append("realism scorecard does not match source actions")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"realism scorecard unreadable: {exc}")
    ledger_count = 0
    if not ledger_path.exists():
        errors.append("realism_ledger.jsonl missing")
    else:
        required_fields = {
            "action_id",
            "mutation_type",
            "source_system",
            "object_id",
            "policy_version",
            "deterministic_seed",
            "original_hash",
            "result_hash",
            "truth_event_ids",
        }
        for number, line in enumerate(ledger_path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            ledger_count += 1
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"invalid realism ledger line {number}: {exc}")
                continue
            missing = required_fields - set(entry)
            if missing:
                errors.append(f"realism ledger line {number} missing {sorted(missing)}")
            if int(entry.get("policy_version", 0) or 0) != version:
                errors.append(f"realism ledger line {number} policy version mismatch")
    expected_count = int(manifest.get("realism_ledger_entries", -1))
    if ledger_count != expected_count:
        errors.append(f"realism ledger count {ledger_count} differs from manifest {expected_count}")
    return _result(
        "realism",
        errors,
        f"policy v{version} scorecard passed with {ledger_count} attributed mutations",
    )


def _check_run_health(corpus_dir: Path, required: bool) -> CheckResult:
    if not required:
        return CheckResult("run_health", True, "skipped for no-cost fixture", required=False)
    errors = []
    path = corpus_dir / "provenance" / "run_status.json"
    if not path.exists():
        errors.append("run_status.json missing")
    else:
        status = json.loads(path.read_text(encoding="utf-8"))
        if status.get("status") != "completed":
            errors.append(f"run status is {status.get('status')!r}")
        unrecovered = int(
            status.get("unrecovered_llm_failures", status.get("unrecovered", 0)) or 0
        )
        if unrecovered != 0:
            errors.append(f"run has {unrecovered} unrecovered LLM failures")
    ledger = corpus_dir / "provenance" / "llm_resilience.jsonl"
    if ledger.exists():
        for line in ledger.read_text(encoding="utf-8").splitlines():
            if line.strip() and json.loads(line).get("outcome") == "unrecovered":
                errors.append("resilience ledger contains unrecovered outcome")
                break
    return _result("run_health", errors, "run completed with zero unrecovered failures")


def _usage_totals(log_text: str) -> tuple[int, int, int]:
    prompt_tokens = 0
    completion_tokens = 0
    records = 0
    for body in re.findall(r"OpenAI API usage:\s*\{([^{}]*)\}", log_text, flags=re.S):
        prompt = re.search(r"['\"]prompt_tokens['\"]\s*:\s*(\d+)", body)
        completion = re.search(r"['\"]completion_tokens['\"]\s*:\s*(\d+)", body)
        if not prompt or not completion:
            continue
        prompt_tokens += int(prompt.group(1))
        completion_tokens += int(completion.group(1))
        records += 1
    return prompt_tokens, completion_tokens, records


def _check_spend(corpus_dir: Path, required: bool, ceiling_usd: float = 25.0) -> CheckResult:
    path = corpus_dir / "provenance" / "simulation.log"
    if not path.exists():
        if required:
            return CheckResult("spend", False, "simulation.log missing; cannot verify spend", True)
        return CheckResult("spend", True, "skipped for no-cost fixture", False)
    prompt_tokens, completion_tokens, records = _usage_totals(
        path.read_text(encoding="utf-8", errors="replace")
    )
    if records == 0:
        if required:
            return CheckResult("spend", False, "no parseable OpenAI usage records", True)
        return CheckResult("spend", True, "no paid usage records in fixture", False)

    status_path = corpus_dir / "provenance" / "run_status.json"
    if required and status_path.exists():
        status = json.loads(status_path.read_text(encoding="utf-8"))
        if {
            "conservative_spend_usd",
            "spend_ceiling_usd",
        } <= status.keys():
            try:
                cost = float(status["conservative_spend_usd"])
                run_ceiling = float(status["spend_ceiling_usd"])
            except (TypeError, ValueError):
                return CheckResult(
                    "spend",
                    False,
                    "run_status.json contains invalid spend budget values",
                    True,
                )
            return CheckResult(
                "spend",
                cost <= run_ceiling,
                (
                    f"authoritative run ledger ${cost:.2f} from {records} usage records; "
                    f"ceiling ${run_ceiling:.2f}"
                ),
                True,
            )

    # Legacy packages lack a runtime budget ledger. Retain their deliberately
    # conservative all-Sol estimate and original $25 gate.
    cost = prompt_tokens * 5.0 / 1_000_000 + completion_tokens * 30.0 / 1_000_000
    passed = cost <= ceiling_usd
    details = (
        f"conservative all-fallback estimate ${cost:.2f} from {records} usage records "
        f"({prompt_tokens} input, {completion_tokens} output tokens); ceiling ${ceiling_usd:.2f}"
    )
    return CheckResult("spend", passed, details, required)


def validate_corpus(corpus_dir: Path, require_run_health: bool = False) -> ValidationReport:
    corpus_dir = corpus_dir.resolve()
    checks: dict[str, CheckResult] = {}
    try:
        manifest = _load_manifest(corpus_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        failure = CheckResult("manifest_coverage", False, f"manifest unreadable: {exc}")
        return ValidationReport(corpus_dir, {"manifest_coverage": failure})

    checks["utf8"] = _check_utf8(corpus_dir)
    checks["privacy"] = _check_privacy(corpus_dir, manifest)
    identity, actions, _state = _check_identity_replay(corpus_dir)
    checks["identity_replay"] = identity
    checks["knowledge_reference_integrity"] = _check_knowledge_reference_integrity(
        corpus_dir, manifest, actions
    )
    checks["temporal_integrity"] = _check_temporal(corpus_dir, actions, manifest)
    checks["native_shape"] = _check_native_shape(corpus_dir)
    checks["source_visible_controls"] = _check_source_visible_controls(
        corpus_dir, manifest
    )
    checks["manifest_coverage"] = _check_manifest_coverage(corpus_dir, manifest)
    checks["messiness"] = _check_messiness(actions)
    checks["semantic_safety"] = _check_semantic_safety(actions)
    checks["realism"] = _check_realism(corpus_dir, manifest, actions)
    checks["run_health"] = _check_run_health(corpus_dir, require_run_health)
    checks["spend"] = _check_spend(corpus_dir, require_run_health)
    return ValidationReport(corpus_dir, checks)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus_dir", type=Path)
    parser.add_argument("--require-run-health", action="store_true")
    args = parser.parse_args()
    report = validate_corpus(args.corpus_dir, require_run_health=args.require_run_health)
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    raise SystemExit(0 if report.ok else 1)


if __name__ == "__main__":
    main()
