import numpy as np
import pandas as pd
import pytest

from jobplan_poc.dataset import demonstration_plans, generate_dataset
from jobplan_poc.evaluation import (
    budget_metrics, compare_methods, experiment_report, rank_queue, score_queue, temporal_split,
)
from jobplan_poc.scoring import fit_model


@pytest.fixture(scope="module")
def evaluated():
    split = temporal_split(generate_dataset())
    model = fit_model(split.training)
    return score_queue(split.test, model), split.test.set_index("plan_id")["material_amendment"], model


def test_random_baseline_same_cohort_reproducible_and_independent_of_input_order(evaluated):
    queue, outcomes, _ = evaluated
    report = experiment_report(queue, outcomes, 30)
    repeated = experiment_report(queue.sample(frac=1, random_state=2), outcomes, 30)
    pd.testing.assert_frame_equal(report.metrics, repeated.metrics)
    pd.testing.assert_frame_equal(report.random_runs, repeated.random_runs)
    assert report.metrics.reviewed.tolist() == [30] * 5
    assert report.metrics.cohort.tolist() == [128] * 5
    assert report.metrics.positives.tolist() == [25] * 5
    assert report.metrics.amendments_found.tolist()[:4] == [8, 6, 7, 8]
    summary = report.metrics.iloc[-1]
    assert len(report.random_runs) == 100
    assert summary.amendments_found == pytest.approx(report.random_runs.amendments_found.mean())
    assert summary.amendments_found_std == pytest.approx(report.random_runs.amendments_found.std(ddof=0))
    assert summary.amendments_found_min == report.random_runs.amendments_found.min()
    assert summary.amendments_found_max == report.random_runs.amendments_found.max()
    assert not experiment_report(queue, outcomes, 30, seed=9).random_runs.equals(report.random_runs)


def test_overlap_disagreements_match_actual_ranking(evaluated):
    queue, outcomes, _ = evaluated
    report = experiment_report(queue, outcomes, 30)
    rules = set(rank_queue(queue, "baseline_index").head(30).plan_id)
    ml = set(rank_queue(queue, "model_index").head(30).plan_id)
    assert report.overlap["shared_cases"] == len(rules & ml)
    assert report.overlap["jaccard"] == len(rules & ml) / len(rules | ml)
    assert set(report.disagreements.plan_id) == rules ^ ml
    for row in report.disagreements.to_dict("records"):
        source = queue.set_index("plan_id").loc[row["plan_id"]]
        assert row["rules_reason"] == source.baseline_main_driver
        assert row["model_reason"] == source.model_main_driver
        assert row["selected_by"] == ("Rules only at K" if row["plan_id"] in rules else "ML only at K")
    whole = experiment_report(queue, outcomes, 500)
    assert whole.overlap["actual_k"] == 128
    assert whole.overlap["jaccard"] == 1
    assert whole.disagreements.empty
    assert whole.metrics.iloc[-1].amendments_found_std == 0


def test_empty_no_positives_and_invalid_repetitions(evaluated):
    queue, outcomes, _ = evaluated
    empty = experiment_report(queue.iloc[:0], outcomes, 30)
    assert empty.metrics.precision_at_k.isna().all()
    assert empty.metrics.recall_at_k.isna().all()
    assert empty.overlap["jaccard"] is None
    assert empty.overlap["shared_fraction_at_k"] is None
    assert empty.disagreements.empty
    no_positives = experiment_report(queue, outcomes * 0, 30)
    assert no_positives.metrics.recall_at_k.isna().all()
    assert no_positives.metrics.precision_at_k.eq(0).all()
    for value in (0, -1, True, 1, 2.5):
        with pytest.raises(ValueError):
            experiment_report(queue, outcomes, 30, repeats=value)
    for budget in (0, -1, True):
        with pytest.raises(ValueError):
            experiment_report(queue, outcomes, budget)


def test_scenario_metrics_cannot_be_requested(evaluated):
    _, outcomes, model = evaluated
    scenarios = score_queue(demonstration_plans(), model)
    for function in (compare_methods, experiment_report):
        with pytest.raises(ValueError, match="demonstration"):
            function(scenarios, outcomes, 3)
    with pytest.raises(ValueError, match="demonstration"):
        budget_metrics(rank_queue(scenarios, "baseline_index"), outcomes, 3)
