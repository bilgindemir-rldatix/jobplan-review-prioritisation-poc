"""Presentation-only language and comparisons; never change scores or source data."""

from html import escape
import re

import pandas as pd

from jobplan_poc.features import extract_features
from jobplan_poc.records import activity_comparison, validate_sources


DISPLAY_CATEGORIES = {
    "High": "Review sooner",
    "Medium": "Standard review",
    "Low": "Standard review",
    "Unscored": "Data clarification required",
}
PRIORITY_FILTERS = {
    "All plans": ("High", "Medium", "Low"),
    "Review sooner": ("High",),
    "Standard review": ("Medium", "Low"),
    "Data clarification required": (),
}
RULE_PHRASES = {
    "R-01": "allocation per WTE",
    "R-02": "the DCC / SPA / Other allocation mix",
    "R-03": "the set of activities",
    "R-04": "the working pattern",
    "R-05": "allocation between sites",
}
MEASURES = (
    ("wte", "Whole-time equivalent (WTE)"),
    ("total_pa", "Total weekly PA"),
    ("direct_care_pa", "DCC allocation (PA)"),
    ("supporting_pa", "SPA allocation (PA)"),
    ("other_pa", "Other allocation (PA)"),
)


def markdown_text(value: object) -> str:
    """Escape dynamic text for native Markdown labels, never for CSS/HTML templates."""
    return re.sub(r"([\\`*_{}\[\]()#+.!|$:<>~-])", r"\\\1", escape(str(value), quote=True))


def display_category(category: str) -> str:
    return DISPLAY_CATEGORIES[category]


def rules_applied(traces: list[dict]) -> int:
    """Partial non-zero signals count; withheld rules do not count as evaluated."""
    return sum(trace["state"] == "evaluated" and trace["signal_strength"] > 0 for trace in traces)


def plain_reason(traces: list[dict]) -> str:
    if any(trace["state"] == "withheld" for trace in traces):
        return "Required information needs clarification before changes can be compared reliably."
    changed = sorted(
        (trace for trace in traces if trace["signal_strength"] > 0),
        key=lambda trace: -trace["points"],
    )
    if not changed:
        return "No change was identified by the activity-change rules. Standard human review still applies."
    phrases = [RULE_PHRASES[trace["rule_id"]] for trace in changed[:2]]
    subject = " and ".join(phrases)
    return f"{subject[0].upper()}{subject[1:]} changed from the previous plan. This may be entirely legitimate."


def model_signals(view: pd.DataFrame) -> dict[str, str]:
    """Strict majority of other eligible plans; ties and singleton cohorts stay neutral."""
    eligible = view.loc[view["baseline_index"].notna() & view["model_index"].notna()]
    result = {}
    for row in view.to_dict("records"):
        if pd.isna(row["model_index"]) or pd.isna(row["baseline_index"]):
            result[row["plan_id"]] = "unavailable until required information is clarified"
            continue
        others = eligible.loc[eligible["plan_id"] != row["plan_id"], "model_index"]
        if others.empty:
            signal = "no comparison available (only one eligible plan in this view)"
        elif int((others < row["model_index"]).sum()) > len(others) / 2:
            signal = "higher than most plans in this view"
        elif int((others > row["model_index"]).sum()) > len(others) / 2:
            signal = "lower than most plans in this view"
        else:
            signal = "similar to other plans in this view (no strict majority)"
        result[row["plan_id"]] = signal
    return result


def information_items(record: dict) -> dict[str, bool] | None:
    """Group existing validation findings; unknown findings must not imply completeness."""
    items = dict.fromkeys((
        "Fictional subject link", "Previous version and activities", "Current version and activities",
        "Snapshot date", "Workflow timing", "Review due date", "Recorded completeness",
    ), True)
    source = validate_sources(record)
    flat = extract_features({key: value for key, value in record.items() if key != "versions"})
    for error in (*source.errors, *flat.errors):
        if error.startswith(("Previous/current", "Previous and current", "Derived features")):
            affected = ("Previous version and activities", "Current version and activities")
        elif error.startswith("previous"):
            affected = ("Previous version and activities",)
        elif error.startswith("current"):
            affected = ("Current version and activities",)
        elif error.startswith("Fictional subject"):
            affected = ("Fictional subject link",)
        elif error.startswith("snapshot_date"):
            affected = ("Snapshot date",)
        elif error.startswith("workflow_started_date"):
            affected = ("Workflow timing",)
        elif error.startswith("review_due_date"):
            affected = ("Review due date",)
        elif error.startswith("completeness_percent"):
            affected = ("Recorded completeness",)
        else:
            return None
        for name in affected:
            items[name] = False
    return items


def comparison_rows(record: dict) -> pd.DataFrame:
    source = validate_sources(record)
    rows = []
    if not source.errors:
        for suffix, label in MEASURES:
            before, after = source.values[f"previous_{suffix}"], source.values[f"current_{suffix}"]
            difference = after - before
            rows.append({
                "Measure": label, "Previous": before, "Current": after,
                "Change": f"{difference:+.2f}" if abs(difference) > 1e-8 else "No change",
            })
    return pd.DataFrame(rows, columns=["Measure", "Previous", "Current", "Change"])


def notable_changes(record: dict) -> list[str]:
    """Describe observed differences, not appropriateness or invented session moves."""
    comparison = comparison_rows(record)
    if comparison.empty:
        return []
    changes = [
        f"{row['Measure']}: {row['Change']} ({row['Previous']:.2f} to {row['Current']:.2f})."
        for row in comparison.to_dict("records") if row["Change"] != "No change"
    ]
    activities = activity_comparison(record)
    added = activities.loc[activities["Previous category"] == "Not present", "Activity"].tolist()
    removed = activities.loc[activities["Current category"] == "Not present", "Activity"].tolist()
    if added:
        changes.append(f"Activities added: {', '.join(added)}.")
    if removed:
        changes.append(f"Activities removed: {', '.join(removed)}.")
    old, new = (record["versions"][name] for name in ("previous", "current"))
    old_slots, new_slots = set(old["working_pattern"]), set(new["working_pattern"])
    if old_slots != new_slots:
        changes.append(
            "Working-pattern sessions: added " + (", ".join(sorted(new_slots - old_slots)) or "none")
            + "; removed " + (", ".join(sorted(old_slots - new_slots)) or "none")
            + ". This does not establish that a particular activity moved."
        )
    for row in activities.to_dict("records"):
        if "Not present" in (row["Previous category"], row["Current category"]):
            continue
        for field in ("session", "site", "category"):
            before, after = row[f"Previous {field}"], row[f"Current {field}"]
            if before != after:
                changes.append(f"Activity {row['Activity']} {field}: {before} to {after}.")
    return changes


def previous_snapshot_label(record: dict) -> str:
    # Linked v1 has version identities but no previous-version snapshot date.
    return "Previous-plan snapshot: not recorded in this synthetic fixture"
