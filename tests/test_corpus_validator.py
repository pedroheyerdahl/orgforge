import json

from build_source_realism_fixture import build_fixture_input
from clearweave_corpus import export_corpus
from corpus_validator import validate_corpus


def _build_valid(tmp_path):
    source = tmp_path / "fixture-input"
    corpus = tmp_path / "fixture-corpus"
    build_fixture_input(source)
    export_corpus(source, corpus, seed=42)
    return corpus


def test_no_cost_fixture_passes_all_local_readiness_checks(tmp_path):
    corpus = _build_valid(tmp_path)

    report = validate_corpus(corpus)

    assert report.ok, report.to_dict()
    assert report.checks["privacy"].passed
    assert report.checks["identity_replay"].passed
    assert report.checks["temporal_integrity"].passed
    assert report.checks["native_shape"].passed
    assert report.checks["manifest_coverage"].passed
    assert report.checks["messiness"].passed
    assert report.checks["semantic_safety"].passed
    assert report.checks["utf8"].passed
    assert report.checks["run_health"].required is False
    assert report.checks["spend"].required is False


def test_validator_detects_checksum_and_manifest_coverage_damage(tmp_path):
    corpus = _build_valid(tmp_path)
    manifest_path = corpus / "provenance" / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    first = corpus / manifest["entries"][0]["path"]
    first.write_text(first.read_text(encoding="utf-8") + "damaged\n", encoding="utf-8")
    manifest["entries"].pop()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = validate_corpus(corpus)

    assert report.ok is False
    assert report.checks["manifest_coverage"].passed is False
    assert "checksum" in report.checks["manifest_coverage"].details
    assert "uncovered" in report.checks["manifest_coverage"].details


def test_validator_detects_invalid_revision_and_orphaned_slack_thread(tmp_path):
    corpus = _build_valid(tmp_path)
    actions_path = corpus / "provenance" / "source_actions.jsonl"
    lines = actions_path.read_text().splitlines()
    actions = [json.loads(line) for line in lines]
    update = next(item for item in actions if item["operation"] == "update")
    update["revision"] = 99
    update.pop("payload_sha256", None)
    actions_path.write_text("".join(json.dumps(item) + "\n" for item in actions))

    slack_path = next((corpus / "raw" / "slack" / "channels").glob("*.json"))
    slack = json.loads(slack_path.read_text())
    replies = next(iter(slack["threads"].values()))
    slack["threads"] = {"1000000000.000000": replies}
    slack_path.write_text(json.dumps(slack), encoding="utf-8")

    report = validate_corpus(corpus)

    assert report.ok is False
    assert report.checks["identity_replay"].passed is False
    assert report.checks["temporal_integrity"].passed is False
    assert "orphan" in report.checks["temporal_integrity"].details


def test_policy_v4_validator_rejects_future_native_data_and_terminal_create(tmp_path):
    corpus = _build_valid(tmp_path)
    manifest_path = corpus / "provenance" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["realism_policy_version"] = 4
    manifest["target_start"] = "2026-01-01"
    manifest["target_end"] = "2026-06-29"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    actions_path = corpus / "provenance" / "source_actions.jsonl"
    actions = [json.loads(line) for line in actions_path.read_text().splitlines()]
    git_create = next(
        item
        for item in actions
        if item["source_system"] == "git" and item["operation"] == "create"
    )
    git_create["observed_at"] = "2026-01-03T09:00:00+00:00"
    git_create["effective_at"] = git_create["observed_at"]
    git_create["payload"].update(
        {
            "status": "merged",
            "created_at": "2026-01-03T09:00:00+00:00",
            "merged_at": "2026-07-10T12:00:00+00:00",
            "comments": [
                {
                    "timestamp": "2026-07-09T11:00:00+00:00",
                    "text": "future review",
                }
            ],
            "source_path": "git/prs/2026-09-03/PR-FUTURE.json",
        }
    )
    git_create.pop("payload_sha256", None)
    actions.sort(key=lambda item: (item["observed_at"], item["action_id"]))
    actions_path.write_text(
        "".join(json.dumps(item) + "\n" for item in actions), encoding="utf-8"
    )

    report = validate_corpus(corpus)

    assert report.checks["temporal_integrity"].passed is False
    assert "future native timestamp" in report.checks["temporal_integrity"].details
    assert "outside declared window" in report.checks["temporal_integrity"].details
    assert "terminal state in create" in report.checks["temporal_integrity"].details
    assert "locator date" in report.checks["temporal_integrity"].details


def test_policy_v4_validator_rejects_source_visible_control_fields(tmp_path):
    corpus = _build_valid(tmp_path)
    manifest_path = corpus / "provenance" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["realism_policy_version"] = 4
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    raw_json = next((corpus / "raw").glob("*/*.json"))
    payload = json.loads(raw_json.read_text(encoding="utf-8"))
    payload["synthetic_routine"] = True
    raw_json.write_text(json.dumps(payload), encoding="utf-8")

    report = validate_corpus(corpus)

    assert report.checks["source_visible_controls"].required is True
    assert report.checks["source_visible_controls"].passed is False
    assert "synthetic_routine" in report.checks["source_visible_controls"].details


def test_strict_run_health_requires_completed_zero_unrecovered_status(tmp_path):
    corpus = _build_valid(tmp_path)
    status = corpus / "provenance" / "run_status.json"
    status.write_text(
        json.dumps({"status": "stopped_error_budget", "unrecovered_llm_failures": 2}),
        encoding="utf-8",
    )

    report = validate_corpus(corpus, require_run_health=True)

    assert report.ok is False
    assert report.checks["run_health"].required is True
    assert report.checks["run_health"].passed is False


def test_strict_spend_uses_conservative_all_fallback_pricing(tmp_path):
    corpus = _build_valid(tmp_path)
    (corpus / "provenance" / "run_status.json").write_text(
        json.dumps({"status": "completed", "unrecovered_llm_failures": 0}),
        encoding="utf-8",
    )
    (corpus / "provenance" / "simulation.log").write_text(
        "OpenAI API usage: {'prompt_tokens': 1000000,\n"
        " 'completion_tokens': 1000000, 'total_tokens': 2000000}\n",
        encoding="utf-8",
    )

    report = validate_corpus(corpus, require_run_health=True)

    assert report.ok is False
    assert report.checks["spend"].required is True
    assert report.checks["spend"].passed is False
    assert "$35.00" in report.checks["spend"].details
    assert "$25.00" in report.checks["spend"].details


def test_strict_spend_uses_authoritative_run_budget_when_present(tmp_path):
    corpus = _build_valid(tmp_path)
    (corpus / "provenance" / "run_status.json").write_text(
        json.dumps(
            {
                "status": "completed",
                "unrecovered_llm_failures": 0,
                "conservative_spend_usd": 31.323768,
                "spend_ceiling_usd": 43.0,
            }
        ),
        encoding="utf-8",
    )
    (corpus / "provenance" / "simulation.log").write_text(
        "OpenAI API usage: {'prompt_tokens': 1000000,\n"
        " 'completion_tokens': 1000000, 'total_tokens': 2000000}\n",
        encoding="utf-8",
    )

    report = validate_corpus(corpus, require_run_health=True)

    assert report.checks["spend"].passed is True
    assert "$31.32" in report.checks["spend"].details
    assert "$43.00" in report.checks["spend"].details


def test_validator_requires_and_checks_v2_realism_scorecard(tmp_path):
    source = tmp_path / "fixture-input"
    corpus = tmp_path / "fixture-corpus"
    build_fixture_input(source)
    export_corpus(
        source,
        corpus,
        seed=42,
        target_days=180,
        target_start="2026-01-01",
        observation_realism=True,
    )

    report = validate_corpus(corpus)

    assert report.checks["realism"].required is True
    assert report.checks["realism"].passed is True


def test_validator_rejects_stale_knowledge_scenario_action_references(tmp_path):
    source = tmp_path / "fixture-input"
    corpus = tmp_path / "fixture-corpus"
    build_fixture_input(source)
    export_corpus(
        source,
        corpus,
        seed=42,
        target_days=180,
        target_start="2026-01-01",
        observation_realism=True,
    )
    scenario_path = corpus / "provenance" / "knowledge_scenarios.jsonl"
    scenarios = [
        json.loads(line)
        for line in scenario_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    scenarios[0]["evidence_action_ids"][0] = "src-action-does-not-exist"
    scenario_path.write_text(
        "".join(json.dumps(item, sort_keys=True) + "\n" for item in scenarios),
        encoding="utf-8",
    )

    report = validate_corpus(corpus)

    assert report.checks["knowledge_reference_integrity"].required is True
    assert report.checks["knowledge_reference_integrity"].passed is False
    assert "missing evidence action" in report.checks["knowledge_reference_integrity"].details

    scorecard_path = corpus / "provenance" / "realism_scorecard.json"
    scorecard = json.loads(scorecard_path.read_text(encoding="utf-8"))
    scorecard["delivery"]["max_daily_share"] = 0.95
    scorecard_path.write_text(json.dumps(scorecard), encoding="utf-8")

    damaged = validate_corpus(corpus)
    assert damaged.checks["realism"].passed is False
    assert "delivery concentration" in damaged.checks["realism"].details
