"""Persistent run-level safety state for OpenAI-backed simulations."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


class ResilienceBudgetExceeded(RuntimeError):
    """Raised at a simulation-day boundary after too many LLM failures."""


class SpendBudgetExceeded(RuntimeError):
    """Raised at a simulation-day boundary before paid usage can run away."""


class RunResilience:
    def __init__(
        self,
        export_dir: Path,
        max_unrecovered: int = 3,
        max_spend_usd: float | None = None,
        input_price_per_million: float = 5.0,
        output_price_per_million: float = 30.0,
    ):
        self.export_dir = export_dir
        self.provenance_dir = export_dir / "provenance"
        self.ledger_path = self.provenance_dir / "llm_resilience.jsonl"
        self.status_path = self.provenance_dir / "run_status.json"
        self.checkpoint_path = self.provenance_dir / "resume_checkpoint.json"
        self.max_unrecovered = max_unrecovered
        self.max_spend_usd = max_spend_usd
        self.input_price_per_million = input_price_per_million
        self.output_price_per_million = output_price_per_million
        self.unrecovered = 0

    def record(self, event: dict[str, Any]) -> None:
        self.provenance_dir.mkdir(parents=True, exist_ok=True)
        with self.ledger_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
        if event.get("outcome") == "unrecovered":
            self.unrecovered += 1

    def should_stop(self) -> bool:
        return self.unrecovered >= self.max_unrecovered

    def conservative_spend_usd(self) -> float:
        """Price logged usage as Sol, the most expensive configured fallback."""
        log_path = self.export_dir / "simulation.log"
        if not log_path.exists():
            return 0.0
        prompt_tokens = 0
        completion_tokens = 0
        text = log_path.read_text(encoding="utf-8", errors="replace")
        for body in re.findall(r"OpenAI API usage:\s*\{([^{}]*)\}", text, flags=re.S):
            prompt = re.search(r"['\"]prompt_tokens['\"]\s*:\s*(\d+)", body)
            completion = re.search(
                r"['\"]completion_tokens['\"]\s*:\s*(\d+)", body
            )
            if prompt and completion:
                prompt_tokens += int(prompt.group(1))
                completion_tokens += int(completion.group(1))
        return (
            prompt_tokens * self.input_price_per_million / 1_000_000
            + completion_tokens * self.output_price_per_million / 1_000_000
        )

    def spend_exceeded(self) -> bool:
        return (
            self.max_spend_usd is not None
            and self.conservative_spend_usd() >= self.max_spend_usd
        )

    def write_status(self, status: str, next_day: int | None) -> None:
        self.provenance_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "status": status,
            "next_day": next_day,
            "unrecovered_llm_failures": self.unrecovered,
        }
        if self.max_spend_usd is not None:
            payload["conservative_spend_usd"] = round(
                self.conservative_spend_usd(), 6
            )
            payload["spend_ceiling_usd"] = self.max_spend_usd
            payload["budget_input_price_per_million"] = self.input_price_per_million
            payload["budget_output_price_per_million"] = self.output_price_per_million
        self.status_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        if status == "completed":
            self.checkpoint_path.unlink(missing_ok=True)
        elif next_day is not None:
            self.checkpoint_path.write_text(
                json.dumps({"next_day": next_day}, indent=2) + "\n", encoding="utf-8"
            )


def validate_run_flags(reset: bool, resume: bool) -> None:
    if reset and resume:
        raise ValueError("--reset and --resume are mutually exclusive")


def load_resume_day(export_dir: Path) -> int:
    checkpoint = export_dir / "provenance" / "resume_checkpoint.json"
    payload = json.loads(checkpoint.read_text(encoding="utf-8"))
    return int(payload["next_day"])
