"""Rules and a linear model with faithful, distinct explanation spaces."""

from dataclasses import dataclass
from math import exp
from numbers import Real

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from jobplan_poc.features import FEATURE_LABELS, FEATURE_NAMES, extract_features, feature_frame


RULES = {
    "activity_change_per_wte": (3.0, 25.0),
    "direct_care_mix_change_pp": (20.0, 20.0),
    "workflow_age_days": (120.0, 20.0),
    "overdue_days": (60.0, 20.0),
    "incompleteness_percent": (40.0, 15.0),
}
ACTIONS = {
    "Low": "Keep in the normal human review queue; check context before any decision.",
    "Medium": "Consider an earlier human review and clarify the highlighted information.",
    "High": "Consider prioritising a Clinical Director review; confirm context and data first.",
    "Unscored": "Resolve missing or invalid required data and route for human triage; do not deprioritise.",
}


@dataclass(frozen=True)
class Score:
    index: float | None
    category: str
    contributions: dict[str, float]
    explanation_space: str
    errors: tuple[str, ...] = ()
    intercept: float | None = None
    decision: float | None = None

    @property
    def action(self) -> str:
        return ACTIONS[self.category]

    @property
    def sufficiency(self) -> str:
        return "Insufficient required data" if self.index is None else "Required inputs available and valid"

    @property
    def main_driver(self) -> str:
        if not self.contributions:
            return "Not available: resolve required input data."
        name = max(self.contributions, key=lambda feature: abs(self.contributions[feature]))
        value = self.contributions[name]
        return f"{FEATURE_LABELS[name]}: {value:+.2f} {self.explanation_space}"


def category(index: float) -> str:
    if isinstance(index, (bool, np.bool_)) or not isinstance(index, Real):
        raise ValueError("Prioritisation index must be a finite number between 0 and 100.")
    if not np.isfinite(index) or not 0 <= index <= 100:
        raise ValueError("Prioritisation index must be finite and between 0 and 100.")
    return "Low" if index < 35 else "Medium" if index < 65 else "High"


def score_baseline(record: dict) -> Score:
    result = extract_features(record)
    if result.values is None:
        return Score(None, "Unscored", {}, "baseline index points", result.errors)
    contributions = {
        name: min(result.values[name] / cap, 1.0) * weight
        for name, (cap, weight) in RULES.items()
    }
    index = float(sum(contributions.values()))
    return Score(index, category(index), contributions, "baseline index points")


@dataclass
class ReviewModel:
    pipeline: Pipeline
    training_rows: int
    excluded_training_rows: int
    training_min: pd.Timestamp
    training_max: pd.Timestamp

    def score(self, record: dict) -> Score:
        result = extract_features(record)
        if result.values is None:
            return Score(None, "Unscored", {}, "signed model log-odds units", result.errors)
        frame = pd.DataFrame([result.values], columns=FEATURE_NAMES)
        scaler = self.pipeline.named_steps["scale"]
        classifier = self.pipeline.named_steps["model"]
        standardised = scaler.transform(frame)[0]
        contributions = dict(zip(FEATURE_NAMES, (standardised * classifier.coef_[0]).tolist()))
        intercept = float(classifier.intercept_[0])
        decision = intercept + sum(contributions.values())
        # Stable logistic transform; this is not a calibrated real-world probability.
        index = 100 * (1 / (1 + exp(-decision)) if decision >= 0 else exp(decision) / (1 + exp(decision)))
        return Score(index, category(index), contributions, "signed model log-odds units",
                     intercept=intercept, decision=decision)


def fit_model(training: pd.DataFrame) -> ReviewModel:
    frame, mask = feature_frame(training)
    if len(frame) < 10:
        raise ValueError("Model unavailable: at least 10 sufficient training records are required.")
    labels = training.loc[mask, "material_amendment"]
    if labels.isna().any() or not labels.isin([0, 1]).all() or labels.nunique() != 2:
        raise ValueError("Model unavailable: training requires both binary outcome classes (0 and 1).")
    pipeline = Pipeline([
        ("scale", StandardScaler()),
        ("model", LogisticRegression(C=1.0, max_iter=2000, random_state=42)),
    ])
    pipeline.fit(frame, labels)
    dates = pd.to_datetime(training.loc[mask, "snapshot_date"])
    return ReviewModel(pipeline, len(frame), int((~mask).sum()), dates.min(), dates.max())


def what_if(record: dict, updates: dict, model: ReviewModel) -> tuple[dict, Score, Score]:
    """Score a detached scenario through the same validation and scoring paths."""
    allowed = {
        "current_total_pa", "current_direct_care_pa", "current_supporting_pa",
        "current_other_pa", "current_wte", "completeness_percent",
        "workflow_started_date", "review_due_date",
    }
    if not set(updates).issubset(allowed):
        raise ValueError("What-if updates must contain only supported pre-review scenario inputs.")
    scenario = {**record, **updates}
    return scenario, score_baseline(scenario), model.score(scenario)
