"""Purged temporal holdout and common-cohort, fixed-budget comparisons."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from jobplan_poc.features import extract_features
from jobplan_poc.scoring import ReviewModel, score_baseline
from jobplan_poc.synthetic import REFERENCE_DATE, TEST_START


@dataclass(frozen=True)
class TemporalSplit:
    training: pd.DataFrame
    test: pd.DataFrame
    purged_rows: int


def temporal_split(records: pd.DataFrame) -> TemporalSplit:
    if records["plan_id"].isna().any() or records["plan_id"].duplicated().any():
        raise ValueError("Plan IDs must be present and unique.")
    if records["entity_id"].isna().any():
        raise ValueError("Entity IDs are required for separation checks.")
    snapshots = pd.to_datetime(records["snapshot_date"], errors="raise")
    observed = pd.to_datetime(records["outcome_observed_date"], errors="raise")
    if snapshots.isna().any() or observed.isna().any() or (observed <= snapshots).any():
        raise ValueError("Each outcome must have a valid observation date after its pre-review snapshot.")
    test_mask = (snapshots >= TEST_START) & (observed <= REFERENCE_DATE)
    test = records.loc[test_mask].copy()
    test_entities = set(test["entity_id"])
    # Purge outcomes not yet observable at the test boundary and repeated holdout entities.
    train_mask = (snapshots < TEST_START) & (observed < TEST_START) & ~records["entity_id"].isin(test_entities)
    training = records.loc[train_mask].copy()
    if training.empty or test.empty:
        raise ValueError("A non-empty earlier training set and later observed holdout are required.")
    return TemporalSplit(training, test, int(len(records) - train_mask.sum() - test_mask.sum()))


def score_queue(records: pd.DataFrame, model: ReviewModel) -> pd.DataFrame:
    rows = []
    for record in records.to_dict("records"):
        baseline = score_baseline(record)
        ml = model.score(record)
        features = extract_features(record)
        rows.append({
            "plan_id": record["plan_id"],
            "specialty": record["specialty"],
            "working_pattern": record["working_pattern"],
            "workflow_stage": record["workflow_stage"],
            "snapshot_date": record["snapshot_date"],
            "baseline_index": baseline.index,
            "baseline_category": baseline.category,
            "model_index": ml.index,
            "model_category": ml.category,
            "workflow_age_days": features.values["workflow_age_days"] if features.values else np.nan,
            "data_sufficiency": baseline.sufficiency,
            "baseline_main_driver": baseline.main_driver,
            "model_main_driver": ml.main_driver,
            "baseline_action": baseline.action,
            "model_action": ml.action,
        })
    return pd.DataFrame(rows, columns=[
        "plan_id", "specialty", "working_pattern", "workflow_stage", "snapshot_date",
        "baseline_index", "baseline_category", "model_index", "model_category",
        "workflow_age_days", "data_sufficiency",
        "baseline_main_driver", "model_main_driver", "baseline_action", "model_action",
    ])


def rank_queue(queue: pd.DataFrame, score_column: str) -> pd.DataFrame:
    if score_column not in ("baseline_index", "model_index", "workflow_age_days"):
        raise ValueError("Unknown ranking method.")
    if queue["plan_id"].isna().any() or queue["plan_id"].duplicated().any():
        raise ValueError("Ranking requires unique, present plan IDs.")
    eligible = queue.loc[queue[score_column].notna()].copy()
    if not np.isfinite(eligible[score_column].to_numpy(dtype=float)).all():
        raise ValueError("Ranking scores must be finite.")
    return eligible.sort_values([score_column, "plan_id"], ascending=[False, True], kind="stable")


def budget_metrics(ranked: pd.DataFrame, labels: pd.Series, budget: int) -> dict:
    if isinstance(budget, bool) or not isinstance(budget, int) or budget < 1:
        raise ValueError("Review budget must be a positive integer.")
    if not labels.index.is_unique or ranked["plan_id"].duplicated().any():
        raise ValueError("Evaluation requires unique plan IDs and outcome indices.")
    cohort_labels = labels.reindex(ranked["plan_id"])
    if cohort_labels.isna().any() or not cohort_labels.isin([0, 1]).all():
        raise ValueError("Every evaluated plan must have a known binary synthetic outcome.")
    reviewed = min(budget, len(ranked))
    positives = int(cohort_labels.sum())
    found = int(cohort_labels.iloc[:reviewed].sum())
    return {
        "requested_budget": budget,
        "reviewed": reviewed,
        "cohort": len(ranked),
        "positives": positives,
        "amendments_found": found,
        "precision_at_k": found / reviewed if reviewed else None,
        "recall_at_k": found / positives if positives else None,
    }


def compare_methods(queue: pd.DataFrame, outcomes: pd.Series, budget: int) -> pd.DataFrame:
    # Use exactly the same sufficient cohort, including for the oldest-first comparator.
    cohort = queue.dropna(subset=["baseline_index", "model_index", "workflow_age_days"])
    rows = []
    for name, column in [
        ("Rules baseline", "baseline_index"),
        ("Experimental ML", "model_index"),
        ("Oldest-first", "workflow_age_days"),
    ]:
        rows.append({"method": name, **budget_metrics(rank_queue(cohort, column), outcomes, budget)})
    return pd.DataFrame(rows)
