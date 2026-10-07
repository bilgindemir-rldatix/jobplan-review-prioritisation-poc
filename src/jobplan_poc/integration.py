"""Fictional before/after presentation, not a connected product integration."""

from pathlib import Path

import pandas as pd
import streamlit as st

from jobplan_poc.dataset import demonstration_plans
from jobplan_poc.review_display import (
    PRESENTATION_IDS, comparison_rows, display_category, review_reason,
)
from jobplan_poc.rules import assess_rules


VALIDATION_NOTICE = "Requires validation against current JobPlan implementation"
PROPOSAL_PATH = Path(__file__).resolve().parents[2] / "docs" / "product-integration.md"


def worklist(records: pd.DataFrame, *, enhanced: bool) -> pd.DataFrame:
    rows = []
    for record in records.to_dict("records"):
        row = {
            "JobPlan": record["plan_id"],
            "Service": record["specialty"],
            "Review status": record["workflow_stage"],
            "Review date": record["review_due_date"].strftime("%d %b %Y"),
        }
        if enhanced:
            assessment = assess_rules(record)
            row["Review priority"] = display_category(assessment.score.category)
            row["Main reason"] = review_reason(record, assessment.export_traces())
        rows.append(row)
    return pd.DataFrame(rows)


def open_example() -> None:
    st.session_state["integration_selected"] = st.session_state["integration_pick"]


def close_example() -> None:
    st.session_state["integration_selected"] = None


def display_signals(record: dict) -> None:
    assessment = assess_rules(record)
    with st.container(border=True):
        st.subheader("Review signals")
        st.badge(
            display_category(assessment.score.category),
            icon=":material/info:" if assessment.score.index is None else ":material/checklist:",
            color="orange" if assessment.score.category in ("High", "Unscored") else "gray",
        )
        st.text(review_reason(record, assessment.export_traces()))
        comparison = comparison_rows(record)
        changed = comparison.loc[comparison["Change"] != "No change"]
        if not changed.empty:
            st.caption("Previous → current")
            for row in changed.to_dict("records"):
                st.text(f"{row['Measure']}: {row['Previous']:g} → {row['Current']:g}")
        if assessment.score.errors:
            st.caption("Insufficient comparison information, not a low priority. Ordinary review remains available.")
        with st.expander("View full comparison"):
            if assessment.score.errors:
                for error in assessment.score.errors:
                    st.text(error)
            else:
                st.table(comparison.set_index("Measure").style.format({"Previous": "{:.2f}", "Current": "{:.2f}"}))
                for version in ("previous", "current"):
                    st.text(version.capitalize() + " working pattern: " +
                            ", ".join(record["versions"][version]["working_pattern"]))
            st.caption("Illustrative POC rules. Source versions, not inferred clinical appropriateness.")
        st.caption("Decision support only. The authorised reviewer retains judgement.")


def display_integration() -> None:
    st.title("JobPlan: proposed product integration")
    st.write("Enhance the existing review worklist and plan review, rather than introduce a separate AI application.")
    st.caption("Representative wireframes using fictional POC records, not current product screenshots. " +
               VALIDATION_NOTICE + ".")
    mode = st.radio("Before / after illustration", ["Existing-style", "With review signals"],
                    index=1, horizontal=True, key="integration_mode")
    enhanced = mode == "With review signals"
    records = demonstration_plans().set_index("plan_id", drop=False).loc[list(PRESENTATION_IDS)].reset_index(drop=True)
    selected = st.session_state.get("integration_selected")
    with st.container(border=True):
        st.caption("JobPlan / Reviews · representative product shell")
        if selected is None:
            st.subheader("Review worklist")
            st.caption("The same three fictional plans and fixed example order in both views. Existing sort and permissions are not known.")
            table = worklist(records, enhanced=enhanced)
            st.dataframe(table, hide_index=True, width="stretch", height="content")
            st.caption("On smaller screens, scroll the table horizontally or read the full-text worklist below.")
            with st.expander("Read worklist as text"):
                for row in table.to_dict("records"):
                    st.text(" · ".join(str(value) for value in row.values()))
            st.selectbox("JobPlan to open", records.plan_id.tolist(), key="integration_pick")
            st.button("Open JobPlan", key="integration_open", on_click=open_example)
            st.caption("Local example navigation only. In the product this would use the existing plan-review route.")
        else:
            st.button("Back to worklist", key="integration_back", on_click=close_example)
            if selected not in records.plan_id.tolist():
                st.error("This fictional example is unavailable. Return to the worklist.")
                return
            record = records.loc[records.plan_id == selected].iloc[0].to_dict()
            st.subheader("JobPlan " + selected)
            st.text(f"{record['specialty']} · {record['workflow_stage']} · Review date: {record['review_due_date']:%d %b %Y}")
            core, addition = st.columns([2, 1]) if enhanced else (st.container(), None)
            with core:
                st.markdown("**Current plan activities**")
                activities = pd.DataFrame(record["versions"]["current"]["activities"])
                st.dataframe(activities[["activity_id", "category", "pa", "session", "site"]].rename(columns={
                    "activity_id": "Activity", "category": "Category", "pa": "PA",
                    "session": "Session", "site": "Location",
                }), hide_index=True, width="stretch", height="content")
                st.caption("Existing-style plan content: fictional fields, not a confirmed JobPlan schema.")
                st.markdown("**Existing review / sign-off workflow**")
                st.write("The product's normal review actions would remain here, with its existing permissions and audit.")
                st.caption("Not connected in this mock. No approval, rejection, edit or clarification request can be submitted.")
            if addition is not None:
                with addition:
                    display_signals(record)
            st.caption("PA = programmed activities; DCC = direct clinical care; SPA = supporting professional activities.")
    with st.expander("Integration recommendation and presentation guide"):
        st.markdown("**Embed, do not replace.** Reuse the authorised worklist, plan/version reads, comparison UI "
                    "where available, existing workflow, permissions, feature flags and audit.")
        st.markdown("**Minimal new module:** validate a version-pair comparison, calculate rules and optional "
                    "separate ML results, assemble faithful reasons, and cache minimal derived evidence.")
        st.code("JobPlan versions -> validated comparison -> rules + optional ML (separate)\n"
                "                  -> derived signals -> existing review UI\n"
                "Existing review / sign-off remains independent of signal calculation.", language=None)
        st.write("If ML is unavailable, use valid rules. If signals are unavailable or disabled, retain ordinary "
                 "review. Missing previous data means clarification, never a fabricated low priority.")
        st.caption("These are proposed product failure behaviours and flags, not implemented production services or access controls.")
        st.write("Product path: synthetic POC → controlled prototype → approved shadow mode → measured pilot → "
                 "conditional rollout. ML must independently justify its value.")
        st.caption("The 5–7 minute storyboard, proposed contracts, data mappings, audit/permission design, "
                   "failure matrix and product-team questions are in docs/product-integration.md. "
                   "Use Experiment results for the unchanged synthetic benchmark.")
        st.download_button("Download integration presentation", PROPOSAL_PATH.read_text(encoding="utf-8"),
                           file_name="jobplan-product-integration.md", mime="text/markdown",
                           key="integration_proposal")
