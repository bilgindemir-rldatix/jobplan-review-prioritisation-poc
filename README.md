# JobPlan Review Prioritisation POC

A standalone, local-running demonstration to help a **Clinical Director decide
which JobPlans to review first**. It compares a transparent rules baseline with
an experimental, interpretable learned model, using **entirely fictional
synthetic data**.

**Prioritise attention, not people. Highlight change or uncertainty, not wrongdoing.**

Research definition and gaps: [POC Definition v1](docs/poc-definition.md).
Study preparation: [synthetic walkthrough protocol](docs/walkthrough-protocol.md)
(**not executed**). H1 workflow, H2 explanation understanding, H3 rules utility
and H4 incremental ML value are separate hypotheses, not validated findings.

**This does not replace clinical judgement, rate clinician performance, predict
clinical safety, identify misconduct or determine whether a plan is appropriate.**
A material amendment after review need not imply a problem with the original
plan. Low review priority is not reassurance, approval or a reason to skip review.

The original POC code can be hosted privately, but the application runs locally.
There is no production integration, cloud service, upload, external explanation
API, real clinician data, proprietary source code or copied company schema.
Streamlit telemetry is disabled and its server binds to loopback by default.
Do not expose the unauthenticated demo to a network or enter real data.

## Run locally

Use Python 3.11 or later. From the repository root in Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open `http://127.0.0.1:8501`. Stop the server with Ctrl+C. No activation script
or credentials are needed. Runtime generation, training and edits stay in memory;
no dataset or model artefact is automatically written. Explicit downloads save
the selected export through your browser. Re-running with the same seed reproduces
the data independently of the wall clock. Exact dependency versions can affect
last-digit model results; supported dependency ranges are in `pyproject.toml`.
The workspace uses the tested Streamlit 1.65+ native tab/selection APIs; no
additional UI framework or runtime dependency is introduced.

### Updating an already running demo

The current interface shows **Build: clinical-workspace-v6** directly below
**JobPlan review workspace**. Check this marker rather than assuming a browser
refresh loads changed Python modules. If it is absent, stop **your own demo
server** with Ctrl+C in its original terminal, change to this checkout and run:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Then refresh `http://127.0.0.1:8501`. Restarting also applies the light theme.
Do not stop another person's process or a server whose identity is uncertain.
A successful health check alone does not identify which app version is loaded.

Run all tests, including the Streamlit AppTest smoke tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -W error
```

For a headless readiness check, start the same command in a separate terminal:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.headless true --server.port 8517
```

Then check from PowerShell:

```powershell
Invoke-WebRequest http://127.0.0.1:8517/_stcore/health -UseBasicParsing
```

The health endpoint checks the server, not application correctness; AppTest
also executes the page, filters, plan details, unscored path and what-if form.

## Clinical review workspace

The dashboard presents the **later synthetic holdout** as a historical
pre-review queue. Each row has its own snapshot date. Ages and overdue days are
measured **at that snapshot**, not at today's date. This is not a live waiting list.
The separate **Demonstration scenarios** collection contains nine fixed
fictional JP cases, never training or evaluation records. Collection changes
retain the current filters; reset them if no cases match. Evidence and the
About-tab benchmark always use the evaluation holdout, never demonstrations.

The default is a restrained **light workspace**, using Streamlit's supported
theme and layout APIs: dark text, white surfaces and teal controls. There is no
injected CSS or JavaScript. Priority remains visible as text, not colour alone.
The compact overview is a single count line rather than large metric cards.

Five prominent top-level tabs stay visible: **Overview**, **Review workspace**
(selected initially), **Review patterns**, **Evidence & export** and
**About this initiative**. Supporting
details use expanders; the main navigation is never hidden in them.

| Area | Purpose |
|---|---|
| Overview tab | Plain-language starting guidance, scored priority distribution and population definitions |
| Review workspace (default) | Compact queue beside the selected plan, both indices, main driver, next human action and data sufficiency |
| Data clarification | Separate selectable unscored list under the queue, with recorded completeness |
| Selected plan expanders | Activity-level and working-pattern comparison, Why highlighted rule evidence, separate model contributions and isolated what-if |
| Review patterns tab | Fictional department/specialty workload counts, denominators and small-group caveats |
| Evidence & export tab | Full-holdout rules/ML/oldest/random/legacy comparison, overlap and disagreement, with downloads in an explicit export expander |
| About this initiative tab | Product-friendly problem, intended users, value hypothesis, fictional journey, current scope, learning and decision gates |

Select a table row or use **Selected plan**; the **Viewing** indicator always
marks the plan shown alongside. Changing filters or ordering resets obsolete
table selections, preventing a stale row from selecting the wrong plan. The
selected plan persists when moving between tabs if still in
scope. The sidebar's **Stack queue and detail (smaller window)** switch places
the same panels vertically without changing selection, scores or filters.
Tables can scroll horizontally where necessary; Streamlit handles narrow
screens and sidebar collapse. Exact contribution tables and what-if controls
stay behind deliberate expanders so they do not dominate the initial workflow.

The review orientation is **choose a plan, understand the review reasons, decide
the next human action**. Hover help explains rules versus experimental ML,
priority indices versus probabilities, and completeness versus confidence.
No approval buttons, saved review decisions or live workflow integration are
implied.

**Reset filters & search** in the sidebar restores all specialty, working-pattern,
stage and priority options in the current collection, clears search, restores rules-led ordering and
selects the first available plan. Obsolete row selections are invalidated.
It preserves the review budget and layout; it does not alter source data,
scenario inputs or model fitting. As before, submitted scenario outputs are
transient and disappear on a new unrelated interaction. Empty states point to
this reset action and the separate unscored list instead of leaving a dead end.

### About this initiative: the Product conversation

The fifth tab explains the finite-review-time problem and the hypothesis of
more understandable, focused prioritisation without claiming time savings or
clinical benefits. It separates what is implemented (synthetic local review
support) from proposed future work. A concrete fictional journey shows how a
Clinical Director might examine a plan and seek clarification while keeping
judgement with an authorised human.

Its default-demo benchmark is calculated using the existing comparison function,
the full common holdout and a fixed budget of **30**, independent of search,
filters, collection, what-if edits and the active sidebar budget. The current default
result is rules **8**, ML **6**, oldest-first **7** synthetic amendments found.
The new activity-change rules happen to find the same count as the old baseline;
they are not the same index. Both are identified in Evidence.
ML has not demonstrated advantage here; Product can assess workflow value even
if transparent rules are preferable. The Evidence tab remains the place to vary
the review budget. Neither table validates future real-world review need.

Decision gates cover an independently reviewed outcome definition, approved
minimised data/access/governance, temporal and entity separation, subgroup
checks, fixed-budget yield and prospective clinician review-time/usability
measurement. A governed shadow-mode pilot with human override and monitoring
is **proposed, not implemented**, before any rollout. There are no invented
targets, promised benefits or timelines. A short walkthrough/glossary is
available without duplicating the detailed model evidence.

The sidebar filters specialty, working pattern, workflow stage and review
priority. Free-text search is a case-insensitive **literal phrase** across
fictional IDs, departments, specialties, both scorers' actual driver labels and
input-error reasons (not a regex or outcome search). All workspace areas use the same
filtered original-plan view **except the benchmark**, which deliberately remains
the full common eligible holdout. Counts and selected-plan options follow that
view. A selection that leaves the view is replaced with its first available
plan; an empty view clears the detail. Clearing search/filters restores options.

Rules-led ordering is the default. Alternatives are explicitly experimental ML
or time in the current workflow stage. The selected score
source defines the priority filter, overview distribution, actions and group
rates. With oldest-first, these remain **rules-based**, while ordering uses age.
Both scores stay separate: no blending, target-score hints, preset category
clipping or ID-based score jitter. IDs only break exact ranking ties.

Missing/invalid required inputs show **Data clarification required / Priority
cannot be reliably calculated**, in a **separate unscored data-triage list**,
never at the bottom of the ranked queue or labelled Low. Priority filters do not
hide them; specialty/pattern/stage filters and text search still apply. Humans
must resolve or triage them independently of the ranked review budget. Recorded
completeness percentage is a **data indicator, NOT model confidence**; a populated
percentage cannot compensate for a missing required scoring input.

What-if controls change current total activity, WTE, completeness, stage age and
due-date offset. Total changes preserve activity mix and rescale the linked
activity allocations; WTE changes retain the existing day/session slots as an
explicit scenario assumption, not an inferred timetable. Source records, queue,
patterns, fitting, benchmark and exports never change. Scenarios pass through
the same validation/scoring functions, stay transient and do not repair missing
source data. They are **not causal estimates or advice to obtain a better score**.

### Review-pattern denominators

Groups contain only plans in the current filtered view. For each department or
specialty, `total_plans = scored_plans + unscored_plans`, and
`high_priority_rate_among_scored = high_priority_plans / scored_plans`, using the
selected scoring source. Rates are proportions from 0 to 1, not percentages.
A zero scored denominator gives an unavailable rate, not zero. Fewer than five
scored plans triggers a small-group warning: do not compare these rates.
There are no groups for an empty view.

Priority filtering changes these denominators: a High-only view naturally
produces 100% among scored groups. These are descriptive **review-workload
distributions**, not clinical quality, clinician performance, causal problem
evidence or reliable comparisons of services. Two deterministic fictional
department groupings map surgery/radiology to planned care and general
medicine/psychiatry to continuing care. They are illustrative display groupings,
not real organisation mappings, and never enter scoring or label generation.

### Export contract (schema 2.0)

Downloads contain the **whole current filtered original-plan view**, not just
the first K. "Baseline/non-what-if" means unchanged source plans; it does **not**
mean rules-only scoring. Matching unscored records are included, bypassing the
priority filter but not other filters/search. Exports contain the selected
original collection (holdout or labelled demonstration cases), never transient
what-if edits, outcome labels, entity IDs or wall-clock timestamps.

JSON contains `metadata` and a `plans` array. CSV uses `record_type` and
`scope_metadata_json` plus the same plan fields. Its **first data record is
`record_type=scope`**, carrying the JSON metadata; subsequent records have
`record_type=plan`. Filter to plan records before tabular analysis. Even an empty
view has its scope record/header and JSON metadata with an empty plans array.
This avoids fake plan rows or losing the scope of an empty export.

Metadata contains the filter/search configuration, ordering/priority source,
scope and unscored policy, counts, synthetic notice, fixed seed/reference/test
dates, training date range/count, feature order and fitted coefficients,
intercept, training means/scales. Version identifiers are
`export_schema_version=2.0`, `scoring_version=activity-change-v1`,
`model_version=standardised-logistic-v1`. Coefficients/preprocessing values
identify the actual fitted model rather than implying all supported library
versions produce identical last-digit results.
Metadata declares collection(s), demonstration exclusion policy and the legacy
rules version. The legacy flat-record test API still reports `rules-v1`, not
activity-change rules it cannot calculate.

Plan records include fictional `plan_id`, `department`, `specialty`,
`working_pattern`, `workflow_stage`, `snapshot_date`, `workflow_age_days`,
`completeness_percent`, `data_sufficiency`, `input_errors`, both
`baseline_index`/`model_index`, both categories, main drivers, human review
actions, explanation-space labels, full contribution dictionaries, and
`model_intercept`/`model_decision`. Rules contributions sum to index points;
signed ML contributions plus intercept sum to the model log-odds decision,
**not its transformed index or probability**.
Schema 2 adds `rule_ids`, full `rule_traces` (ID/version/input evidence/
threshold/observed difference/signal/points/state/explanation),
`data_quality_state`, `change_summary`, `legacy_baseline_index`, `cohort`,
`generator_version`, `generator_seed` and `scenario_name`.
Withheld traces export null differences/signals/points, never zero. All points
can be reproduced from the exported rule inputs, thresholds and weights.

Numbers retain numeric precision in JSON and numeric text in CSV. Unavailable
scores are JSON `null` and empty CSV cells, never non-standard JSON `NaN`.
Nested CSV fields are JSON-encoded. Potential spreadsheet-formula text
(leading `=`, `+`, `-`, `@`, including whitespace prefixes, or a leading tab/
line break) is apostrophe-prefixed in CSV only; genuine numeric negatives are
unchanged. JSON preserves original text. Keep spreadsheet import settings
appropriate for text identifiers.

Exports are byte-deterministic for unchanged data, model and normalised filter
configuration. They are generated only from the original scored queue and do
not mutate it. Browser downloads are an explicit local user action; nothing
is uploaded or sent to another service.

## Synthetic data and assumptions

`generate_dataset(n=800, seed=42, missing_rate=0.04)` creates linked fictional
entities, one row per entity, with IDs such as `FIC-00001`. No identifying
information is generated. The seed and fixed reference date `2026-02-01` are
visible in the dashboard.

`synthetic.generate_plans` is retained as the **frozen legacy numerical fixture**
for regression comparison. The linked adapter uses that initial allocation
distribution, creates actual activity records, then derives/reconciles all
feature-facing totals from the activity records. The ML feature matrix,
stochastic outcome labels, split and fitted predictions remain equivalent to
the legacy experiment within floating-point tolerance. There is no independent
second set of activity totals used to score the linked UI.

Each JobPlan links an ID-only fictional subject, previous/current version IDs
and activities with stable matching IDs, category (DCC/SPA/Other), PA, a day/
session slot and a fictional site. Versions declare WTE, their working-pattern
slots, completeness and a reported total to validate against derived totals.
Version/subject/activity links and duplicate IDs are checked. The comparison
matches activities by stable ID, not by row position. A genuine added/removed
activity in two complete versions may have zero on the absent side; an
unavailable/partial version never does.

The provenance is `linked-activities-v1` and the seed. An independent seeded
stream supplies fictional schedule/site/identity changes, not target hints.
These added fields are a simplified fixture, not a validated joint simulation
of NHS job planning. Multiple activities can share a session; PA is not an
appointment duration. Real schedule feasibility/contract validation is outside
scope. For a missing legacy prior total, the linked prior version is unavailable.

### Named demonstration cases (excluded from every experiment)

| ID | Mechanism | Observed rules / ML indices in the default run |
|---|---|---|
| JP-001 | Unchanged activities/pattern/sites | 0 / 10.44 |
| JP-002 | Small DCC-to-SPA allocation change | 2.5 / 10.53 |
| JP-003 | Legitimate WTE and PA halved, sessions changed | 15 / 10.44; zero R-01/R-02 points |
| JP-004 | Unusual allocation, activity IDs, pattern and site change | 100 / 42.50 |
| JP-005 | Missing previous version | Unscored / unscored |
| JP-006 | Partial current activity list | Unscored / unscored |
| JP-007 | Declared total contradicts activities | Unscored / unscored |
| JP-008 | Activity/category/site turnover but short administrative wait | 75 / 13.24 |
| JP-009 | Stable activities but long wait/overdue date and known incompleteness | 0 / 81.28 |

These are fixed semantic inputs, not searched, target-shaped or band-clipped
examples. JP-008/009 demonstrate strong-rules/weak-ML and the reverse because
the two methods use different signals. Names/IDs do not enter scoring.
They have no amendment label or outcome date, a `demonstration` cohort flag,
and disjoint entity IDs. Fitting, temporal splitting and metrics explicitly
reject demonstration records; the UI keeps collections separate.

Snapshots span `2024-01-01` to `2025-12-31`. Each record has current and previous
weekly programmed activities (PA), direct-care/supporting/other activity mix,
whole-time equivalent (WTE), a fictional specialty/working pattern, workflow
stage/start, illustrative review due date and percentage completeness.
Previous-plan quantities are contextual pre-review inputs, **not additional
training rows**.

The generator includes less-than-full-time work, working-pattern changes,
specialty-dependent activity mixes, legitimate within-plan variation and large
but plausible changes. Its quantities and categories are **illustrative**, not
confirmed ejobplan fields, interfaces, contractual rules or NHS policy thresholds.
Specialty and working-pattern names are context, not performance labels.
Activity changes are normalised by each plan's WTE; a proportional reduction in
activities and WTE alone does not create an activity-change or mix-change signal.
Even a large residual change can be completely appropriate.

The synthetic target is a binary **material amendment recorded within 30 days of
review of that snapshot**. For simulation, every label becomes observable 30
days after its snapshot. A Bernoulli draw uses a logistic propensity formed from:

```text
-2.4
+ 0.35  * absolute activity change per WTE
+ 0.018 * absolute direct-care mix change (percentage points)
+ 0.005 * workflow-stage age (days)
+ 0.012 * overdue days
+ 0.025 * incompleteness percentage
+ unobserved normal noise (mean 0, standard deviation 0.8)
```

This is a **made-up data-generating process**, not a clinical finding or fitted
real-world relationship. Labels are not baseline threshold labels, and include
latent variation and Bernoulli randomness. Missing previous totals are introduced
after target generation, independently of the target; changing missingness does
not change labels. This conveniently random missingness is itself unrealistic.

**Target mismatch:** this is a synthetic amendment, **not** the proposed label
“a reviewer would prioritise for earlier review”. The definition document
proposes an independently reviewed earlier-attention rubric; it is not built
or validated. Do not treat amendment yield as proof of workflow usefulness.

## Validation and sufficiency

Both scorers require the same three dates, current/previous WTE, current/previous
totals and all three activity components, plus completeness. Numeric fields
must be finite numbers (not booleans or numeric strings); totals/WTE must be
positive; components non-negative; completeness between 0 and 100. Component
sums must agree with their total within **0.02 PA rounding tolerance**. Workflow
start must not be after the snapshot. Dates must be valid, timezone-free,
midnight dates. Derived features must also be finite. Linked versions also
require explicit complete activity lists, valid category/site/session fields,
stable unique IDs, correct links and consistent declared/derived totals.
All five rule calculations and ML scoring are withheld when this common
required input contract fails. Reliable individual facts may still be inspected,
but no partial index is presented as complete. This conservative common contract
also means a missing site withholds ML, even though site is not an ML predictor.

Invalid/missing required input returns **Unscored / Insufficient required data**,
an explicit reason and a human-triage action. It is never imputed to zero or
scored Low. In contrast, an explicitly known completeness percentage below 100
is a usable input to the legacy ML/administrative rules, not a replacement for
required-data validation. The new change rules do not score that percentage.
Input validity
does not prove that an otherwise complete record is true or sufficient for
clinical judgement.

## Score definitions and explanations

The five preserved ML/legacy-baseline pre-review features are:

| Feature | Definition |
|---|---|
| Activity change per WTE | Absolute difference between current total/current WTE and previous total/previous WTE |
| Direct-care mix change | Absolute difference in current/previous direct-care shares, in percentage points |
| Workflow-stage age | Snapshot date minus current stage start, in days |
| Overdue days | Maximum of zero and snapshot minus illustrative review due date |
| Incompleteness | 100 minus known completeness percentage |

### Current rules: activity-change-v1

`rules.CATALOGUE` is the versioned configuration; `assess_rules` accepts an
explicit catalogue for controlled experiments. Thresholds must be positive,
weights non-negative and total weights 100. Record a new configuration/version
when changing them; there is no live threshold tuning against holdout labels.
These are **illustrative POC settings**, not NHS policy or contract thresholds.

| Rule | Observed difference from source | Full-signal threshold | Maximum points |
|---|---|---:|---:|
| R-01 Total PA change per WTE | Absolute current PA/current WTE minus previous PA/previous WTE | 3 PA per WTE | 25 |
| R-02 Activity-category redistribution | Half the sum of absolute category-share differences, times 100 | 20 percentage points redistributed | 25 |
| R-03 Activities added/removed | Symmetric difference / union of stable activity IDs | 0.5 | 20 |
| R-04 Working-pattern change | Maximum of session symmetric-difference/union and absolute WTE change/max WTE | 0.5 | 15 |
| R-05 Site allocation change | Half the sum of absolute site PA-share differences | 0.5 | 15 |

For every evaluated rule, `signal = min(observed / threshold, 1)` and
`points = weight * signal`. The index is the **sum of trace points**.
“Triggered” means the full-signal threshold was reached; smaller non-zero
changes contribute partial points and remain visible. A zero-change rule has
zero points, but a **withheld** rule has null difference/signal/points and an
explicit data-quality reason. No overall index is issued if any required
source validation fails. Neutral text explicitly allows legitimate changes.

R-01 controls for proportional WTE change; R-02 compares category shares so
gross proportional changes do not masquerade as redistribution. R-04 can still
highlight the changed pattern for context. Source evidence includes old/new
allocations or shares, stable IDs, WTE and sessions; **Why highlighted?**
shows ID/version, rationale, exact inputs, observed value, threshold, units,
strength, points and state, separately from model contributions.

### Legacy v5 comparator: rules-v1

The previous baseline remains `score_baseline`, explicitly **Legacy v5 rules**
in evaluation. It is not blended with R-01..R-05. Each feature adds `weight * min(feature / cap, 1)`.
The non-negative terms sum to a bounded 0-100 index:

| Feature | Illustrative cap | Maximum index points |
|---|---:|---:|
| Activity change per WTE | 3 PA per WTE | 25 |
| Direct-care mix change | 20 percentage points | 20 |
| Workflow-stage age | 120 days | 20 |
| Overdue days | 60 days | 20 |
| Incompleteness | 40% | 15 |

These are product demonstration choices, not clinical norms, service targets
or contractual thresholds. Baseline contributions are **index points**, not ML
explanations. Zero terms simply mean no points under these rules.

**Experimental learned model:** a training-only `StandardScaler` followed by
L2-regularised logistic regression (`C=1`, maximum 2,000 iterations). The model
uses exactly the five named features, not identifiers, specialty, working
pattern label, day/session slots, site, activity ID, workflow-stage label,
target or outcome-observation date. WTE is used in derived normalised PA change.
There is no
hyperparameter search or held-out-data tuning.

For each plan, every actual signed contribution is
`coefficient * (feature - training_mean) / training_standard_deviation`.
The intercept plus all contributions equals `decision_function` to floating
point precision. Positive/negative terms raise/lower the linear model decision
relative to the training-feature mean. This reference is **not a clinical norm**.
Correlated inputs, regularisation and generator assumptions limit interpretation;
terms are associations, not causes or independent attribution of responsibility.

The ML index is `100 * logistic(decision_function)`, the fitted logistic output
rescaled to 0-100, **not a calibrated real-world probability**. Signed terms are
in **model log-odds space** and do not add to the nonlinear index or represent
probability contributions. Rules rationales and ML explanations remain separate.
The two index constructions are not equivalent scales.

For both indices the illustrative categories use unrounded values:

| Index | Review priority | Human action |
|---|---|---|
| 0 to below 35 | Low | Retain normal human review and check context |
| 35 to below 65 | Medium | Consider earlier review and clarify highlighted information |
| 65 to 100 | High | Consider prioritising Clinical Director review; confirm context and data |
| No score | Unscored | Resolve required data and route for human triage; do not deprioritise |

## Evaluation design

Training snapshots are earlier than `2025-09-01`, and their outcomes must have
become observable **strictly before** that boundary. Later snapshots with
observable outcomes by `2026-02-01` form the holdout. Training rows with outcomes
crossing the boundary are purged. If repeated entity IDs are supplied, all
training records for holdout entities are also purged. Plan IDs must be unique.
The default generator has no repeated entities. All feature preprocessing and
model fitting use sufficient training rows only. No post-review fields enter
feature extraction.

The dashboard compares current rules, ML, oldest-first, legacy rules and
repeated seeded random order on the **same sufficient
holdout cohort** at a fixed user-selected budget K (default 30). Benchmark
results do not change with queue filters or scenario edits. Actual reviewed
count is `min(K, eligible cohort size)`. Amendments found is the positive count
among those reviews; precision is found/reviewed; recall is found/all positives
in the eligible cohort. A zero-positive cohort makes recall unavailable, and
an empty cohort also makes precision unavailable. Undefined values are shown
as empty/None, never replaced by zero. Missing outcomes are errors, not negatives.
The excluded insufficient-data count is displayed; their exclusion is an
evaluation convention, not clinical permission to ignore those plans.

Random ordering uses 100 permutations with seed 314 after sorting the common
cohort by fictional plan ID. Report mean, population standard deviation and
range; undefined precision/recall stay unavailable. This spread is **random
order variability**, not model ranking stability or a clinical confidence
interval. No bootstrap stability, calibrated probabilities, NDCG or new ML
candidate is claimed without a defensible research question/target.

Top-K overlap reports intersection/actual K and intersection/union (Jaccard).
Disagreements are the symmetric difference of rules/ML selections, with actual
positions, indices and reasons; a disclosure exposes exact rule traces and
signed model terms. At K covering the cohort there are no selection
disagreements; empty-cohort overlap ratios are unavailable, not zero.

Learning this generator **does not demonstrate real-world validity**. A single
synthetic holdout is not evidence of ML superiority. There is no calibration,
fairness assurance, uncertainty interval or prospective clinical evaluation.
Working pattern and specialty are excluded as predictors but can still be
indirectly associated with other features.

### Recorded default run

Seed 42, 800 generated records, 4% missingness setting, budget **K = 30**:
615 sufficient training rows, 19 insufficient training rows excluded, 33
boundary-purged rows, and 133 holdout rows. Five holdout rows are unscored,
leaving a common evaluated cohort of **128 plans with 25 positive outcomes**.
The realised missing count need not be exactly 4% of the dataset.

| Method | Reviewed | Amendments found | Precision at K | Recall at K |
|---|---:|---:|---:|---:|
| Activity-change rules v1 | 30 | 8 | 26.67% | 32.00% |
| Experimental ML | 30 | 6 | 20.00% | 24.00% |
| Oldest-first | 30 | 7 | 23.33% | 28.00% |
| Legacy v5 rules | 30 | 8 | 26.67% | 32.00% |
| Random ordering (100-run mean) | 30 | 5.76 | 19.20% | 23.04% |

Random cases found: population SD **1.7557**, observed range **0 to 11**;
precision SD **0.05852**, recall SD **0.07023**. Current rules and ML share
**8 of 30** selected plans, with **22 rules-only and 22 ML-only** selections;
Jaccard **0.15385**. The new rules finding the same count as the legacy index
is coincidental, not evidence that the indices or selected cases are equivalent.

**ML did not win this holdout.** These are actual synthetic results, not a
promise, a policy recommendation or evidence that any method is useful on real
JobPlans. The run used Python 3.14.0, NumPy 2.5.3, pandas 2.3.3,
scikit-learn 1.9.1 and Streamlit 1.65.0. The live dashboard recomputes the
comparison for its selected budget.

## Architecture

```text
synthetic.py -> fictional pre-review records and stochastic outcome labels
records.py / dataset.py -> linked activities/versions, reconciliation and separate JP scenarios
features.py -> explicit validation and five shared pre-review features
rules.py -> versioned R-01..R-05 catalogue, source evidence and exact index points
scoring.py -> legacy rules / training-only linear model / signed terms / isolated what-if
evaluation.py -> purged split, common-cohort ranks, repeated random benchmark and disagreement
presentation.py -> shared filtered scope, workload denominators, deterministic safe exports
dashboard.py -> light review workspace, adjacent detail, secondary patterns/evidence/export
app.py -> Streamlit entry point
tests/ -> reproducibility, bounds, missingness, leakage, contributions, metrics and UI
```

There is no database, trained-model file, automatically persisted synthetic
dataset or hidden API. Explicit exports are saved only through the browser.
`.venv`, caches, local secrets and build artefacts are excluded from Git.

## Before any real-world research

A governed follow-on would first need an agreed review purpose and field
definitions, information governance and consent/legal basis, representative
pre-review data, an independently specified amendment outcome, clinician-led
assessment of legitimate variation, subgroup/error analysis, temporal external
validation, capacity-aware evaluation and prospective human oversight. Historic
amendments may reflect reviewer habits or service constraints rather than need.
Do not connect this POC to production or treat the synthetic thresholds as policy.

The walkthrough protocol is a blank **unexecuted** study plan, not a study
report. Agree thresholds and an independent assessment rubric before collecting
data. React/FastAPI, persistence, live APIs, authentication/authorisation,
governed shadow mode and real-data import remain deferred. A proposed read-only
API contract (not an endpoint implementation) is in the POC definition.
