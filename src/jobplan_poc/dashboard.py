"""In-memory Streamlit demonstration: no uploads, external APIs or persistence."""

import pandas as pd
import streamlit as st

from jobplan_poc.evaluation import compare_methods, rank_queue, score_queue, temporal_split
from jobplan_poc.features import FEATURE_LABELS, extract_features
from jobplan_poc.scoring import ReviewModel, Score, fit_model, score_baseline, what_if
from jobplan_poc.synthetic import DEFAULT_SEED, REFERENCE_DATE, TEST_START, generate_plans


@st.cache_resource
def load_demo():
    records = generate_plans()
    split = temporal_split(records)
    model = fit_model(split.training)
    queue = score_queue(split.test, model)
    return split, model, queue


def display_score(title: str, score: Score) -> None:
    st.subheader(title)
    st.metric("Prioritisation index", "Unscored" if score.index is None else f"{score.index:.1f} / 100")
    st.write(f"**Review priority: {score.category}**")
    st.caption(score.sufficiency)
    st.write(score.action)
    if score.index is None:
        return
    st.caption(f"Largest absolute term: {score.main_driver}")
    contributions = pd.DataFrame([
        {"Feature": FEATURE_LABELS[name], "Contribution": value}
        for name, value in sorted(score.contributions.items(), key=lambda item: abs(item[1]), reverse=True)
    ])
    st.dataframe(contributions, hide_index=True, width="stretch")
    if score.intercept is not None:
        st.caption(
            f"Signed model log-odds units, not index or probability contributions. "
            f"Intercept {score.intercept:+.4f} + terms {sum(score.contributions.values()):+.4f} "
            f"= decision {score.decision:+.4f}. Positive raises, negative lowers the model decision "
            f"relative to the training-mean feature reference. Correlation is not causation."
        )
    else:
        st.caption("Non-negative baseline index points; these terms sum to the rules index, not an ML explanation.")


def display_detail(record: dict, model: ReviewModel) -> None:
    st.header(f"Plan detail: {record['plan_id']}")
    st.write(
        f"**{record['specialty']} | {record['working_pattern']} | {record['workflow_stage']}**"
    )
    st.caption(
        f"Pre-review snapshot: {record['snapshot_date']:%Y-%m-%d}; "
        f"illustrative due date: {record['review_due_date']:%Y-%m-%d}. "
        "Each fictional entity appears once; the previous-plan values are contextual inputs, not a second training row."
    )
    comparison = pd.DataFrame([
        {"Measure": label, "Previous": record[f"previous_{field}"], "Current": record[f"current_{field}"]}
        for field, label in [
            ("wte", "Whole-time equivalent (WTE)"),
            ("total_pa", "Total weekly programmed activities (PA)"),
            ("direct_care_pa", "Direct care PA"),
            ("supporting_pa", "Supporting activity PA"),
            ("other_pa", "Other activity PA"),
        ]
    ])
    comparison["Change"] = comparison["Current"] - comparison["Previous"]
    st.subheader("Previous / current activity comparison")
    st.dataframe(comparison, hide_index=True, width="stretch")
    st.caption(
        "PA and activity groupings are illustrative. A different specialty, working pattern or legitimate plan change "
        "is not evidence of poor performance, misconduct or clinical safety concerns."
    )
    features = extract_features(record)
    if features.values is None:
        st.error("Insufficient required data: this plan has no index. It must not be treated as low priority.")
        for error in features.errors:
            st.write(f"- {error}")
    else:
        st.dataframe(
            pd.DataFrame([{"Derived pre-review feature": FEATURE_LABELS[key], "Value": value}
                          for key, value in features.values.items()]),
            hide_index=True, width="stretch",
        )
    baseline_column, model_column = st.columns(2)
    with baseline_column:
        display_score("Rules baseline", score_baseline(record))
    with model_column:
        display_score("Experimental learned model", model.score(record))
    st.caption(
        "Illustrative boundaries for both indices: Low < 35; Medium 35 to < 65; High 65 to 100. "
        "Categories use unrounded scores. These indices are different constructions, not interchangeable measurements."
    )
    with st.expander("Isolated what-if scenario", expanded=False):
        st.warning(
            "Exploration only: these edits stay in memory and do not change the source plan, review queue, model "
            "or benchmark. They are neither causal estimates nor advice to alter a plan to obtain a lower score."
        )
        if features.values is None:
            st.info("What-if is unavailable until required source data is sufficient. Resolve the data through human triage.")
            return
        prefix = record["plan_id"]
        with st.form(f"scenario-{prefix}"):
            total = st.number_input("Scenario total weekly PA", min_value=0.1, max_value=40.0,
                                    value=float(record["current_total_pa"]), step=0.1)
            wte = st.number_input("Scenario WTE", min_value=0.1, max_value=2.0,
                                  value=float(record["current_wte"]), step=0.1)
            completeness = st.slider("Scenario completeness (%)", 0.0, 100.0,
                                     float(record["completeness_percent"]), 0.1)
            age = st.number_input("Scenario days in workflow stage", min_value=0, max_value=1000,
                                  value=int(features.values["workflow_age_days"]))
            due_offset = st.number_input("Scenario due date offset from snapshot (days; negative = overdue)",
                                         min_value=-1000, max_value=1000,
                                         value=int((record["review_due_date"] - record["snapshot_date"]).days))
            submitted = st.form_submit_button("Score isolated scenario")
        st.caption(
            "Changing the total preserves the original activity mix; the previous plan remains fixed. "
            "Control bounds are demo UI limits, not contractual or policy thresholds."
        )
        if submitted:
            original_total = record["current_total_pa"]
            direct = round(total * record["current_direct_care_pa"] / original_total, 2)
            supporting = round(total * record["current_supporting_pa"] / original_total, 2)
            updates = {
                "current_total_pa": total,
                "current_direct_care_pa": direct,
                "current_supporting_pa": supporting,
                "current_other_pa": total - direct - supporting,
                "current_wte": wte,
                "completeness_percent": completeness,
                "workflow_started_date": record["snapshot_date"] - pd.Timedelta(age, unit="D"),
                "review_due_date": record["snapshot_date"] + pd.Timedelta(due_offset, unit="D"),
            }
            _, scenario_baseline, scenario_model = what_if(record, updates, model)
            if scenario_baseline.errors:
                st.error("Scenario is unscored: " + " ".join(scenario_baseline.errors))
            left, right = st.columns(2)
            with left:
                display_score("Scenario rules baseline", scenario_baseline)
            with right:
                display_score("Scenario learned model", scenario_model)


def main() -> None:
    st.set_page_config(page_title="JobPlan Review Prioritisation POC", layout="wide")
    st.title("JobPlan Review Prioritisation")
    st.warning(
        "SYNTHETIC DEMONSTRATION ONLY. Supports Clinical Director review prioritisation, not clinical judgement. "
        "Does not rate clinician performance or predict clinical safety. No real clinician data or NHS policy thresholds."
    )
    st.caption(
        "All identifiers and records are fictional. No confirmed ejobplan fields or contracts are used. "
        "There are no uploads, integrations, LLM explanations or saved edits."
    )
    try:
        split, model, queue = load_demo()
    except ValueError as exc:
        st.error(f"Demo cannot be scored: {exc}")
        st.stop()
    st.info(
        "This is a historical pre-review simulation, not a live waiting list. Ages and overdue days are calculated "
        "at each row's snapshot, never today's clock. Outcomes are used only to train on earlier records and "
        "evaluate the later holdout. A material amendment is not a finding of poor performance."
    )
    st.sidebar.header("Review queue filters")
    ranking = st.sidebar.selectbox("Rank by", ["Experimental ML", "Rules baseline", "Oldest-first"])
    specialties = st.sidebar.multiselect("Specialty", sorted(queue["specialty"].unique()),
                                         default=sorted(queue["specialty"].unique()))
    patterns = st.sidebar.multiselect("Working pattern", sorted(queue["working_pattern"].unique()),
                                      default=sorted(queue["working_pattern"].unique()))
    stages = st.sidebar.multiselect("Workflow stage", sorted(queue["workflow_stage"].unique()),
                                    default=sorted(queue["workflow_stage"].unique()))
    priorities = st.sidebar.multiselect("Review priority", ["High", "Medium", "Low"], default=["High", "Medium", "Low"])
    budget = int(st.sidebar.number_input("Fixed review budget K", min_value=1, max_value=500, value=30, step=1))
    column = {"Experimental ML": "model_index", "Rules baseline": "baseline_index", "Oldest-first": "workflow_age_days"}[ranking]
    category_column = "model_category" if ranking == "Experimental ML" else "baseline_category"
    driver_column = "model_main_driver" if ranking == "Experimental ML" else "baseline_main_driver"
    action_column = "model_action" if ranking == "Experimental ML" else "baseline_action"
    filtered = queue[
        queue["specialty"].isin(specialties)
        & queue["working_pattern"].isin(patterns)
        & queue["workflow_stage"].isin(stages)
    ]
    needs_triage = filtered[filtered["baseline_index"].isna()]
    eligible = filtered[filtered[category_column].isin(priorities)]
    ranked = rank_queue(eligible, column)
    st.header("Review queue")
    st.write(f"**{len(ranked)} scored plans in this view | {len(needs_triage)} require separate data triage**")
    st.caption(
        "Unscored plans are never ranked last or counted as Low: they have a separate human-triage list below. "
        "Priority filters do not hide data-triage records. Identical scores are tied by fictional plan ID."
    )
    if ranking == "Oldest-first":
        st.caption("Oldest-first means time in the current workflow stage. Categories and drivers shown remain those of the rules baseline.")
    if ranked.empty:
        st.info("No scored plans match the current filters.")
    else:
        display = ranked[[
            "plan_id", "specialty", "working_pattern", "workflow_stage", "snapshot_date",
            "baseline_index", "model_index", category_column, "workflow_age_days",
            "data_sufficiency", driver_column, action_column,
        ]].copy()
        display.insert(0, "rank", range(1, len(display) + 1))
        display.insert(1, "within_view_budget", display["rank"] <= budget)
        st.dataframe(display, hide_index=True, width="stretch")
    st.subheader("Needs data triage - unscored")
    if needs_triage.empty:
        st.caption("No insufficient-data records match the specialty, pattern and workflow filters.")
    else:
        st.dataframe(needs_triage[["plan_id", "specialty", "workflow_stage", "data_sufficiency", "baseline_action"]],
                     hide_index=True, width="stretch")
    detail_ids = [*ranked["plan_id"].tolist(), *needs_triage["plan_id"].tolist()]
    if detail_ids:
        selected = st.selectbox("Choose a plan for detail", detail_ids)
        record = split.test.loc[split.test["plan_id"] == selected].iloc[0].to_dict()
        display_detail(record, model)

    st.header("Synthetic-only fixed-budget benchmark")
    st.warning(
        "The learned model is learning generator behaviour. This does not establish real-world validity, calibration, "
        "fairness or clinical utility. ML is not guaranteed to outperform the baseline or oldest-first."
    )
    outcomes = split.test.set_index("plan_id")["material_amendment"]
    metrics = compare_methods(queue, outcomes, budget)
    st.dataframe(metrics, hide_index=True, width="stretch")
    st.caption(
        f"Full later holdout, unaffected by queue filters or what-if edits; same sufficient cohort for all methods. "
        f"{len(queue) - int(metrics.iloc[0]['cohort'])} insufficient-data rows excluded from ALL benchmark methods "
        "(not a recommendation to ignore them). Actual K is min(requested budget, eligible cohort size). "
        "Precision = amendments found / reviewed; recall = amendments found / all amendments in the eligible cohort. "
        "Undefined metrics are shown as empty/None, never zero; no-positive recall is unavailable. "
        "Outcomes are stochastic synthetic material amendments observed 30 days after the snapshot."
    )
    with st.expander("Model and data provenance"):
        st.write(
            f"Seed {DEFAULT_SEED}; fixed reference date {REFERENCE_DATE:%Y-%m-%d}; "
            f"test starts {TEST_START:%Y-%m-%d}. Training uses {model.training_rows} sufficient records "
            f"from {model.training_min:%Y-%m-%d} to {model.training_max:%Y-%m-%d}; "
            f"{model.excluded_training_rows} insufficient training rows excluded; "
            f"{split.purged_rows} records purged at the temporal boundary; {len(split.test)} later holdout rows."
        )
        st.write(
            "StandardScaler and L2-regularised logistic regression are fitted on earlier training records only. "
            "Only five named pre-review features enter the model; IDs, specialty, working pattern, "
            "workflow stage label, outcomes and outcome dates do not. There is no hyperparameter search. "
            "Repeated holdout entity IDs are excluded from training if supplied."
        )
        st.write(
            "ML index = 100 times the logistic transform of its linear decision. It is the fitted model output "
            "rescaled to 0-100, NOT a calibrated real-world probability. Exact signed contributions add to the "
            "model log-odds decision before the nonlinear transform, not to the index. "
            "The reference is the training-feature mean, not a clinical norm. "
            "Neither differences nor model terms determine whether a change is appropriate."
        )
        st.caption("See README.md for complete rules, synthetic target definition, limitations and reproducible results.")
