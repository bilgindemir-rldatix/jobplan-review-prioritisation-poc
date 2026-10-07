# Synthetic usability walkthrough protocol v1

**Status: proposed, NOT EXECUTED. No participant results or measured benefits.**

This protocol tests review support, not clinician performance. Use only the
fictional evaluation plans and labelled JP demonstration collection. Agree
the purpose, task rubric, permitted prompts, observation recording, acceptance
thresholds and stopping criteria **before recruiting or running a study**.
Do not invent percentage targets after seeing results.

## Preparation

Confirm participants are appropriate Clinical Directors/authorised reviewers
and agree consent, recording and minimisation arrangements. Explain that no
real decision is made, no clinical safety claim exists and disagreement with
an index is appropriate. Record build, generator seed/version, rule catalogue,
thresholds, model version, budget, displayed collection and facilitator prompts.

Obtain an independently reviewed assessment rubric before assessing H3/H4:
earlier attention, routine order, clarification and uncertain must be distinct.
The existing **synthetic amendment** label is not that rubric. Do not let model
scores define the correct answer. Consider blinded assessment and counterbalance
which ordering participants see first to reduce anchoring/learning effects.

## Tasks and observation plan

| Task | Hypotheses | Observe, without inventing a score |
|---|---|---|
| Find a plan to review from a fixed-budget queue; explain the choice | H1, H3 | Time to orient, unnecessary navigation, rationale and capacity assumptions |
| Compare prior/current activities and explain R-01/R-02 for JP-003 | H2, H3 | Recognition of proportional WTE change and legitimate context |
| Inspect JP-005, JP-006 and JP-007 | H1, H2 | Distinguish unavailable/partial/contradictory input from Low; request clarification |
| Explain Why highlighted using the observed value, threshold and points | H2 | Correct source, units, partial signal versus threshold reached; no causal inference |
| Compare JP-008 and JP-009, then full-holdout top-K disagreement | H2, H4 | Identify which signals each method uses; avoid treating discrepancy as misconduct |
| Try what-if and check the original queue/export | H1, H2 | Understand isolation and non-causality; no score-gaming advice inferred |
| Reset a no-result search and locate the selected plan | H1 | Recovery, selection consistency, data-triage discoverability |
| Compare orderings with an independent rubric, if available | H3, H4 | Fixed-budget review yield plus observed time/usability; assess no-ML-benefit conclusion |

A facilitator should not imply that a higher number is correct or that a
participant should prefer ML. Stop and clarify if a user interprets the demo
as approval/rejection, a clinical probability, performance surveillance or an
authoritative answer. Record the interpretation error and the exact UI wording.

## Observation template (blank; one row per task)

| Anonymous participant | Task / order shown | Start / end | Assistance / navigation | Participant explanation | Interpretation errors | Missing-data handling | Suggested improvement |
|---|---|---|---|---|---|---|---|
| Not collected | Not run | Not measured | Not observed | Not collected | Not assessed | Not assessed | Not collected |

Also record source completeness, scenario/cohort, overrides/rejections of
ranking, confidence in understanding (self-report, **not model confidence**),
and facilitator deviations. Avoid identifiable real cases in free text.

## Interpretation and decision gates

Separate H1-H4. Software tests establish mechanics, not human usability.
Permutation spread in the random comparator is not study uncertainty.
A synthetic task cannot establish time savings or real clinical/workforce
outcomes. Review errors and qualitative observations before pooled summaries;
subgroup comparisons require an agreed sampling and analysis plan.

Agree outcome/rubric and governance; assess temporal/entity leakage, subgroup
effects and operational missingness; compare yield at fixed capacity; measure
time/usability prospectively. Only then consider a governed **shadow-mode**
pilot, with human override, monitored disagreements and a rollback/stopping
plan. Shadow mode, production access controls, monitoring and rollout are
**not implemented** in this local POC.
