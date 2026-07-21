import json

import pytest

from run_resilience import RunResilience, load_resume_day, validate_run_flags


def test_error_budget_writes_stopped_status_and_checkpoint(tmp_path):
    resilience = RunResilience(tmp_path, max_unrecovered=2)
    resilience.record({"outcome": "unrecovered", "model": "gpt-5.6-terra"})
    resilience.record({"outcome": "unrecovered", "model": "gpt-5.6-terra"})

    assert resilience.should_stop() is True

    resilience.write_status("stopped_error_budget", next_day=4)

    status = json.loads((tmp_path / "provenance/run_status.json").read_text())
    assert status == {
        "status": "stopped_error_budget",
        "next_day": 4,
        "unrecovered_llm_failures": 2,
    }
    assert len((tmp_path / "provenance/llm_resilience.jsonl").read_text().splitlines()) == 2
    assert json.loads((tmp_path / "provenance/resume_checkpoint.json").read_text()) == {
        "next_day": 4
    }


def test_completed_status_removes_resume_checkpoint(tmp_path):
    resilience = RunResilience(tmp_path)
    resilience.write_status("stopped_error_budget", next_day=2)
    resilience.write_status("completed", next_day=None)

    assert not (tmp_path / "provenance/resume_checkpoint.json").exists()


def test_resume_rejects_reset_and_reads_checkpoint(tmp_path):
    checkpoint = tmp_path / "provenance" / "resume_checkpoint.json"
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_text(json.dumps({"next_day": 4}))

    assert load_resume_day(tmp_path) == 4
    with pytest.raises(ValueError, match="mutually exclusive"):
        validate_run_flags(reset=True, resume=True)


def test_conservative_spend_budget_stops_at_usage_boundary(tmp_path):
    log_path = tmp_path / "simulation.log"
    log_path.write_text(
        "OpenAI API usage: {'prompt_tokens': 1000000,\n"
        " 'completion_tokens': 500000}\n"
    )
    resilience = RunResilience(tmp_path, max_spend_usd=19.0)

    assert resilience.conservative_spend_usd() == pytest.approx(20.0)
    assert resilience.spend_exceeded() is True

    resilience.write_status("stopped_spend_budget", next_day=7)
    status = json.loads((tmp_path / "provenance/run_status.json").read_text())
    assert status["conservative_spend_usd"] == 20.0
    assert status["spend_ceiling_usd"] == 19.0
