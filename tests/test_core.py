from math import exp

import numpy as np
import pandas as pd
import pytest

from jobplan_poc.evaluation import budget_metrics, compare_methods, rank_queue, score_queue, temporal_split
from jobplan_poc.features import FEATURE_NAMES, extract_features, feature_frame
from jobplan_poc.scoring import category, fit_model, score_baseline, what_if
from jobplan_poc.synthetic import REFERENCE_DATE, TEST_START, generate_plans


@pytest.fixture(scope="module")
def records():
    return generate_plans()


@pytest.fixture(scope="module")
def fitted(records):
    split = temporal_split(records)
    return split, fit_model(split.training)


@pytest.fixture
def record(records):
    return records.dropna().iloc[0].to_dict()


def test_generation_reproducible_and_fictional(records):
    pd.testing.assert_frame_equal(records, generate_plans())
    assert not records.equals(generate_plans(seed=9))
    assert records["plan_id"].str.startswith("FIC-").all()
    assert records["entity_id"].is_unique
    assert records["plan_id"].is_unique
    assert records["working_pattern"].nunique() == 2
    assert records["specialty"].nunique() == 4
    assert (records["outcome_observed_date"] <= REFERENCE_DATE).all()
    assert records["material_amendment"].nunique() == 2
    assert records["previous_total_pa"].isna().any()
    # Missingness must not change latent complete data or labels.
    complete = generate_plans(missing_rate=0)
    pd.testing.assert_series_equal(complete["material_amendment"], records["material_amendment"])
    pd.testing.assert_series_equal(complete["current_total_pa"], records["current_total_pa"])


@pytest.mark.parametrize("n,missing_rate", [(1, 0), (True, 0), (20, -0.1), (20, 1.1), (20, np.nan)])
def test_invalid_generation(n, missing_rate):
    with pytest.raises(ValueError):
        generate_plans(n=n, missing_rate=missing_rate)


@pytest.mark.parametrize("index,expected", [(0, "Low"), (34.999, "Low"), (35, "Medium"),
                                          (64.999, "Medium"), (65, "High"), (100, "High")])
def test_categories(index, expected):
    assert category(index) == expected


@pytest.mark.parametrize("index", [-1, 100.01, np.nan, np.inf, True, np.bool_(True), None, "35"])
def test_invalid_index(index):
    with pytest.raises(ValueError):
        category(index)


def test_bounds_and_deterministic_fit(records, fitted):
    split, model = fitted
    repeated_model = fit_model(split.training)
    for record in records.to_dict("records"):
        baseline = score_baseline(record)
        ml = model.score(record)
        if not extract_features(record).sufficient:
            assert baseline.index is None and ml.index is None
            assert baseline.category == ml.category == "Unscored"
            assert baseline.errors and ml.errors
            assert "human triage" in baseline.action
        else:
            assert 0 <= baseline.index <= 100
            assert 0 <= ml.index <= 100
            assert sum(baseline.contributions.values()) == pytest.approx(baseline.index)
            assert repeated_model.score(record).index == pytest.approx(ml.index)


@pytest.mark.parametrize("field,value", [
    ("current_total_pa", None), ("previous_total_pa", np.nan),
    ("current_wte", 0), ("previous_wte", -0.3), ("current_wte", np.inf),
    ("current_wte", "0.8"), ("current_wte", True),
    ("current_direct_care_pa", -1), ("current_supporting_pa", 500),
    ("previous_other_pa", -0.1), ("completeness_percent", -1),
    ("completeness_percent", 101), ("snapshot_date", None),
    ("snapshot_date", "not-a-date"), ("review_due_date", pd.NaT),
    ("snapshot_date", "2024-01-01T12:00:00"), ("snapshot_date", "2024-01-01T00:00:00Z"),
    ("workflow_started_date", "2099-01-01"),
])
def test_missing_or_invalid_unscored(record, fitted, field, value):
    _, model = fitted
    record[field] = value
    result = extract_features(record)
    assert not result.sufficient
    assert result.errors
    for score in (score_baseline(record), model.score(record)):
        assert score.index is None
        assert score.category == "Unscored"
        assert score.contributions == {}
        assert score.sufficiency == "Insufficient required data"


def test_absent_required_field(record):
    del record["review_due_date"]
    assert not extract_features(record).sufficient


def test_working_pattern_normalisation_and_rules(record):
    for suffix in ("total_pa", "direct_care_pa", "supporting_pa", "other_pa"):
        record[f"current_{suffix}"] = record[f"previous_{suffix}"] * 0.5
    record["current_wte"] = record["previous_wte"] * 0.5
    record["workflow_started_date"] = record["snapshot_date"]
    record["review_due_date"] = record["snapshot_date"] + pd.Timedelta(1, unit="D")
    record["completeness_percent"] = 100.0
    features = extract_features(record).values
    assert features["activity_change_per_wte"] == pytest.approx(0)
    assert features["direct_care_mix_change_pp"] == pytest.approx(0)
    assert score_baseline(record).index == pytest.approx(0)
    record["workflow_started_date"] -= pd.Timedelta(500, unit="D")
    record["review_due_date"] -= pd.Timedelta(500, unit="D")
    record["completeness_percent"] = 0
    assert score_baseline(record).index == pytest.approx(55)


def test_all_rules_saturate_at_100(record):
    record.update({
        "current_total_pa": 15.0, "current_direct_care_pa": 6.0,
        "current_supporting_pa": 6.0, "current_other_pa": 3.0, "current_wte": 1.0,
        "previous_total_pa": 10.0, "previous_direct_care_pa": 8.0,
        "previous_supporting_pa": 2.0, "previous_other_pa": 0.0, "previous_wte": 1.0,
        "completeness_percent": 0.0,
        "workflow_started_date": record["snapshot_date"] - pd.Timedelta(200, unit="D"),
        "review_due_date": record["snapshot_date"] - pd.Timedelta(200, unit="D"),
    })
    score = score_baseline(record)
    assert score.index == 100
    assert score.category == "High"
    assert list(score.contributions.values()) == [25, 20, 20, 20, 15]


def test_exact_model_contributions_and_no_outcome_input(record, fitted):
    _, model = fitted
    score = model.score(record)
    frame = pd.DataFrame([extract_features(record).values], columns=FEATURE_NAMES)
    expected = model.pipeline.decision_function(frame)[0]
    assert score.intercept + sum(score.contributions.values()) == pytest.approx(expected, abs=1e-12)
    assert score.decision == pytest.approx(expected, abs=1e-12)
    assert score.index == pytest.approx(100 / (1 + exp(-expected)))
    assert score.explanation_space == "signed model log-odds units"
    altered = {**record, "material_amendment": 1 - record["material_amendment"],
               "outcome_observed_date": "2099-01-01", "plan_id": "different",
               "entity_id": "different", "specialty": "different", "workflow_stage": "different"}
    assert model.score(altered) == score
    assert score_baseline(altered) == score_baseline(record)
    means = model.pipeline.named_steps["scale"].mean_
    reference = pd.DataFrame([means], columns=FEATURE_NAMES)
    assert model.pipeline.decision_function(reference)[0] == pytest.approx(score.intercept)


def test_temporal_and_entity_separation(records, fitted):
    split, model = fitted
    assert split.training["snapshot_date"].max() < split.test["snapshot_date"].min()
    assert (split.training["outcome_observed_date"] < TEST_START).all()
    assert (split.test["snapshot_date"] >= TEST_START).all()
    assert not set(split.training["entity_id"]) & set(split.test["entity_id"])
    assert not set(split.training["plan_id"]) & set(split.test["plan_id"])
    frame, _ = feature_frame(split.training)
    np.testing.assert_allclose(model.pipeline.named_steps["scale"].mean_, frame.mean().values)
    changed = records.copy(deep=True)
    held_out_entity = split.test.iloc[0]["entity_id"]
    changed.loc[changed.index[0], "entity_id"] = held_out_entity
    regrouped = temporal_split(changed)
    assert held_out_entity not in set(regrouped.training["entity_id"])
    assert len(regrouped.training) == len(split.training) - 1
    # Changing future values cannot affect fitting.
    changed = records.copy(deep=True)
    changed.loc[split.test.index, "current_total_pa"] = 9999
    changed.loc[split.test.index, "material_amendment"] = 1
    refitted = fit_model(temporal_split(changed).training)
    np.testing.assert_array_equal(model.pipeline.named_steps["model"].coef_, refitted.pipeline.named_steps["model"].coef_)


def test_split_rejects_invalid_identity_and_outcome_dates(records):
    for field, value in [("plan_id", None), ("entity_id", None), ("outcome_observed_date", pd.NaT)]:
        changed = records.copy()
        changed.loc[0, field] = value
        with pytest.raises(ValueError):
            temporal_split(changed)
    duplicate = pd.concat([records, records.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="unique"):
        temporal_split(duplicate)
    with pytest.raises(ValueError, match="non-empty"):
        temporal_split(records.head(20))


def test_no_data_or_single_class_model_unavailable(fitted):
    split, _ = fitted
    with pytest.raises(ValueError, match="at least 10"):
        fit_model(split.training.head(3))
    single_class = split.training.copy()
    single_class["material_amendment"] = 0
    with pytest.raises(ValueError, match="both binary"):
        fit_model(single_class)


def test_ranking_ties_unscored_and_budget_edges():
    queue = pd.DataFrame({"plan_id": ["B", "C", "A", "D"], "model_index": [50.0, None, 50.0, 10.0]})
    ranked = rank_queue(queue, "model_index")
    assert ranked["plan_id"].tolist() == ["A", "B", "D"]
    outcomes = pd.Series({"A": 1, "B": 0, "D": 1})
    metrics = budget_metrics(ranked, outcomes, 2)
    assert metrics["amendments_found"] == 1
    assert metrics["precision_at_k"] == 0.5
    assert metrics["recall_at_k"] == 0.5
    assert budget_metrics(ranked, outcomes, 50)["reviewed"] == 3
    no_positives = budget_metrics(ranked, outcomes * 0, 2)
    assert no_positives["precision_at_k"] == 0
    assert no_positives["recall_at_k"] is None
    empty = budget_metrics(ranked.iloc[:0], outcomes, 2)
    assert empty["reviewed"] == 0
    assert empty["precision_at_k"] is None and empty["recall_at_k"] is None
    for invalid_budget in (0, -1, True, 1.5):
        with pytest.raises(ValueError):
            budget_metrics(ranked, outcomes, invalid_budget)
    with pytest.raises(ValueError, match="known binary"):
        budget_metrics(ranked, outcomes.drop("A"), 2)
    with pytest.raises(ValueError, match="Unknown"):
        rank_queue(queue, "plan_id")
    with pytest.raises(ValueError, match="finite"):
        rank_queue(pd.DataFrame({"plan_id": ["A"], "model_index": [np.inf]}), "model_index")
    with pytest.raises(ValueError, match="unique"):
        rank_queue(pd.concat([queue, queue]), "model_index")
    with pytest.raises(ValueError, match="unique"):
        budget_metrics(ranked, pd.concat([outcomes, outcomes]), 2)


def test_common_cohort_and_empty_queue(fitted):
    split, model = fitted
    queue = score_queue(split.test, model)
    labels = split.test.set_index("plan_id")["material_amendment"]
    comparison = compare_methods(queue, labels, 30)
    assert comparison["cohort"].nunique() == 1
    assert comparison["reviewed"].nunique() == 1
    assert comparison["positives"].nunique() == 1
    assert comparison.iloc[0]["cohort"] == queue["baseline_index"].notna().sum()
    assert comparison["amendments_found"].tolist() == [8, 6, 7]
    empty = score_queue(split.test.iloc[:0], model)
    assert rank_queue(empty, "model_index").empty
    metrics = compare_methods(empty, labels, 30)
    assert (metrics["reviewed"] == 0).all()
    assert metrics["precision_at_k"].isna().all()
    assert metrics["recall_at_k"].isna().all()


def test_target_not_baseline_threshold(fitted):
    split, model = fitted
    queue = score_queue(split.test, model)
    scored = queue.dropna(subset=["baseline_index"]).set_index("plan_id")
    labels = split.test.set_index("plan_id").loc[scored.index, "material_amendment"]
    for threshold in [35, 65]:
        assert (labels != (scored["baseline_index"] >= threshold).astype(int)).any()


def test_what_if_consistency_and_isolation(record, fitted):
    _, model = fitted
    original = record.copy()
    baseline = score_baseline(record)
    ml = model.score(record)
    unchanged, unchanged_baseline, unchanged_ml = what_if(record, {}, model)
    assert unchanged == original and unchanged is not record
    assert unchanged_baseline == baseline and unchanged_ml == ml
    scenario, scenario_baseline, scenario_ml = what_if(record, {"completeness_percent": 100.0}, model)
    assert record == original
    assert scenario_baseline == score_baseline(scenario)
    assert scenario_ml == model.score(scenario)
    assert scenario_baseline.index <= baseline.index
    _, invalid_baseline, invalid_ml = what_if(record, {"current_wte": 0}, model)
    assert invalid_baseline.index is None and invalid_ml.index is None
    with pytest.raises(ValueError, match="supported"):
        what_if(record, {"material_amendment": 0}, model)
