from pathlib import Path
import json
import re

import pytest


ROOT = Path(__file__).resolve().parents[1]


def start_app():
    testing = pytest.importorskip("streamlit.testing.v1")
    app = testing.AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    app.radio(key="navigation").set_value("Review queue").run()
    return app


def navigate(app, page):
    app.radio(key="navigation").set_value(page).run()
    assert not app.exception


def experiment(app, collection=None):
    navigate(app, "Experiment results")
    if collection:
        app.selectbox(key="collection").set_value(collection).run()
        assert not app.exception


def benchmark(app):
    return next(item.value for item in app.dataframe if "amendments_found" in item.value.columns)


def content(app):
    return " ".join(item.value for kind in ("title", "subheader", "caption", "markdown", "text", "info", "warning")
                    for item in getattr(app, kind))


def plan_buttons(app):
    return [item for item in app.button if item.key and item.key.startswith("view_")]


def back(app):
    next(item for item in app.button if item.label == "Back to queue").click().run()
    assert not app.exception


def test_navigation_three_plans_and_no_primary_technical_controls():
    app = start_app()
    assert not app.exception
    assert app.title[0].value == "Plans to review"
    assert app.sidebar.title[0].value == "JobPlan review"
    assert app.radio(key="navigation").options == ["Product integration", "Review queue", "Experiment results", "About the POC"]
    assert app.radio(key="navigation").value == "Review queue"
    assert not app.tabs and not app.metric
    assert "clinical-workspace-v9" in content(app)
    assert not any("Build:" in item.value for item in app.title)
    assert not app.number_input and not app.selectbox and not app.text_input
    assert not app.dataframe and not app.expander
    assert [item.key for item in plan_buttons(app)] == ["view_JP-004", "view_JP-002", "view_JP-005"]
    assert all(item.label == "Review JobPlan" for item in plan_buttons(app))
    assert "3 plans · 1 review sooner · 1 need data clarification" in content(app)
    assert "DCC allocation decreased by 6 PA and the working pattern changed." in content(app)
    assert "The previous plan is missing" in content(app)
    assert not re.search(r"R-0[1-5]|/100|/ 100|Unscored|Rules index|ML index|Experimental model", content(app))
    assert len(app.button) == 3


def test_search_empty_reset_and_selection_consistency():
    app = start_app()
    app.button(key="view_JP-002").click().run()
    assert app.session_state["selected_plan"] == "JP-002"
    experiment(app)
    assert benchmark(app).amendments_found.tolist()[:3] == [8, 6, 7]
    navigate(app, "Review queue")
    assert app.session_state["selected_plan"] == "JP-002"
    back(app)
    experiment(app)
    app.text_input(key="search").set_value("no-such-fictional-plan").run()
    assert not app.exception
    assert "No plans match the analysis filters" in content(app)
    navigate(app, "Review queue")
    assert not plan_buttons(app)
    assert app.session_state["selected_plan"] is None
    assert "No plans match the current settings" in content(app)
    app.button(key="reset_demo").click().run()
    assert not app.exception
    assert len(plan_buttons(app)) == 3
    experiment(app)
    assert app.text_input(key="search").value == ""
    assert app.selectbox(key="order").value == "Rules-led"


def test_missing_plan_is_not_low_priority_and_never_has_an_invented_comparison():
    app = start_app()
    app.button(key="view_JP-005").click().run()
    assert not app.exception
    assert "The previous plan is missing, so changes cannot be compared." in content(app)
    assert "A reliable comparison is not available" in content(app)
    assert "Information available: 6 of 7 required items" in content(app)
    assert not any("Change" in item.value.columns for item in app.table)
    assert not any(item.label == "Score isolated scenario" for item in app.button)
    assert app.radio(key="consideration-JP-005").value is None
    back(app)
    experiment(app)
    app.selectbox(key="priority_filter").set_value("Review sooner").run()
    navigate(app, "Review queue")
    assert [item.key for item in plan_buttons(app)] == ["view_JP-004", "view_JP-005"]


def test_immediate_comparison_judgement_and_optional_rule_only_dialog():
    app = start_app()
    app.button(key="view_JP-004").click().run()
    assert not app.exception
    assert [item.value for item in app.subheader][:3] == [
        "Why this plan was highlighted", "What changed?", "What would you do next?",
    ]
    comparison = app.table[0].value
    assert comparison.loc["DCC allocation (PA)", "Previous"] == 7
    assert comparison.loc["DCC allocation (PA)", "Current"] == 1
    assert comparison.loc["DCC allocation (PA)", "Change"] == "-6.00"
    assert "Final judgement remains with the authorised reviewer" in content(app)
    assert app.radio(key="consideration-JP-004").options == [
        "Continue standard review", "Seek clarification", "Review earlier",
    ]
    assert app.radio(key="consideration-JP-004").value is None
    assert "See details" in [item.label for item in app.expander]
    assert not app.slider
    app.radio(key="consideration-JP-004").set_value("Seek clarification").run()
    assert "No decision or request is saved or sent" in content(app)
    app.button(key="why_highlighted").click().run()
    assert not app.exception
    assert "Rule details" in content(app)
    assert any(item.label.startswith("R-01") for item in app.expander)
    assert "Why the model highlighted this" not in [item.label for item in app.expander]
    assert len(app.json) == 5
    app.button(key="close_explanation").click().run()
    assert not app.exception and not app.json
    back(app)
    assert len(plan_buttons(app)) == 3


def test_what_if_does_not_change_exports_cohort_or_benchmark():
    app = start_app()
    before = [item.key for item in plan_buttons(app)]
    experiment(app)
    evidence_before = benchmark(app).copy(deep=True)
    downloads_before = [item.proto.url for item in app.get("download_button")]
    app.slider[0].set_value(100.0)
    next(item for item in app.button if item.label == "Score isolated scenario").click().run()
    assert not app.exception
    assert "Scenario rules baseline:" in content(app)
    assert benchmark(app).equals(evidence_before)
    assert [item.proto.url for item in app.get("download_button")] == downloads_before
    navigate(app, "Review queue")
    assert [item.key for item in plan_buttons(app)] == before
    assert "Scenario rules baseline:" not in content(app)


def test_about_short_story_fixed_benchmark_and_settings_across_pages():
    app = start_app()
    experiment(app)
    app.text_input(key="search").set_value("no-such-plan").run()
    app.number_input(key="budget").set_value(12).run()
    assert benchmark(app).reviewed.tolist() == [12] * 5
    assert "No workload groups" in content(app)
    navigate(app, "About the POC")
    text = content(app)
    for expected in (
        "many JobPlans and limited review time", "Why ML?", "Who", "not proven time savings",
        "No live eJobPlan integration", "ML has not demonstrated an advantage",
        "independently reviewed outcome", "information governance", "subgroup",
        "Shadow mode is proposed, NOT implemented", "SYNTHETIC AMENDMENT",
    ):
        assert expected in text
    assert benchmark(app).amendments_found.tolist() == [8, 6, 7]
    assert benchmark(app).reviewed.eq(30).all()
    navigate(app, "Review queue")
    assert not plan_buttons(app)
    app.button(key="reset_demo").click().run()
    experiment(app)
    assert app.number_input(key="budget").value == 12
    assert benchmark(app).reviewed.eq(12).all()
    summary = next(item.value for item in app.table if "Plans reviewed" in item.value.columns)
    assert summary["Plans reviewed"].eq(12).all()


def test_experiment_disagreements_model_summary_and_no_blending():
    app = start_app()
    experiment(app, "All demonstration scenarios")
    app.text_input(key="search").set_value("JP-005").run()
    assert benchmark(app).amendments_found.tolist()[:3] == [8, 6, 7]
    assert "No blended score" in content(app)
    disagreements = next(item.value for item in app.dataframe if "selected_by" in item.value.columns)
    assert len(disagreements) == 44
    assert disagreements.selected_by.value_counts().to_dict() == {"ML only at K": 22, "Rules only at K": 22}
    assert "100 permutations" in content(app)
    assert any("Mean absolute signed-term magnitude" in item.value.columns for item in app.table)
    assert len(app.get("download_button")) == 2
    app.number_input(key="budget").set_value(500).run()
    assert not app.exception
    assert "No top-K selection disagreements" in content(app)
    assert benchmark(app).reviewed.eq(128).all()


def test_filter_callbacks_only_change_view_state(monkeypatch):
    from jobplan_poc import dashboard
    from jobplan_poc.synthetic import generate_plans

    queue = generate_plans(20)
    original = queue.copy(deep=True)
    state = {
        "selected_plan": "old", "search": "old", "order": "Experimental model",
        "priority_filter": "Review sooner", "queue_page": 3, "budget": 12,
        "FIC-00001-completeness": 57.0, "collection": "Evaluation holdout",
    }
    monkeypatch.setattr(dashboard.st, "session_state", state)
    dashboard.reset_review_filters(queue)
    assert queue.equals(original)
    assert state["selected_plan"] is None and state["search"] == ""
    assert state["queue_page"] == 0 and state["order"] == "Rules-led"
    assert state["FIC-00001-completeness"] == 57.0
    assert state["budget"] == 12 and state["collection"] == "Evaluation holdout"
    dashboard.open_detail("A")
    assert state["selected_plan"] == "A"


def test_full_holdout_pagination_collection_change_and_reset():
    app = start_app()
    experiment(app, "Evaluation holdout")
    navigate(app, "Review queue")
    assert "133 plans" in content(app)
    first = [item.key for item in plan_buttons(app)]
    assert len(first) == 13
    app.button(key="queue_page_next").click().run()
    assert not app.exception
    second = [item.key for item in plan_buttons(app)]
    assert first[:8] != second[:8]
    plan_buttons(app)[0].click().run()
    experiment(app, "All demonstration scenarios")
    assert app.session_state["selected_plan"] is None
    navigate(app, "Review queue")
    assert len(plan_buttons(app)) == 9
    app.button(key="reset_demo").click().run()
    assert len(plan_buttons(app)) == 3
    experiment(app, "Evaluation holdout")
    navigate(app, "Review queue")
    assert "133 plans" in content(app)  # Old scenario-only service filters do not leak.


def test_only_static_theme_uses_unsafe_html():
    app = start_app()
    unsafe = [item.value for item in app.markdown if item.proto.allow_html]
    from jobplan_poc.theme import CSS
    assert unsafe == ["<style>" + CSS + "</style>"]
    experiment(app)
    app.text_input(key="search").set_value('<img src=x onerror="alert(1)">').run()
    assert not app.exception
    assert [item.value for item in app.markdown if item.proto.allow_html] == unsafe


@pytest.mark.parametrize("plan_id,reason", [
    ("JP-005", "previous plan unavailable"),
    ("JP-006", "current plan is partial"),
    ("JP-007", "declared total contradicts"),
])
def test_invalid_scenario_dialog_withholds_values_and_names_actual_problem(plan_id, reason):
    app = start_app()
    experiment(app, "All demonstration scenarios")
    app.selectbox(key="inspection_plan").set_value(plan_id).run()
    assert not app.exception
    app.button(key="analysis_evidence").click().run()
    assert not app.exception
    assert reason in content(app)
    traces = [json.loads(item.value) for item in app.json if "rule_id" in json.loads(item.value)]
    assert len(traces) == 5
    for trace in traces:
        assert trace["state"] == "withheld"
        assert trace["points"] is None and trace["observed_difference"] is None
    assert "Experimental model: unavailable" in content(app)
    assert not any(item.label == "Score isolated scenario" for item in app.button)


def test_model_analysis_order_does_not_change_rules_led_review_priority():
    app = start_app()
    experiment(app, "All demonstration scenarios")
    app.selectbox(key="order").set_value("Experimental model").run()
    app.selectbox(key="inspection_plan").set_value("JP-009").run()
    app.button(key="analysis_evidence").click().run()
    assert not app.exception
    assert "Why the model highlighted this" in [item.label for item in app.expander]
    assert "not index or probability contributions" in content(app)
    assert "training-mean" in content(app)
    app.button(key="close_explanation").click().run()
    navigate(app, "Review queue")
    assert plan_buttons(app)[0].key == "view_JP-004"
    app.button(key="view_JP-009").click().run()
    assert not app.exception
    assert "No change was identified by the activity-change rules" in content(app)
    assert "Experimental model signal:" not in content(app)
    assert not app.slider
