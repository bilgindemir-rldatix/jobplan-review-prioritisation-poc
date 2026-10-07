"""Versioned change rules; every point comes from the exported source trace."""

from dataclasses import asdict, dataclass
from math import fsum

import numpy as np

from jobplan_poc.features import extract_features
from jobplan_poc.records import CATEGORIES
from jobplan_poc.scoring import Score, category


RULESET_VERSION = "activity-change-v1"


@dataclass(frozen=True)
class RuleDefinition:
    rule_id: str
    name: str
    rationale: str
    threshold: float
    unit: str
    weight: float
    version: str = RULESET_VERSION


# Full-signal thresholds, not NHS policy. Changing these is a new experiment/configuration.
CATALOGUE = (
    RuleDefinition("R-01", "Total PA change per WTE", "Separate allocation change from proportional WTE change.",
                   3.0, "PA per WTE", 25.0),
    RuleDefinition("R-02", "Activity-category redistribution", "Show movement among DCC, SPA and Other shares.",
                   20.0, "percentage points redistributed", 25.0),
    RuleDefinition("R-03", "Activities added or removed", "Surface changes in stable activity identity.",
                   0.5, "fraction of union of activity IDs", 20.0),
    RuleDefinition("R-04", "Working-pattern change", "Show WTE or day/session changes needing context.",
                   0.5, "maximum of session/WTE change fractions", 15.0),
    RuleDefinition("R-05", "Site allocation change", "Surface movement of activity allocation between sites.",
                   0.5, "fraction of total allocation redistributed", 15.0),
)


@dataclass(frozen=True)
class RuleResult:
    rule_id: str
    version: str
    name: str
    rationale: str
    previous: dict | None
    current: dict | None
    observed_difference: float | None
    threshold: float
    unit: str
    weight: float
    signal_strength: float | None
    points: float | None
    triggered: bool | None
    state: str
    explanation: str


@dataclass(frozen=True)
class RuleAssessment:
    score: Score
    traces: tuple[RuleResult, ...]

    def export_traces(self) -> list[dict]:
        return [asdict(trace) for trace in self.traces]


def _distance(before: set, after: set) -> float:
    return len(before ^ after) / len(before | after) if before | after else 0.0


def _shares(activities: list[dict], key: str) -> dict[str, float]:
    total = fsum(activity["pa"] for activity in activities)
    return {
        value: fsum(activity["pa"] for activity in activities if activity[key] == value) / total
        for value in sorted({activity[key] for activity in activities})
    }


def _redistribution(previous: dict, current: dict) -> float:
    return 0.5 * fsum(abs(current.get(key, 0) - previous.get(key, 0))
                      for key in previous.keys() | current.keys())


def assess_rules(record: dict, catalogue: tuple[RuleDefinition, ...] = CATALOGUE) -> RuleAssessment:
    if ({rule.rule_id for rule in catalogue} != {f"R-0{i}" for i in range(1, 6)}
            or len(catalogue) != 5
            or any(not np.isfinite(rule.threshold) or rule.threshold <= 0
                   or not np.isfinite(rule.weight) or rule.weight < 0 for rule in catalogue)
            or not np.isclose(sum(rule.weight for rule in catalogue), 100)):
        raise ValueError("Rule catalogue requires R-01..R-05, positive finite thresholds and weights totalling 100.")
    features = extract_features(record)
    errors = features.errors
    if "versions" not in record:
        errors = (*errors, "Linked previous/current activity records are required for activity-change rules.")
    if errors:
        explanation = "Priority cannot be reliably calculated. Data clarification required: " + " ".join(errors)
        traces = tuple(
            RuleResult(rule.rule_id, rule.version, rule.name, rule.rationale, None, None, None,
                       rule.threshold, rule.unit, rule.weight, None, None, None, "withheld", explanation)
            for rule in catalogue
        )
        return RuleAssessment(Score(None, "Unscored", {}, "rules index points", errors), traces)
    previous, current = record["versions"]["previous"], record["versions"]["current"]
    old_categories = _shares(previous["activities"], "category")
    new_categories = _shares(current["activities"], "category")
    old_ids = {a["activity_id"] for a in previous["activities"]}
    new_ids = {a["activity_id"] for a in current["activities"]}
    old_slots, new_slots = set(previous["working_pattern"]), set(current["working_pattern"])
    old_sites, new_sites = _shares(previous["activities"], "site"), _shares(current["activities"], "site")
    old_total = fsum(a["pa"] for a in previous["activities"])
    new_total = fsum(a["pa"] for a in current["activities"])
    evidence = {
        "R-01": (
            {"total_pa": old_total, "wte": previous["wte"], "normalised_pa": old_total / previous["wte"]},
            {"total_pa": new_total, "wte": current["wte"], "normalised_pa": new_total / current["wte"]},
            abs(new_total / current["wte"] - old_total / previous["wte"]),
        ),
        "R-02": (
            {key: old_categories.get(key, 0.0) for key in CATEGORIES},
            {key: new_categories.get(key, 0.0) for key in CATEGORIES},
            100 * _redistribution(old_categories, new_categories),
        ),
        "R-03": (
            {"activity_ids": sorted(old_ids), "removed": sorted(old_ids - new_ids)},
            {"activity_ids": sorted(new_ids), "added": sorted(new_ids - old_ids)},
            _distance(old_ids, new_ids),
        ),
        "R-04": (
            {"sessions": sorted(old_slots), "wte": previous["wte"]},
            {"sessions": sorted(new_slots), "wte": current["wte"]},
            max(_distance(old_slots, new_slots),
                abs(current["wte"] - previous["wte"]) / max(current["wte"], previous["wte"])),
        ),
        "R-05": (old_sites, new_sites, _redistribution(old_sites, new_sites)),
    }
    traces = []
    for rule in catalogue:
        before, after, observed = evidence[rule.rule_id]
        signal = min(observed / rule.threshold, 1.0)
        points = rule.weight * signal
        triggered = observed >= rule.threshold
        explanation = (
            f"{rule.name}: observed {observed:.4g} {rule.unit}; full-signal threshold {rule.threshold:g}. "
            f"Signal {signal:.4g} contributes {points:.4g} index points. "
            "This change may be entirely legitimate; review its context, not the person."
            if observed else f"{rule.name}: no observed change; no index points. This does not replace human review."
        )
        traces.append(RuleResult(rule.rule_id, rule.version, rule.name, rule.rationale, before, after, observed,
                                 rule.threshold, rule.unit, rule.weight, signal, points, triggered,
                                 "evaluated", explanation))
    contributions = {f"{trace.rule_id} {trace.name}": trace.points for trace in traces}
    index = float(sum(contributions.values()))
    return RuleAssessment(Score(index, category(index), contributions, "rules index points"), tuple(traces))
