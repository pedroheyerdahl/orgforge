import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from confluence_writer import ConfluenceWriter


def test_design_doc_records_deterministic_domain_fit_and_gap_classification():
    writer = ConfluenceWriter.__new__(ConfluenceWriter)
    writer._registry = MagicMock()
    writer._registry.next_id.return_value = "CONF-ENG-900"
    writer._clock = MagicMock()
    writer._clock.advance_actor.return_value = (datetime(2026, 1, 3, 10, 0), None)
    writer._mem = MagicMock()
    writer._mem.search_artifacts_text.return_value = []
    writer._mem.get_author_domain_tokens.return_value = {"python"}
    writer._mem._db.__getitem__.return_value.find.return_value = []
    writer._state = SimpleNamespace(day=3)
    writer._gd = MagicMock()
    writer._planner = MagicMock()
    writer._lifecycle = MagicMock()
    writer._finalize_page = MagicMock(return_value=["CONF-ENG-900"])
    writer._spawn_tickets = MagicMock(return_value=[])

    generated = {
        "markdown_doc": "## Problem Statement\n\nSynthetic retry behavior.",
        "new_tickets": [],
        "aliases": ["retry"],
        "self_audit": {
            "topics_in_doc": ["python"],
            "topics_outside_my_expertise": [],
            "claims_i_approximated": [],
            "sections_i_left_thin": [],
        },
    }

    with (
        patch("confluence_writer.make_agent"),
        patch("confluence_writer.Task"),
        patch("confluence_writer.Crew") as crew,
        patch("confluence_writer.persona_utils.get_voice_card", return_value="voice"),
    ):
        crew.return_value.kickoff.return_value = json.dumps(generated)
        result = writer.write_design_doc(
            author="Hanna",
            participants=["Hanna", "Miki"],
            topic="Python retry behavior",
            slack_transcript=[],
            date_str="2026-01-03",
        )

    assert result == "CONF-ENG-900"
    event = writer._mem.log_event.call_args.args[0]
    assert event.facts["author_domain_fit"] == "high"
    assert event.facts["gap_classification"] == "none"
