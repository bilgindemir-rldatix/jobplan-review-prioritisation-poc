from pathlib import Path

import pytest


def start_app():
    testing = pytest.importorskip("streamlit.testing.v1")
    return testing.AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"),
                                    default_timeout=60).run()


def test_tabs_filters_search_selection_and_empty_states():
    app = start_app()
    assert not app.exception
    assert [tab.label for tab in app.tabs] == [
        "Overview", "Review Queue", "Plan Detail & What-if", "Review Patterns", "Evidence & Export",
    ]
    assert any("SYNTHETIC" in item.value for item in app.warning)
    assert [item.value for item in app.tabs[0].metric] == ["133", "128", "5"]
    assert len(app.get("download_button")) == 2
    benchmark = app.tabs[4].dataframe[0].value.copy(deep=True)
    selected = app.selectbox(key="selected_plan").value
    alternative = next(value for value in app.selectbox(key="selected_plan").options if value != selected)
    app.sidebar.text_input[0].set_value(alternative.lower()).run()
    assert not app.exception
    assert app.selectbox(key="selected_plan").value == alternative
    assert app.selectbox(key="selected_plan").options == [alternative]
    assert alternative in app.tabs[2].header[0].value
    assert [item.value for item in app.tabs[0].metric][:2] == ["1", "1"]
    app.sidebar.text_input[0].set_value("no-such-fictional-plan").run()
    assert not app.exception
    assert [item.value for item in app.tabs[0].metric] == ["0", "0", "0"]
    assert not app.tabs[2].selectbox
    assert not app.tabs[2].header
    assert any("No plan is selected" in item.value for item in app.tabs[2].info)
    assert any("No workload groups" in item.value for item in app.tabs[3].info)
    assert app.tabs[4].dataframe[0].value.equals(benchmark)
    app.sidebar.text_input[0].set_value("").run()
    assert not app.exception
    assert app.selectbox(key="selected_plan").value in app.selectbox(key="selected_plan").options
    retained = app.selectbox(key="selected_plan").value
    app.sidebar.selectbox[0].select("Oldest-first").run()
    assert not app.exception
    assert app.selectbox(key="selected_plan").value == retained
    app.sidebar.multiselect[0].set_value([]).run()
    assert not app.exception
    assert any("No scored plans" in item.value for item in app.tabs[1].info)
    assert app.tabs[4].dataframe[0].value.equals(benchmark)


def test_what_if_isolation_and_completeness():
    app = start_app()
    assert not app.exception
    before = {
        i: [item.value.copy(deep=True) for item in app.tabs[i].dataframe]
        for i in (0, 1, 3, 4)
    }
    downloads = [item.proto.url for item in app.get("download_button")]
    metrics = [item.value for item in app.tabs[2].metric if item.label == "Prioritisation index"]
    assert any(item.label == "Recorded data completeness (%)" for item in app.tabs[2].metric)
    assert any("NOT model confidence" in item.value for item in app.tabs[2].caption)
    app.button[0].click().run()
    assert not app.exception
    assert [item.value for item in app.tabs[2].metric if item.label == "Prioritisation index"][-2:] == metrics
    app.slider[0].set_value(100.0)
    app.button[0].click().run()
    assert not app.exception
    assert any(item.value == "Scenario rules baseline" for item in app.tabs[2].subheader)
    for i, frames in before.items():
        for actual, expected in zip(app.tabs[i].dataframe, frames):
            assert actual.value.equals(expected)
    assert [item.proto.url for item in app.get("download_button")] == downloads


def test_unscored_detail_survives_priority_filter():
    from jobplan_poc.synthetic import generate_plans
    from jobplan_poc.evaluation import temporal_split

    records = temporal_split(generate_plans()).test
    plan_id = records.loc[records["previous_total_pa"].isna(), "plan_id"].iloc[0]
    app = start_app()
    app.sidebar.multiselect[3].set_value([]).run()
    assert not app.exception
    assert [item.value for item in app.tabs[0].metric] == ["5", "0", "5"]
    assert any("No scored plans" in item.value for item in app.tabs[1].info)
    app.selectbox(key="selected_plan").select(plan_id).run()
    assert not app.exception
    assert any("Insufficient required data" in item.value for item in app.error)
    assert all(item.value == "Unscored" for item in app.tabs[2].metric if item.label == "Prioritisation index")
    assert not app.button
    app.sidebar.text_input[0].set_value(plan_id).run()
    assert not app.exception
    assert app.selectbox(key="selected_plan").options == [plan_id]
