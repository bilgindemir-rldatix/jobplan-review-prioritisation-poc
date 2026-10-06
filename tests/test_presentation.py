import csv
import io
import json

import numpy as np
import pandas as pd
import pytest

from jobplan_poc.evaluation import score_queue, temporal_split
from jobplan_poc.presentation import (
    ViewConfig, export_csv, export_json, export_payload, filtered_queue,
    priority_distribution, workload_groups,
)
from jobplan_poc.scoring import fit_model, what_if
from jobplan_poc.synthetic import generate_plans


@pytest.fixture(scope="module")
def demo():
    split = temporal_split(generate_plans())
    model = fit_model(split.training)
    queue = score_queue(split.test, model)
    return split, model, queue


def config(queue, **overrides):
    values = dict(ranking="Experimental ML", specialties=tuple(queue.specialty.unique()),
                  patterns=tuple(queue.working_pattern.unique()), stages=tuple(queue.workflow_stage.unique()),
                  priorities=("Low", "Medium", "High"))
    return ViewConfig(**{**values, **overrides})


def test_shared_scope_search_and_triage(demo):
    _, _, queue = demo
    pd.testing.assert_frame_equal(filtered_queue(queue, config(queue)).sort_index(), queue.sort_index())
    for field in ("plan_id", "specialty", "department"):
        phrase = queue.iloc[0][field]
        view = filtered_queue(queue, config(queue, search=phrase.upper()))
        assert not view.empty
        assert view[field].str.casefold().eq(phrase.casefold()).all()
    assert not filtered_queue(queue, config(queue, search="workflow")).empty
    assert filtered_queue(queue, config(queue, search=".*")).empty  # Literal, not regex.
    assert filtered_queue(queue.iloc[:0], config(queue, search="anything")).empty
    assert filtered_queue(queue, config(queue, search="FIC-", specialties=())).empty
    triage = filtered_queue(queue, config(queue, priorities=()))
    assert len(triage) == queue.baseline_index.isna().sum()
    assert triage.baseline_index.isna().all()
    assert filtered_queue(queue, config(queue, search="previous_total_pa")).baseline_index.isna().all()
    high = filtered_queue(queue, config(queue, ranking="Rules baseline", priorities=("High",)))
    assert high.baseline_category.isin(["High", "Unscored"]).all()
    assert priority_distribution(high, "baseline").scored_plans.sum() == high.baseline_index.notna().sum()


def test_group_denominators_zero_and_small_groups():
    view = pd.DataFrame({
        "department": ["A", "A", "A", "B"], "specialty": ["X", "X", "Y", "Y"],
        "baseline_index": [80., 10., np.nan, np.nan],
        "baseline_category": ["High", "Low", "Unscored", "Unscored"],
        "model_index": [20., 10., np.nan, np.nan],
        "model_category": ["Low", "Low", "Unscored", "Unscored"],
    })
    groups = workload_groups(view, "department", "baseline").set_index("department")
    assert groups.loc["A", "total_plans"] == 3
    assert groups.loc["A", "scored_plans"] == 2
    assert groups.loc["A", "unscored_plans"] == 1
    assert groups.loc["A", "high_priority_rate_among_scored"] == 0.5
    assert groups.loc["A", "high_priority_plans"] == 1
    assert pd.isna(groups.loc["B", "high_priority_rate_among_scored"])
    assert "Small" in groups.loc["A", "interpretation"]
    baseline = workload_groups(view, "specialty", "baseline").set_index("specialty")
    model = workload_groups(view, "specialty", "model").set_index("specialty")
    assert baseline.loc["Y", "high_priority_plans"] == 0
    assert baseline.loc["X", "high_priority_plans"] == 1
    assert model.loc["X", "high_priority_plans"] == 0
    assert workload_groups(view.iloc[:0], "department", "model").empty
    larger = pd.concat([view.iloc[[0]]] * 5, ignore_index=True)
    assert "Small" not in workload_groups(larger, "department", "baseline").iloc[0]["interpretation"]


def test_exports_deterministic_numeric_faithful_and_unscored(demo):
    _, model, queue = demo
    configuration = config(queue)
    payload = export_payload(queue, configuration, model)
    text = export_json(payload)
    assert text == export_json(export_payload(queue, configuration, model))
    decoded = json.loads(text, parse_constant=lambda value: pytest.fail(f"Invalid JSON constant: {value}"))
    assert decoded["metadata"]["row_count"] == len(queue)
    assert decoded["metadata"]["unscored_count"] == 5
    assert decoded["metadata"]["priority_source"] == "model"
    assert decoded["metadata"]["scoring_version"] == "rules-v1"
    assert decoded["metadata"]["model_version"] == "standardised-logistic-v1"
    assert decoded["metadata"]["export_schema_version"] == "1.0"
    for plan in decoded["plans"]:
        original = queue.set_index("plan_id").loc[plan["plan_id"]]
        assert "material_amendment" not in plan
        if plan["baseline_index"] is None:
            assert plan["model_index"] is None and plan["model_decision"] is None
            assert plan["baseline_category"] == "Unscored"
            assert plan["input_errors"]
        else:
            assert isinstance(plan["baseline_index"], float)
            assert plan["baseline_index"] == original.baseline_index
            assert sum(plan["baseline_contributions"].values()) == pytest.approx(plan["baseline_index"])
            assert plan["model_intercept"] + sum(plan["model_contributions"].values()) == pytest.approx(plan["model_decision"])
            assert plan["model_index"] == original.model_index
            assert plan["model_contributions"] == original.model_contributions
    csv_text = export_csv(payload, list(queue.columns))
    assert csv_text == export_csv(export_payload(queue, configuration, model), list(queue.columns))
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    assert rows[0]["record_type"] == "scope"
    assert json.loads(rows[0]["scope_metadata_json"]) == decoded["metadata"]
    assert len(rows) == len(queue) + 1
    for csv_row, plan in zip(rows[1:], decoded["plans"]):
        assert csv_row["record_type"] == "plan"
        assert csv_row["plan_id"] == plan["plan_id"]
        assert json.loads(csv_row["model_contributions"]) == plan["model_contributions"]
        if plan["model_index"] is None:
            assert csv_row["model_index"] == ""
        else:
            assert float(csv_row["model_index"]) == plan["model_index"]


def test_empty_export_has_scope_and_csv_formula_safety(demo):
    _, model, queue = demo
    empty = export_payload(queue, config(queue, search="not a matching plan"), model)
    assert json.loads(export_json(empty))["plans"] == []
    rows = list(csv.DictReader(io.StringIO(export_csv(empty, list(queue.columns)))))
    assert len(rows) == 1 and rows[0]["record_type"] == "scope"
    assert json.loads(rows[0]["scope_metadata_json"])["row_count"] == 0
    for unsafe in ("=2+2", "+SUM(1,1)", "-formula", "@SUM(1,1)", "  =2+2", "\ttext", "\ntext"):
        payload = {"metadata": {}, "plans": [{"plan_id": unsafe, "model_decision": -1.5}]}
        row = list(csv.DictReader(io.StringIO(export_csv(payload, ["plan_id", "model_decision"]))))[1]
        assert row["plan_id"] == "'" + unsafe
        assert row["model_decision"] == "-1.5"
        assert json.loads(export_json(payload))["plans"][0]["plan_id"] == unsafe


def test_export_filter_scope_and_what_if_isolation(demo):
    split, model, queue = demo
    configuration = config(queue, search="Radiology", ranking="Rules baseline")
    before = export_json(export_payload(queue, configuration, model))
    original = queue.copy(deep=True)
    groups = workload_groups(filtered_queue(queue, configuration), "department", "baseline")
    record = split.test.dropna().iloc[0].to_dict()
    what_if(record, {"completeness_percent": 100.0}, model)
    assert export_json(export_payload(queue, configuration, model)) == before
    pd.testing.assert_frame_equal(queue, original)
    pd.testing.assert_frame_equal(workload_groups(filtered_queue(queue, configuration), "department", "baseline"), groups)
    decoded = json.loads(before)
    assert decoded["metadata"]["filters"]["search"] == "radiology"
    assert decoded["metadata"]["priority_source"] == "baseline"
    assert all(plan["specialty"] == "Radiology" for plan in decoded["plans"])
    triage_only = export_payload(queue, config(queue, priorities=()), model)
    assert triage_only["metadata"]["scored_count"] == 0
    assert triage_only["metadata"]["unscored_count"] == 5
    assert all(plan["model_index"] is None for plan in triage_only["plans"])


def test_absent_completeness_and_missing_date_export_unscored(demo):
    split, model, _ = demo
    records = split.test.head(1).drop(columns="completeness_percent").copy()
    records["snapshot_date"] = pd.NaT
    queue = score_queue(records, model)
    payload = json.loads(export_json(export_payload(queue, config(queue), model)))
    plan = payload["plans"][0]
    assert plan["completeness_percent"] is None
    assert plan["snapshot_date"] is None
    assert plan["baseline_index"] is None and plan["model_index"] is None
    assert any("completeness_percent" in error for error in plan["input_errors"])
