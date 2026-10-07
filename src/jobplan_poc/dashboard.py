"""In-memory Streamlit demonstration: no uploads, external APIs or persistence."""

import pandas as pd
import streamlit as st

from jobplan_poc.evaluation import (
    RANDOM_REPEATS, RANDOM_SEED, compare_methods, experiment_report, score_queue, temporal_split,
)
from jobplan_poc.features import FEATURE_LABELS, extract_features
from jobplan_poc.dataset import demonstration_plans, generate_dataset
from jobplan_poc.records import activity_comparison, validate_sources
from jobplan_poc.rules import RULESET_VERSION, assess_rules
from jobplan_poc.presentation import (
    ViewConfig, export_csv, export_json, export_payload, filtered_queue,
    workload_groups,
)
from jobplan_poc.review_display import (
    PRIORITY_FILTERS, comparison_rows, display_category, information_items, markdown_text,
    model_signals, notable_changes, plain_reason, previous_snapshot_label, rules_applied,
)
from jobplan_poc.scoring import ReviewModel, Score, fit_model, what_if
from jobplan_poc.synthetic import DEFAULT_SEED, REFERENCE_DATE, TEST_START
from jobplan_poc.theme import apply_theme


BUILD_LABEL = "clinical-workspace-v7"
DEFAULT_REVIEW_BUDGET = 30
PAGE_SIZE = 8
NAVIGATION = ["Review queue", "Rules vs ML", "About this POC"]
ORDER_LABELS = {"Rules-led": "Rules baseline", "Experimental model": "Experimental ML"}


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
    if score.index is None:
        st.info(f"{title}: unavailable until required information is clarified.", icon=":material/info:")
        return
    value = f"{score.index:.1f} / 100"
    st.markdown(f"**{title}: {value} | {score.category}**")
    st.caption(score.sufficiency)
    st.write(score.action)
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


def display_what_if(record: dict, model: ReviewModel) -> None:
    features = extract_features(record)
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


def display_information(record: dict, errors: tuple | list, *, details: bool = False) -> None:
    items = information_items(record)
    if items is None:
        st.caption("Information available: item count cannot be established for these validation findings.")
    else:
        st.caption(f"Information available: {sum(items.values())} of {len(items)} required items")
    if errors:
        for error in errors:
            st.text(error)
    if details:
        st.caption(
            "Items are grouped validation checks, not a percentage of all fields or model confidence. "
            "Known recorded completeness can be below 100% while all required items are valid."
        )
        if items is not None:
            with st.expander("Required information checklist"):
                st.table(pd.DataFrame([
                    {"Required item": name, "State": "Available and valid" if valid else "Needs clarification"}
                    for name, valid in items.items()
                ]))


def priority_badge(category: str) -> None:
    label = display_category(category)
    if category == "Unscored":
        icon, colour = ":material/info:", "orange"
    elif category == "High":
        icon, colour = ":material/schedule:", "orange"
    else:
        icon, colour = ":material/checklist:", "gray"
    st.badge(label, icon=icon, color=colour)


@st.dialog("Why is this highlighted?", width="large", on_dismiss="rerun")
def display_explanation(record: dict, model: ReviewModel, signal: str) -> None:
    assessment = assess_rules(record)
    st.caption(markdown_text(f"JobPlan {record['plan_id']} · {record['specialty']}"))
    st.subheader("Why this plan appeared")
    st.text(plain_reason(assessment.export_traces()))
    st.subheader("Rule details")
    st.caption(
        "Illustrative POC thresholds, not NHS policy. Partial signals count too. "
        "Rules points sum to the rules index; they are not model contributions."
    )
    for trace in assessment.export_traces():
        with st.expander(f"{trace['rule_id']} · {trace['name']} · {trace['state']}"):
            st.text(trace["explanation"])
            st.caption(f"Rule version: {trace['version']}")
            st.json(trace, expanded=True)
    if assessment.score.index is not None:
        st.caption(f"Rules index: {assessment.score.index:.4f} / 100. Separate from the experimental model.")
    else:
        st.warning("Rule calculations withheld. Data clarification required.", icon=":material/info:")
        display_information(record, assessment.score.errors)
    st.divider()
    st.subheader("Experimental model")
    st.text("Experimental model signal: " + signal)
    st.caption("A relative ordering of plans in this view, not a cause, confidence measure or clinical probability.")
    with st.expander("View model details"):
        display_score("Experimental model", model.score(record))
        features = extract_features(record)
        if features.values is not None:
            st.table(pd.DataFrame([
                {"Pre-review feature": FEATURE_LABELS[key], "Value": value}
                for key, value in features.values.items()
            ]))
    if st.button("Close explanation", key="close_explanation"):
        st.rerun()


def close_detail() -> None:
    st.session_state["selected_plan"] = None


def open_detail(plan_id: str) -> None:
    st.session_state["selected_plan"] = plan_id


def display_detail(record: dict, model: ReviewModel, source: str, signal: str) -> None:
    st.button("Back to queue", icon=":material/arrow_back:", on_click=close_detail)
    st.title(markdown_text(f"JobPlan {record['plan_id']} · {record['specialty']}"))
    assessment = assess_rules(record)
    chosen = model.score(record) if source == "model" else assessment.score
    st.text("Suggested review priority: " + display_category(chosen.category))
    priority_badge(chosen.category)
    if st.button("Why is this highlighted?", icon=":material/info:", key="why_highlighted"):
        display_explanation(record, model, signal)
    st.subheader("Why this plan appeared")
    st.text(plain_reason(assessment.export_traces()))
    st.caption("Priority source: " + ("Experimental model" if source == "model" else "Rules-led"))
    st.caption(markdown_text(
        f"{previous_snapshot_label(record)} · Current snapshot: {record['snapshot_date']:%d %b %Y}"
    ))
    if record.get("cohort") == "demonstration":
        st.info(markdown_text(f"Demonstration only: {record['scenario_name']}. {record['scenario_note']}"),
                icon=":material/science:")
    display_information(record, chosen.errors, details=True)
    if chosen.errors:
        st.warning("Data clarification required. Priority cannot be reliably calculated.", icon=":material/info:")
    changes = notable_changes(record)
    if validate_sources(record).errors:
        st.info("Comparison withheld until source information is clarified. Missing activities are not assumed to be zero.")
    else:
        st.subheader(f"{len(changes)} notable changes")
        st.caption("Observed differences, not findings of inappropriate allocation.")
        if changes:
            for change in changes:
                st.markdown("- " + markdown_text(change))
        else:
            st.text("No observed activity, allocation or working-pattern changes. Continue human review as usual.")
        with st.expander("Compare versions", expanded=True):
            st.subheader("Previous vs current")
            comparison = comparison_rows(record)
            changed = comparison.loc[comparison["Change"] != "No change"]
            if not changed.empty:
                st.table(changed.set_index("Measure").style.format({"Previous": "{:.2f}", "Current": "{:.2f}"}))
            else:
                st.text("No allocation or WTE changes.")
            unchanged = comparison.loc[comparison["Change"] == "No change"]
            if not unchanged.empty:
                with st.expander("Unchanged measures"):
                    st.table(unchanged.set_index("Measure").style.format({"Previous": "{:.2f}", "Current": "{:.2f}"}))
            st.markdown("**Working pattern**")
            for prefix in ("previous", "current"):
                st.text(prefix.capitalize() + ": " + ", ".join(record["versions"][prefix]["working_pattern"]))
            st.caption("PA = programmed activities; DCC = direct clinical care; SPA = supporting professional activities. "
                       "Illustrative categories. WTE = whole-time equivalent, not a performance measure.")
        with st.expander("Activity records"):
            for activity in activity_comparison(record).to_dict("records"):
                st.markdown("**" + markdown_text(activity["Activity"]) + "**")
                st.table(pd.DataFrame([
                    {"Item": field.capitalize(), "Previous": str(activity[f"Previous {field}"]),
                     "Current": str(activity[f"Current {field}"])}
                    for field in ("category", "PA", "session", "site")
                ]).set_index("Item"))
    with st.container(border=True):
        st.subheader("Reviewer consideration")
        st.caption("Workflow options only, not system recommendations. Selecting one records no decision or request.")
        st.radio(
            "Possible next step", ["Continue standard review", "Seek clarification", "Bring forward formal review"],
            index=None, key=f"consideration-{record['plan_id']}",
        )
        st.text("The system highlights review signals only. The decision remains with the authorised reviewer.")
    display_what_if(record, model)


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
    with st.expander("Model behaviour: largest contributions"):
        contributions = pd.DataFrame(queue.loc[queue["model_index"].notna(), "model_contributions"].tolist())
        if contributions.empty:
            st.info("No eligible model contributions are available.")
        else:
            magnitude = contributions.abs().mean().sort_values(ascending=False)
            st.table(pd.DataFrame({
                "Feature": [FEATURE_LABELS[name] for name in magnitude.index],
                "Mean absolute signed-term magnitude": magnitude.values,
            }))
        st.caption("Full eligible holdout, mean absolute log-odds term per feature. "
                   "A description of this fitted model, not a causal effect or evidence of clinical importance. "
                   "Inspect individual signed terms in a plan's explanation.")
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


def reset_review_filters(queue: pd.DataFrame) -> None:
    for state_key, column in (
        ("specialties", "specialty"), ("patterns", "working_pattern"), ("stages", "workflow_stage"),
    ):
        st.session_state[state_key] = sorted(queue[column].unique())
    st.session_state["priority_filter"] = "All plans"
    st.session_state["search"] = ""
    st.session_state["order"] = "Rules-led"
    st.session_state["selected_plan"] = None
    st.session_state["queue_page"] = 0
    st.session_state["clarification_page"] = 0


def change_priority_filter(label: str) -> None:
    st.session_state["priority_filter"] = (
        "All plans" if st.session_state["priority_filter"] == label else label
    )
    st.session_state["queue_page"] = 0
    st.session_state["clarification_page"] = 0
    close_detail()


def display_cards(view: pd.DataFrame, records: pd.DataFrame, source: str, signals: dict, *, triage=False) -> None:
    if view.empty:
        st.info("No matching plans in this section. Clear search or use Reset filters & search.")
        return
    page_key = "clarification_page" if triage else "queue_page"
    signature_key = page_key + "_ids"
    signature = tuple(view["plan_id"])
    if st.session_state.get(signature_key) != signature:
        st.session_state[page_key] = 0
        st.session_state[signature_key] = signature
    page = st.session_state.get(page_key, 0)
    start = page * PAGE_SIZE
    if len(view) > PAGE_SIZE:
        st.caption(f"Showing {start + 1} to {min(start + PAGE_SIZE, len(view))} of {len(view)} plans")
        with st.container(horizontal=True):
            st.button("Previous page", key=page_key + "_previous", disabled=page == 0,
                      on_click=change_page, args=(page_key, -1), icon=":material/chevron_left:")
            st.button("Next page", key=page_key + "_next", disabled=start + PAGE_SIZE >= len(view),
                      on_click=change_page, args=(page_key, 1), icon=":material/chevron_right:")
    originals = records.set_index("plan_id", drop=False)
    for row in view.iloc[start:start + PAGE_SIZE].to_dict("records"):
        record = originals.loc[row["plan_id"]].to_dict()
        with st.container(border=True, key="plan-card-" + row["plan_id"]):
            st.markdown("**" + markdown_text(f"{row['plan_id']} · {row['specialty']}") + "**")
            priority_badge(row[f"{source}_category"])
            if triage:
                display_information(record, row["input_errors"])
                st.button("Request data clarification", key="view_" + row["plan_id"],
                          icon=":material/contact_support:", on_click=open_detail, args=(row["plan_id"],),
                          help="Open the plan and review missing information. No request is sent or saved.")
            else:
                st.markdown("**" + markdown_text(plain_reason(row["rule_traces"])) + "**")
                count = rules_applied(row["rule_traces"])
                st.caption(f"{count} {'rule applies' if count == 1 else 'rules apply'} · "
                           f"Experimental model signal: {signals[row['plan_id']]}")
                st.caption(previous_snapshot_label(record))
                st.button("View JobPlan", key="view_" + row["plan_id"], icon=":material/arrow_forward:",
                          on_click=open_detail, args=(row["plan_id"],),
                          help="Open " + row["plan_id"] + " and compare the source versions.")


def change_page(key: str, step: int) -> None:
    st.session_state[key] = st.session_state.get(key, 0) + step


def display_patterns(view: pd.DataFrame, source: str, source_label: str) -> None:
    st.subheader("Review-workload distribution")
    st.caption("Descriptive workload, not clinical quality, clinician performance or evidence of causal problems.")
    st.caption(
        f"Filtered original plans | Source: {source_label}. Review-sooner rate = existing High / scored plans in each group. "
        "Total = scored + data clarification; zero scored denominator means unavailable. "
        "Do not compare rates for groups with fewer than 5 scored plans. "
        "Filters affect denominators: a High-only view will show 100% for scored groups."
    )
    if view.empty:
        st.info("No workload groups to display for the current filters and search.")
    else:
        for group in ("specialty",):
            st.markdown(f"**By fictional {group}**")
            st.dataframe(workload_groups(view, group, source), hide_index=True, width="stretch",
                         column_config={
                             group: st.column_config.TextColumn(group.capitalize()),
                             "total_plans": "All plans", "scored_plans": "Scored", "unscored_plans": "Data clarification",
                             "high_priority_plans": "Review sooner",
                             "high_priority_rate_among_scored": st.column_config.NumberColumn(
                                 "Review sooner / scored", format="%.2f", help="Proportion, 0 to 1; not percentage"),
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
        "Ratios are proportions from 0 to 1. Rules vs ML lets you explore a different budget."
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
            "Start in Review queue; use View JobPlan, read the reason and compare activities. "
            "Inspect Data clarification, try an isolated what-if, then compare methods in Rules vs ML. "
            "Ask whether the reasons are understandable and whether the workflow helps a reviewer decide where to look."
        )
        st.write(
            "**Priority index:** an ordering aid from 0 to 100, not a clinical probability. "
            "**Rules:** visible weighted signals. **ML:** an experimental model fitted to synthetic outcomes. "
            "**Completeness:** recorded data availability, not model confidence. "
            "**Unscored:** required data must be clarified; not Low. "
            "**Review yield:** amendments found among a fixed number of reviews, not proof of clinical quality."
        )
    with st.expander("Display categories, information and design"):
        st.write(
            "**Review sooner** displays the existing High category. **Standard review** combines Medium and Low. "
            "**Data clarification required** means required information is missing or invalid; it is not Standard review. "
            "These are illustrative display settings, not policy, validated earlier-review need or changed scores. "
            "The underlying target is still synthetic amendment. Selecting the experimental ordering also changes "
            "the displayed category source, not the underlying rules or model."
        )
        st.write(
            "Information available counts seven grouped requirements: subject link; previous version and activities; "
            "current version and activities; snapshot date; workflow timing; review due date; recorded completeness. "
            "A group is counted only when its existing validation checks pass. It is not a confidence estimate or "
            "a percentage of all fields. Unknown validation findings make the count unavailable."
        )
        st.write(
            "The relative model signal uses a strict majority of other eligible plans in the filtered view. "
            "Ties and small views may have no higher/lower comparison; filtering can change this wording without "
            "changing a model index. 'Rules apply' counts non-zero signals, including partial threshold signals. "
            "Previous-version snapshot dates are not recorded in the fixture; no dates are inferred."
        )
        st.caption(
            "RLDatix-inspired colour direction only, not an official design or proprietary assets. "
            "Native Streamlit controls with one static scoped style block. Automated contrast checks and "
            "representative screenshots are not a WCAG conformance or screen-reader audit. "
            "See docs/ux-design-system.md for tokens, component mapping and verification limits."
        )
    st.caption(f"Build: {BUILD_LABEL}")


def main() -> None:
    st.set_page_config(page_title="JobPlan | Review queue", layout="wide")
    apply_theme()
    try:
        split, model, evaluation_queue = load_demo()
    except ValueError as exc:
        st.error(f"Demo cannot be scored: {exc}")
        st.stop()

    _, scenario_queue = load_scenarios()
    initialise_view(evaluation_queue, scenario_queue)
    st.sidebar.title("JobPlan review")
    st.sidebar.caption("Fictional demonstration")
    navigation = st.sidebar.radio("Workspace", NAVIGATION, key="navigation")
    st.sidebar.divider()
    st.sidebar.caption("Prioritise attention, not people.")
    st.sidebar.caption(f"Build: {BUILD_LABEL}")
    if navigation == "About this POC":
        st.title("About this POC")
        display_initiative(split, evaluation_queue)
        return
    detail_open = st.session_state.get("selected_plan") is not None
    if navigation == "Review queue" and not detail_open:
        st.title("Review queue")
        st.caption("Synthetic plans only. Prioritise attention, not people; changes may be entirely legitimate.")
        st.toggle("Demonstration scenarios", key="show_demos",
                  help="Nine fictional examples, separate from model fitting and evaluation. Reset filters if needed.")
    if st.session_state["show_demos"]:
        selected_records, queue = load_scenarios()
        cohort = "Demonstration scenarios"
    else:
        selected_records, queue = split.test, evaluation_queue
        cohort = "Evaluation holdout"
    if navigation == "Review queue" and not detail_open:
        if st.session_state["show_demos"]:
            st.info("Demonstration scenarios: no outcome labels. Never used for fitting or evaluation.",
                    icon=":material/science:")
        with st.container(horizontal=True, vertical_alignment="bottom"):
            st.text_input("Search plans", placeholder="Fictional ID, service or review reason", key="search",
                          help="Literal phrase search across IDs, specialty, department and both methods' actual reasons.")
            st.selectbox("Order by", list(ORDER_LABELS), key="order",
                         help="Changes the ordering and displayed category source. Separate methods, never a blend.")
        with st.expander("Filter plans"):
            for key, label in (("specialties", "Service"), ("patterns", "Working pattern"), ("stages", "Workflow stage")):
                st.multiselect(label, st.session_state["filter_choices"][key], key=key)
        st.button("Reset filters & search", key="reset_filters", on_click=reset_review_filters, args=(queue,),
                  help="Clear search and category filters, restore rules ordering and close detail. "
                       "Keeps the collection and experimental budget. Never changes the source or scenario.")
    config = current_config()
    view = filtered_queue(queue, config)
    ranked = view[view["baseline_index"].notna()]
    needs_triage = view[view["baseline_index"].isna()]
    if st.session_state.get("selected_plan") not in view["plan_id"].tolist():
        st.session_state["selected_plan"] = None
        if detail_open and navigation == "Review queue":
            st.rerun()
    signals = model_signals(view)
    if navigation == "Rules vs ML":
        st.title("Rules vs ML · synthetic-only evaluation")
        st.caption("For Product and evaluation, not an automated review decision.")
        budget = int(st.number_input("Review budget K", min_value=1, max_value=500, step=1, key="budget",
                                     help="Compare methods at a fixed review capacity; not a policy target."))
        st.info("No blended score: the two indices have different meanings. "
                "Overlap and disagreement show where their selections differ without merging them.",
                icon=":material/compare_arrows:")
        display_evidence(split, model, evaluation_queue, budget)
        with st.expander("Service-level review workload"):
            display_patterns(view, config.source, st.session_state["order"])
        with st.expander("Export current original-plan view"):
            st.caption(markdown_text(
                f"Collection: {cohort} · Order: {st.session_state['order']} · "
                f"Category filter: {st.session_state['priority_filter']} · Search: {config.search or '(none)'}"
            ))
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
        return
    selected = st.session_state.get("selected_plan")
    if selected is not None:
        record = selected_records.loc[selected_records["plan_id"] == selected].iloc[0].to_dict()
        display_detail(record, model, config.source, signals[selected])
        return
    all_priorities = filtered_queue(queue, current_config(all_priorities=True))
    categories = all_priorities[f"{config.source}_category"]
    counts = {
        "Review sooner": int(categories.eq("High").sum()),
        "Standard review": int(categories.isin(["Low", "Medium"]).sum()),
        "Data clarification required": int(all_priorities["baseline_index"].isna().sum()),
    }
    with st.container(horizontal=True):
        for label, count in counts.items():
            st.button(f"{label} · {count}", key="summary_" + label,
                      icon=":material/info:" if label == "Data clarification required" else ":material/checklist:",
                      type="primary" if st.session_state["priority_filter"] == label else "secondary",
                      on_click=change_priority_filter, args=(label,))
    st.caption(
        f"{len(view)} plans in view · {cohort} · Filter: {st.session_state['priority_filter']}. "
        "Counts reflect search and service filters before category filtering; select a count again to show all."
    )
    st.caption(
        "Data clarification always stays visible in its own section. 'Rules apply' includes partial change signals. "
        "Model signal compares with all eligible plans in this filtered view, not just this page."
    )
    if ranked.empty:
        st.info("No scored plans match this view. Reset filters & search, or inspect Data clarification below.")
    else:
        display_cards(ranked, selected_records, config.source, signals)
    st.subheader("Data clarification required")
    st.caption("These plans need information, not a lower priority. Opening an item sends no request and records no decision.")
    display_cards(needs_triage, selected_records, config.source, signals, triage=True)


def initialise_view(evaluation: pd.DataFrame, demonstration: pd.DataFrame) -> None:
    defaults = {
        "search": "", "order": "Rules-led", "priority_filter": "All plans", "show_demos": False,
        "budget": DEFAULT_REVIEW_BUDGET, "selected_plan": None,
    }
    choices = {}
    for key, column in (("specialties", "specialty"), ("patterns", "working_pattern"), ("stages", "workflow_stage")):
        choices[key] = sorted(set(evaluation[column]) | set(demonstration[column]))
        defaults[key] = choices[key]
    st.session_state["filter_choices"] = choices
    # Interrupt native widget cleanup so hidden controls retain scope across pages.
    for key, default in defaults.items():
        st.session_state[key] = st.session_state.get(key, default)


def current_config(*, all_priorities: bool = False) -> ViewConfig:
    return ViewConfig(
        ORDER_LABELS[st.session_state["order"]],
        tuple(st.session_state["specialties"]), tuple(st.session_state["patterns"]), tuple(st.session_state["stages"]),
        PRIORITY_FILTERS["All plans" if all_priorities else st.session_state["priority_filter"]],
        st.session_state["search"],
    )
