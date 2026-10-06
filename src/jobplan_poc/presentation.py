"""Shared view scope, workload summaries and deterministic original-plan exports."""

import csv
import io
import json
from dataclasses import asdict, dataclass
from numbers import Real

import numpy as np
import pandas as pd

from jobplan_poc.evaluation import rank_queue
from jobplan_poc.features import FEATURE_LABELS
from jobplan_poc.scoring import ReviewModel
from jobplan_poc.synthetic import DEFAULT_SEED, REFERENCE_DATE, TEST_START


EXPORT_VERSION = "1.0"
SCORING_VERSION = "rules-v1"
MODEL_VERSION = "standardised-logistic-v1"
SYNTHETIC_NOTICE = (
    "Fictional synthetic data only; review prioritisation support, not clinical quality, "
    "clinician performance or clinical safety. Not a calibrated real-world probability."
)
RANK_COLUMNS = {
    "Experimental ML": "model_index", "Rules baseline": "baseline_index",
    "Oldest-first": "workflow_age_days",
}


@dataclass(frozen=True)
class ViewConfig:
    ranking: str
    specialties: tuple[str, ...]
    patterns: tuple[str, ...]
    stages: tuple[str, ...]
    priorities: tuple[str, ...]
    search: str = ""

    @property
    def source(self) -> str:
        return "model" if self.ranking == "Experimental ML" else "baseline"


def filtered_queue(queue: pd.DataFrame, config: ViewConfig) -> pd.DataFrame:
    if config.ranking not in RANK_COLUMNS:
        raise ValueError("Unknown ranking method.")
    if queue.empty:
        return queue.copy()
    mask = (
        queue["specialty"].isin(config.specialties)
        & queue["working_pattern"].isin(config.patterns)
        & queue["workflow_stage"].isin(config.stages)
    )
    query = config.search.strip().casefold()
    if query:
        def searchable(row):
            reasons = [
                FEATURE_LABELS[name]
                for column in ("baseline_contributions", "model_contributions")
                for name, value in row[column].items() if value != 0
            ]
            return " ".join([
                row["plan_id"], row["department"], row["specialty"],
                row["baseline_main_driver"], row["model_main_driver"],
                *row["input_errors"], *reasons,
            ]).casefold()
        mask &= queue.apply(searchable, axis=1).str.contains(query, regex=False)
    matched = queue.loc[mask]
    unscored = matched[matched["baseline_index"].isna()].sort_values("plan_id")
    scored = matched[matched[f"{config.source}_category"].isin(config.priorities)]
    ordered_indices = [*rank_queue(scored, RANK_COLUMNS[config.ranking]).index, *unscored.index]
    return queue.loc[ordered_indices].copy()


def priority_distribution(view: pd.DataFrame, source: str) -> pd.DataFrame:
    if source not in ("baseline", "model"):
        raise ValueError("Unknown scoring source.")
    return pd.DataFrame({
        "review_priority": ["Low", "Medium", "High"],
        "scored_plans": [int((view[f"{source}_category"] == category).sum())
                         for category in ("Low", "Medium", "High")],
    })


def workload_groups(view: pd.DataFrame, group: str, source: str) -> pd.DataFrame:
    if group not in ("department", "specialty") or source not in ("baseline", "model"):
        raise ValueError("Unknown grouping or scoring source.")
    rows = []
    for name, records in view.groupby(group, sort=True):
        scored = int(records[f"{source}_index"].notna().sum())
        high = int((records[f"{source}_category"] == "High").sum())
        rows.append({
            group: name, "total_plans": len(records), "scored_plans": scored,
            "unscored_plans": len(records) - scored, "high_priority_plans": high,
            "high_priority_rate_among_scored": high / scored if scored else None,
            "interpretation": "Small scored group (<5): do not compare rates" if scored < 5
                              else "Descriptive workload only; no quality inference",
        })
    return pd.DataFrame(rows, columns=[
        group, "total_plans", "scored_plans", "unscored_plans", "high_priority_plans",
        "high_priority_rate_among_scored", "interpretation",
    ])


def _json_value(value):
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, Real):
        if not np.isfinite(value):
            return None
        return value.item() if isinstance(value, np.generic) else value
    return value


def export_payload(queue: pd.DataFrame, config: ViewConfig, model: ReviewModel) -> dict:
    """Only accept the original scored queue, never a scenario or UI display table."""
    view = filtered_queue(queue, config)
    configuration = asdict(config)
    for key in ("specialties", "patterns", "stages", "priorities"):
        configuration[key] = sorted(configuration[key])
    configuration["search"] = config.search.strip().casefold()
    return _json_value({
        "metadata": {
            "export_schema_version": EXPORT_VERSION,
            "scoring_version": SCORING_VERSION, "model_version": MODEL_VERSION,
            "synthetic_notice": SYNTHETIC_NOTICE,
            "scope": "Current filtered original-plan holdout queue; no what-if edits; not limited to K.",
            "filters": configuration,
            "priority_source": config.source,
            "unscored_policy": "Included when search and non-priority filters match; priority filter does not hide them.",
            "row_count": len(view), "scored_count": int(view["baseline_index"].notna().sum()),
            "unscored_count": int(view["baseline_index"].isna().sum()),
            "seed": DEFAULT_SEED, "reference_date": REFERENCE_DATE, "test_start": TEST_START,
            "training_rows": model.training_rows,
            "training_min": model.training_min, "training_max": model.training_max,
            "feature_order": list(model.pipeline.named_steps["scale"].feature_names_in_),
            "model_coefficients": model.pipeline.named_steps["model"].coef_[0].tolist(),
            "model_intercept": float(model.pipeline.named_steps["model"].intercept_[0]),
            "training_feature_means": model.pipeline.named_steps["scale"].mean_.tolist(),
            "training_feature_scales": model.pipeline.named_steps["scale"].scale_.tolist(),
        },
        "plans": view.to_dict("records"),
    })


def export_json(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n"


def _csv_cell(value):
    if isinstance(value, (dict, list, tuple)):
        value = json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False)
    if isinstance(value, str) and (
        value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n"))
    ):
        return "'" + value
    return value


def export_csv(payload: dict, plan_columns: list[str]) -> str:
    """One scope record, then plan records; even an empty view retains its metadata."""
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=["record_type", "scope_metadata_json", *plan_columns],
                            lineterminator="\n")
    writer.writeheader()
    writer.writerow({"record_type": "scope", "scope_metadata_json": _csv_cell(payload["metadata"])})
    for plan in payload["plans"]:
        writer.writerow({"record_type": "plan", **{key: _csv_cell(value) for key, value in plan.items()}})
    return output.getvalue()
