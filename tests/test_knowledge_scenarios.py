from collections import defaultdict
from datetime import datetime, timedelta, timezone

from knowledge_scenarios import apply_knowledge_scenarios
from source_actions import SourceAction, replay_actions


def test_knowledge_scenarios_span_sources_days_and_publish_pending_gold_labels():
    start = datetime(2026, 1, 1, 9, tzinfo=timezone.utc)
    anchors = [
        SourceAction(
            source_system="jira",
            object_id=f"ANCHOR-{index}",
            revision=1,
            operation="create",
            observed_at=(start + timedelta(days=index * 179)).isoformat(),
            effective_at=(start + timedelta(days=index * 179)).isoformat(),
            truth_event_ids=(f"EVT-{index}",),
            payload={"status": "open"},
        )
        for index in range(2)
    ]

    transformed, scenarios = apply_knowledge_scenarios(anchors, seed=42)

    required = {
        "stale_document",
        "superseded_owner",
        "provisional_as_final",
        "delayed_correction",
        "partial_correction",
        "unresolved_conflict",
    }
    counts = defaultdict(int)
    source_combinations = set()
    evidence_counts = set()
    observed_day_counts = set()
    durations = set()
    all_sources = set()
    for scenario in scenarios:
        counts[scenario["scenario_type"]] += 1
        assert scenario["review_status"] == "pending_human_review"
        assert len(scenario["source_systems"]) >= 2
        assert len(scenario["observed_days"]) >= 2
        assert len(scenario["evidence_action_ids"]) >= 3
        assert scenario["expected_state_by_day"]
        source_combinations.add(tuple(scenario["source_systems"]))
        evidence_counts.add(len(scenario["evidence_action_ids"]))
        observed_day_counts.add(len(scenario["observed_days"]))
        durations.add(scenario["duration_days"])
        all_sources.update(scenario["source_systems"])
    assert required <= set(counts)
    assert all(counts[name] >= 3 for name in required)
    assert len(set(counts.values())) >= 2
    assert len(source_combinations) >= 8
    assert all_sources == {"confluence", "slack", "jira", "email", "git", "zendesk"}
    assert len(evidence_counts) >= 4
    assert min(evidence_counts) == 3
    assert max(evidence_counts) >= 6
    assert len(observed_day_counts) >= 3
    assert len(durations) >= 6
    assert min(durations) <= 3
    assert max(durations) >= 21
    unresolved = [item for item in scenarios if item["resolution_state"] == "unresolved"]
    assert unresolved
    assert all(not item["correction_action_id"] for item in unresolved)
    replay_actions(transformed)
