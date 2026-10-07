# A simpler JobPlan product demonstration

**One sentence:** This helps a Clinical Director decide where to look first,
tells them what changed, and leaves the decision with them.

This three-plan POC script remains available under **Review queue**. V9 opens
instead on **Product integration**; use its [5–7 minute integration storyboard](product-integration.md)
to present the proposed fit within the existing product. Neither set of
wireframes is a confirmed representation of current JobPlan implementation.

**Prioritise attention, not people.** The two-minute understanding goal and
three-to-five-minute script below are design targets, not measured user results.

## Assessment: what was getting in the way

V7 had the right safeguards but led with the machinery: dataset selection,
search, ordering, filters, count filters, pagination and explanation terminology
before the first plan. Cards repeated rule counts, relative model signals and
unavailable dates. Detail repeated its priority, reason, data checklist, scenario
description and change list before showing the comparison. The Product story
was a long research page rather than a short introduction.

| Remove from the primary journey | Retain elsewhere |
|---|---|
| Dataset controls, multiple ordering choices, advanced filters | Experiment results: queue settings |
| Rule counts, model signals, indices and absent-date metadata on cards | Exact evidence and source information |
| Duplicate priority/reason panels and change-count summaries | One reason, immediate before/after comparison |
| What-if and model terminology during a normal review | Experiment results: inspect a plan |
| Repeated large disclaimer banners | One concise decision-support boundary |
| A long About page as the product introduction | Short story, with research notes disclosed |

## Essential product model and journey

Three concepts: **a plan, its review signal, a human judgement**.

1. **Choose a plan:** a short queue answers why it is worth inspecting.
2. **See what changed:** one sentence followed immediately by a before/after
   comparison and relevant working-pattern context.
3. **Decide what to do next:** continue standard review, seek clarification
   or review earlier. These are unselected, simulated reviewer options.

Navigation stays small: **Review queue**, **Experiment results**, **About the POC**.
There is no dashboard, separate detail navigation, My Reviews or approval flow.

## Presentation examples

Reuse three existing deterministic scenarios rather than generate new data or
tune scores to fit the story. They remain excluded from training and evaluation.

| Existing fictional ID | Role in the main demo | What is actually in the record |
|---|---|---|
| JP-004 | Review sooner | DCC decreases from 7 to 1 PA, SPA increases from 2 to 13 PA, and working-pattern sessions change |
| JP-002 | Standard review | Small DCC-to-SPA redistribution, with no working-pattern change |
| JP-005 | Data clarification | Previous plan is unavailable; comparison and both scores are withheld |

Two optional examples belong in the experiment, not the default queue:
**JP-003** illustrates a legitimate proportional WTE/PA reduction, and
**JP-009** illustrates disagreement (stable activities but long administrative
waiting/overdue signals). The latter is a strong, not merely slight, model signal
in this fixture. Do not invent another ID or claim a subtly different outcome.

All nine existing scenarios and the complete evaluation holdout remain accessible
in queue settings. The three-plan presentation is the default, not a new
evaluation cohort. Labels and scores are unchanged. The presentation subset
must never enter model fitting or benchmark calculations.

## What remains on each screen

**Queue:** fictional ID, service, one text/icon priority, one reason and
**Review JobPlan**. One small summary gives plan/earlier-review/clarification
counts. No model signal, rule count, numeric index or missing-date placeholder.

**Review:** plan identity, one priority, **Why this plan was highlighted**,
**What changed?**, working-pattern context and **What would you do next?**.
Supporting source records/checklists and exact rule evidence remain available
through **See details**. Missing source information is named; no comparison is
invented and no missing plan becomes Standard review.

**Experiment:** the question is whether ML adds value beyond rules. An
evaluator-driven result is visible first. Precision/recall, random variability,
overlap, disagreement, model terms, provenance and workload remain secondary.
Original-plan exports and isolated what-if remain usable without entering the
primary reviewer journey.

**About:** problem, purpose, ML's experimental role and who decides. A short
walkthrough and the detailed research scope are optional disclosures.

## Copy and faithful explanations

Use **Plans to review**, **Review JobPlan**, **What changed?**, **See details**,
**What would you do next?**, **Seek clarification**, **Review earlier**.
Review sooner / Standard review / Data clarification retain the existing
illustrative category mapping; these are not new NHS thresholds.

Main reasons describe actual source differences. Say "DCC allocation decreased
by 6 PA and the working pattern changed", not "the person is unusual".
No model explanation may claim that it learned real historical clinical norms
or that working-pattern sessions are predictors: it learns this synthetic
generator using the existing five pre-review features. Signed terms remain
associations, not causes or probability contributions.

The target remains **synthetic material amendment**, not independently assessed
earlier-review need. No benefits, calibration or clinical validity are established.

## Three-to-five-minute script

| Scene | Suggested narration and action |
|---|---|
| 0:00-0:30: problem | "Clinical Directors can have many JobPlans and limited review time. This helps them decide where to look first." |
| 0:30-1:00: queue | Show the three examples. "One has substantial changes, one has small changes, and one needs more information." |
| 1:00-2:00: review | Open JP-004. Read the plain reason, then compare DCC/SPA and the working pattern. "These are changes to understand, not a judgement about a clinician." |
| 2:00-2:45: judgement | Point to the reviewer options. "The authorised reviewer decides whether to continue, clarify or review earlier. This demo records no decision." |
| 2:45-3:15: missing information | Return and open JP-005. "It does not invent a low priority when the previous plan is missing." |
| Optional 3:15-4:30: experiment | Open Experiment results. "We are testing whether ML adds anything beyond transparent rules." Show actual results, not a promise that ML wins. Optionally inspect JP-009. |

End: **"ML is an experiment. Human judgement remains central."**

## Presentation readiness and limits

Start with the default three-plan presentation, no previous filters or scenario
edits. Use **Reset presentation demo** to recover a changed scope. Check the build marker.
Keep the comparison readable without opening technical details. Do not make
a fictitious approval, request-sending or live eJobPlan integration claim.

Review against five questions: what problem, what signal, what changed, who
decides, and what happens when information is missing. Software and layout
checks are not evidence that a first-time stakeholder answers them in two minutes.
That still needs the unexecuted clinician/stakeholder walkthrough and accessibility
assessment. The full research protocol and governance gates remain in the POC
definition and walkthrough protocol.
