# NHS JobPlan Review Prioritisation POC Definition v1

**Prioritise attention, not people. Highlight change or uncertainty, not wrongdoing.**

## Problem, users and need

Clinical Directors and authorised JobPlan reviewers have finite review time.
They need a clear starting point, a faithful explanation and sufficient context
to decide where to look first. A highlighted change may be entirely legitimate.
Product and service stakeholders need evidence of workflow value, not a claim
that machine learning is necessary.

## Hypotheses and success criteria

| Hypothesis | Question | Evidence needed |
|---|---|---|
| H1 Workflow | Does a prioritised queue help a reviewer decide where to look first? | Observed synthetic tasks, usability feedback and prospectively measured review time |
| H2 Explainability | Can a reviewer understand why a plan is highlighted? | Correct identification of inputs, thresholds, missingness and rules versus ML reasons |
| H3 Rules | Are transparent change rules useful? | Independently assessed prioritisation relevance and fixed-budget yield versus chronological/random order |
| H4 ML incremental value | Does ML add useful prioritisation beyond rules? | Same-cohort comparison, disagreements, uncertainty and clinician assessment |

H4 may be false. Successful engineering proves traceability, reproducibility,
reconciliation and safe missing-data behaviour, not these product hypotheses.
Agree study tasks, rubric and acceptance thresholds **before** a study.
No invented target percentages, timelines, time savings, cost savings, clinical
safety improvements, workforce performance or patient outcomes are claimed.

## Goals, non-goals and priority

**Must:** fictional linked plan data, prior/current activity comparisons,
versioned rules with exact evidence, separate experimental ML, missing-data
triage, deterministic queues, fair evaluation, explicit boundaries and tests.

**Should:** review-reason inspection, semantic demonstration scenarios,
rules/ML disagreement, stable exports and a structured walkthrough protocol.

**Could later:** independently assessed earlier-review labels, a governed
read-only service and a shadow-mode study.

**Not in this POC:** production integration, real employee records,
authentication or a secure data store, approval/rejection, persisted review
decisions, clinical decisions, employment/disciplinary decisions, clinician
performance scoring, automatic escalation or a live deployment.

## Workflow and screens

V9 adds a separate **Product integration** presentation landing page: original,
fictional before/after worklist and detail wireframes. It proposes embedding
signals into the existing product rather than shipping this standalone POC
architecture. See the [integration recommendation](product-integration.md).
Current product implementation, APIs and permissions require validation.
The v8 review journey below remains available under **Review queue**.

Choose a fictional plan; inspect its change summary and data-quality state;
compare activities, working pattern and sites; open **Why highlighted?** for
the actual rule evidence and separate model terms; decide the next human action.
Missing or contradictory information requires clarification, not a Low score.
Prioritisation is not a decision.

The v8 review presentation keeps Streamlit: Review queue,
Experiment results, About the POC. Three existing fictional scenarios introduce
the workflow. Review JobPlan opens one reason, an immediate comparison and
human options; Back to queue returns. Supporting records and rule traces sit
under See details. Model evidence, what-if, full collections, filters, analysis
ordering, workload and original-plan exports sit with experimentation.
The reviewer queue is always rules-led, separate from experimental analysis order.
See the [design system](ux-design-system.md) and [demo guide](demo-guide.md).
No scoring, generation, evaluation or export-engine semantics changed.
Technical evidence is a demonstration surface, not a production permission model.

## Rules approach

R-01: total PA change after normalising by each version's WTE.
R-02: redistribution across DCC/SPA/Other category shares, invariant to proportional WTE/PA change.
R-03: stable activity IDs added or removed.
R-04: changed working-pattern sessions.
R-05: changed site allocation.

Each result includes ID/version/name/rationale, prior/current inputs, observed
difference, threshold and units, signal, points, evaluated/withheld state and
neutral explanation. Thresholds and weights are **illustrative configurable POC
settings**, not NHS policy or contract rules. A trigger means a change merits
context, never wrongdoing. Proportional WTE changes must not inflate PA change.
Withhold unreliable calculations on missing/inconsistent input. Do not invent
zero-valued activity rows for an unavailable or partial version.

The v5 administrative/change baseline remains a named legacy comparator.
The new activity-change rules are a new index version: do not silently reuse
the old meaning or old benchmark numbers. Report both where useful.

## ML experiment and the target mismatch

The existing target is **synthetic material amendment after review**, generated
stochastically from pre-review signals and latent noise. It is **not** an
independent judgement that a reviewer would prioritise the plan earlier.
Do not relabel it. Amendment yield is only a simulation metric and cannot test
H1-H4 alone; amendments may reflect service constraints or reviewer habits.

Recommendation: retain the existing training-only standardised logistic
regression and its exact signed linear contributions as a controlled experiment.
Keep its five features and fitted behaviour while improving the source-data
trace. No new candidate model is justified by invented labels.

An independently reviewed earlier-review rubric is **proposed**: define what
earlier attention means, permitted evidence, handling of legitimate change,
clarification versus prioritisation, and how disagreements are adjudicated.
Reviewers should assess cases without seeing algorithm scores first. Analyse
agreement and selection bias. Only then consider binary earlier-review labels
(Option A). Pairwise reviewer rankings (Option B) need a reliable collection
process; anomaly detection (Option C) measures unusualness, not appropriateness.
Neither is implemented. Model probabilities are not calibrated for real use.

## Rules-versus-ML methodology

Later-time holdout with training outcomes observable before the boundary;
exclude any holdout entity from training. Fit preprocessing only on training.
Use one common sufficient cohort for rules, ML, oldest-stage-first and repeated
seeded random order. Show cases found, Precision@K and Recall@K with actual
reviewed count. Zero-positive recall and empty-cohort precision are unavailable.
Random mean/spread is permutation variability, not clinical confidence.
Show top-K overlap and cases selected by only one method with real explanations.
Preserve and label the legacy comparator. Do not tune rules against holdout
labels to make them win.

Named demonstration scenarios have no outcome labels and never enter training,
holdout or reported metrics. They show mechanisms and failure handling, not
empirical performance. No claim of ranking stability without a meaningful
resampling question; no NDCG without graded relevance or real-world calibration
claim. Candidate-rule sensitivity is a future question.

## Synthetic strategy, schema and reconciliation

Keep the seeded legacy numerical generator as a reference fixture. Build
versioned activity records from its allocations, then derive the feature-facing
totals from those activities; validate redundant reported totals against them.
This lets the original ML experiment remain comparable without implying
realistic joint modelling of every added schedule/site field.

| Entity | Relationship / responsibility |
|---|---|
| Fictional subject | ID only, linked to one JobPlan; never a person-level score |
| JobPlan | Plan ID, subject ID, fictional service and previous/current versions |
| JobPlanVersion | Version ID, WTE, working pattern, declared total and activities |
| Activity | Stable matching ID within a plan, category, PA, session, site |
| ActivityCategory | Illustrative DCC, SPA and Other mapping; not contractual policy |
| WorkingPattern | Explicit day/session slots; not inferred from activity duration |
| PlanComparison | Activity/category totals, ID matches, pattern and location differences |
| RuleDefinition / RuleResult | Versioned catalogue and evaluated/withheld trace |
| FeatureVector / ModelPrediction | Five pre-review features and independent linear output |
| Explanation / QueueEntry | Exact traces/terms, actions, sufficiency and ordering |
| DataQualityFlag | Missing/malformed/contradictory source, explicit reason |

PA is illustrative weekly allocation, not an appointment duration. Activities
may share a session; this POC does not validate timetables or contracts.
Site labels and sessions are fictional context, excluded from ML predictors.
Record generator version and seed. Demonstrations include unchanged, small
change, substantial legitimate working-pattern/WTE change, unusual change,
missing prior plan, partial current plan, contradictory totals and contrasting
rules/ML mechanisms. IDs/labels must not influence scores. Do not tune inputs
until a desired category is obtained; show actual disagreement if present.

## Architecture and optional future API

One local Python/Streamlit modular monolith; no React/FastAPI rewrite.
UI -> comparison/validation -> independent trace rules and ML -> ranking/
evaluation -> synthetic in-memory records. Exports are original-plan only,
versioned, deterministic, JSON-safe and spreadsheet-formula-safe.

Current code modules: `synthetic`, linked-data/comparison, `features`,
trace rules, `scoring`, `evaluation`, `presentation`, `dashboard`; pytest and
AppTest cover boundaries and UI. Configuration lives in versioned code and the
Streamlit theme file. Local loopback and disabled telemetry are not access
control; do not load real records or expose the demo to a network.

**Proposed read-only API, not implemented:** `GET /plans` (filters, scope and
pagination), `GET /plans/{id}/comparison`, `GET /plans/{id}/explanations`,
`GET /experiment` (budget/cohort/version). Responses would include input-quality
state and versions; insufficient data is an unscored result, unknown IDs 404,
invalid queries 400. Authentication, authorisation, audited access, retention,
logging/monitoring, threat review and deployment approval are prerequisites.
No decision-write endpoint is proposed.

## Responsible AI, risks and open questions

The human keeps all decisions. Exact explanations are associations, not causal
judgements. Missing data cannot become reassurance. Avoid surveillance,
person-level rankings and good/bad clinician language. Keep scenarios distinct
from evidence. Activity/site changes and WTE may proxy service or protected
characteristics: validate subgroup effects and legitimate variation before use.

Open questions: which decision is supported, what independent outcome/rubric,
which local activity mappings and thresholds, who may see experimental results,
how scarce capacity and missing records are triaged, and how override/monitoring
would work in a governed pilot? The synthetic site/schedule generator is not
evidence that such fields are available or useful in eJobPlan.

## Gap analysis from v5 and implementation sequence

| v5 capability / gap | Next increment |
|---|---|
| Clear boundaries; implicit hypotheses and target mismatch | Definition v1, H1-H4 and independent-rubric proposal |
| Flat PA totals; no activity records/schedules/sites | Linked records, derived/reconciled totals, semantic scenarios |
| Five legacy weighted features, no rule IDs | Independent R-01..R-05 catalogue, exact traces and withheld state |
| Compact detail and what-if, ML default | Rules-led queue, activity/pattern comparison, Why highlighted |
| Rules/ML/age top-K, no random or disagreement | Random repeats, overlap, disagreement, actual results |
| No executed usability study | Explicitly unexecuted protocol and observation template |

Implement/commit in that order, then regression tests, isolated browser
inspection and private publication. Keep earlier engine tests; add adversarial
reconciliation, missingness, trace, isolation and scenario-exclusion checks.

## Cross-functional review and unified recommendation

Product: test the workflow and explanation separately from ML lift.
Domain: local mappings and thresholds need review, not invented policy.
Architecture: a modular local demo is sufficient; APIs/deployment are deferred.
ML: synthetic amendments do not establish the proposed earlier-review target.
UX: retain compact human-led review, expose uncertainty before an index.
Responsible AI: prioritise attention, not people; no automated decisions.
QA: trace every displayed value to source, distinguish study plans from results.

**Build reconcilable comparisons and transparent rules first, retain ML as an
honestly labelled amendment experiment, then evaluate the human workflow.**
This resolves the tension between a compelling ML demo and defensible evidence.
