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
    assert any("clinical-workspace-v4" in item.value for item in app.caption)
    assert any("Synthetic demo only" in item.value for item in app.caption)
    assert not app.metric
    assert [tab.label for tab in app.tabs] == [
        "Overview", "Review workspace", "Review patterns", "Evidence & export",
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
    assert benchmark(app).amendments_found.tolist() == [8, 6, 7]
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
    app.button[0].click().run()
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
    assert any("Insufficient required data" in item.value for item in app.warning)
    assert not app.button
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
