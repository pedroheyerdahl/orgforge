# OpenAI Transient-Auth Resilience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make OpenAI corpus simulations either complete with auditable resilience metadata or stop cleanly before an invalid corpus is mistaken for a valid one.

**Architecture:** Keep retry/fallback policy in `src/llm_resilience.py`; expose an event sink that records only redacted metadata. `flow.py` owns run state, error budget, checkpointing, and CLI resume validation. The corpus exporter copies run state and the resilience ledger into packaged provenance.

**Tech Stack:** Python 3.13, CrewAI, OpenAI SDK, MongoDB Atlas Local, pytest.

## Global Constraints

- Apply resilience behavior only when `quality_preset` uses provider `openai`.
- Retry only 401 errors containing `insufficient permissions`; invalid keys and all other errors fail immediately.
- Do not write prompts, completions, API keys, or request headers to provenance.
- Default unrecovered-failure budget is exactly `3`; override only with `ORGFORGE_MAX_UNRECOVERED_LLM_FAILURES`.
- `--reset` and `--resume` must be mutually exclusive.
- A corpus with `stopped_error_budget` or `failed_unexpectedly` is never validation-ready.

---

### Task 1: Make retry outcomes observable

**Files:**
- Modify: `src/llm_resilience.py`
- Modify: `tests/test_llm_resilience.py`

**Interfaces:**
- Produces: `ResilienceEvent` with fields `timestamp`, `outcome`, `model`, `attempt`, and `error_class`.
- Produces: `call_with_transient_permission_retry(call, *, model, event_sink, attempts=8, sleep=time.sleep)`.
- Produces: `install_openai_permission_retry(llm_class, fallback_model, event_sink)`.

- [ ] **Step 1: Write the failing tests**

```python
def test_retry_emits_redacted_recovery_events():
    events = []
    attempts = 0
    def flaky_call():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError('401 insufficient permissions secret prompt')
        return 'OK'
    assert call_with_transient_permission_retry(
        flaky_call, model='gpt-5.6-terra', event_sink=events.append, sleep=lambda _: None
    ) == 'OK'
    assert [event['outcome'] for event in events] == ['retry', 'retry', 'recovered']
    assert all('secret prompt' not in str(event) for event in events)

def test_invalid_key_emits_unrecovered_without_retry():
    events = []
    with pytest.raises(RuntimeError, match='Incorrect API key'):
        call_with_transient_permission_retry(
            lambda: (_ for _ in ()).throw(RuntimeError('Incorrect API key')),
            model='gpt-5.6-terra', event_sink=events.append, sleep=lambda _: None,
        )
    assert [event['outcome'] for event in events] == ['unrecovered']
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose run --rm -v "$PWD/tests:/app/tests:ro" orgforge uv run --no-project pytest -q /app/tests/test_llm_resilience.py`

Expected: FAIL because the retry function does not accept `model` and `event_sink`.

- [ ] **Step 3: Implement event emission**

```python
def _event(model: str, outcome: str, attempt: int, error: BaseException | None = None) -> dict:
    return {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'model': model,
        'outcome': outcome,
        'attempt': attempt,
        'error_class': type(error).__name__ if error else None,
    }
```

Call `event_sink(_event(...))` before each retry, after a recovered retry, and before each unrecovered raise. Pass the primary/fallback model name through the CrewAI patch.

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose run --rm -v "$PWD/tests:/app/tests:ro" orgforge uv run --no-project pytest -q /app/tests/test_llm_resilience.py`

Expected: PASS.

### Task 2: Add run ledger, status, and error budget

**Files:**
- Create: `src/run_resilience.py`
- Modify: `src/flow.py`
- Create: `tests/test_run_resilience.py`

**Interfaces:**
- Produces: `RunResilience(export_dir: Path, max_unrecovered: int)`.
- Produces: `record(event: dict) -> None`, `record_unrecovered() -> None`, `should_stop() -> bool`, `write_status(status: str, next_day: int | None) -> None`.
- Consumes: retry events from Task 1 through the event sink passed from `build_llm`.

- [ ] **Step 1: Write the failing tests**

```python
def test_error_budget_writes_stopped_status_and_checkpoint(tmp_path):
    resilience = RunResilience(tmp_path, max_unrecovered=2)
    resilience.record({'outcome': 'unrecovered', 'model': 'gpt-5.6-terra'})
    resilience.record({'outcome': 'unrecovered', 'model': 'gpt-5.6-terra'})
    assert resilience.should_stop() is True
    resilience.write_status('stopped_error_budget', next_day=4)
    status = json.loads((tmp_path / 'provenance/run_status.json').read_text())
    assert status == {'status': 'stopped_error_budget', 'next_day': 4, 'unrecovered_llm_failures': 2}
    assert len((tmp_path / 'provenance/llm_resilience.jsonl').read_text().splitlines()) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose run --rm -v "$PWD/tests:/app/tests:ro" orgforge uv run --no-project pytest -q /app/tests/test_run_resilience.py`

Expected: FAIL with `ModuleNotFoundError: No module named 'run_resilience'`.

- [ ] **Step 3: Implement the run-state object**

```python
class RunResilience:
    def __init__(self, export_dir: Path, max_unrecovered: int = 3):
        self.provenance_dir = export_dir / 'provenance'
        self.max_unrecovered = max_unrecovered
        self.unrecovered = 0

    def should_stop(self) -> bool:
        return self.unrecovered >= self.max_unrecovered
```

Append JSON lines in `record`, increment `unrecovered` only for outcome `unrecovered`, and write both `run_status.json` and `resume_checkpoint.json` in `write_status`.

- [ ] **Step 4: Connect it to `flow.py`**

Create one `RunResilience` instance using `EXPORT_DIR` and the environment override. Pass `resilience.record` into `install_openai_permission_retry`. Before starting each simulation day, raise `ResilienceBudgetExceeded` when `resilience.should_stop()` is true. In `OrgForgeSimulation.run()`, write `completed`, `stopped_error_budget`, or `failed_unexpectedly` from the `try/except/finally` path while always writing the event sidecar.

- [ ] **Step 5: Run tests to verify they pass**

Run: `docker compose run --rm -v "$PWD/tests:/app/tests:ro" orgforge uv run --no-project pytest -q /app/tests/test_run_resilience.py /app/tests/test_llm_resilience.py`

Expected: PASS.

### Task 3: Add safe day-boundary resume

**Files:**
- Modify: `src/flow.py`
- Modify: `tests/test_run_resilience.py`

**Interfaces:**
- Produces: CLI flag `--resume`.
- Consumes: `provenance/resume_checkpoint.json` with `next_day`.

- [ ] **Step 1: Write the failing tests**

```python
def test_resume_rejects_reset_and_uses_checkpoint_day(tmp_path, monkeypatch):
    checkpoint = tmp_path / 'provenance/resume_checkpoint.json'
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_text(json.dumps({'next_day': 4}))
    assert load_resume_day(tmp_path) == 4
    with pytest.raises(ValueError, match='mutually exclusive'):
        validate_run_flags(reset=True, resume=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose run --rm -v "$PWD/tests:/app/tests:ro" orgforge uv run --no-project pytest -q /app/tests/test_run_resilience.py`

Expected: FAIL because `load_resume_day` and `validate_run_flags` do not exist.

- [ ] **Step 3: Implement resume validation and state restoration**

```python
def validate_run_flags(reset: bool, resume: bool) -> None:
    if reset and resume:
        raise ValueError('--reset and --resume are mutually exclusive')

def load_resume_day(export_dir: Path) -> int:
    checkpoint = json.loads((export_dir / 'provenance/resume_checkpoint.json').read_text())
    return int(checkpoint['next_day'])
```

Add `--resume`; on resume, do not call genesis reset and set the simulation day to the checkpoint day before `daily_cycle` starts. Remove the checkpoint only after writing `completed`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose run --rm -v "$PWD/tests:/app/tests:ro" orgforge uv run --no-project pytest -q /app/tests/test_run_resilience.py`

Expected: PASS.

### Task 4: Package resilience provenance and validate a controlled failure

**Files:**
- Modify: `src/clearweave_corpus.py`
- Modify: `tests/test_clearweave_corpus.py`

**Interfaces:**
- Consumes: `provenance/run_status.json`, `provenance/llm_resilience.jsonl`, and `provenance/resume_checkpoint.json` from Tasks 2-3.
- Produces: identical files in packaged corpus `provenance/`.

- [ ] **Step 1: Write the failing test**

```python
def test_export_corpus_copies_run_resilience_provenance(tmp_path):
    source = tmp_path / 'export'
    provenance = source / 'provenance'
    provenance.mkdir(parents=True)
    (provenance / 'run_status.json').write_text('{"status":"completed"}')
    (provenance / 'llm_resilience.jsonl').write_text('{"outcome":"recovered"}\n')
    output = tmp_path / 'corpus'
    export_corpus(source, output)
    assert (output / 'provenance/run_status.json').exists()
    assert (output / 'provenance/llm_resilience.jsonl').exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose run --rm -v "$PWD/tests:/app/tests:ro" orgforge uv run --no-project pytest -q /app/tests/test_clearweave_corpus.py`

Expected: FAIL because the resilience files are not copied.

- [ ] **Step 3: Implement provenance copying**

```python
for filename in ('run_status.json', 'llm_resilience.jsonl', 'resume_checkpoint.json'):
    source_file = export_dir / 'provenance' / filename
    if source_file.exists():
        shutil.copyfile(source_file, provenance / filename)
```

- [ ] **Step 4: Run focused regression tests**

Run: `docker compose run --rm -v "$PWD/tests:/app/tests:ro" orgforge uv run --no-project pytest -q /app/tests/test_llm_resilience.py /app/tests/test_run_resilience.py /app/tests/test_clearweave_corpus.py`

Expected: PASS.

- [ ] **Step 5: Run controlled failure verification**

Run the simulation with an injected always-failing OpenAI call in a test fixture. Verify `run_status.json` is `stopped_error_budget`, `simulation_events.jsonl` exists, the checkpoint has the next day, and package export preserves all three provenance files.
