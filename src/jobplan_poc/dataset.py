"""Linked cohort adapter and isolated, mechanism-led demonstration scenarios."""

from copy import deepcopy

import numpy as np
import pandas as pd

from jobplan_poc.records import link_record, refresh_totals
from jobplan_poc.synthetic import DEFAULT_SEED, generate_plans


def generate_dataset(n: int = 800, seed: int = DEFAULT_SEED, missing_rate: float = 0.04) -> pd.DataFrame:
    legacy = generate_plans(n=n, seed=seed, missing_rate=missing_rate)
    rng = np.random.default_rng(seed + 100_000)
    return pd.DataFrame([link_record(record, rng, seed) for record in legacy.to_dict("records")])


def demonstration_plans(seed: int = DEFAULT_SEED) -> pd.DataFrame:
    base = generate_dataset(n=2, seed=seed, missing_rate=0).iloc[0].to_dict()
    base.pop("material_amendment")
    base.pop("outcome_observed_date")
    base["snapshot_date"] = pd.Timestamp("2025-12-01")
    base["workflow_started_date"] = base["snapshot_date"]
    base["review_due_date"] = base["snapshot_date"] + pd.Timedelta(30, unit="D")
    base["completeness_percent"] = 100.0
    base["cohort"] = "demonstration"
    for prefix in ("previous", "current"):
        version = base["versions"][prefix]
        version["wte"] = 1.0
        version["working_pattern"] = ["Monday AM", "Tuesday PM", "Thursday AM"]
        for activity, pa in zip(version["activities"], (4.0, 3.0, 2.0, 1.0)):
            activity["pa"] = pa
            activity["site"] = "Fictional site A"
            activity["session"] = "Monday AM"
        for activity, activity_id in zip(version["activities"], ("care-a", "care-b", "support", "other")):
            activity["activity_id"] = activity_id
    rows = []
    names = [
        ("Unchanged plan", "No change to activities, pattern or location."),
        ("Small allocation change", "A small DCC to SPA redistribution; context still belongs to the reviewer."),
        ("Substantial legitimate working-pattern change", "Illustrative planned reduction in WTE and PA; not evidence of wrongdoing."),
        ("Unusual allocation change", "Changed allocation, schedule and sites require context, not a judgement."),
        ("Missing previous plan", "The prior version is unavailable; request comparison information."),
        ("Partial current plan", "An incomplete activity list must not imply activities were removed."),
        ("Contradictory totals", "A reported total conflicts with activities; clarify the source."),
        ("Changed activities and sites, short wait", "Contrasting mechanism: change rules see turnover; ML lacks these new predictors."),
        ("Stable activities, long administrative wait", "Contrasting mechanism: legacy ML sees age, due date and completeness; activity rules see no change."),
    ]
    for index, (name, note) in enumerate(names, start=1):
        record = deepcopy(base)
        record.update(plan_id=f"JP-{index:03d}", entity_id=f"FICTIONAL-SUBJECT-{index:03d}",
                      scenario_name=name, scenario_note=note)
        record["subject"]["subject_id"] = record["entity_id"]
        for prefix, version in record["versions"].items():
            version["plan_id"] = record["plan_id"]
            version["version_id"] = f"{record['plan_id']}-{prefix}"
            for activity in version["activities"]:
                activity["version_id"] = version["version_id"]
        current = record["versions"]["current"]
        if index == 2:
            current["activities"][0]["pa"] -= 0.2
            current["activities"][2]["pa"] += 0.2
        if index == 3:
            current["wte"] = 0.5
            current["working_pattern"] = ["Tuesday AM", "Friday PM"]
            for activity in current["activities"]:
                activity["pa"] *= 0.5
                activity["session"] = "Tuesday AM"
        if index in (4, 8):
            current["working_pattern"] = ["Wednesday AM", "Friday PM"]
            for activity in current["activities"]:
                activity["activity_id"] += "-new"
                activity["site"] = "Fictional site B"
                activity["session"] = "Wednesday AM"
            # Fixed semantic redistribution, not fitted or searched for a desired score.
            for activity, pa in zip(current["activities"], (0.5, 0.5, 8.0, 1.0)):
                activity["pa"] = pa
        if index == 4:
            current["activities"][2]["pa"] += 5.0
        if index == 9:
            record["workflow_started_date"] -= pd.Timedelta(240, unit="D")
            record["review_due_date"] = record["snapshot_date"] - pd.Timedelta(100, unit="D")
            record["completeness_percent"] = 30.0
        record = refresh_totals(record)
        if index == 5:
            record["versions"]["previous"] = None
            record["previous_total_pa"] = np.nan
        if index == 6:
            record["versions"]["current"]["complete"] = False
            record["versions"]["current"]["activities"][0]["pa"] = None
        if index == 7:
            record["versions"]["current"]["declared_total_pa"] += 3
        rows.append(record)
    return pd.DataFrame(rows)
