import logging

from llm_resilience import (
    call_with_transient_permission_retry,
    install_openai_permission_retry,
    install_responses_usage_logging,
)


def test_retries_only_transient_insufficient_permission_errors():
    attempts = 0

    def flaky_call():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError(
                "Error code: 401 - You have insufficient permissions for this operation."
            )
        return "OK"

    assert call_with_transient_permission_retry(flaky_call, sleep=lambda _: None) == "OK"
    assert attempts == 3


def test_does_not_retry_other_authentication_errors():
    attempts = 0

    def invalid_key_call():
        nonlocal attempts
        attempts += 1
        raise RuntimeError("Incorrect API key provided")

    try:
        call_with_transient_permission_retry(invalid_key_call, sleep=lambda _: None)
    except RuntimeError as exc:
        assert "Incorrect API key" in str(exc)
    else:
        raise AssertionError("expected invalid key error")
    assert attempts == 1


def test_retry_emits_redacted_recovery_events():
    events = []
    attempts = 0

    def flaky_call():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("401 insufficient permissions prompt: never write this")
        return "OK"

    assert call_with_transient_permission_retry(
        flaky_call,
        model="gpt-5.6-terra",
        event_sink=events.append,
        sleep=lambda _: None,
    ) == "OK"
    assert [event["outcome"] for event in events] == ["retry", "retry", "recovered"]
    assert all("never write this" not in str(event) for event in events)


def test_invalid_key_emits_one_unrecovered_event_without_retry():
    events = []
    attempts = 0

    def invalid_key_call():
        nonlocal attempts
        attempts += 1
        raise RuntimeError("Incorrect API key provided")

    try:
        call_with_transient_permission_retry(
            invalid_key_call,
            model="gpt-5.6-terra",
            event_sink=events.append,
            sleep=lambda _: None,
        )
    except RuntimeError as exc:
        assert "Incorrect API key" in str(exc)
    else:
        raise AssertionError("expected invalid key error")
    assert attempts == 1
    assert [event["outcome"] for event in events] == ["unrecovered"]


def test_fallback_recovery_does_not_emit_unrecovered_event():
    events = []
    constructed = []

    class FakeLLM:
        def __init__(self, model, api=None, **_):
            self.model = model
            self.api = api
            constructed.append((model, api))

        def call(self, *_args, **_kwargs):
            if self.model == "primary":
                raise RuntimeError("401 insufficient permissions")
            return "OK"

    install_openai_permission_retry(FakeLLM, "fallback", event_sink=events.append)

    assert FakeLLM("primary", api="responses").call("prompt") == "OK"
    assert ("fallback", "responses") in constructed
    assert "fallback" in [event["outcome"] for event in events]
    assert "unrecovered" not in [event["outcome"] for event in events]


def test_responses_usage_is_logged_for_spend_guard(caplog):
    class FakeProvider:
        def _extract_responses_token_usage(self, _response):
            return {"prompt_tokens": 123, "completion_tokens": 45, "total_tokens": 168}

    logger = logging.getLogger("test.responses.usage")
    install_responses_usage_logging(FakeProvider, logger)

    with caplog.at_level(logging.INFO, logger=logger.name):
        usage = FakeProvider()._extract_responses_token_usage(object())

    assert usage["total_tokens"] == 168
    assert "OpenAI API usage: {'prompt_tokens': 123" in caplog.text
