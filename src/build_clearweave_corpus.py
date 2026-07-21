"""Build, validate, and safely promote a Clearweave corpus package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from corpus_pipeline import CorpusBuildProfile, CorpusPipelineError, build_corpus


DEFAULT_PROFILE = (
    Path(__file__).resolve().parents[1] / "config" / "clearweave_180d.yaml"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_export", type=Path, help="completed OrgForge export")
    parser.add_argument(
        "output_dir", type=Path, help="final Clearweave corpus directory"
    )
    parser.add_argument(
        "--profile",
        type=Path,
        default=DEFAULT_PROFILE,
        help="build profile (default: config/clearweave_180d.yaml)",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="replace an existing destination only after the staged build passes",
    )
    parser.add_argument(
        "--keep-failed",
        action="store_true",
        help="retain failed staging output for diagnosis",
    )
    args = parser.parse_args(argv)

    try:
        profile = CorpusBuildProfile.load(args.profile)
        report = build_corpus(
            args.source_export,
            args.output_dir,
            profile,
            replace=args.replace,
            keep_failed=args.keep_failed,
            profile_path=args.profile,
        )
    except CorpusPipelineError as exc:
        print(f"Corpus build failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
