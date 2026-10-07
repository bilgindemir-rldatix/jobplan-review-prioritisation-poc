from pathlib import Path
import re

import pytest


ROOT = Path(__file__).resolve().parents[1]


def start_app():
    testing = pytest.importorskip("streamlit.testing.v1")
    return testing.AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()


def navigate(app, page):
    app.radio(key="navigation").set_value(page).run()
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


def test_navigation_reason_first_queue_and_no_technical_indices():
    app = start_app()
    assert not app.exception
    assert app.title[0].value == "Review queue"
    assert app.sidebar.title[0].value == "JobPlan review"
    assert any(item.value == "Review queue" for item in app.title)
    assert app.radio(key="navigation").options == ["Review queue", "Rules vs ML", "About this POC"]
    assert app.radio(key="navigation").value == "Review queue"
    assert not app.tabs and not app.metric
    assert "clinical-workspace-v7" in content(app)
    assert not any("Build:" in item.value for item in app.title)
    assert app.selectbox(key="order").value == "Rules-led"
    assert [item.label for item in app.button if item.key.startswith("summary_")] == [
        "Review sooner · 0", "Standard review · 128", "Data clarification required · 5",
    ]
    assert not app.number_input  # Budget is not part of the reviewer rail.
    assert not app.dataframe
    assert len(plan_buttons(app)) == 13  # Eight scored cards and five separate clarification cards.
    assert any("changed from the previous plan" in item.value for item in app.markdown)
    assert not re.search(r"R-0[1-5]|/100|/ 100|Unscored|Rules index|ML index", content(app))
    assert "higher than most plans" in content(app) or "lower than most plans" in content(app)


def test_search_empty_reset_and_selection_consistency():
    app = start_app()
    initial = [item.key for item in plan_buttons(app)]
    selected = plan_buttons(app)[1].key.removeprefix("view_")
    app.text_input(key="search").set_value(selected.lower()).run()
    assert [item.key for item in plan_buttons(app)] == ["view_" + selected]
    app.button(key="view_" + selected).click().run()
    assert not app.exception
    assert app.session_state["selected_plan"] == selected
    assert any(f"JobPlan {selected}" in item.value.replace("\\", "") for item in app.title)
    assert not app.text_input
    navigate(app, "Rules vs ML")
    assert benchmark(app).amendments_found.tolist()[:3] == [8, 6, 7]
    navigate(app, "Review queue")
    assert app.session_state["selected_plan"] == selected
    back(app)
    assert app.text_input(key="search").value == selected.lower()
    app.text_input(key="search").set_value("no-such-fictional-plan").run()
    assert not app.exception
    assert not plan_buttons(app)
    assert app.session_state["selected_plan"] is None
    assert "Reset filters & search" in content(app)
    app.button(key="reset_filters").click().run()
    assert not app.exception
    assert [item.key for item in plan_buttons(app)] == initial
    assert app.selectbox(key="order").value == "Rules-led"


def test_category_filters_and_separate_missing_data_actions():
    app = start_app()
    app.button(key="summary_Data clarification required").click().run()
    assert not app.exception
    assert len(plan_buttons(app)) == 5
    assert all(item.label == "Request data clarification" for item in plan_buttons(app))
    assert "previous plan unavailable" in content(app)
    assert "Information available: 6 of 7 required items" in content(app)
    assert "Unscored" not in content(app)
    plan_buttons(app)[0].click().run()
    assert not app.exception
    assert "Data clarification required" in content(app)
    assert "Priority cannot be reliably calculated" in content(app)
    assert "Comparison withheld" in content(app)
    assert not any(item.label == "Score isolated scenario" for item in app.button)
    assert "Suggested review priority: Data clarification required" in content(app)
    back(app)
    app.button(key="summary_Data clarification required").click().run()
    assert len(plan_buttons(app)) == 13
    app.button(key="summary_Review sooner").click().run()
    assert len(plan_buttons(app)) == 5  # Priority never conceals matching clarification records.


def test_scenario_detail_comparison_dialog_and_reviewer_control():
    app = start_app()
    app.toggle(key="show_demos").set_value(True).run()
    assert not app.exception
    assert len(plan_buttons(app)) == 9
    app.button(key="view_JP-003").click().run()
    assert not app.exception
    assert "Suggested review priority: Standard review" in content(app)
    assert "DCC allocation" in content(app) and "-3.50" in content(app).replace("\\", "")
    assert "This may be entirely legitimate" in content(app)
    assert "The decision remains with the authorised reviewer" in content(app)
    assert app.radio(key="consideration-JP-003").value is None
    assert any(item.label == "Compare versions" for item in app.expander)
    assert any("Change" in item.value.columns for item in app.table)
    app.button(key="why_highlighted").click().run()
    assert not app.exception
    assert "Why this plan appeared" in content(app)
    assert "Rule details" in content(app) and "Experimental model" in content(app)
    labels = [item.label for item in app.expander]
    assert any(label.startswith("R-01") for label in labels)
    assert "View model details" in labels
    assert "not index or probability contributions" in content(app)
    assert "training-mean" in content(app)
    assert len(app.json) == 5
    app.button(key="close_explanation").click().run()
    assert not app.exception
    assert not app.json
    back(app)
    app.toggle(key="show_demos").set_value(False).run()
    assert not app.exception
    assert all(item.key.startswith("view_FIC-") for item in plan_buttons(app))
    assert app.session_state["selected_plan"] is None


def test_what_if_does_not_change_exports_cohort_or_benchmark():
    app = start_app()
    navigate(app, "Rules vs ML")
    evidence_before = benchmark(app).copy(deep=True)
    downloads_before = [item.proto.url for item in app.get("download_button")]
    navigate(app, "Review queue")
    before = [item.key for item in plan_buttons(app)]
    plan_buttons(app)[0].click().run()
    assert not app.exception
    app.slider[0].set_value(100.0)
    next(item for item in app.button if item.label == "Score isolated scenario").click().run()
    assert not app.exception
    assert "Scenario rules baseline:" in content(app)
    navigate(app, "Rules vs ML")
    assert benchmark(app).equals(evidence_before)
    assert [item.proto.url for item in app.get("download_button")] == downloads_before
    navigate(app, "Review queue")
    back(app)
    assert [item.key for item in plan_buttons(app)] == before


def test_about_content_fixed_benchmark_and_filter_state_across_pages():
    app = start_app()
    app.text_input(key="search").set_value("no-such-plan").run()
    navigate(app, "Rules vs ML")
    app.number_input(key="budget").set_value(12).run()
    assert benchmark(app).reviewed.tolist() == [12] * 5
    assert "No workload groups" in content(app)
    navigate(app, "About this POC")
    text = content(app)
    for expected in (
        "finite review time", "not proven time savings", "No live eJobPlan integration",
        "automatic approval/rejection", "ML has not demonstrated an advantage",
        "independently reviewed outcome", "information governance", "subgroup",
        "review time and usability", "Shadow mode is proposed, NOT implemented",
        "SYNTHETIC AMENDMENT", "seven grouped requirements", "Review sooner", "Medium and Low",
    ):
        assert expected in text
    assert benchmark(app).amendments_found.tolist() == [8, 6, 7]
    assert benchmark(app).reviewed.eq(30).all()
    navigate(app, "Review queue")
    assert app.text_input(key="search").value == "no-such-plan"
    app.button(key="reset_filters").click().run()
    navigate(app, "Rules vs ML")
    assert app.number_input(key="budget").value == 12
    assert benchmark(app).reviewed.eq(12).all()


def test_experiment_disagreements_model_summary_and_no_blending():
    app = start_app()
    app.toggle(key="show_demos").set_value(True).run()
    app.text_input(key="search").set_value("JP-005").run()
    navigate(app, "Rules vs ML")
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
        "FIC-00001-completeness": 57.0, "show_demos": True,
    }
    monkeypatch.setattr(dashboard.st, "session_state", state)
    dashboard.reset_review_filters(queue)
    assert queue.equals(original)
    assert state["selected_plan"] is None and state["search"] == ""
    assert state["queue_page"] == 0 and state["order"] == "Rules-led"
    assert state["FIC-00001-completeness"] == 57.0
    assert state["budget"] == 12 and state["show_demos"] is True
    dashboard.open_detail("A")
    assert state["selected_plan"] == "A"
    dashboard.change_priority_filter("Standard review")
    assert state["selected_plan"] is None and state["priority_filter"] == "Standard review"


def test_pagination_and_source_switch_clear_obsolete_selection():
    app = start_app()
    first = [item.key for item in plan_buttons(app) if item.label == "View JobPlan"]
    app.button(key="queue_page_next").click().run()
    assert not app.exception
    second = [item.key for item in plan_buttons(app) if item.label == "View JobPlan"]
    assert not set(first) & set(second)
    app.selectbox(key="order").set_value("Experimental model").run()
    assert not app.exception
    assert app.session_state["queue_page"] == 0
    app.multiselect(key="specialties").set_value([]).run()
    assert not app.exception
    assert not plan_buttons(app) and app.session_state["selected_plan"] is None
    app.button(key="reset_filters").click().run()
    assert not app.exception
    assert [item.key for item in plan_buttons(app) if item.label == "View JobPlan"] == first


def test_only_static_theme_uses_unsafe_html():
    app = start_app()
    unsafe = [item.value for item in app.markdown if item.proto.allow_html]
    from jobplan_poc.theme import CSS
    assert unsafe == ["<style>" + CSS + "</style>"]
    app.text_input(key="search").set_value('<img src=x onerror="alert(1)">').run()
    assert not app.exception
    assert [item.value for item in app.markdown if item.proto.allow_html] == unsafe
