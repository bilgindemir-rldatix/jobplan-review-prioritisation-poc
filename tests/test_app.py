from pathlib import Path

import pytest


def test_dashboard_smoke_filters_detail_and_what_if():
    testing = pytest.importorskip("streamlit.testing.v1")
    app = testing.AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=60)
    app.run()
    assert not app.exception
    assert "JobPlan Review Prioritisation" in app.title[0].value
    assert any("SYNTHETIC" in item.value for item in app.warning)
    assert len(app.dataframe) >= 6
    queue_before = app.dataframe[0].value.copy(deep=True)
    benchmark_before = app.dataframe[-1].value.copy(deep=True)
    original_metrics = [item.value for item in app.metric]
    app.button[0].click().run()
    assert not app.exception
    assert [item.value for item in app.metric][-2:] == original_metrics
    app.slider[0].set_value(100.0)
    app.button[0].click().run()
    assert not app.exception
    assert any(item.value == "Scenario rules baseline" for item in app.subheader)
    assert app.dataframe[0].value.equals(queue_before)
    assert app.dataframe[-1].value.equals(benchmark_before)
    app.sidebar.selectbox[0].select("Oldest-first").run()
    assert not app.exception
    app.sidebar.multiselect[0].set_value([]).run()
    assert not app.exception
    assert any("No scored plans" in item.value for item in app.info)
    assert app.dataframe[-1].value.equals(benchmark_before)


def test_unscored_detail():
    testing = pytest.importorskip("streamlit.testing.v1")
    from jobplan_poc.synthetic import generate_plans
    from jobplan_poc.evaluation import temporal_split

    records = temporal_split(generate_plans()).test
    plan_id = records.loc[records["previous_total_pa"].isna(), "plan_id"].iloc[0]
    app = testing.AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=60)
    app.run()
    app.sidebar.multiselect[3].set_value([]).run()
    assert not app.exception
    assert any("No scored plans" in item.value for item in app.info)
    assert plan_id in app.selectbox[0].options
    app.selectbox[0].select(plan_id).run()
    assert not app.exception
    assert any("Insufficient required data" in item.value for item in app.error)
    assert all(item.value == "Unscored" for item in app.metric)
    assert not app.button
