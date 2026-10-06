"""In-memory Streamlit demonstration: no uploads, external APIs or persistence."""

from functools import partial

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


BUILD_LABEL = "clinical-workspace-v4"


@st.cache_resource
def load_demo():
    """View schema v2: regenerate cached data after the tabbed-dashboard upgrade."""
    records = generate_plans()
    split = temporal_split(records)
    model = fit_model(split.training)
    queue = score_queue(split.test, model)
    return split, model, queue


def display_score(title: str, score: Score) -> None:
    value = "Unscored" if score.index is None else f"{score.index:.1f} / 100"
    st.markdown(f"**{title}: {value} | {score.category}**")
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


def display_detail(record: dict, model: ReviewModel, source: str) -> None:
    st.subheader(f"Plan {record['plan_id']}")
    st.caption(f"{record['specialty']} | {record['working_pattern']} | {record['workflow_stage']}")
    baseline, ml = score_baseline(record), model.score(record)
    selected_score = ml if source == "model" else baseline
    for label, score in [("Rules index", baseline), ("Experimental ML index", ml)]:
        value = "Unscored" if score.index is None else f"{score.index:.1f} / 100"
        st.markdown(f"**{label}** &nbsp; {value} &nbsp; | &nbsp; {score.category}")
    st.caption("Separate review-priority indices, not a clinical probability. Low does not mean no review needed.")
    st.markdown("**Next human action**")
    st.write(selected_score.action)
    if selected_score.errors:
        st.warning("Insufficient required data - unscored, not Low.")
        for error in selected_score.errors:
            st.text(error)
    else:
        st.markdown("**Main review driver**")
        st.write(selected_score.main_driver)
    st.caption(
        f"Recorded completeness: {record['completeness_percent']:.1f}% | {selected_score.sufficiency}. "
        "Data completeness is NOT model confidence."
    )
    st.caption(
        f"Snapshot {record['snapshot_date']:%d %b %Y} | Illustrative review due {record['review_due_date']:%d %b %Y}"
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
    with st.expander("Previous / current plan", expanded=True):
        st.dataframe(comparison, hide_index=True, width="stretch",
                     column_config={name: st.column_config.NumberColumn(format="%.2f")
                                    for name in ("Previous", "Current", "Change")})
        st.caption("WTE = whole-time equivalent; PA = programmed activities. Legitimate variation is not poor performance.")
    features = extract_features(record)
    with st.expander("Score breakdown & input context"):
        st.caption(f"Department: {record['department']}. Each entity has one pre-review row; previous values are context.")
        if features.values is not None:
            st.dataframe(
                pd.DataFrame([{"Derived pre-review feature": FEATURE_LABELS[key], "Value": value}
                              for key, value in features.values.items()]),
                hide_index=True, width="stretch",
            )
        display_score("Rules baseline", baseline)
        display_score("Experimental learned model", ml)
        st.caption(
            "Illustrative boundaries: Low < 35; Medium 35 to < 65; High 65 to 100, using unrounded values. "
            "These are not policy thresholds. Model terms are signed log-odds contributions, not index points."
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
            display_score("Scenario rules baseline", scenario_baseline)
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


def select_table_plan(table_key: str, plan_ids: list[str]) -> None:
    rows = st.session_state[table_key]["selection"]["rows"]
    if rows and 0 <= rows[0] < len(plan_ids):
        st.session_state["selected_plan"] = plan_ids[rows[0]]


def display_queue_table(records: pd.DataFrame, source: str, table_key: str, *, triage: bool = False) -> None:
    plan_ids = records["plan_id"].tolist()
    fields = (["plan_id", "completeness_percent"] if triage else
              ["plan_id", f"{source}_category", "baseline_index", "model_index"])
    display = records[fields].copy()
    display.insert(0, "Viewing", display["plan_id"] == st.session_state.get("selected_plan"))
    st.dataframe(
        display, hide_index=True, width="stretch", height=180 if triage else 390,
        row_height=32, key=table_key, on_select=partial(select_table_plan, table_key, plan_ids),
        selection_mode="single-row",
        column_config={
            "Viewing": st.column_config.CheckboxColumn("Viewing", width="small"),
            "plan_id": st.column_config.TextColumn("Plan", width="small"),
            "specialty": st.column_config.TextColumn("Specialty"),
            f"{source}_category": st.column_config.TextColumn("Priority"),
            "baseline_index": st.column_config.NumberColumn("Rules /100", format="%.1f", width="small"),
            "model_index": st.column_config.NumberColumn("ML /100", format="%.1f", width="small"),
            "completeness_percent": st.column_config.NumberColumn("Complete %", format="%.1f",
                                                                 help="Recorded data completeness, NOT model confidence."),
        },
    )


def display_patterns(view: pd.DataFrame, source: str, source_label: str) -> None:
    st.subheader("Review-workload distribution")
    st.caption("Descriptive workload, not clinical quality, clinician performance or evidence of causal problems.")
    st.caption(
        f"Filtered original plans | Source: {source_label}. High-priority rate = high / scored plans in each group. "
        "Total = scored + unscored; zero scored denominator means unavailable. "
        "Do not compare rates for groups with fewer than 5 scored plans. "
        "Filters affect denominators: a High-only view will show 100% for scored groups."
    )
    if view.empty:
        st.info("No workload groups to display for the current filters and search.")
    else:
        for group in ("department", "specialty"):
            st.markdown(f"**By fictional {group}**")
            st.dataframe(workload_groups(view, group, source), hide_index=True, width="stretch",
                         column_config={
                             group: st.column_config.TextColumn(group.capitalize()),
                             "total_plans": "All plans", "scored_plans": "Scored", "unscored_plans": "Unscored",
                             "high_priority_plans": "High priority",
                             "high_priority_rate_among_scored": st.column_config.NumberColumn(
                                 "High / scored", format="%.2f", help="Proportion, 0 to 1; not percentage"),
                             "interpretation": "Interpretation",
                         })
    st.caption("Departments are fictional display groupings, not real organisations or model predictors.")


def main() -> None:
    st.set_page_config(page_title="JobPlan | Review workspace", layout="wide")
    st.header("JobPlan review workspace")
    st.caption(f"Clinical Director review support | Build: {BUILD_LABEL}")
    st.caption("Synthetic demo only. Supports human review, not clinician performance assessment or clinical safety prediction.")
    try:
        split, model, queue = load_demo()
    except ValueError as exc:
        st.error(f"Demo cannot be scored: {exc}")
        st.stop()

    st.sidebar.subheader("Review view")
    ranking = st.sidebar.selectbox("Order and priority source", ["Experimental ML", "Rules baseline", "Oldest-first"], key="ranking")
    with st.sidebar.expander("Filter plans"):
        specialties = st.multiselect("Specialty", sorted(queue["specialty"].unique()),
                                     default=sorted(queue["specialty"].unique()), key="specialties")
        patterns = st.multiselect("Working pattern", sorted(queue["working_pattern"].unique()),
                                  default=sorted(queue["working_pattern"].unique()), key="patterns")
        stages = st.multiselect("Workflow stage", sorted(queue["workflow_stage"].unique()),
                                default=sorted(queue["workflow_stage"].unique()), key="stages")
        priorities = st.multiselect("Review priority", ["High", "Medium", "Low"],
                                    default=["High", "Medium", "Low"], key="priorities")
    budget = int(st.sidebar.number_input("Review budget K", min_value=1, max_value=500, value=30, step=1))
    st.sidebar.caption("Evidence uses the full eligible holdout at this budget; filters do not change its benchmark.")
    search = st.text_input("Search plans", placeholder="Fictional ID, specialty, department or review reason",
                           key="search", label_visibility="collapsed",
                           help="Case-insensitive literal phrase search across both scorers and input errors.")
    config = ViewConfig(ranking, tuple(specialties), tuple(patterns), tuple(stages), tuple(priorities), search)
    view = filtered_queue(queue, config)
    ranked = view[view["baseline_index"].notna()]
    needs_triage = view[view["baseline_index"].isna()]
    source_label = "Experimental ML" if config.source == "model" else "Rules baseline"
    st.markdown(
        f"**{len(view)}** plans in view &nbsp; | &nbsp; **{len(ranked)}** scored &nbsp; | &nbsp; "
        f"**{len(needs_triage)}** need data clarification"
    )
    st.caption(f"Of {len(queue)} historical holdout plans | Priority/action source: {source_label} | Ordered by: {ranking}")
    tabs = st.tabs(["Overview", "Review workspace", "Review patterns", "Evidence & export"],
                   default="Review workspace")
    with tabs[0]:
        st.subheader("A clearer starting point for human review")
        st.write(
            "Open **Review workspace** to choose a plan and see its context alongside the queue. "
            "Review the suggested action and main driver, then make your own judgement. "
            "Check **Data clarification** separately: an unscored plan is not a low-priority plan."
        )
        st.markdown(f"**Priority distribution - {source_label}**")
        st.dataframe(priority_distribution(view, config.source), hide_index=True, width="stretch",
                     column_config={"review_priority": "Review priority", "scored_plans": "Scored plans"})
        st.caption(
            "Review patterns describes workload by fictional group. Evidence & export contains the synthetic "
            "benchmark and downloads. What-if is inside the selected plan and never changes the original queue."
        )
        st.caption(
            "All counts and patterns use this filtered original-plan view. Unscored records bypass only the priority "
            "filter, never become Low, and need separate human triage. Ages refer to each snapshot, not today's clock. "
            "Oldest-first orders by stage age but uses rules categories/actions. Exact score ties use fictional ID. "
            "The benchmark alone uses the full eligible holdout; exports include all matching plans, not just K."
        )
    detail_ids = view["plan_id"].tolist()
    if st.session_state.get("selected_plan") not in detail_ids:
        st.session_state["selected_plan"] = detail_ids[0] if detail_ids else None
    with tabs[1]:
        stacked = st.sidebar.checkbox("Stack queue and detail (smaller window)", key="stacked")
        panels = [st.container(), st.container()] if stacked else st.columns([1.05, 1], gap="large")
        with panels[0]:
            st.subheader("Review queue")
            if detail_ids:
                st.selectbox("Selected plan", detail_ids, key="selected_plan",
                             help="Choose here or select a table row. Viewing marks the plan shown alongside.")
            signature = (tuple(detail_ids), st.session_state["selected_plan"], config.source)
            if st.session_state.get("queue_signature") != signature:
                st.session_state["queue_revision"] = st.session_state.get("queue_revision", 0) + 1
                st.session_state["queue_signature"] = signature
            revision = st.session_state["queue_revision"]
            st.caption(
                f"Select a row to inspect. First {min(budget, len(ranked))} scored plans are within this view's budget. "
                "Both indices are /100. Scored plans have valid required inputs; see detail for completeness."
            )
            if ranked.empty:
                st.info("No scored plans match the current filters and search.")
            else:
                display_queue_table(ranked, config.source, f"queue-{revision}")
            with st.expander(f"Data clarification - {len(needs_triage)} unscored", expanded=bool(len(needs_triage))):
                st.caption("No score means insufficient required inputs, not low review priority. Select a plan for the exact issue.")
                if needs_triage.empty:
                    st.caption("No unscored records match this view.")
                else:
                    display_queue_table(needs_triage, config.source, f"triage-{revision}", triage=True)
        with panels[1]:
            if detail_ids:
                selected = st.session_state["selected_plan"]
                record = split.test.loc[split.test["plan_id"] == selected].iloc[0].to_dict()
                display_detail(record, model, config.source)
            else:
                st.info("No plan is selected: no plans match the current filters and search.")
    with tabs[2]:
        display_patterns(view, config.source, source_label)
    with tabs[3]:
        display_evidence(split, model, queue, budget)
        with st.expander("Export current original-plan view"):
            st.caption(
                f"{len(ranked)} scored and {len(needs_triage)} unscored original plans; both scores/categories, exact "
                "contributions, actions and input sufficiency included. No what-if edits or outcome labels; not limited to K. "
                "Unavailable JSON values are null. CSV has one scope record then plan records (record_type=plan); "
                "potential spreadsheet-formula text is apostrophe-prefixed. Exports stay local to your browser."
            )
            payload = export_payload(queue, config, model)
            st.download_button("Download filtered queue CSV", export_csv(payload, list(queue.columns)),
                               file_name="synthetic-review-queue.csv", mime="text/csv", key="export_csv")
            st.download_button("Download filtered queue JSON", export_json(payload),
                               file_name="synthetic-review-queue.json", mime="application/json", key="export_json")
