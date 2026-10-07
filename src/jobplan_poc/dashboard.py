"""In-memory Streamlit demonstration: no uploads, external APIs or persistence."""

from functools import partial

import pandas as pd
import streamlit as st

from jobplan_poc.evaluation import (
    RANDOM_REPEATS, RANDOM_SEED, compare_methods, experiment_report, score_queue, temporal_split,
)
from jobplan_poc.features import FEATURE_LABELS, extract_features
from jobplan_poc.dataset import demonstration_plans, generate_dataset
from jobplan_poc.records import activity_comparison, validate_sources
from jobplan_poc.rules import CATALOGUE, RULESET_VERSION, assess_rules
from jobplan_poc.presentation import (
    ViewConfig, export_csv, export_json, export_payload, filtered_queue,
    priority_distribution, workload_groups,
)
from jobplan_poc.scoring import ReviewModel, Score, fit_model, score_baseline, what_if
from jobplan_poc.synthetic import DEFAULT_SEED, REFERENCE_DATE, TEST_START, generate_plans


BUILD_LABEL = "clinical-workspace-v6"
DEFAULT_REVIEW_BUDGET = 30


@st.cache_resource
def load_demo():
    """Linked activity cohort v1; preserve the existing model experiment."""
    records = generate_dataset()
    split = temporal_split(records)
    model = fit_model(split.training)
    queue = score_queue(split.test, model)
    return split, model, queue


@st.cache_resource
def load_scenarios():
    _, model, _ = load_demo()
    records = demonstration_plans()
    return records, score_queue(records, model)


def display_score(title: str, score: Score) -> None:
    value = "Unscored" if score.index is None else f"{score.index:.1f} / 100"
    st.markdown(f"**{title}: {value} | {score.category}**")
    st.caption(score.sufficiency)
    st.write(score.action)
    if score.index is None:
        return
    st.caption(f"Largest absolute term: {score.main_driver}")
    contributions = pd.DataFrame([
        {"Feature": FEATURE_LABELS.get(name, name), "Contribution": value}
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
    assessment = assess_rules(record)
    baseline, ml = assessment.score, model.score(record)
    selected_score = ml if source == "model" else baseline
    for label, score in [("Rules index", baseline), ("Experimental ML index", ml)]:
        value = "Unscored" if score.index is None else f"{score.index:.1f} / 100"
        st.markdown(f"**{label}** &nbsp; {value} &nbsp; | &nbsp; {score.category}")
    st.caption("Prioritisation is not a decision. Separate review-priority indices, not a clinical probability.")
    st.markdown("**Next human action**")
    st.write(selected_score.action)
    if selected_score.errors:
        st.warning("Data clarification required. Priority cannot be reliably calculated - unscored, not Low.")
        for error in selected_score.errors:
            st.text(error)
    else:
        st.markdown("**Main review driver**")
        st.write(selected_score.main_driver)
    st.caption(
        f"Recorded completeness: {record['completeness_percent']:.1f}% | {selected_score.sufficiency}. "
        "Data completeness is NOT model confidence."
    )
    if record.get("cohort") == "demonstration":
        st.info(f"Demonstration only: {record['scenario_name']}. {record['scenario_note']}")
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
    with st.expander("Previous / current activities and working pattern", expanded=True):
        source = validate_sources(record)
        if source.errors:
            st.info("Comparison withheld until the missing or contradictory source information is clarified. "
                    "No missing activity is assumed to have zero allocation.")
        else:
            st.dataframe(comparison, hide_index=True, width="stretch",
                         column_config={name: st.column_config.NumberColumn(format="%.2f")
                                        for name in ("Previous", "Current", "Change")})
            st.dataframe(activity_comparison(record), hide_index=True, width="stretch")
            st.dataframe(pd.DataFrame([
                {"Version": prefix.capitalize(), "WTE": version["wte"],
                 "Days / sessions": ", ".join(version["working_pattern"])}
                for prefix, version in record["versions"].items()
            ]), hide_index=True, width="stretch")
        st.caption("Totals are derived from linked activities and checked against reported totals. "
                   "DCC / SPA / Other are illustrative categories; WTE and PA are not performance measures.")
    features = extract_features(record)
    triggered = [f"{trace.rule_id} {trace.name}" for trace in assessment.traces if trace.triggered]
    st.caption("Full-signal rule thresholds reached: " + (", ".join(triggered) if triggered else "None; see any partial signals below."))
    with st.expander("Why highlighted? Exact rule evidence and separate model contributions"):
        st.markdown(f"**Activity-change rules ({RULESET_VERSION})**")
        st.caption("Illustrative configurable POC thresholds, not NHS policy. Signal = min(observed / threshold, 1); "
                   "points = weight × signal. Partial changes also contribute; triggered means the full-signal threshold is reached.")
        st.dataframe(pd.DataFrame(assessment.export_traces()), hide_index=True, width="stretch",
                     column_config={
                         "rule_id": "Rule ID", "version": "Version", "name": "Rule", "rationale": "Rationale",
                         "observed_difference": "Observed difference", "threshold": "Full-signal threshold",
                         "signal_strength": "Signal strength", "weight": "Maximum points", "points": "Index points",
                         "state": "Calculation state", "previous": "Previous inputs", "current": "Current inputs",
                         "explanation": "Explanation", "unit": "Unit", "triggered": "Threshold reached",
                     })
        st.caption("All five rules are withheld if required inputs are unreliable; this is not a zero signal.")
        with st.expander("Exact machine-readable trace"):
            st.json(assessment.export_traces())
        st.caption(f"Department: {record['department']}. Each entity has one pre-review row; previous values are context.")
        if features.values is not None:
            st.dataframe(
                pd.DataFrame([{"Derived pre-review feature": FEATURE_LABELS[key], "Value": value}
                              for key, value in features.values.items()]),
                hide_index=True, width="stretch",
            )
        display_score("Activity-change rules", baseline)
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
    report = experiment_report(queue, outcomes, budget)
    metrics = report.metrics
    st.dataframe(metrics[["method", "reviewed", "cohort", "positives", "amendments_found",
                          "precision_at_k", "recall_at_k"]], hide_index=True, width="stretch",
                 column_config={
                     "method": "Ordering", "reviewed": "Plans reviewed", "cohort": "Eligible plans",
                     "positives": "Synthetic amendments", "amendments_found": "Cases found",
                     "precision_at_k": st.column_config.NumberColumn("Precision@K", format="%.3f"),
                     "recall_at_k": st.column_config.NumberColumn("Recall@K", format="%.3f"),
                 })
    st.caption(
        f"Full later holdout, unaffected by queue filters or what-if edits; same sufficient cohort for all methods. "
        f"{len(queue) - int(metrics.iloc[0]['cohort'])} insufficient-data rows excluded from ALL benchmark methods "
        "(not a recommendation to ignore them). Actual K is min(requested budget, eligible cohort size). "
        "Precision = amendments found / reviewed; recall = amendments found / all amendments in the eligible cohort. "
        "Undefined metrics are shown as empty/None, never zero; no-positive recall is unavailable. "
        "Outcomes are stochastic synthetic material amendments observed 30 days after the snapshot."
    )
    st.caption(
        f"Rules baseline now means {RULESET_VERSION}, calculated from R-01..R-05. Legacy v5 rules retain the "
        "previous administrative/change index for reference; they are not blended. Oldest-first means current "
        "workflow-stage age, not clinician age or a clinical urgency judgement."
    )
    with st.expander("Random comparison: mean and spread"):
        st.dataframe(metrics.loc[metrics["method"].str.startswith("Random"), [
            "amendments_found", "amendments_found_std", "amendments_found_min", "amendments_found_max",
            "precision_at_k", "precision_at_k_std", "recall_at_k", "recall_at_k_std",
        ]], hide_index=True, width="stretch")
        st.caption(
            f"{RANDOM_REPEATS} permutations of the same eligible cohort, seed {RANDOM_SEED}. "
            "Mean, population standard deviation and observed range describe random-order variability, "
            "not confidence intervals, model ranking stability or real-world uncertainty. "
            "No bootstrap stability claim is made for this single synthetic fitted model."
        )
    overlap = report.overlap
    st.subheader("Rules versus ML: top-K overlap and disagreements")
    st.write(
        f"Of {overlap['actual_k']} reviewed plans per method, {overlap['shared_cases']} are shared; "
        f"{overlap['rules_only']} are selected only by rules and {overlap['model_only']} only by ML."
    )
    st.caption(
        "Same full sufficient holdout, independent of view filters and demonstration scenarios. "
        "Shared fraction uses actual K; Jaccard uses the union of the two selections. "
        f"Shared fraction: {overlap['shared_fraction_at_k']}; Jaccard: {overlap['jaccard']}. "
        "Undefined empty-cohort ratios are unavailable. Different rankings do not establish which is appropriate."
    )
    if report.disagreements.empty:
        st.info("No top-K selection disagreements at this budget (or no eligible records).")
    else:
        st.dataframe(report.disagreements, hide_index=True, width="stretch",
                     column_config={
                         "plan_id": "Plan", "selected_by": "Selected by", "rules_rank": "Rules position",
                         "model_rank": "ML position", "rules_index": "Rules /100", "model_index": "ML /100",
                         "rules_reason": "Actual rules reason", "model_reason": "Actual model reason",
                     })
        with st.expander("Inspect a disagreement's exact explanations"):
            disagreement_id = st.selectbox("Disagreement plan", report.disagreements["plan_id"].tolist())
            evidence_row = queue.loc[queue["plan_id"] == disagreement_id].iloc[0]
            st.json({"rule_traces": evidence_row["rule_traces"],
                     "model_intercept": evidence_row["model_intercept"],
                     "model_decision": evidence_row["model_decision"],
                     "signed_model_log_odds_contributions": evidence_row["model_contributions"]})
            st.caption("Exact source rule traces and actual model-space contributions, not a causal explanation or approval.")
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
            "Only five named pre-review features enter the model; IDs, specialty, working-pattern labels, "
            "day/session slots, site, activity IDs, workflow stage label, outcomes and outcome dates do not. "
            "WTE is used to derive normalised PA change. There is no hyperparameter search. "
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


def reset_review_filters(queue: pd.DataFrame) -> None:
    for state_key, column in (
        ("specialties", "specialty"), ("patterns", "working_pattern"), ("stages", "workflow_stage"),
    ):
        st.session_state[state_key] = sorted(queue[column].unique())
    st.session_state["priorities"] = ["High", "Medium", "Low"]
    st.session_state["search"] = ""
    st.session_state["ranking"] = "Rules baseline"
    st.session_state["selected_plan"] = None
    st.session_state.pop("queue_signature", None)


def display_queue_table(records: pd.DataFrame, source: str, table_key: str, *, triage: bool = False) -> None:
    plan_ids = records["plan_id"].tolist()
    fields = (["plan_id", "specialty", "completeness_percent", "data_quality_state"] if triage else
              ["plan_id", "specialty", f"{source}_category", "baseline_index", "model_index",
               "change_summary", f"{source}_main_driver", "data_quality_state"])
    display = records[fields].copy()
    display.insert(0, "Viewing", display["plan_id"] == st.session_state.get("selected_plan"))
    st.dataframe(
        display, hide_index=True, width="stretch", height=180 if triage else 390,
        row_height=32, key=table_key, on_select=partial(select_table_plan, table_key, plan_ids),
        selection_mode="single-row",
        column_config={
            "Viewing": st.column_config.CheckboxColumn("Viewing", width="small"),
            "plan_id": st.column_config.TextColumn("Plan", width="small"),
            "specialty": st.column_config.TextColumn("Service / specialty"),
            "change_summary": st.column_config.TextColumn("Change summary"),
            f"{source}_main_driver": st.column_config.TextColumn("Main review reason"),
            "data_quality_state": st.column_config.TextColumn("Data quality"),
            f"{source}_category": st.column_config.TextColumn("Priority"),
            "baseline_index": st.column_config.NumberColumn(
                "Rules /100", format="%.1f", width="small",
                help="Transparent weighted rules index: review priority, not a probability."),
            "model_index": st.column_config.NumberColumn(
                "ML /100", format="%.1f", width="small",
                help="Experimental machine-learning index learned from synthetic outcomes; not a validated probability."),
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


def display_initiative(split, queue: pd.DataFrame) -> None:
    st.subheader("Why explore JobPlan review prioritisation?")
    st.write(
        "Clinical Directors have finite review time. This initiative explores whether a transparent queue can help "
        "them choose where to look first, understand why a plan is highlighted and keep the decision with the reviewer."
    )
    st.markdown("**For whom, and what value are we testing?**")
    st.write(
        "Clinical Directors and authorised JobPlan reviewers are the intended users; Product and service stakeholders "
        "can use this demo to assess the workflow. The hypothesis is easier prioritisation and more focused review, "
        "not proven time savings or better clinical outcomes. Simple rules may provide value even if ML adds none."
    )
    st.markdown("**A fictional review journey**")
    st.write(
        "A Clinical Director has time to review a limited number of plans. They choose a fictional plan from the queue, "
        "check the previous/current activities and main reason, then decide whether clarification or earlier review "
        "is appropriate. A working-pattern change may be entirely legitimate. If required inputs are missing, "
        "they use Data clarification instead of treating the plan as Low. No decision is recorded by this demo."
    )
    st.markdown("**How it works**")
    st.write(
        "Linked pre-review activities and working pattern → separate rules and experimental model indices → "
        "a ranked queue with faithful reasons → authorised human judgement."
    )
    st.caption(
        "Signals include activity changes, workflow age, review due dates and completeness. "
        "The two indices are never blended; neither measures clinical safety or clinician performance."
    )
    st.info(
        "Prioritise attention, not people. Highlight change or uncertainty, not wrongdoing. "
        "H1 tests workflow; H2 explanation understanding; H3 rules usefulness; H4 incremental ML value. "
        "These hypotheses have not been validated by a clinician study."
    )
    st.caption(
        "The current ML target is a SYNTHETIC AMENDMENT outcome, not 'a reviewer would prioritise earlier'. "
        "An independently reviewed earlier-review rubric is proposed, not implemented. "
        "See docs/poc-definition.md and the unexecuted walkthrough protocol for the research plan."
    )
    st.markdown("**Available now / proposed later**")
    st.dataframe(pd.DataFrame([
        {"Available in this demo": "Fictional synthetic plans; local filtering and review detail",
         "Future proposal, not implemented": "Approved, minimised real pre-review data and controlled access"},
        {"Available in this demo": "Separate rules/ML indices, actual reasons and missing-data triage",
         "Future proposal, not implemented": "Clinician-led validation of outcomes, usefulness and subgroup effects"},
        {"Available in this demo": "Isolated what-if, synthetic benchmark and local exports",
         "Future proposal, not implemented": "Governed shadow-mode evaluation before considering any live integration"},
    ]), hide_index=True, width="stretch")
    st.caption(
        "No live eJobPlan integration, automatic approval/rejection, persisted review decisions, "
        "clinical safety assessment or clinician performance assessment."
    )
    st.markdown("**What have we learned so far?**")
    outcomes = split.test.set_index("plan_id")["material_amendment"]
    comparison = compare_methods(queue, outcomes, DEFAULT_REVIEW_BUDGET)
    st.dataframe(
        comparison[["method", "reviewed", "amendments_found", "precision_at_k", "recall_at_k"]],
        hide_index=True, width="stretch",
        column_config={
            "method": "Method", "reviewed": "Plans reviewed", "amendments_found": "Synthetic amendments found",
            "precision_at_k": st.column_config.NumberColumn("Found / reviewed", format="%.2f"),
            "recall_at_k": st.column_config.NumberColumn("Found / all amendments", format="%.2f"),
        },
    )
    st.caption(
        f"Default demo: seed {DEFAULT_SEED}, fixed budget {DEFAULT_REVIEW_BUDGET}; "
        f"{int(comparison.iloc[0]['cohort'])} eligible holdout plans with "
        f"{int(comparison.iloc[0]['positives'])} synthetic amendments. "
        f"{len(queue) - int(comparison.iloc[0]['cohort'])} unscored plans excluded equally from this comparison, "
        "not from human triage. Independent of the current filters, scenario edits and sidebar budget. "
        "Ratios are proportions from 0 to 1. Evidence & export lets you explore a different budget."
    )
    st.write(
        "ML has not demonstrated an advantage in this default comparison. The labels teach generator behaviour, "
        "not validated future review need. Synthetic results are not evidence of real-world benefit; "
        "Product can still test whether the rules-led workflow is understandable and useful."
    )
    st.markdown("**Decision gates before any rollout**")
    st.write(
        "1. Agree the intended review decision and an independently reviewed outcome definition; "
        "a material amendment is not automatically a problem.\n"
        "2. Approve minimised data, access controls and information governance before using real records.\n"
        "3. Validate on later time periods with entity separation; examine missingness, errors and subgroup effects.\n"
        "4. Compare review yield at a fixed budget, and prospectively measure review time and usability with clinicians.\n"
        "5. Only then consider an approved shadow-mode pilot with human override and monitoring before any rollout."
    )
    st.caption(
        "Shadow mode is proposed, NOT implemented: a future pilot would observe suggestions alongside existing "
        "review without changing decisions automatically. No target percentages or delivery dates are assumed."
    )
    with st.expander("Stakeholder walkthrough & plain-language glossary"):
        st.write(
            "Start in Review workspace; choose a scored plan, read the next human action and compare activities. "
            "Inspect Data clarification, try an isolated what-if, then compare methods in Evidence & export. "
            "Ask whether the reasons are understandable and whether the workflow helps a reviewer decide where to look."
        )
        st.write(
            "**Priority index:** an ordering aid from 0 to 100, not a clinical probability. "
            "**Rules:** visible weighted signals. **ML:** an experimental model fitted to synthetic outcomes. "
            "**Completeness:** recorded data availability, not model confidence. "
            "**Unscored:** required data must be clarified; not Low. "
            "**Review yield:** amendments found among a fixed number of reviews, not proof of clinical quality."
        )


def main() -> None:
    st.set_page_config(page_title="JobPlan | Review workspace", layout="wide")
    st.header("JobPlan review workspace")
    st.caption(f"Clinical Director review support | Build: {BUILD_LABEL}")
    st.caption("Synthetic demo only. Prioritise attention, not people. Highlight change or uncertainty, not wrongdoing.")
    try:
        split, model, evaluation_queue = load_demo()
    except ValueError as exc:
        st.error(f"Demo cannot be scored: {exc}")
        st.stop()

    st.sidebar.subheader("Review view")
    cohort = st.sidebar.radio("Plan collection", ["Evaluation holdout", "Demonstration scenarios"], key="cohort")
    if cohort == "Demonstration scenarios":
        selected_records, queue = load_scenarios()
        st.info("Demonstration scenarios: fixed fictional examples, no outcome labels. "
                "Never used for fitting or benchmark evaluation. Evidence always uses the evaluation holdout.")
    else:
        selected_records, queue = split.test, evaluation_queue
    ranking = st.sidebar.selectbox(
        "Order and priority source", ["Rules baseline", "Experimental ML", "Oldest-first"], key="ranking",
        help="Rules use visible weights; ML learns synthetic patterns. Both are priority indices, not probabilities. "
             "Oldest-first orders by workflow age and retains rules-based categories.")
    with st.sidebar.expander("Filter plans"):
        specialties = st.multiselect("Specialty", sorted(queue["specialty"].unique()),
                                     default=sorted(queue["specialty"].unique()), key="specialties")
        patterns = st.multiselect("Working pattern", sorted(queue["working_pattern"].unique()),
                                  default=sorted(queue["working_pattern"].unique()), key="patterns")
        stages = st.multiselect("Workflow stage", sorted(queue["workflow_stage"].unique()),
                                default=sorted(queue["workflow_stage"].unique()), key="stages")
        priorities = st.multiselect("Review priority", ["High", "Medium", "Low"],
                                    default=["High", "Medium", "Low"], key="priorities")
    st.sidebar.button(
        "Reset filters & search", key="reset_filters", on_click=reset_review_filters, args=(queue,),
        help="Show all plans in this collection, clear search, restore rules ordering and select the first plan. "
             "Keeps your review budget and layout; does not change source data or the model.")
    budget = int(st.sidebar.number_input(
        "Review budget K", min_value=1, max_value=500, value=DEFAULT_REVIEW_BUDGET, step=1,
        help="How many plans to compare at a fixed review capacity. Not an approval limit or policy target."))
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
    st.caption(f"Of {len(queue)} {cohort.lower()} plans | Priority/action source: {source_label} | Ordered by: {ranking}")
    tabs = st.tabs(["Overview", "Review workspace", "Review patterns", "Evidence & export", "About this initiative"],
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
        st.caption("Choose a plan → understand the review reasons → decide the next human action.")
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
                st.info("No scored plans match the current filters and search. Clear the search or use Reset filters & search "
                        "in the sidebar. Any matching unscored plans are in Data clarification below.")
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
                record = selected_records.loc[selected_records["plan_id"] == selected].iloc[0].to_dict()
                display_detail(record, model, config.source)
            else:
                st.info("No plan is selected: no plans match the current filters and search. "
                        "Use Reset filters & search in the sidebar, then choose a plan.")
    with tabs[2]:
        display_patterns(view, config.source, source_label)
    with tabs[3]:
        display_evidence(split, model, evaluation_queue, budget)
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
    with tabs[4]:
        display_initiative(split, evaluation_queue)
