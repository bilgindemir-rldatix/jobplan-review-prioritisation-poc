from copy import deepcopy
from dataclasses import replace
import json

import numpy as np
import pandas as pd
import pytest

from jobplan_poc.dataset import demonstration_plans, generate_dataset
from jobplan_poc.evaluation import score_queue, temporal_split
from jobplan_poc.presentation import ViewConfig, export_json, export_payload
from jobplan_poc.rules import CATALOGUE, assess_rules
from jobplan_poc.scoring import fit_model, what_if


@pytest.fixture(scope="module")
def model():
    return fit_model(temporal_split(generate_dataset()).training)


def test_rules_trace_fidelity_from_sources_and_parameters():
    for record in generate_dataset(n=40, missing_rate=0).to_dict("records"):
        assessment = assess_rules(record)
        previous, current = record["versions"]["previous"], record["versions"]["current"]
        traces = assessment.traces
        assert traces[0].observed_difference == pytest.approx(
            abs(sum(a["pa"] for a in current["activities"]) / current["wte"]
                - sum(a["pa"] for a in previous["activities"]) / previous["wte"]))
        assert traces[1].observed_difference == pytest.approx(
            50 * sum(abs(traces[1].current[key] - traces[1].previous[key]) for key in traces[1].current))
        old_ids = {a["activity_id"] for a in previous["activities"]}
        new_ids = {a["activity_id"] for a in current["activities"]}
        assert traces[2].observed_difference == len(old_ids ^ new_ids) / len(old_ids | new_ids)
        old_slots, new_slots = set(previous["working_pattern"]), set(current["working_pattern"])
        assert traces[3].observed_difference == max(
            len(old_slots ^ new_slots) / len(old_slots | new_slots),
            abs(current["wte"] - previous["wte"]) / max(current["wte"], previous["wte"]))
        all_sites = traces[4].current.keys() | traces[4].previous.keys()
        assert traces[4].observed_difference == pytest.approx(
            0.5 * sum(abs(traces[4].current.get(key, 0) - traces[4].previous.get(key, 0)) for key in all_sites))
        for trace in traces:
            assert trace.points == pytest.approx(trace.weight * min(trace.observed_difference / trace.threshold, 1))
            assert trace.signal_strength == min(trace.observed_difference / trace.threshold, 1)
            assert trace.triggered == (trace.observed_difference >= trace.threshold)
            assert trace.state == "evaluated"
            assert trace.previous is not None and trace.current is not None
            assert trace.rationale and trace.version
        assert sum(trace.points for trace in traces) == pytest.approx(assessment.score.index)
        assert 0 <= assessment.score.index <= 100
        changed = deepcopy(record)
        changed["plan_id"] = "JP-CHANGED"
        for version in changed["versions"].values():
            version["plan_id"] = "JP-CHANGED"
        assert assess_rules(changed).score == assessment.score  # No ID jitter.
    changed_catalogue = tuple(replace(rule, threshold=rule.threshold * 2) for rule in CATALOGUE)
    assert assess_rules(record, changed_catalogue).score.index <= assess_rules(record).score.index
    with pytest.raises(ValueError):
        assess_rules(record, (replace(CATALOGUE[0], threshold=0), *CATALOGUE[1:]))


def test_semantic_scenarios_rules_zero_legitimate_missing_and_disagreement(model):
    scenarios = demonstration_plans().set_index("plan_id", drop=False)
    unchanged = assess_rules(scenarios.loc["JP-001"].to_dict())
    assert unchanged.score.index == 0 and not any(trace.triggered for trace in unchanged.traces)
    legitimate = assess_rules(scenarios.loc["JP-003"].to_dict())
    assert legitimate.traces[0].points == 0
    assert legitimate.traces[1].points == 0
    assert legitimate.traces[3].points == 15
    assert "entirely legitimate" in legitimate.traces[3].explanation
    for plan_id in ("JP-005", "JP-006", "JP-007"):
        assessment = assess_rules(scenarios.loc[plan_id].to_dict())
        assert assessment.score.index is None
        assert assessment.score.category == "Unscored"
        assert len(assessment.traces) == 5
        assert all(trace.state == "withheld" and trace.signal_strength is None
                   and trace.points is None and trace.observed_difference is None
                   for trace in assessment.traces)
    turnover = scenarios.loc["JP-008"].to_dict()
    waiting = scenarios.loc["JP-009"].to_dict()
    assert assess_rules(turnover).score.category == "High"
    assert model.score(turnover).index < 35
    assert assess_rules(waiting).score.index == 0
    assert model.score(waiting).index > 65
    # These properties arise from independent mechanisms, not desired-category hints.
    assert all("target" not in key and "hint" not in key for key in turnover)


def test_scenarios_rejected_by_fit_and_split(model):
    mixed = pd.DataFrame([*generate_dataset().to_dict("records"), *demonstration_plans().to_dict("records")])
    with pytest.raises(ValueError, match="evaluation"):
        temporal_split(mixed)
    with pytest.raises(ValueError, match="evaluation"):
        fit_model(mixed)


def test_linked_what_if_reconciles_and_does_not_mutate_source(model):
    record = demonstration_plans().iloc[0].to_dict()
    original = deepcopy(record)
    updates = {
        "current_total_pa": 5.0, "current_direct_care_pa": 3.5,
        "current_supporting_pa": 1.0, "current_other_pa": 0.5, "current_wte": 0.5,
    }
    scenario, rules, ml = what_if(record, updates, model)
    assert record == original
    assert rules == assess_rules(scenario).score
    assert ml == model.score(scenario)
    assert sum(a["pa"] for a in scenario["versions"]["current"]["activities"]) == 5
    assert rules.contributions["R-01 Total PA change per WTE"] == 0
    _, rules, ml = what_if(record, {"current_total_pa": 100}, model)
    assert rules.index is None and ml.index is None


def test_trace_exports_include_quality_and_versions(model):
    records = demonstration_plans()
    queue = score_queue(records, model)
    configuration = ViewConfig("Rules baseline", tuple(queue.specialty.unique()), tuple(queue.working_pattern.unique()),
                               tuple(queue.workflow_stage.unique()), ("Low", "Medium", "High"))
    payload = json.loads(export_json(export_payload(queue, configuration, model)))
    assert payload["metadata"]["scoring_version"] == "activity-change-v1"
    assert payload["metadata"]["export_schema_version"] == "2.0"
    for row in payload["plans"]:
        assert row["cohort"] == "demonstration"
        assert row["generator_version"] == "linked-activities-v1"
        assert row["rule_ids"] == ["R-01", "R-02", "R-03", "R-04", "R-05"]
        if row["baseline_index"] is None:
            assert row["data_quality_state"] == "Data clarification required"
            assert all(trace["points"] is None for trace in row["rule_traces"])
        else:
            assert sum(trace["points"] for trace in row["rule_traces"]) == pytest.approx(row["baseline_index"])
