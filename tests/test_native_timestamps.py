from datetime import datetime, timedelta, timezone

from native_timestamps import iter_native_timestamps, rebase_native_timestamps


def test_classifies_historical_and_planned_native_timestamps_without_parsing_prose():
    payload = {
        "ts": "1767261600.125000",
        "edited": {"ts": "1767261660.500000"},
        "created_at": "2026-01-01T10:00:00+00:00",
        "updated_at": "2026-01-02T11:00:00+00:00",
        "comments": [
            {"timestamp": "2026-01-03T12:00:00+00:00", "text": "reviewed"}
        ],
        "due_date": "2026-02-15",
        "expected_close_date": "2026-03-01",
        "description": "The old note mentions 2027-01-01 but this is prose.",
    }

    values = list(iter_native_timestamps("git", payload))
    kinds = {value.path: value.kind for value in values}

    assert kinds[("ts",)] == "historical"
    assert kinds[("edited", "ts")] == "historical"
    assert kinds[("created_at",)] == "historical"
    assert kinds[("updated_at",)] == "historical"
    assert kinds[("comments", 0, "timestamp")] == "historical"
    assert kinds[("due_date",)] == "planned"
    assert kinds[("expected_close_date",)] == "planned"
    assert all(value.path != ("description",) for value in values)


def test_rebases_native_timestamps_without_changing_source_representation():
    payload = {
        "ts": "1767261600.125000",
        "created_at": "2026-01-01T10:00:00+00:00",
        "date": "2026-01-02",
        "comments": [{"timestamp": "2026-01-03T12:00:00"}],
        "due_date": "2026-02-15",
    }

    def mapper(value: datetime) -> datetime:
        return value.astimezone(timezone.utc) + timedelta(days=10, seconds=7)

    rebased = rebase_native_timestamps("slack", payload, mapper)

    assert rebased["ts"] == "1768125607.125000"
    assert rebased["created_at"] == "2026-01-11T10:00:07+00:00"
    assert rebased["date"] == "2026-01-12"
    assert rebased["comments"][0]["timestamp"] == "2026-01-13T12:00:07"
    assert rebased["due_date"] == "2026-02-25"
    assert payload["date"] == "2026-01-02"
