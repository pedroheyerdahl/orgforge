"""Small reliability shim for transient OpenAI project-permission responses."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from datetime import datetime, timezone
import logging
from typing import Any


def _is_transient_permission_error(error: BaseException) -> bool:
    message = str(error).lower()
    return "401" in message and "insufficient permissions" in message


def _emit(
    event_sink: Callable[[dict[str, Any]], None] | None,
    *,
    model: str,
    outcome: str,
    attempt: int,
    error: BaseException | None = None,
) -> None:
    if event_sink is None:
        return
    event_sink(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": model,
            "outcome": outcome,
            "attempt": attempt,
            "error_class": type(error).__name__ if error else None,
        }
    )


def call_with_transient_permission_retry(
    call: Callable[[], Any],
    *,
    model: str = "unknown",
    event_sink: Callable[[dict[str, Any]], None] | None = None,
    attempts: int = 8,
    emit_unrecovered: bool = True,
    sleep: Callable[[float], None] = time.sleep,
) -> Any:
    """Retry only the intermittent 401 response seen from the OpenAI project.

    Invalid keys and ordinary authorization failures are deliberately not
    retried; they require configuration changes and should fail immediately.
    """
    recovered_after_retry = False
    for attempt in range(1, attempts + 1):
        try:
            result = call()
            if recovered_after_retry:
                _emit(event_sink, model=model, outcome="recovered", attempt=attempt)
            return result
        except Exception as error:
            if not _is_transient_permission_error(error) or attempt == attempts:
                if emit_unrecovered:
                    _emit(
                        event_sink,
                        model=model,
                        outcome="unrecovered",
                        attempt=attempt,
                        error=error,
                    )
                raise
            _emit(event_sink, model=model, outcome="retry", attempt=attempt, error=error)
            recovered_after_retry = True
            sleep(min(0.5 * (2 ** (attempt - 1)) * (1 + random.random()), 4.0))
    raise RuntimeError("unreachable")


def install_openai_permission_retry(
    llm_class: type,
    fallback_model: str | None = None,
    event_sink: Callable[[dict[str, Any]], None] | None = None,
) -> None:
    """Patch CrewAI's LLM call boundary once for this simulation process."""
    if getattr(llm_class.call, "_orgforge_permission_retry", False):
        return

    original_call = llm_class.call

    def resilient_call(self, *args: Any, **kwargs: Any) -> Any:
        try:
            return call_with_transient_permission_retry(
                lambda: original_call(self, *args, **kwargs),
                model=str(getattr(self, "model", "unknown")),
                event_sink=event_sink,
                emit_unrecovered=fallback_model is None,
            )
        except Exception as error:
            if not fallback_model or not _is_transient_permission_error(error):
                raise
            fallback_kwargs = {
                "model": fallback_model,
                "api": getattr(self, "api", None),
                "max_completion_tokens": getattr(self, "max_completion_tokens", None),
                "reasoning_effort": getattr(self, "reasoning_effort", None),
                "max_retries": getattr(self, "max_retries", 2),
            }
            fallback_kwargs = {k: v for k, v in fallback_kwargs.items() if v is not None}
            fallback = llm_class(**fallback_kwargs)
            _emit(
                event_sink,
                model=fallback_model,
                outcome="fallback",
                attempt=1,
                error=error,
            )
            return call_with_transient_permission_retry(
                lambda: original_call(fallback, *args, **kwargs),
                model=fallback_model,
                event_sink=event_sink,
                attempts=3,
            )

    resilient_call._orgforge_permission_retry = True
    llm_class.call = resilient_call


def install_responses_usage_logging(provider_class: type, logger: logging.Logger) -> None:
    """Expose Responses API token usage to the run-level spend guard."""
    original = provider_class._extract_responses_token_usage
    if getattr(original, "_orgforge_usage_logging", False):
        return

    def extract_and_log(self, response: Any) -> dict[str, Any]:
        usage = original(self, response)
        logger.info("OpenAI API usage: %s", usage)
        return usage

    extract_and_log._orgforge_usage_logging = True
    provider_class._extract_responses_token_usage = extract_and_log
