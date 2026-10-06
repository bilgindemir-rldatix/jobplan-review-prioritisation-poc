# JobPlan Review Prioritisation POC

A standalone, local-running demonstration to help a **Clinical Director decide
which JobPlans to review first**. It compares a transparent rules baseline with
an experimental, interpretable learned model, using **entirely fictional
synthetic data**.

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
no dataset or model artefact is written. Re-running with the same seed reproduces
the data independently of the wall clock. Exact dependency versions can affect
last-digit model results; supported dependency ranges are in `pyproject.toml`.

Run all tests, including the Streamlit AppTest smoke tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

For a headless readiness check, start the same command in a separate terminal:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.headless true --server.port 8501
```

Then check from PowerShell:

```powershell
Invoke-WebRequest http://127.0.0.1:8501/_stcore/health -UseBasicParsing
```

The health endpoint checks the server, not application correctness; AppTest
also executes the page, filters, plan details, unscored path and what-if form.

## Dashboard

The dashboard presents the **later synthetic holdout** as a historical
pre-review queue. Each row has its own snapshot date. Ages and overdue days are
measured **at that snapshot**, not at today's date. This is not a live waiting list.

- Filter specialty, working pattern, workflow stage and review priority. Rank by
  baseline, ML or time in the current workflow stage (oldest-first). Both indices,
  the selected method's priority/action and its largest absolute driver appear
  alongside explicit input sufficiency. Ties use fictional plan ID.
- Inspect a plan's previous/current activities, WTE, derived features, both scores
  and the full contribution breakdown. Under oldest-first, displayed categories
  and explanations still belong to the baseline, not an invented age model.
- See missing/invalid required inputs in a **separate unscored data-triage list**,
  never at the bottom of the scored queue or labelled Low. Priority filters do
  not hide this list; specialty/pattern/stage filters still apply. A human must
  resolve or triage these plans independently of the ranked review budget.
- Use an isolated, explicitly submitted what-if form for current total activity,
  WTE, completeness, stage age and due-date offset. Total changes preserve the
  activity mix. Source records, queue, model and benchmark are never changed.
  Outputs are recalculated through the identical validation/scoring functions.
  Scenarios are transient, do not repair missing source data and are **not causal
  estimates or advice to change a plan to obtain a better score**.

## Synthetic data and assumptions

`generate_plans(n=800, seed=42, missing_rate=0.04)` creates independent fictional
entities, one row per entity, with IDs such as `FIC-00001`. No identifying
information is generated. The seed and fixed reference date `2026-02-01` are
visible in the dashboard.

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

## Validation and sufficiency

Both scorers require the same three dates, current/previous WTE, current/previous
totals and all three activity components, plus completeness. Numeric fields
must be finite numbers (not booleans or numeric strings); totals/WTE must be
positive; components non-negative; completeness between 0 and 100. Component
sums must agree with their total within **0.02 PA rounding tolerance**. Workflow
start must not be after the snapshot. Dates must be valid, timezone-free,
midnight dates. Derived features must also be finite.

Invalid/missing required input returns **Unscored / Insufficient required data**,
an explicit reason and a human-triage action. It is never imputed to zero or
scored Low. In contrast, an explicitly known completeness percentage below 100
is a usable input to the illustrative review-priority rules. Input validity
does not prove that an otherwise complete record is true or sufficient for
clinical judgement.

## Score definitions and explanations

The five shared pre-review features are:

| Feature | Definition |
|---|---|
| Activity change per WTE | Absolute difference between current total/current WTE and previous total/previous WTE |
| Direct-care mix change | Absolute difference in current/previous direct-care shares, in percentage points |
| Workflow-stage age | Snapshot date minus current stage start, in days |
| Overdue days | Maximum of zero and snapshot minus illustrative review due date |
| Incompleteness | 100 minus known completeness percentage |

**Rules baseline:** each feature adds `weight * min(feature / cap, 1)`.
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
pattern, workflow-stage label, target or outcome-observation date. There is no
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

The dashboard compares baseline, ML and oldest-first on the **same sufficient
holdout cohort** at a fixed user-selected budget K (default 30). Benchmark
results do not change with queue filters or scenario edits. Actual reviewed
count is `min(K, eligible cohort size)`. Amendments found is the positive count
among those reviews; precision is found/reviewed; recall is found/all positives
in the eligible cohort. A zero-positive cohort makes recall unavailable, and
an empty cohort also makes precision unavailable. Undefined values are shown
as empty/None, never replaced by zero. Missing outcomes are errors, not negatives.
The excluded insufficient-data count is displayed; their exclusion is an
evaluation convention, not clinical permission to ignore those plans.

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
| Rules baseline | 30 | 8 | 26.67% | 32.00% |
| Experimental ML | 30 | 6 | 20.00% | 24.00% |
| Oldest-first | 30 | 7 | 23.33% | 28.00% |

**ML did not win this holdout.** These are actual synthetic results, not a
promise, a policy recommendation or evidence that any method is useful on real
JobPlans. The run used Python 3.14.0, NumPy 2.5.3, pandas 2.3.3,
scikit-learn 1.9.1 and Streamlit 1.65.0. The live dashboard recomputes the
comparison for its selected budget.

## Architecture

```text
synthetic.py -> fictional pre-review records and stochastic outcome labels
features.py -> explicit validation and five shared pre-review features
scoring.py  -> rules / training-only linear model / signed terms / isolated scenarios
evaluation.py -> purged temporal split, scored queues, deterministic ranks, top-K metrics
dashboard.py -> in-memory Streamlit filters, detail, scenario and benchmark
app.py -> Streamlit entry point
tests/ -> reproducibility, bounds, missingness, leakage, contributions, metrics and UI
```

There is no database, trained-model file, persisted synthetic dataset or hidden
API. `.venv`, caches, local secrets and build artefacts are excluded from Git.

## Before any real-world research

A governed follow-on would first need an agreed review purpose and field
definitions, information governance and consent/legal basis, representative
pre-review data, an independently specified amendment outcome, clinician-led
assessment of legitimate variation, subgroup/error analysis, temporal external
validation, capacity-aware evaluation and prospective human oversight. Historic
amendments may reflect reviewer habits or service constraints rather than need.
Do not connect this POC to production or treat the synthetic thresholds as policy.
