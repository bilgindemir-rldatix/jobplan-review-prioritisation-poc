"""Validate pre-review records and derive an explicit, shared feature contract."""

from dataclasses import dataclass
from numbers import Real

import numpy as np
import pandas as pd

from jobplan_poc.records import validate_sources


FEATURE_NAMES = (
    "activity_change_per_wte",
    "direct_care_mix_change_pp",
    "workflow_age_days",
    "overdue_days",
    "incompleteness_percent",
)
FEATURE_LABELS = {
    "activity_change_per_wte": "Absolute activity change per WTE (PA)",
    "direct_care_mix_change_pp": "Absolute direct-care mix change (percentage points)",
    "workflow_age_days": "Time in current workflow stage (days)",
    "overdue_days": "Days past illustrative review due date",
    "incompleteness_percent": "Uncompleted fields (%)",
}
NUMERIC_FIELDS = (
    "current_total_pa",
    "current_direct_care_pa",
    "current_supporting_pa",
    "current_other_pa",
    "current_wte",
    "previous_total_pa",
    "previous_direct_care_pa",
    "previous_supporting_pa",
    "previous_other_pa",
    "previous_wte",
    "completeness_percent",
)
DATE_FIELDS = ("snapshot_date", "workflow_started_date", "review_due_date")


@dataclass(frozen=True)
class FeatureResult:
    values: dict[str, float] | None
    errors: tuple[str, ...]

    @property
    def sufficient(self) -> bool:
        return self.values is not None


def read_date(value: object, name: str) -> pd.Timestamp:
    if not isinstance(value, (str, pd.Timestamp, np.datetime64)):
        raise ValueError(f"{name}: a date in YYYY-MM-DD format is required.")
    try:
        timestamp = pd.Timestamp(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError(f"{name}: invalid date.") from exc
    if pd.isna(timestamp) or timestamp.tzinfo is not None:
        raise ValueError(f"{name}: a valid timezone-free date is required.")
    if timestamp != timestamp.normalize():
        raise ValueError(f"{name}: use a date without a time component.")
    return timestamp


def extract_features(record: dict) -> FeatureResult:
    errors: list[str] = []
    if "versions" in record:
        source = validate_sources(record)
        if source.errors:
            return FeatureResult(None, source.errors)
        record = {**record, **source.values}
    numbers: dict[str, float] = {}
    dates: dict[str, pd.Timestamp] = {}
    for field in NUMERIC_FIELDS:
        value = record.get(field)
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
            errors.append(f"{field}: a finite numeric value is required.")
        elif not np.isfinite(value):
            errors.append(f"{field}: a finite numeric value is required.")
        else:
            numbers[field] = float(value)
    for field in DATE_FIELDS:
        try:
            dates[field] = read_date(record.get(field), field)
        except ValueError as exc:
            errors.append(str(exc))

    for field, value in numbers.items():
        strictly_positive = field.endswith(("_wte", "_total_pa"))
        if value < 0 or (strictly_positive and value == 0):
            errors.append(f"{field}: must be {'positive' if strictly_positive else 'non-negative'}.")
    completeness = numbers.get("completeness_percent")
    if completeness is not None and completeness > 100:
        errors.append("completeness_percent: must be between 0 and 100.")
    for prefix in ("current", "previous"):
        components = [f"{prefix}_{name}_pa" for name in ("direct_care", "supporting", "other")]
        total = f"{prefix}_total_pa"
        if all(field in numbers for field in [total, *components]):
            if not np.isclose(sum(numbers[field] for field in components), numbers[total], atol=0.02, rtol=0):
                errors.append(f"{prefix} activity components must sum to the total (within 0.02 PA).")
    if "snapshot_date" in dates and "workflow_started_date" in dates:
        if dates["workflow_started_date"] > dates["snapshot_date"]:
            errors.append("workflow_started_date: cannot be after the snapshot date.")
    if errors:
        return FeatureResult(None, tuple(errors))

    current_normalised = numbers["current_total_pa"] / numbers["current_wte"]
    previous_normalised = numbers["previous_total_pa"] / numbers["previous_wte"]
    current_mix = numbers["current_direct_care_pa"] / numbers["current_total_pa"]
    previous_mix = numbers["previous_direct_care_pa"] / numbers["previous_total_pa"]
    values = {
        "activity_change_per_wte": abs(current_normalised - previous_normalised),
        "direct_care_mix_change_pp": abs(current_mix - previous_mix) * 100,
        "workflow_age_days": float((dates["snapshot_date"] - dates["workflow_started_date"]).days),
        "overdue_days": float(max(0, (dates["snapshot_date"] - dates["review_due_date"]).days)),
        "incompleteness_percent": 100 - numbers["completeness_percent"],
    }
    if not all(np.isfinite(value) for value in values.values()):
        return FeatureResult(None, ("Derived features must be finite; check activity totals and WTE.",))
    return FeatureResult(values, ())


def feature_frame(records: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Return only sufficient rows; preserve indices for label alignment."""
    results = [extract_features(record) for record in records.to_dict("records")]
    mask = pd.Series([result.sufficient for result in results], index=records.index, dtype=bool)
    rows = [result.values for result in results if result.sufficient]
    return pd.DataFrame(rows, index=records.index[mask], columns=FEATURE_NAMES, dtype=float), mask
