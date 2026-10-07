from copy import deepcopy
from pathlib import Path
import tomllib

import pandas as pd
import pytest

from jobplan_poc.dataset import demonstration_plans
from jobplan_poc.review_display import (
    comparison_rows, display_category, information_items, markdown_text, model_signals,
    PRESENTATION_IDS, notable_changes, plain_reason, previous_snapshot_label, review_reason, rules_applied,
)
from jobplan_poc.rules import assess_rules
from jobplan_poc.theme import CSS, TOKENS


@pytest.fixture
def cases():
    return {row["plan_id"]: row for row in demonstration_plans().to_dict("records")}


def test_display_categories_do_not_recalculate_indices():
    assert [display_category(value) for value in ("High", "Medium", "Low", "Unscored")] == [
        "Review sooner", "Standard review", "Standard review", "Data clarification",
    ]
    with pytest.raises(KeyError):
        display_category("Safe")


def test_reason_and_notable_changes_are_source_faithful(cases):
    legitimate = cases["JP-003"]
    before = deepcopy(legitimate)
    traces = assess_rules(legitimate).export_traces()
    assert rules_applied(traces) == 1
    assert plain_reason(traces) == (
        "The working pattern changed from the previous plan. This may be entirely legitimate."
    )
    assert not any(rule_id in plain_reason(traces) for rule_id in ("R-01", "R-04"))
    changes = notable_changes(legitimate)
    assert "DCC allocation (PA): -3.50 (7.00 to 3.50)." in changes
    assert "Whole-time equivalent (WTE): -0.50 (1.00 to 0.50)." in changes
    assert any("does not establish that a particular activity moved" in value for value in changes)
    for field in ("site", "session"):
        old = {a["activity_id"]: a for a in legitimate["versions"]["previous"]["activities"]}
        new = {a["activity_id"]: a for a in legitimate["versions"]["current"]["activities"]}
        for identity in old.keys() & new.keys():
            sentence = f"Activity {identity} {field}: {old[identity][field]} to {new[identity][field]}."
            assert (sentence in changes) == (old[identity][field] != new[identity][field])
    assert legitimate == before
    assert comparison_rows(cases["JP-001"])["Change"].eq("No change").all()
    assert notable_changes(cases["JP-001"]) == []
    assert "No change was identified" in plain_reason(assess_rules(cases["JP-001"]).export_traces())
    assert "not recorded" in previous_snapshot_label(legitimate)


def test_partial_signals_and_withheld_comparisons(cases):
    small = assess_rules(cases["JP-002"]).export_traces()
    assert not any(trace["triggered"] for trace in small)
    assert rules_applied(small) == 1
    assert "allocation mix" in plain_reason(small)
    assert "materially" not in plain_reason(small)
    for identity in ("JP-005", "JP-006", "JP-007"):
        record = cases[identity]
        traces = assess_rules(record).export_traces()
        assert "clarification" in plain_reason(traces)
        assert rules_applied(traces) == 0
        assert notable_changes(record) == []
        assert comparison_rows(record).empty
        assert sum(information_items(record).values()) < 7
    assert sum(information_items(cases["JP-001"]).values()) == 7
    assert information_items(cases["JP-005"])["Previous version and activities"] is False
    assert information_items(cases["JP-006"])["Current version and activities"] is False
    assert information_items(cases["JP-007"])["Current version and activities"] is False
    incomplete = deepcopy(cases["JP-001"])
    incomplete["completeness_percent"] = 20
    assert sum(information_items(incomplete).values()) == 7  # Known percentage is a valid input, not confidence.
    incomplete["review_due_date"] = None
    assert information_items(incomplete)["Review due date"] is False


def test_presentation_subset_and_concise_reasons_are_source_faithful(cases):
    assert PRESENTATION_IDS == ("JP-004", "JP-002", "JP-005")
    assert all(cases[key]["cohort"] == "demonstration" for key in PRESENTATION_IDS)
    expected = {
        "JP-004": "DCC allocation decreased by 6 PA and the working pattern changed.",
        "JP-002": "DCC allocation decreased by 0.2 PA and SPA allocation increased by 0.2 PA.",
        "JP-005": "The previous plan is missing, so changes cannot be compared.",
    }
    original = deepcopy(cases)
    for key, record in cases.items():
        traces = assess_rules(record).export_traces()
        reason = review_reason(record, traces)
        assert reason == review_reason(record, traces)
        if key in expected:
            assert reason == expected[key]
        assert not any(term in reason for term in ("R-0", "model", "confidence", "/100"))
    assert cases == original
    assert "No change was identified" in review_reason(cases["JP-009"], assess_rules(cases["JP-009"]).export_traces())


def test_unknown_validation_finding_never_reports_complete(cases, monkeypatch):
    from jobplan_poc import review_display
    from jobplan_poc.records import SourceResult
    monkeypatch.setattr(review_display, "validate_sources", lambda record: SourceResult({}, ("New validation rule",)))
    assert information_items(cases["JP-001"]) is None


def test_model_relative_signal_handles_strict_majority_ties_singleton_and_missing():
    view = pd.DataFrame({
        "plan_id": ["A", "B", "C", "D", "E"], "baseline_index": [10, 10, 10, 10, None],
        "model_index": [10, 20, 20, 90, None],
    })
    signals = model_signals(view)
    assert signals["A"].startswith("lower")
    assert signals["D"].startswith("higher")
    assert signals["B"].startswith("similar") and signals["C"].startswith("similar")
    assert signals["E"].startswith("unavailable")
    assert "only one" in model_signals(view.iloc[[0]])["A"]
    assert model_signals(view.iloc[0:0]) == {}


def contrast(foreground, background):
    def luminance(colour):
        rgb = [int(colour[index:index + 2], 16) / 255 for index in (1, 3, 5)]
        linear = [value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4 for value in rgb]
        return sum(value * weight for value, weight in zip(linear, (.2126, .7152, .0722)))
    low, high = sorted((luminance(foreground), luminance(background)))
    return (high + .05) / (low + .05)


def test_theme_tokens_have_text_and_control_contrast():
    for foreground, background in (
        ("surface", "brand-deep"), ("surface", "brand-primary"), ("surface", "brand-hover"),
        ("text", "surface"), ("text-secondary", "surface"), ("text-muted", "canvas"),
        ("text", "mint"), ("attention-text", "attention-bg"), ("info-text", "info-bg"),
        ("error-text", "error-bg"),
    ):
        assert contrast(TOKENS[foreground], TOKENS[background]) >= 4.5
    for foreground, background in (
        ("border-control", "surface"), ("brand-primary", "surface"), ("brand-primary", "canvas"),
        ("attention-icon", "attention-bg"),
    ):
        assert contrast(TOKENS[foreground], TOKENS[background]) >= 3
    config = tomllib.loads((Path(__file__).resolve().parents[1] / ".streamlit" / "config.toml").read_text())["theme"]
    assert config["primaryColor"] == TOKENS["brand-primary"]
    assert config["sidebar"]["backgroundColor"] == TOKENS["brand-deep"]
    assert config["textColor"] == TOKENS["text"]
    assert config["baseFontSize"] == 14


def test_dynamic_text_is_escaped_and_never_enters_static_css():
    text = '<script>alert("test")</script> **bold** [link](https://invalid) :material/warning:'
    escaped = markdown_text(text)
    assert "<script>" not in escaped and "&lt;script&gt;" in escaped
    assert r"\*\*bold\*\*" in escaped
    assert r"\[link\]" in escaped and r"\:material/" in escaped
    assert text not in CSS
    assert "javascript" not in CSS.lower()
