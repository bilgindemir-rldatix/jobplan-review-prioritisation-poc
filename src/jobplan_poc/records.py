"""Fictional linked versions, authoritative activity totals and reconciliation."""

from copy import deepcopy
from dataclasses import dataclass
from math import fsum
from numbers import Real

import numpy as np
import pandas as pd


GENERATOR_VERSION = "linked-activities-v1"
CATEGORIES = {"DCC": "direct_care", "SPA": "supporting", "Other": "other"}
SLOTS = tuple(f"{day} {part}" for day in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
              for part in ("AM", "PM"))


def finite_number(value: object, *, positive: bool = False) -> bool:
    return (not isinstance(value, (bool, np.bool_)) and isinstance(value, Real)
            and np.isfinite(value) and (value > 0 if positive else value >= 0))


@dataclass(frozen=True)
class SourceResult:
    values: dict[str, float]
    errors: tuple[str, ...]


def version_totals(version: dict) -> dict[str, float]:
    """Only call after validation, or while constructing known complete records."""
    values = {
        f"{label}_pa": round(fsum(a["pa"] for a in version["activities"] if a["category"] == category), 8)
        for category, label in CATEGORIES.items()
    }
    values["total_pa"] = round(fsum(values.values()), 8)
    values["wte"] = version["wte"]
    return values


def validate_sources(record: dict) -> SourceResult:
    errors: list[str] = []
    values: dict[str, float] = {}
    versions = record.get("versions")
    if not isinstance(versions, dict):
        return SourceResult({}, ("Previous/current version records are required.",))
    subject = record.get("subject")
    if not isinstance(subject, dict) or subject.get("subject_id") != record.get("entity_id"):
        errors.append("Fictional subject link does not match the JobPlan entity.")
    version_ids = []
    for prefix in ("previous", "current"):
        version = versions.get(prefix)
        start = len(errors)
        if not isinstance(version, dict):
            errors.append(f"{prefix} plan unavailable; comparison cannot be calculated.")
            continue
        if version.get("plan_id") != record.get("plan_id") or not version.get("version_id"):
            errors.append(f"{prefix} version must link to this plan and have a version ID.")
        version_ids.append(version.get("version_id"))
        if version.get("complete") is not True:
            errors.append(f"{prefix} plan is partial; activity absence cannot be interpreted as removal.")
        if not finite_number(version.get("wte"), positive=True):
            errors.append(f"{prefix} version WTE must be a positive finite number.")
        pattern = version.get("working_pattern")
        if not isinstance(pattern, list) or not pattern or any(slot not in SLOTS for slot in pattern):
            errors.append(f"{prefix} working pattern requires known day/session slots.")
        elif len(set(pattern)) != len(pattern):
            errors.append(f"{prefix} working pattern has duplicate sessions.")
        activities = version.get("activities")
        if not isinstance(activities, list) or not activities:
            errors.append(f"{prefix} activity records are missing.")
            continue
        ids = []
        for activity in activities:
            if not isinstance(activity, dict):
                errors.append(f"{prefix} activity must be a record.")
                continue
            activity_id = activity.get("activity_id")
            if not isinstance(activity_id, str) or not activity_id:
                errors.append(f"{prefix} activity requires a stable ID.")
            else:
                ids.append(activity_id)
            if activity.get("version_id") != version.get("version_id"):
                errors.append(f"{prefix} activity {activity_id}: version link mismatch.")
            if activity.get("category") not in CATEGORIES:
                errors.append(f"{prefix} activity {activity_id}: category mapping is missing or invalid.")
            if not finite_number(activity.get("pa")):
                errors.append(f"{prefix} activity {activity_id}: PA must be a finite non-negative number.")
            if not isinstance(activity.get("site"), str) or not activity["site"].strip():
                errors.append(f"{prefix} activity {activity_id}: site is required.")
            if not isinstance(pattern, list) or activity.get("session") not in pattern:
                errors.append(f"{prefix} activity {activity_id}: session must belong to the working pattern.")
        if len(ids) != len(set(ids)):
            errors.append(f"{prefix} activity IDs are duplicated; stable matching is ambiguous.")
        if len(errors) != start:
            continue
        derived = version_totals(version)
        if not finite_number(derived["total_pa"], positive=True):
            errors.append(f"{prefix} activity total must be positive.")
        declared = version.get("declared_total_pa")
        if not finite_number(declared) or not np.isclose(declared, derived["total_pa"], atol=0.02, rtol=0):
            errors.append(f"{prefix} declared total contradicts the activity total.")
        for suffix, value in derived.items():
            field = f"{prefix}_{suffix}"
            values[field] = value
            reported = record.get(field)
            if not finite_number(reported) or not np.isclose(reported, value, atol=0.02, rtol=0):
                errors.append(f"{field}: reported value does not reconcile to the version/activity records.")
    if len(version_ids) == 2 and version_ids[0] == version_ids[1]:
        errors.append("Previous and current versions must have different IDs.")
    return SourceResult(values, tuple(errors))


def refresh_totals(record: dict) -> dict:
    """Construction/scenario helper, never used to repair untrusted source input."""
    result = deepcopy(record)
    for prefix in ("previous", "current"):
        version = result["versions"].get(prefix)
        if version is not None:
            totals = version_totals(version)
            version["declared_total_pa"] = totals["total_pa"]
            result.update({f"{prefix}_{key}": value for key, value in totals.items()})
    result["working_pattern"] = "Full-time" if result["current_wte"] == 1 else "Less than full-time"
    return result


def link_record(record: dict, rng: np.random.Generator, seed: int) -> dict:
    result = deepcopy(record)
    result["generator_version"] = GENERATOR_VERSION
    result["generator_seed"] = seed
    result["cohort"] = "evaluation"
    result["subject"] = {"subject_id": record["entity_id"], "label": "Fictional subject"}
    result["versions"] = {}
    for prefix in ("previous", "current"):
        version_id = f"{record['plan_id']}-{prefix}"
        count = max(1, min(10, round(record[f"{prefix}_wte"] * 10)))
        pattern = list(SLOTS[:count])
        if prefix == "current" and rng.random() < 0.25:
            pattern = list(SLOTS[-count:])
        direct = record[f"{prefix}_direct_care_pa"]
        first = round(direct * 0.6, 2)
        allocations = [
            ("care-a", "DCC", first), ("care-b", "DCC", round(direct - first, 2)),
            ("support", "SPA", record[f"{prefix}_supporting_pa"]),
            ("other", "Other", record[f"{prefix}_other_pa"]),
        ]
        activities = []
        for index, (activity_id, category, pa) in enumerate(allocations):
            site = "Fictional site A"
            if prefix == "current" and rng.random() < 0.15:
                site = "Fictional site B"
            if prefix == "current" and rng.random() < 0.08:
                activity_id += "-replacement"
            activities.append({
                "activity_id": activity_id, "version_id": version_id, "category": category,
                "pa": pa, "session": pattern[index % len(pattern)], "site": site,
            })
        result["versions"][prefix] = {
            "version_id": version_id, "plan_id": record["plan_id"], "complete": True,
            "wte": record[f"{prefix}_wte"], "working_pattern": pattern, "activities": activities,
            "declared_total_pa": record[f"{prefix}_total_pa"],
        }
    if pd.isna(record["previous_total_pa"]):
        result["versions"]["previous"] = None
    result = refresh_totals(result)
    return result


def activity_comparison(record: dict) -> pd.DataFrame:
    """No comparison numbers when source records are incomplete or contradictory."""
    result = validate_sources(record)
    columns = ["Activity", "Previous category", "Current category", "Previous PA", "Current PA",
               "Change PA", "Previous session", "Current session", "Previous site", "Current site"]
    if result.errors:
        return pd.DataFrame(columns=columns)
    old = {a["activity_id"]: a for a in record["versions"]["previous"]["activities"]}
    new = {a["activity_id"]: a for a in record["versions"]["current"]["activities"]}
    rows = []
    for activity_id in sorted(old.keys() | new.keys()):
        before, after = old.get(activity_id), new.get(activity_id)
        prior_pa, current_pa = before["pa"] if before else 0.0, after["pa"] if after else 0.0
        rows.append({
            "Activity": activity_id,
            "Previous category": before["category"] if before else "Not present",
            "Current category": after["category"] if after else "Not present",
            "Previous PA": prior_pa, "Current PA": current_pa, "Change PA": current_pa - prior_pa,
            "Previous session": before["session"] if before else "Not present",
            "Current session": after["session"] if after else "Not present",
            "Previous site": before["site"] if before else "Not present",
            "Current site": after["site"] if after else "Not present",
        })
    return pd.DataFrame(rows, columns=columns)


def linked_what_if(record: dict, updates: dict) -> dict:
    scenario = deepcopy(record)
    scenario.update(updates)
    current = scenario["versions"]["current"]
    if "current_wte" in updates:
        current["wte"] = updates["current_wte"]
    for category, label in CATEGORIES.items():
        field = f"current_{label}_pa"
        if field not in updates:
            continue
        matches = [a for a in current["activities"] if a["category"] == category]
        total = fsum(a["pa"] for a in matches)
        if not matches:
            raise ValueError(f"Scenario cannot allocate {category}: no source activity exists.")
        for index, activity in enumerate(matches):
            activity["pa"] = (updates[field] * activity["pa"] / total if total else updates[field] / len(matches))
    if "current_total_pa" in updates:
        current["declared_total_pa"] = updates["current_total_pa"]
    return scenario
