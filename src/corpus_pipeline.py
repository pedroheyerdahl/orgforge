"""Safe orchestration for reproducible Clearweave corpus builds."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Callable
import uuid

import yaml


PACKAGE_LAYOUT = ["raw", "deliveries", "inbox", "provenance", "gold"]


class CorpusPipelineError(RuntimeError):
    """Raised when a corpus build cannot be completed safely."""


def _integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CorpusPipelineError(f"{field} must be an integer")
    return value


@dataclass(frozen=True)
class CorpusBuildProfile:
    schema_version: int
    name: str
    seed: int
    target_start: str
    target_days: int
    observation_realism: bool
    datadog_inbox_limit: int | None
    require_run_health: bool
    expected_realism_policy_version: int | None

    @classmethod
    def load(cls, path: Path) -> "CorpusBuildProfile":
        try:
            values = yaml.load(
                path.read_text(encoding="utf-8"), Loader=yaml.SafeLoader
            )
        except (OSError, yaml.YAMLError) as exc:
            raise CorpusPipelineError(f"unable to read profile {path}: {exc}") from exc
        if not isinstance(values, dict):
            raise CorpusPipelineError("profile must be a YAML mapping")

        required = {field.name for field in cls.__dataclass_fields__.values()}
        missing = required - set(values)
        unknown = set(values) - required
        if missing:
            raise CorpusPipelineError(f"profile missing fields: {sorted(missing)}")
        if unknown:
            raise CorpusPipelineError(f"profile has unknown fields: {sorted(unknown)}")

        schema_version = _integer(values["schema_version"], "schema_version")
        seed = _integer(values["seed"], "seed")
        target_days = _integer(values["target_days"], "target_days")
        if schema_version != 1:
            raise CorpusPipelineError("schema_version must be 1")
        if target_days <= 0:
            raise CorpusPipelineError("target_days must be positive")
        try:
            date.fromisoformat(str(values["target_start"]))
        except ValueError as exc:
            raise CorpusPipelineError("target_start must be an ISO date") from exc

        limit = values["datadog_inbox_limit"]
        if limit is not None:
            limit = _integer(limit, "datadog_inbox_limit")
            if limit < 0:
                raise CorpusPipelineError("datadog_inbox_limit cannot be negative")

        policy_version = values["expected_realism_policy_version"]
        if policy_version is not None:
            policy_version = _integer(
                policy_version, "expected_realism_policy_version"
            )
            if policy_version <= 0:
                raise CorpusPipelineError(
                    "expected_realism_policy_version must be positive"
                )

        if not isinstance(values["name"], str) or not values["name"].strip():
            raise CorpusPipelineError("name must be a non-empty string")
        for field in ("observation_realism", "require_run_health"):
            if not isinstance(values[field], bool):
                raise CorpusPipelineError(f"{field} must be a boolean")

        return cls(
            schema_version=schema_version,
            name=values["name"].strip(),
            seed=seed,
            target_start=str(values["target_start"]),
            target_days=target_days,
            observation_realism=values["observation_realism"],
            datadog_inbox_limit=limit,
            require_run_health=values["require_run_health"],
            expected_realism_policy_version=policy_version,
        )


def build_corpus(
    source_dir: Path,
    output_dir: Path,
    profile: CorpusBuildProfile,
    *,
    replace: bool = False,
    keep_failed: bool = False,
    exporter: Callable[..., dict[str, Any]] | None = None,
    validator: Callable[..., Any] | None = None,
    profile_path: Path | None = None,
) -> dict[str, Any]:
    """Build and validate a corpus before promoting it to ``output_dir``."""

    source_dir = source_dir.resolve()
    output_dir = output_dir.resolve()
    if not source_dir.is_dir():
        raise CorpusPipelineError(f"source export does not exist: {source_dir}")
    if source_dir == output_dir:
        raise CorpusPipelineError("source export and destination must differ")
    if output_dir.is_relative_to(source_dir) or source_dir.is_relative_to(output_dir):
        raise CorpusPipelineError(
            "source export and destination cannot contain each other"
        )
    if output_dir.exists() and not replace:
        raise CorpusPipelineError(
            f"destination already exists; pass --replace to replace it: {output_dir}"
        )
    if exporter is None:
        from clearweave_corpus import export_corpus

        exporter = export_corpus
    if validator is None:
        from corpus_validator import validate_corpus

        validator = validate_corpus

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{output_dir.name}.staging-", dir=output_dir.parent
        )
    )
    promoted = False
    try:
        manifest = exporter(
            source_dir,
            staging,
            seed=profile.seed,
            target_days=profile.target_days,
            target_start=profile.target_start,
            observation_realism=profile.observation_realism,
            datadog_inbox_limit=profile.datadog_inbox_limit,
        )
        validation = validator(
            staging, require_run_health=profile.require_run_health
        )
        if not validation.ok:
            raise CorpusPipelineError(
                "staged corpus failed required checks: "
                + ", ".join(validation.failed)
            )

        expected_policy = profile.expected_realism_policy_version
        actual_policy = manifest.get("realism_policy_version")
        if expected_policy is not None and actual_policy != expected_policy:
            raise CorpusPipelineError(
                "realism policy mismatch: "
                f"expected {expected_policy}, generated {actual_policy!r}"
            )

        profile_bytes = (
            profile_path.resolve().read_bytes()
            if profile_path is not None
            else json.dumps(asdict(profile), sort_keys=True).encode("utf-8")
        )
        validation_data = validation.to_dict()
        validation_data.pop("corpus_dir", None)
        build_report = {
            "schema_version": 1,
            "ok": True,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_export": source_dir.name,
            "output_dir": ".",
            "profile": {
                **asdict(profile),
                "sha256": hashlib.sha256(profile_bytes).hexdigest(),
            },
            "corpus": {
                "corpus_id": manifest.get("corpus_id"),
                "manifest_entries": len(manifest.get("entries", [])),
                "delivery_actions": len(manifest.get("deliveries", [])),
                "realism_policy_version": actual_policy,
                "layout": manifest.get("layout", PACKAGE_LAYOUT),
            },
            "validation": validation_data,
        }
        report_path = staging / "provenance" / "build_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(build_report, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )

        final_validation = validator(
            staging, require_run_health=profile.require_run_health
        )
        if not final_validation.ok:
            raise CorpusPipelineError(
                "staged corpus failed checks after build report: "
                + ", ".join(final_validation.failed)
            )

        _promote(staging, output_dir)
        promoted = True
        return build_report
    except CorpusPipelineError as exc:
        if keep_failed and staging.exists():
            raise CorpusPipelineError(
                f"{exc}; failed staging kept at {staging}"
            ) from exc
        raise
    except Exception as exc:
        raise CorpusPipelineError(f"corpus build failed: {exc}") from exc
    finally:
        if not promoted and staging.exists() and not keep_failed:
            shutil.rmtree(staging)


def _remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


def _promote(staging: Path, output_dir: Path) -> None:
    previous = output_dir.parent / f".{output_dir.name}.previous-{uuid.uuid4().hex}"
    moved_previous = False
    try:
        if output_dir.exists() or output_dir.is_symlink():
            os.replace(output_dir, previous)
            moved_previous = True
        try:
            os.replace(staging, output_dir)
        except Exception:
            if moved_previous and not output_dir.exists():
                os.replace(previous, output_dir)
                moved_previous = False
            raise
        if moved_previous:
            _remove_path(previous)
    except Exception as exc:
        raise CorpusPipelineError(f"unable to promote staged corpus: {exc}") from exc
