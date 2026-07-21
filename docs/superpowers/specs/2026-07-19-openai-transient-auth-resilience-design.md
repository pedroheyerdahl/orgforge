# OpenAI transient-auth resilience design

## Goal

Make OpenAI-backed corpus simulations safe to run when the API intermittently
returns `401 insufficient permissions` for otherwise valid requests. A run must
either produce a traceable, complete corpus or stop with explicit recovery data;
it must not silently skip activities and appear valid.

## Scope

This applies to the OpenAI `openai_corpus` preset only. It does not change local
Ollama or Bedrock behavior.

## Behavior

1. Each OpenAI LLM call retries only the known transient response: HTTP 401 with
   `insufficient permissions`. Invalid-key and other authorization failures fail
   immediately.
2. Retries use bounded randomized exponential backoff. After retry exhaustion,
   the call may use the configured fallback model once, with its own bounded
   retry budget.
3. Every retry, recovery, fallback, and unrecovered failure is appended to a
   run ledger in `provenance/llm_resilience.jsonl`. Entries contain timestamps,
   model role/name, attempt number, outcome, and a redacted error class; no API
   keys or prompt contents are written.
4. The simulation tracks unrecovered LLM failures. The default error budget is
   three, configurable through `ORGFORGE_MAX_UNRECOVERED_LLM_FAILURES`.
5. When the budget is exceeded, the simulation raises a dedicated stop signal at
   the current activity boundary. The `finally` path still writes events, the
   resilience ledger, and a checkpoint describing the next simulation day.
6. A `--resume` run reads the checkpoint and resumes at the failed day without
   wiping Mongo or the export directory. `--reset` and `--resume` are mutually
   exclusive.

## Corpus validity contract

`provenance/run_status.json` is authoritative:

- `completed`: safe to package as a validation candidate.
- `stopped_error_budget`: safe for debugging or workload testing only; not for
  validation or the 180-day corpus.
- `failed_unexpectedly`: incomplete; investigate before reuse.

The exporter copies this run-status data and resilience ledger into the packaged
corpus provenance directory.

## Testing

Unit tests cover retry classification, jitter/backoff injection, fallback,
ledger redaction, error-budget exhaustion, checkpoint writing, and resume
argument validation. A five-day calibration is accepted only when
`run_status.json` reports `completed`, the event sidecar exists, and the ledger
contains no unrecovered failures.

## Cost control

Retries and fallback calls are bounded. The calibration keeps existing token
caps. The 180-day run remains unauthorized unless the five-day run completes
within the user’s $25 ceiling and without unrecovered failures.
