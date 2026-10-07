from copy import deepcopy
from pathlib import Path

import pytest
import pandas as pd

from jobplan_poc.dataset import demonstration_plans
from jobplan_poc.integration import VALIDATION_NOTICE, worklist
from jobplan_poc.review_display import PRESENTATION_IDS


def start():
    testing = pytest.importorskip("streamlit.testing.v1")
    return testing.AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=60).run()


def text(app):
    return " ".join(item.value for kind in ("title", "subheader", "caption", "text", "markdown")
                    for item in getattr(app, kind))


def test_before_after_only_adds_derived_metadata_without_mutating_source():
    records = demonstration_plans()
    original = deepcopy(records.to_dict("records"))
    before = worklist(records, enhanced=False)
    after = worklist(records, enhanced=True)
    assert after[before.columns].equals(before)
    assert before.JobPlan.tolist() == after.JobPlan.tolist()
    assert after.loc[after.JobPlan == "JP-005", "Review priority"].iloc[0] == "Data clarification"
    assert "previous plan is missing" in after.loc[after.JobPlan == "JP-005", "Main reason"].iloc[0]
    assert "decreased by 6 PA" in after.loc[after.JobPlan == "JP-004", "Main reason"].iloc[0]
    assert not any("model" in column.lower() or "index" in column.lower() for column in after)
    pd.testing.assert_frame_equal(records, pd.DataFrame(original))


def test_existing_style_does_not_call_signal_provider(monkeypatch):
    from jobplan_poc import integration
    records = demonstration_plans()
    def unavailable(_):
        raise RuntimeError("provider unavailable")
    monkeypatch.setattr(integration, "assess_rules", unavailable)
    assert len(worklist(records, enhanced=False)) == 9


def test_integration_landing_and_four_representative_screens():
    app = start()
    assert not app.exception
    assert app.radio(key="navigation").value == "Product integration"
    assert VALIDATION_NOTICE in text(app)
    assert "not current product screenshots" in text(app)
    assert app.dataframe[0].value.JobPlan.tolist() == list(PRESENTATION_IDS)
    enhanced = app.dataframe[0].value.copy()
    app.radio(key="integration_mode").set_value("Existing-style").run()
    assert not app.exception
    assert "Review priority" not in app.dataframe[0].value.columns
    assert app.dataframe[0].value.JobPlan.tolist() == enhanced.JobPlan.tolist()
    app.button(key="integration_open").click().run()
    assert not app.exception
    assert "Current plan activities" in text(app)
    assert "Existing review / sign-off workflow" in text(app)
    assert not any(item.value == "Review signals" for item in app.subheader)
    current = app.dataframe[0].value.copy()
    app.radio(key="integration_mode").set_value("With review signals").run()
    assert not app.exception
    assert current.equals(app.dataframe[0].value)
    assert any(item.value == "Review signals" for item in app.subheader)
    assert "decreased by 6 PA" in text(app)
    assert "DCC allocation (PA): 7 → 1" in text(app)
    assert "No approval, rejection, edit or clarification request can be submitted" in text(app)
    assert not app.slider


def test_missing_comparison_retains_current_plan_and_existing_workflow():
    app = start()
    app.selectbox(key="integration_pick").set_value("JP-005").run()
    app.button(key="integration_open").click().run()
    assert not app.exception
    assert "previous plan is missing" in text(app)
    assert "Ordinary review remains available" in text(app)
    assert "Existing review / sign-off workflow" in text(app)
    assert len(app.dataframe[0].value) == 4
    assert not app.table  # No invented previous values.
    app.radio(key="integration_mode").set_value("Existing-style").run()
    assert not app.exception and len(app.dataframe[0].value) == 4
    app.button(key="integration_back").click().run()
    assert not app.exception and len(app.dataframe[0].value) == 3


def test_integration_is_independent_of_model_training_and_retains_poc_filters(monkeypatch):
    from jobplan_poc import dashboard
    with monkeypatch.context() as patch:
        def unavailable():
            raise RuntimeError("Model experiment unavailable")
        patch.setattr(dashboard, "load_demo", unavailable)
        app = start()
        assert not app.exception
        assert len(app.dataframe[0].value) == 3
    app.radio(key="navigation").set_value("Experiment results").run()
    assert not app.exception
    app.text_input(key="search").set_value("JP-005").run()
    app.number_input(key="budget").set_value(12).run()
    downloads = [item.proto.url for item in app.get("download_button")]
    app.radio(key="navigation").set_value("Product integration").run()
    assert not app.exception
    assert len(app.dataframe[0].value) == 3  # Presentation scope is isolated.
    app.radio(key="navigation").set_value("Experiment results").run()
    assert not app.exception
    assert app.text_input(key="search").value == "JP-005"
    assert app.number_input(key="budget").value == 12
    assert [item.proto.url for item in app.get("download_button")] == downloads
