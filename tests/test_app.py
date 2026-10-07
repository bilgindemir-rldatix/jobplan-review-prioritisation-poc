from pathlib import Path
import tomllib

import pytest


ROOT = Path(__file__).resolve().parents[1]


def start_app():
    testing = pytest.importorskip("streamlit.testing.v1")
    return testing.AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()


def queue_frames(app):
    return [item.value.copy(deep=True) for item in app.dataframe if "Viewing" in item.value.columns]


def benchmark(app):
    return next(item.value for item in app.dataframe if "amendments_found" in item.value.columns)


def test_workspace_identity_selection_search_empty_and_secondary_navigation():
    app = start_app()
    assert not app.exception
    assert app.header[0].value == "JobPlan review workspace"
    assert any("clinical-workspace-v6" in item.value for item in app.caption)
    assert any("Synthetic demo only" in item.value for item in app.caption)
    assert not app.metric
    assert [tab.label for tab in app.tabs] == [
        "Overview", "Review workspace", "Review patterns", "Evidence & export", "About this initiative",
    ]
    assert len(app.get("column")) == 2
    assert any("**133** plans" in item.value and "**128** scored" in item.value for item in app.markdown)
    assert len(app.get("download_button")) == 2
    alternative = app.selectbox(key="selected_plan").options[1]
    app.text_input(key="search").set_value(alternative.lower()).run()
    assert not app.exception
    assert app.selectbox(key="selected_plan").value == alternative
    assert app.selectbox(key="selected_plan").options == [alternative]
    assert any(item.value == f"Plan {alternative}" for item in app.subheader)
    selected = queue_frames(app)[0]
    assert selected.loc[selected.Viewing, "plan_id"].tolist() == [alternative]
    app.text_input(key="search").set_value("no-such-fictional-plan").run()
    assert not app.exception
    assert not any(item.key == "selected_plan" for item in app.selectbox)
    assert not any(item.value.startswith("Plan FIC-") for item in app.subheader)
    assert any("No plan is selected" in item.value for item in app.info)
    assert any("No workload groups" in item.value for item in app.info)
    assert len(app.get("download_button")) == 2
    assert benchmark(app).amendments_found.tolist()[:3] == [8, 6, 7]
    app.text_input(key="search").set_value("").run()
    assert not app.exception
    retained = app.selectbox(key="selected_plan").options[2]
    app.selectbox(key="selected_plan").select(retained).run()
    assert len(app.tabs[2].dataframe) == 2
    assert app.selectbox(key="selected_plan").value == retained
    app.selectbox(key="ranking").select("Oldest-first").run()
    assert not app.exception
    assert app.selectbox(key="selected_plan").value == retained
    app.checkbox(key="stacked").check().run()
    assert not app.exception
    assert not app.get("column")
    assert any(item.value == f"Plan {retained}" for item in app.subheader)
    app.multiselect(key="specialties").set_value([]).run()
    assert not app.exception
    assert any("No scored plans" in item.value for item in app.info)


def test_what_if_isolation_completeness_and_secondary_downloads():
    app = start_app()
    assert not app.exception
    selected_plan = app.selectbox(key="selected_plan").value
    before = queue_frames(app)
    assert any("Recorded completeness" in item.value and "NOT model confidence" in item.value for item in app.caption)
    patterns_before = [item.value.copy(deep=True) for item in app.tabs[2].dataframe]
    evidence_before = benchmark(app).copy(deep=True)
    downloads_before = [item.proto.url for item in app.get("download_button")]
    assert app.selectbox(key="selected_plan").value == selected_plan
    app.slider[0].set_value(100.0)
    next(button for button in app.button if button.label == "Score isolated scenario").click().run()
    assert not app.exception
    assert any("Scenario rules baseline:" in item.value for item in app.markdown)
    for actual, expected in zip(queue_frames(app), before):
        assert actual.equals(expected)
    for actual, expected in zip(app.tabs[2].dataframe, patterns_before):
        assert actual.value.equals(expected)
    assert benchmark(app).equals(evidence_before)
    assert [item.proto.url for item in app.get("download_button")] == downloads_before


def test_unscored_detail_and_compact_priority_indicators():
    from jobplan_poc.synthetic import generate_plans
    from jobplan_poc.evaluation import temporal_split

    records = temporal_split(generate_plans()).test
    plan_id = records.loc[records["previous_total_pa"].isna(), "plan_id"].iloc[0]
    app = start_app()
    app.multiselect(key="priorities").set_value([]).run()
    assert not app.exception
    assert any("**5** plans" in item.value and "**0** scored" in item.value for item in app.markdown)
    app.selectbox(key="selected_plan").select(plan_id).run()
    assert not app.exception
    assert any("Data clarification required" in item.value for item in app.warning)
    assert not any(button.label == "Score isolated scenario" for button in app.button)
    app.text_input(key="search").set_value(plan_id).run()
    assert not app.exception
    assert app.selectbox(key="selected_plan").options == [plan_id]
    triage = queue_frames(app)[0]
    assert triage.loc[triage.Viewing, "plan_id"].tolist() == [plan_id]
    assert "completeness_percent" in triage.columns
    assert any("Unscored" in item.value and "Rules index" in item.value for item in app.markdown)


def test_table_selection_callback_is_bound_to_displayed_ids(monkeypatch):
    from jobplan_poc import dashboard

    state = {"queue-1": {"selection": {"rows": [1]}}, "selected_plan": "A"}
    monkeypatch.setattr(dashboard.st, "session_state", state)
    dashboard.select_table_plan("queue-1", ["C", "B", "A"])
    assert state["selected_plan"] == "B"
    state["queue-1"]["selection"]["rows"] = []
    dashboard.select_table_plan("queue-1", ["C", "B", "A"])
    assert state["selected_plan"] == "B"


def test_light_theme_readable_contrast():
    theme = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text())["theme"]
    assert theme["base"] == "light"

    def luminance(colour):
        rgb = [int(colour[index:index + 2], 16) / 255 for index in (1, 3, 5)]
        linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in rgb]
        return sum(value * weight for value, weight in zip(linear, (0.2126, 0.7152, 0.0722)))

    for foreground, background in [
        (theme["textColor"], theme["backgroundColor"]),
        (theme["textColor"], theme["secondaryBackgroundColor"]),
        (theme["primaryColor"], theme["backgroundColor"]),
    ]:
        values = sorted([luminance(foreground), luminance(background)])
        assert (values[1] + 0.05) / (values[0] + 0.05) >= 4.5


def test_reset_filters_search_and_selection_without_changing_model_or_budget():
    app = start_app()
    initial_frames = queue_frames(app)
    initial_evidence = benchmark(app).copy(deep=True)
    initial_downloads = [item.proto.url for item in app.get("download_button")]
    initial_plan = app.selectbox(key="selected_plan").value
    app.multiselect(key="specialties").set_value(["Radiology"])
    app.multiselect(key="patterns").set_value(["Full-time"])
    app.multiselect(key="stages").set_value(["Draft"])
    app.multiselect(key="priorities").set_value(["High"])
    app.selectbox(key="ranking").select("Rules baseline")
    app.text_input(key="search").set_value("no-such-plan").run()
    assert not app.exception
    assert not any(item.key == "selected_plan" for item in app.selectbox)
    assert any("Reset filters & search" in item.value for item in app.info)
    app.button(key="reset_filters").click().run()
    assert not app.exception
    assert app.text_input(key="search").value == ""
    assert app.selectbox(key="ranking").value == "Rules baseline"
    for key in ("specialties", "patterns", "stages", "priorities"):
        widget = app.multiselect(key=key)
        assert set(widget.value) == set(widget.options)
    assert app.selectbox(key="selected_plan").value == initial_plan
    for actual, expected in zip(queue_frames(app), initial_frames):
        assert actual.equals(expected)
    assert benchmark(app).equals(initial_evidence)
    assert [item.proto.url for item in app.get("download_button")] == initial_downloads
    budget = next(item for item in app.number_input if item.label == "Review budget K")
    budget.set_value(12)
    app.checkbox(key="stacked").check()
    app.text_input(key="search").set_value("no-such-plan").run()
    app.button(key="reset_filters").click().run()
    assert not app.exception
    assert next(item for item in app.number_input if item.label == "Review budget K").value == 12
    assert app.checkbox(key="stacked").value is True


def test_initiative_content_and_fixed_default_benchmark():
    app = start_app()
    initiative = app.tabs[4]
    content = " ".join(item.value for item in [*initiative.markdown, *initiative.caption])
    for expected in (
        "finite review time", "value", "not proven time savings", "No live eJobPlan integration",
        "automatic approval/rejection", "ML has not demonstrated an advantage",
        "independently reviewed outcome", "information governance", "subgroup",
        "review time and usability", "Shadow mode is proposed, NOT implemented",
    ):
        assert expected in content
    default = next(item.value for item in initiative.dataframe if "amendments_found" in item.value.columns)
    assert default.reviewed.tolist() == [30, 30, 30]
    assert default.amendments_found.tolist() == [8, 6, 7]
    next(item for item in app.number_input if item.label == "Review budget K").set_value(12)
    app.text_input(key="search").set_value("no-such-plan").run()
    assert not app.exception
    assert benchmark(app).reviewed.tolist() == [12] * 5
    actual = next(item.value for item in app.tabs[4].dataframe if "amendments_found" in item.value.columns)
    assert actual.equals(default)


def test_reset_callback_only_changes_view_state(monkeypatch):
    from jobplan_poc import dashboard
    from jobplan_poc.synthetic import generate_plans

    queue = generate_plans(20)
    original = queue.copy(deep=True)
    state = {
        "selected_plan": "old", "search": "old", "ranking": "Rules baseline",
        "queue_signature": ("old",), "queue_revision": 4, "budget": 12,
        "FIC-00001-completeness": 57.0, "stacked": True,
    }
    monkeypatch.setattr(dashboard.st, "session_state", state)
    dashboard.reset_review_filters(queue)
    assert queue.equals(original)
    assert state["selected_plan"] is None
    assert "queue_signature" not in state
    assert state["queue_revision"] == 4
    assert state["FIC-00001-completeness"] == 57.0
    assert state["budget"] == 12 and state["stacked"] is True


def test_linked_review_scenarios_trace_and_evaluation_isolation():
    app = start_app()
    assert app.selectbox(key="ranking").value == "Rules baseline"
    evidence = benchmark(app).copy(deep=True)
    assert any("Why highlighted?" in item.label for item in app.expander)
    app.radio(key="cohort").set_value("Demonstration scenarios").run()
    assert not app.exception
    assert len(app.selectbox(key="selected_plan").options) == 9
    assert any("Never used for fitting" in item.value for item in app.info)
    app.selectbox(key="selected_plan").select("JP-003").run()
    assert not app.exception
    assert benchmark(app).equals(evidence)
    traces = next(item.value for item in app.dataframe if "rule_id" in item.value.columns)
    assert traces.loc[traces.rule_id == "R-01", "points"].iloc[0] == 0
    assert traces.loc[traces.rule_id == "R-04", "points"].iloc[0] == 15
    activities = next(item.value for item in app.dataframe if "Activity" in item.value.columns)
    assert activities["Current PA"].sum() == 5
    assert activities["Previous PA"].sum() == 10
    assert any("Prioritisation is not a decision" in item.value for item in app.caption)
    for plan_id in ("JP-005", "JP-006", "JP-007"):
        app.selectbox(key="selected_plan").select(plan_id).run()
        assert not app.exception
        assert any("Data clarification required" in item.value for item in app.warning)
        assert any("Comparison withheld" in item.value for item in app.info)
        traces = next(item.value for item in app.dataframe if "rule_id" in item.value.columns)
        assert traces.state.eq("withheld").all()
        assert traces.points.isna().all()
        assert not any(item.label == "Score isolated scenario" for item in app.button)
        assert benchmark(app).equals(evidence)
    app.radio(key="cohort").set_value("Evaluation holdout").run()
    assert not app.exception
    assert all(value.startswith("FIC-") for value in app.selectbox(key="selected_plan").options)


def test_experiment_disagreement_and_whole_cohort_ui():
    app = start_app()
    assert not app.exception
    evidence = app.tabs[3]
    assert any("top-K overlap" in item.value for item in evidence.subheader)
    comparisons = next(item.value for item in evidence.dataframe if "selected_by" in item.value.columns)
    assert len(comparisons) == 44
    assert comparisons.selected_by.value_counts().to_dict() == {"ML only at K": 22, "Rules only at K": 22}
    assert any("100 permutations" in item.value for item in evidence.caption)
    next(item for item in app.number_input if item.label == "Review budget K").set_value(500).run()
    assert not app.exception
    assert any("No top-K selection disagreements" in item.value for item in app.tabs[3].info)
    assert benchmark(app).reviewed.eq(128).all()
