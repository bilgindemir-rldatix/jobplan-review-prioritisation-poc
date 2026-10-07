"""Purged temporal holdout and common-cohort, fixed-budget comparisons."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from jobplan_poc.features import extract_features
from jobplan_poc.scoring import ReviewModel, score_baseline
from jobplan_poc.rules import assess_rules
from jobplan_poc.synthetic import REFERENCE_DATE, TEST_START


@dataclass(frozen=True)
class TemporalSplit:
    training: pd.DataFrame
    test: pd.DataFrame
    purged_rows: int


def temporal_split(records: pd.DataFrame) -> TemporalSplit:
    if "cohort" in records and not records["cohort"].eq("evaluation").all():
        raise ValueError("Temporal evaluation excludes demonstration scenarios; supply only the evaluation cohort.")
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
        legacy = score_baseline(record)
        assessment = assess_rules(record) if "versions" in record else None
        baseline = assessment.score if assessment else legacy
        ml = model.score(record)
        features = extract_features(record)
        rows.append({
            "plan_id": record["plan_id"],
            "specialty": record["specialty"],
            "department": record["department"],
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
            "completeness_percent": record.get("completeness_percent"),
            "input_errors": baseline.errors,
            "baseline_contributions": baseline.contributions,
            "model_contributions": ml.contributions,
            "model_intercept": ml.intercept,
            "model_decision": ml.decision,
            "baseline_explanation_space": baseline.explanation_space,
            "model_explanation_space": ml.explanation_space,
            "legacy_baseline_index": legacy.index,
            "rule_traces": assessment.export_traces() if assessment else [],
            "rule_ids": [trace.rule_id for trace in assessment.traces] if assessment else [],
            "data_quality_state": "Data clarification required" if baseline.index is None else "Required inputs reconciled",
            "cohort": record.get("cohort", "evaluation"),
            "generator_version": record.get("generator_version", "legacy-flat-v1"),
            "generator_seed": record.get("generator_seed"),
            "change_summary": (
                "Priority cannot be reliably calculated" if baseline.index is None else
                f"Total PA {record['previous_total_pa']:g} to {record['current_total_pa']:g}; "
                f"WTE {record['previous_wte']:g} to {record['current_wte']:g}"
            ),
        })
    return pd.DataFrame(rows, columns=[
        "plan_id", "specialty", "department", "working_pattern", "workflow_stage", "snapshot_date",
        "baseline_index", "baseline_category", "model_index", "model_category",
        "workflow_age_days", "data_sufficiency",
        "baseline_main_driver", "model_main_driver", "baseline_action", "model_action",
        "completeness_percent", "input_errors", "baseline_contributions", "model_contributions",
        "model_intercept", "model_decision", "baseline_explanation_space", "model_explanation_space",
        "legacy_baseline_index", "rule_traces", "rule_ids", "data_quality_state",
        "cohort", "generator_version", "generator_seed", "change_summary",
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
