"""Build a no-cost synthetic source export and package it for validation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from clearweave_corpus import export_corpus


CLASSIFICATION = "synthetic_non_confidential"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_fixture_input(root: Path) -> None:
    if root.exists() and any(root.iterdir()):
        raise ValueError(f"fixture input directory must be empty: {root}")
    root.mkdir(parents=True, exist_ok=True)

    _write(
        root / "slack" / "channels" / "engineering" / "2026-01-02.json",
        json.dumps(
            [
                {
                    "message_id": "slack-msg-fixture-root",
                    "user": "Hanna",
                    "text": "retry banner still has the previous copy",
                    "ts": "2026-01-02T09:05:00+00:00",
                },
                {
                    "message_id": "slack-msg-fixture-reply",
                    "user": "Miki",
                    "text": "looking after standup",
                    "ts": "2026-01-02T09:07:00+00:00",
                    "thread_ts": "2026-01-02T09:05:00+00:00",
                },
            ],
            ensure_ascii=False,
        ),
    )
    _write(
        root / "jira" / "SYN-FIX-104.json",
        json.dumps(
            {
                "id": "SYN-FIX-104",
                "title": "Verify retry banner behavior",
                "description": "Check the existing behavior on supported clients.\n\nEnvironment:\n\nObserved:",
                "status": "In Progress",
                "assignee": "Hanna",
                "created_at": "2026-01-02T08:00:00+00:00",
                "updated_at": "2026-01-03T14:00:00+00:00",
                "comments": [
                    {
                        "author": "Hanna",
                        "created": "2026-01-03T10:00:00+00:00",
                        "text": "web checked; mobile pending",
                    }
                ],
            },
            ensure_ascii=False,
        ),
    )
    _write(
        root / "confluence" / "general" / "CONF-SYN-FIX-001.md",
        "# Retry behavior notes\n**ID:** CONF-SYN-FIX-001\n**Author:** Hanna\n**Date:** 2026-01-02\n\nThe service timeout remains unchanged.\n",
    )
    _write(
        root / "zoom" / "2026-01-03" / "zoom-syn-fix-1.md",
        "# Meeting Transcript\n**Date:** 2026-01-03\n\n**[10:00:00] Hanna:** TitanDB reads still use the existing timeout.\n\n**[10:02:00] Miki:** I need to check the mobile retry state.\n",
    )
    _write(
        root / "emails" / "synthetic-thread.eml",
        "From: hanna@apexathletics.io\nTo: miki@apexathletics.io\nDate: Sat, 03 Jan 2026 11:00:00 +0000\nMessage-ID: <fixture-thread-1@apexathletics.io>\nSubject: retry copy\nMIME-Version: 1.0\nContent-Type: text/plain; charset=UTF-8\nX-Data-Classification: synthetic_non_confidential\n\nCan you check mobile?\n",
    )
    _write(
        root / "salesforce" / "opportunity.json",
        json.dumps(
            {
                "Id": "006SYNFIX1",
                "Name": "Synthetic coaching group renewal",
                "StageName": "Discovery",
                "OwnerId": None,
                "LastModifiedDate": "2026-01-03T12:00:00+00:00",
            }
        ),
    )
    _write(
        root / "zendesk" / "ticket.json",
        json.dumps(
            {
                "id": 4104,
                "subject": "retry banner wording",
                "status": "open",
                "assignee_id": None,
                "updated_at": "2026-01-03T12:30:00+00:00",
            }
        ),
    )
    _write(
        root / "git" / "prs" / "PR-17.json",
        json.dumps(
            {
                "pr_id": "PR-17",
                "title": "Adjust retry-state copy",
                "status": "open",
                "created_at": "2026-01-03T13:00:00+00:00",
                "comments": [{"author": "Build Monitor", "text": "one check is still pending"}],
            }
        ),
    )
    _write(
        root / "datadog" / "alerts.jsonl",
        json.dumps(
            {
                "id": "dd-syn-fix-1",
                "title": "Retry error rate above warning threshold",
                "timestamp": "2026-01-03T13:15:00+00:00",
                "status": "Warn",
            }
        )
        + "\n",
    )
    _write(
        root / "invoices" / "invoice.json",
        json.dumps(
            {
                "id": "INV-SYN-FIX-1",
                "status": "draft",
                "date": "2026-01-03",
                "line_items": [{"description": "device pilot", "amount": 1200}],
            }
        ),
    )
    _write(
        root / "nps" / "response.json",
        json.dumps(
            {
                "id": "NPS-SYN-FIX-1",
                "score": 7,
                "comment": "setup was fine, retry message was confusing",
                "date": "2026-01-03",
            }
        ),
    )
    _write(
        root / "simulation_events.jsonl",
        json.dumps(
            {
                "event_id": "sim-event-fixture-1",
                "artifact_ids": {"jira": "SYN-FIX-104"},
                "classification": CLASSIFICATION,
            }
        )
        + "\n",
    )


def build_fixture(input_dir: Path, corpus_dir: Path, seed: int = 42) -> dict:
    build_fixture_input(input_dir)
    return export_corpus(input_dir, corpus_dir, seed=seed)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("corpus_dir", type=Path)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    manifest = build_fixture(args.input_dir, args.corpus_dir, seed=args.seed)
    print(
        f"Built no-cost fixture with {len(manifest['entries'])} raw/inbox artifacts "
        f"and {len(manifest['deliveries'])} delivery actions at {args.corpus_dir}"
    )


if __name__ == "__main__":
    main()
