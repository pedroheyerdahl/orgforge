import json
from pathlib import Path
import subprocess
import sys

import pytest

from build_source_realism_fixture import build_fixture_input
from corpus_pipeline import CorpusBuildProfile, CorpusPipelineError, build_corpus
from corpus_validator import CheckResult, ValidationReport


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _write_profile(path: Path, **overrides) -> Path:
    values = {
        "schema_version": 1,
        "name": "test-clearweave",
        "seed": 42,
        "target_start": "2026-01-01",
        "target_days": 5,
        "observation_realism": False,
        "datadog_inbox_limit": None,
        "require_run_health": False,
        "expected_realism_policy_version": None,
    }
    values.update(overrides)
    lines = []
    for key, value in values.items():
        if value is None:
            rendered = "null"
        elif isinstance(value, bool):
            rendered = str(value).lower()
        else:
            rendered = str(value)
        lines.append(f"{key}: {rendered}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_committed_180_day_profile_locks_validated_release_settings():
    profile = CorpusBuildProfile.load(PROJECT_ROOT / "config" / "clearweave_180d.yaml")

    assert profile.name == "clearweave-180d"
    assert profile.seed == 42
    assert profile.target_start == "2026-01-01"
    assert profile.target_days == 180
    assert profile.observation_realism is True
    assert profile.datadog_inbox_limit == 1000
    assert profile.require_run_health is True
    assert profile.expected_realism_policy_version == 5


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"target_start": "January-1"}, "target_start"),
        ({"target_days": 0}, "target_days"),
        ({"expected_realism_policy_version": 0}, "expected_realism_policy_version"),
        ({"datadog_inbox_limit": -1}, "datadog_inbox_limit"),
    ],
)
def test_profile_rejects_invalid_release_settings(tmp_path, overrides, message):
    path = _write_profile(tmp_path / "profile.yaml", **overrides)

    with pytest.raises(CorpusPipelineError, match=message):
        CorpusBuildProfile.load(path)


def test_existing_destination_requires_replace_before_export(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    output = tmp_path / "corpus"
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("original", encoding="utf-8")
    profile = CorpusBuildProfile.load(_write_profile(tmp_path / "profile.yaml"))
    exporter_called = False

    def exporter(*_args, **_kwargs):
        nonlocal exporter_called
        exporter_called = True
        return {}

    with pytest.raises(CorpusPipelineError, match="--replace"):
        build_corpus(source, output, profile, exporter=exporter)

    assert exporter_called is False
    assert marker.read_text(encoding="utf-8") == "original"
    assert not list(tmp_path.glob(".corpus.staging-*"))


def _fake_exporter(_source, staging, **_kwargs):
    for name in ("raw", "deliveries", "inbox", "provenance", "gold"):
        (staging / name).mkdir(parents=True, exist_ok=True)
    (staging / "raw" / "new.txt").write_text("new corpus", encoding="utf-8")
    manifest = {
        "corpus_id": "corpus-test",
        "entries": [{"path": "raw/new.txt"}],
        "deliveries": [],
    }
    (staging / "provenance" / "manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    return manifest


def test_failed_validation_never_replaces_existing_destination(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    output = tmp_path / "corpus"
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("original", encoding="utf-8")
    profile = CorpusBuildProfile.load(_write_profile(tmp_path / "profile.yaml"))

    def failing_validator(staging, **_kwargs):
        return ValidationReport(
            staging,
            {"release_gate": CheckResult("release_gate", False, "deliberate failure")},
        )

    with pytest.raises(CorpusPipelineError, match="release_gate"):
        build_corpus(
            source,
            output,
            profile,
            replace=True,
            exporter=_fake_exporter,
            validator=failing_validator,
        )

    assert marker.read_text(encoding="utf-8") == "original"
    assert not (output / "raw" / "new.txt").exists()
    assert not list(tmp_path.glob(".corpus.staging-*"))
    assert not list(tmp_path.glob(".corpus.previous-*"))


def test_keep_failed_reports_and_retains_staging_directory(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    output = tmp_path / "corpus"
    profile = CorpusBuildProfile.load(_write_profile(tmp_path / "profile.yaml"))

    def failing_validator(staging, **_kwargs):
        return ValidationReport(
            staging,
            {"release_gate": CheckResult("release_gate", False, "deliberate failure")},
        )

    with pytest.raises(CorpusPipelineError, match="failed staging kept at"):
        build_corpus(
            source,
            output,
            profile,
            keep_failed=True,
            exporter=_fake_exporter,
            validator=failing_validator,
        )

    staging = list(tmp_path.glob(".corpus.staging-*"))
    assert len(staging) == 1
    assert (staging[0] / "raw" / "new.txt").exists()


def test_passing_build_writes_report_and_atomically_replaces_destination(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    output = tmp_path / "corpus"
    output.mkdir()
    (output / "old.txt").write_text("old corpus", encoding="utf-8")
    profile_path = _write_profile(tmp_path / "profile.yaml")
    profile = CorpusBuildProfile.load(profile_path)
    validation_calls = []

    def passing_validator(staging, **_kwargs):
        validation_calls.append(staging)
        return ValidationReport(
            staging,
            {"release_gate": CheckResult("release_gate", True, "passed")},
        )

    result = build_corpus(
        source,
        output,
        profile,
        replace=True,
        exporter=_fake_exporter,
        validator=passing_validator,
        profile_path=profile_path,
    )

    report = json.loads(
        (output / "provenance" / "build_report.json").read_text(encoding="utf-8")
    )
    assert result == report
    assert report["ok"] is True
    assert report["profile"]["name"] == "test-clearweave"
    assert report["profile"]["sha256"]
    assert report["corpus"]["corpus_id"] == "corpus-test"
    assert report["corpus"]["manifest_entries"] == 1
    assert report["validation"]["checks"]["release_gate"]["passed"] is True
    assert report["output_dir"] == "."
    assert report["source_export"] == "source"
    assert (output / "raw" / "new.txt").read_text(encoding="utf-8") == "new corpus"
    assert not (output / "old.txt").exists()
    assert len(validation_calls) == 2
    assert not list(tmp_path.glob(".corpus.staging-*"))
    assert not list(tmp_path.glob(".corpus.previous-*"))


def test_public_cli_documents_profile_and_safety_flags():
    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "src" / "build_clearweave_corpus.py"),
            "--help",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "--profile" in result.stdout
    assert "--replace" in result.stdout
    assert "--keep-failed" in result.stdout


def test_real_no_cost_fixture_builds_valid_complete_package(tmp_path):
    source = tmp_path / "fixture-input"
    build_fixture_input(source)
    output = tmp_path / "fixture-corpus"
    profile_path = _write_profile(tmp_path / "fixture-profile.yaml")
    profile = CorpusBuildProfile.load(profile_path)

    report = build_corpus(
        source,
        output,
        profile,
        profile_path=profile_path,
    )

    expected_layout = ["raw", "deliveries", "inbox", "provenance", "gold"]
    assert report["ok"] is True
    assert report["corpus"]["layout"] == expected_layout
    assert all((output / name).is_dir() for name in expected_layout)
    assert report["validation"]["ok"] is True
    assert not list(tmp_path.glob(".fixture-corpus.staging-*"))
