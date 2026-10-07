from copy import deepcopy

import numpy as np
import pandas as pd
import pytest

from jobplan_poc.dataset import demonstration_plans, generate_dataset
from jobplan_poc.evaluation import temporal_split
from jobplan_poc.features import extract_features, feature_frame
from jobplan_poc.records import activity_comparison, validate_sources, version_totals
from jobplan_poc.scoring import fit_model
from jobplan_poc.synthetic import generate_plans


@pytest.fixture(scope="module")
def linked():
    records = generate_dataset()
    split = temporal_split(records)
    return records, split, fit_model(split.training)


def test_linked_cohort_reconciles_and_preserves_legacy_experiment(linked):
    records, split, model = linked
    pd.testing.assert_frame_equal(records, generate_dataset())
    legacy = generate_plans()
    pd.testing.assert_series_equal(records.material_amendment, legacy.material_amendment)
    derived, mask = feature_frame(records)
    original, old_mask = feature_frame(legacy)
    pd.testing.assert_series_equal(mask, old_mask)
    np.testing.assert_allclose(derived, original, rtol=0, atol=1e-12)
    old_model = fit_model(temporal_split(legacy).training)
    np.testing.assert_allclose(model.pipeline.named_steps["model"].coef_,
                               old_model.pipeline.named_steps["model"].coef_, atol=1e-10)
    for record in records.loc[mask].to_dict("records"):
        assert not validate_sources(record).errors
        for prefix, version in record["versions"].items():
            totals = version_totals(version)
            assert totals["total_pa"] == pytest.approx(record[f"{prefix}_total_pa"])
            assert sum(a["pa"] for a in version["activities"]) == pytest.approx(totals["total_pa"])
            assert version["plan_id"] == record["plan_id"]
        comparison = activity_comparison(record)
        assert comparison["Previous PA"].sum() == pytest.approx(record["previous_total_pa"])
        assert comparison["Current PA"].sum() == pytest.approx(record["current_total_pa"])
    assert split.training.entity_id.is_unique


def test_semantic_scenarios_are_deterministic_separate_and_unscored_when_incomplete(linked):
    records, _, model = linked
    scenarios = demonstration_plans()
    pd.testing.assert_frame_equal(scenarios, demonstration_plans())
    assert scenarios.plan_id.tolist() == [f"JP-{i:03d}" for i in range(1, 10)]
    assert not set(scenarios.entity_id) & set(records.entity_id)
    assert "material_amendment" not in scenarios and "outcome_observed_date" not in scenarios
    assert (scenarios.cohort == "demonstration").all()
    for plan_id in ("JP-005", "JP-006", "JP-007"):
        record = scenarios.set_index("plan_id", drop=False).loc[plan_id].to_dict()
        assert extract_features(record).values is None
        assert model.score(record).index is None
        assert activity_comparison(record).empty
    legitimate = scenarios.iloc[2].to_dict()
    features = extract_features(legitimate).values
    assert features["activity_change_per_wte"] == 0
    assert features["direct_care_mix_change_pp"] == 0
    assert legitimate["current_total_pa"] == legitimate["previous_total_pa"] / 2


@pytest.mark.parametrize("mutate", [
    lambda r: r["versions"]["current"]["activities"][0].update(pa=-1),
    lambda r: r["versions"]["current"]["activities"][0].update(category=None),
    lambda r: r["versions"]["current"]["activities"][0].update(category={"invalid": "category"}),
    lambda r: r["versions"]["current"]["activities"][0].update(site=None),
    lambda r: r["versions"]["current"]["activities"][0].update(session="Sunday AM"),
    lambda r: r["versions"]["current"]["activities"][0].update(version_id="wrong"),
    lambda r: r["versions"]["current"]["activities"].append(deepcopy(r["versions"]["current"]["activities"][0])),
    lambda r: r["versions"]["current"].update(working_pattern=[]),
    lambda r: r.update(current_total_pa=r["current_total_pa"] + 2),
    lambda r: r["subject"].update(subject_id="wrong"),
    lambda r: [a.update(pa=1e308) for a in r["versions"]["current"]["activities"]],
])
def test_contradictions_never_silently_repaired(linked, mutate):
    records, _, model = linked
    record = deepcopy(records.dropna().iloc[0].to_dict())
    mutate(record)
    assert validate_sources(record).errors
    assert extract_features(record).values is None
    assert model.score(record).index is None
