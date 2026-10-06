"""In-memory Streamlit demonstration: no uploads, external APIs or persistence."""

import pandas as pd
import streamlit as st

from jobplan_poc.evaluation import compare_methods, score_queue, temporal_split
from jobplan_poc.features import FEATURE_LABELS, extract_features
from jobplan_poc.presentation import (
    ViewConfig, export_csv, export_json, export_payload, filtered_queue,
    priority_distribution, workload_groups,
)
from jobplan_poc.scoring import ReviewModel, Score, fit_model, score_baseline, what_if
from jobplan_poc.synthetic import DEFAULT_SEED, REFERENCE_DATE, TEST_START, generate_plans


@st.cache_resource
def load_demo():
    """View schema v2: regenerate cached data after the tabbed-dashboard upgrade."""
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
    st.write(f"**Fictional department:** {record['department']}")
    st.metric("Recorded data completeness (%)", f"{record['completeness_percent']:.1f}")
    st.caption("Data-completeness indicator, NOT model confidence. All required scoring inputs must also be valid.")
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
                                    value=float(record["current_total_pa"]), step=0.1, key=f"{prefix}-total")
            wte = st.number_input("Scenario WTE", min_value=0.1, max_value=2.0,
                                  value=float(record["current_wte"]), step=0.1, key=f"{prefix}-wte")
            completeness = st.slider("Scenario completeness (%)", 0.0, 100.0,
                                     float(record["completeness_percent"]), 0.1, key=f"{prefix}-completeness")
            age = st.number_input("Scenario days in workflow stage", min_value=0, max_value=1000,
                                  value=int(features.values["workflow_age_days"]), key=f"{prefix}-age")
            due_offset = st.number_input("Scenario due date offset from snapshot (days; negative = overdue)",
                                         min_value=-1000, max_value=1000,
                                         value=int((record["review_due_date"] - record["snapshot_date"]).days),
                                         key=f"{prefix}-due")
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


def display_evidence(split, model, queue, budget: int) -> None:
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


def main() -> None:
    st.set_page_config(page_title="JobPlan Review Prioritisation POC", layout="wide")
    st.title("JobPlan Review Prioritisation")
    st.warning(
        "SYNTHETIC DEMONSTRATION ONLY. Supports Clinical Director review prioritisation, not clinical judgement. "
        "Does not rate clinician performance or predict clinical safety. No real clinician data or NHS policy thresholds."
    )
    st.caption(
        "All identifiers and records are fictional. No confirmed ejobplan fields or contracts are used. "
        "No uploads, integrations, LLM explanations or saved edits."
    )
    try:
        split, model, queue = load_demo()
    except ValueError as exc:
        st.error(f"Demo cannot be scored: {exc}")
        st.stop()
    st.sidebar.header("Shared review view")
    ranking = st.sidebar.selectbox("Rank by", ["Experimental ML", "Rules baseline", "Oldest-first"])
    specialties = st.sidebar.multiselect("Specialty", sorted(queue["specialty"].unique()),
                                         default=sorted(queue["specialty"].unique()))
    patterns = st.sidebar.multiselect("Working pattern", sorted(queue["working_pattern"].unique()),
                                      default=sorted(queue["working_pattern"].unique()))
    stages = st.sidebar.multiselect("Workflow stage", sorted(queue["workflow_stage"].unique()),
                                    default=sorted(queue["workflow_stage"].unique()))
    priorities = st.sidebar.multiselect("Review priority", ["High", "Medium", "Low"], default=["High", "Medium", "Low"])
    search = st.sidebar.text_input("Search fictional ID, department, specialty or review reasons")
    st.sidebar.caption("Case-insensitive literal phrase search across both scorers' actual drivers and input-error reasons.")
    budget = int(st.sidebar.number_input("Fixed review budget K", min_value=1, max_value=500, value=30, step=1))
    config = ViewConfig(ranking, tuple(specialties), tuple(patterns), tuple(stages), tuple(priorities), search)
    view = filtered_queue(queue, config)
    ranked = view[view["baseline_index"].notna()]
    needs_triage = view[view["baseline_index"].isna()]
    source_label = "Experimental ML" if config.source == "model" else "Rules baseline"
    st.caption(
        f"View scope: {len(view)} of {len(queue)} later synthetic holdout plans match the sidebar filters/search. "
        f"Priority categories, distribution and actions use {source_label}; ordering uses {ranking}. "
        "Rules and ML indices remain separate. Unscored plans bypass the priority filter but not the other filters/search. "
        "The evidence benchmark always uses the full eligible holdout, not this filtered view."
    )
    tabs = st.tabs(["Overview", "Review Queue", "Plan Detail & What-if", "Review Patterns", "Evidence & Export"])
    with tabs[0]:
        st.header("Review workload overview")
        st.info(
            "Historical pre-review simulation, not a live waiting list. Ages and overdue days are calculated at each "
            "row's snapshot, never today's clock. An amendment or a high review priority is not a finding of poor performance."
        )
        columns = st.columns(3)
        columns[0].metric("Plans in filtered view", len(view))
        columns[1].metric("Eligible scored plans", len(ranked))
        columns[2].metric("Unscored - data clarification", len(needs_triage))
        if view.empty:
            st.info("No plans match the current filters and search.")
        st.subheader(f"Priority distribution - {source_label}")
        st.dataframe(priority_distribution(view, config.source), hide_index=True, width="stretch")
        st.caption(
            "Counts cover scored plans in this filtered view, not all holdout plans. Unscored plans are separate, "
            "never Low. Completeness is a recorded data indicator, NOT model confidence or clinical assurance."
        )
        st.write(
            "Start with the queue and separate data-clarification list; inspect a plan's context and exact explanations "
            "before deciding on review. What-if edits are isolated experiments, not recommendations."
        )
    with tabs[1]:
        st.header("Review queue")
        st.caption(
            "Ranks apply only to scored plans. Identical scores are tied by fictional plan ID. "
            "The first K rows are highlighted by within_view_budget; exports include the whole filtered view."
        )
        if ranking == "Oldest-first":
            st.caption("Oldest-first means time in current workflow stage; categories and drivers remain rules-based.")
        if ranked.empty:
            st.info("No scored plans match the current filters and search.")
        else:
            display = ranked[[
                "plan_id", "department", "specialty", "working_pattern", "workflow_stage", "snapshot_date",
                "baseline_index", "baseline_category", "model_index", "model_category", "workflow_age_days",
                "completeness_percent", "data_sufficiency", f"{config.source}_main_driver",
                f"{config.source}_action",
            ]].copy()
            display.insert(0, "rank", range(1, len(display) + 1))
            display.insert(1, "within_view_budget", display["rank"] <= budget)
            st.dataframe(display, hide_index=True, width="stretch")
        st.subheader("Needs data triage - unscored")
        if needs_triage.empty:
            st.caption("No insufficient-data records match the non-priority filters and search.")
        else:
            st.dataframe(needs_triage[[
                "plan_id", "department", "specialty", "completeness_percent", "data_sufficiency",
                "input_errors", "baseline_action",
            ]], hide_index=True, width="stretch")
    with tabs[2]:
        detail_ids = view["plan_id"].tolist()
        if st.session_state.get("selected_plan") not in detail_ids:
            st.session_state["selected_plan"] = detail_ids[0] if detail_ids else None
        if detail_ids:
            selected = st.selectbox("Choose a plan for detail", detail_ids, key="selected_plan")
            record = split.test.loc[split.test["plan_id"] == selected].iloc[0].to_dict()
            display_detail(record, model)
        else:
            st.info("No plan is selected: no plans match the current filters and search.")
    with tabs[3]:
        st.header("Review-workload distribution")
        st.warning(
            "Descriptive review workload, NOT clinical quality, clinician performance or evidence of causal problems. "
            "Small groups and changes to filters can make comparisons misleading."
        )
        st.caption(
            f"Same filtered original-plan view; source: {source_label}. "
            "High-priority rate = high-priority scored plans / scored plans within each group, "
            "NOT / all plans. Total = scored + unscored. Zero scored denominator gives an unavailable rate. "
            "Groups with fewer than 5 scored plans are flagged; do not compare their rates. "
            "Priority filtering also changes denominators: a High-only view will show 100% for scored groups."
        )
        if view.empty:
            st.info("No workload groups to display for the current filters and search.")
        else:
            for group in ("department", "specialty"):
                st.subheader(f"By fictional {group}")
                st.dataframe(workload_groups(view, group, config.source), hide_index=True, width="stretch")
        st.caption(
            "Departments are two deterministic fictional groupings of specialties, not real organisational mappings. "
            "They are not predictors and do not affect scores or outcomes."
        )
    with tabs[4]:
        display_evidence(split, model, queue, budget)
        st.subheader("Export current original-plan view")
        st.caption(
            f"Exports contain {len(ranked)} scored and {len(needs_triage)} unscored original plans matching this view. "
            "BASELINE here means the unchanged source records, not rules-only scoring: both scores, categories, "
            "exact contributions, actions and data sufficiency are included. No scenario edits or outcome labels. "
            "Not limited to the review budget. JSON uses null for unavailable values. "
            "CSV begins with a scope metadata record, followed by plan records; select record_type=plan for analysis. "
            "Text that could be interpreted as a spreadsheet formula is apostrophe-prefixed in CSV only."
        )
        payload = export_payload(queue, config, model)
        st.download_button("Download filtered queue CSV", export_csv(payload, list(queue.columns)),
                           file_name="synthetic-review-queue.csv", mime="text/csv", key="export_csv")
        st.download_button("Download filtered queue JSON", export_json(payload),
                           file_name="synthetic-review-queue.json", mime="application/json", key="export_json")
