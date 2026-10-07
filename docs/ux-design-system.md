# Review experience and design system

**Prioritise attention, not people.** RLDatix-inspired colour direction only:
no logos, proprietary assets or claim that this is an official design.
The accepted direction stays on Streamlit. This is a presentation change,
not a new clinical workflow or model experiment.

## V8 simplification

The [assessment and demo guide](demo-guide.md) supersede the v7 screen hierarchy
below, not its theme or accessibility safeguards. V8 opens on three existing
fictional examples. Cards retain only identity/service, one category, one reason
and Review JobPlan. Detail shows the comparison immediately, then human options.
Source information and rule evidence are optional; model evidence and what-if
live in Experiment results. Native minimal toolbar configuration reduces developer
chrome; it is not a production authentication or permission boundary.

## V7 baseline: assessment and accepted direction

V6 made exact evidence available, but five competing tabs, adjacent dense
tables and visible indices asked reviewers to interpret the experiment before
understanding a plan. Missing-data percentage could be mistaken for confidence.
The new design leads with the reason, separates data clarification, makes
detail a deliberate action and moves experimentation out of the reviewer rail.

| Screen / user goal | Before: friction | After: hierarchy, trust and accessibility |
|---|---|---|
| Queue: where might I look first? | Numeric indices and horizontally dense rows; separate Overview | Three count/filter buttons, reason-first native cards, simple order choice; no row indices or rule IDs |
| Detail: what changed? | Competing queue/detail columns and lengthy technical evidence | Focused plan identity, plain reason, observed differences, changed comparison rows and human options; Back to queue |
| Explanation: can I verify the reason? | Technical trace alongside model terms | Native dialog: plain reason, exact rule disclosures, separate experimental model panel; numeric model details opt-in |
| Clarification: what is missing? | Unscored label and recorded percentage | Amber icon + words, actual validator findings, grouped information count; no low/safe inference or sent request |
| Evaluation: is ML useful here? | Reviewer controls mixed with experiment controls | Rules vs ML with fixed-budget common-cohort evidence, overlap, disagreement, small service workload and original-plan exports |
| Product: what is this initiative? | Fifth tab mixed with day-to-day review | About this POC, actual fixed default benchmark, hypotheses and explicit proposed decision gates |

Principles: lower cognitive load; faithful rather than persuasive explanations;
neutral language; progressive disclosure; human ownership; native keyboard
controls; colour-independent states; reproducible, scoped information.
The redesign is implemented, not merely a proposal. User testing is still needed.

## Information architecture

```text
JobPlan review
  Review queue (default)
    Three fictional plans, one compact count summary
    Review JobPlan
      One reason -> What changed? -> What would you do next?
      See details -> source information / exact rule evidence dialog
  Experiment results
    Simple rules/ML/oldest-first result
    Evidence / budget / overlap / disagreements / model behaviour
    Demo settings / full collections / filters / analysis order
    Plan inspection / model dialog / isolated what-if
    Service workload / original-plan analysis export
  About the POC
    Short story / optional demo script / research notes
```

Native radio navigation is deliberately small and requires no routing framework.
No Overview, My Reviews or separate detail navigation item. The footer exposes
**Build: clinical-workspace-v8**. Navigation may collapse on small screens.
No live workflow, approval, message-sending, authorisation boundary or saved
review action is implied.

## Tokens and measured contrast

`theme.py` is the Python token catalogue and the **only** static style block.
`.streamlit/config.toml` applies the corresponding native theme tokens.
Tests check representative token correspondence and compute sRGB contrast,
not a visual guess. Ratios below use the actual token values.

| Token | Value | Intended use |
|---|---|---|
| brand-deep | `#0B3B3C` | Navigation background |
| brand-primary / brand-hover | `#1B7F5A` / `#14694A` | Selected actions and focus / hover |
| mint | `#E8F4EF` | Hover and selected navigation |
| surface / canvas | `#FFFFFF` / `#F6F8F7` | Cards / page |
| text / text-secondary | `#14292B` / `#44595B` | Body / secondary text |
| text-muted | `#5F7173` | Captions only, at full opacity |
| border / border-control | `#D3DEDB` / `#6F8582` | Decorative / essential controls |
| attention-bg / text / icon | `#FFF4DB` / `#6B4700` / `#8A5300` | Review sooner / data clarification |
| info-bg / text | `#E8F0F8` / `#1D4E89` | Supporting information |
| error-bg / text | `#FDECEA` / `#A4262C` | Actual system/validation errors only |

| Pair | Contrast |
|---|---:|
| White on deep teal | 12.32:1 |
| White on primary / hover | 4.96:1 / 6.67:1 |
| Body / secondary on white | 15.20:1 / 7.43:1 |
| Muted on white / canvas | 5.13:1 / 4.81:1 |
| Attention text / icon on attention background | 7.61:1 / 5.79:1 |
| Information text on information background | 7.29:1 |
| Error text on error background | 6.35:1 |
| Control border on white | 3.92:1 |
| Primary focus on canvas | 4.65:1 |
| Body on selected mint | 13.47:1 |

Text checks target at least 4.5:1 and essential control/icon checks 3:1.
Decorative borders are not the sole indicator of a control.
Green denotes brand/selection, **not priority**. Review sooner and clarification
use amber icons/text; standard uses neutral icon/text. Red is not a priority band.
Native Streamlit captions have an additional 0.6 opacity: the style block
explicitly removes that opacity so the measured token contrast survives rendering.

Typography: page title 24px/600; sections 18px/600; body base 14px; metadata
13px. Native widgets may use their own smaller label styles. Eight-pixel spacing
increments, 8px corner radius, 1px borders, no added shadow (native dialog excepted).
Native action buttons target 40px minimum height; inputs and navigation rows
target 44px. Compact cards wrap rather than use fixed row heights.
Focus is a 3px primary outline with 2px offset on the light canvas. The dark
rail uses a white outline: primary green alone would not have sufficient
contrast against deep teal. Selected navigation also has a 3px primary left bar.

## Component implementation and future mapping

These React names are a future mapping, **not implemented React components**.

| Component | Streamlit implementation |
|---|---|
| AppShell / Sidebar | `set_page_config`, `sidebar`, three-option `radio`, footer marker |
| PageHeader | Native title and concise notice; detail has Back to queue |
| PriorityBadge / DataQualityBadge | `badge` with text + Material icon; amber/neutral, no numeric score |
| ReviewQueueTable | Three native cards by default; full collections paginate eight items per section |
| ChangeSummary | Immediate changed rows and working pattern; detailed source-derived bullets disclosed |
| PlanComparison | Changed numeric rows in a native table; unchanged measures and activity records disclosed |
| ReasonPanel | Plain source-faithful reason, not the old points-formatted main-driver label |
| RuleDetails | One native expander per exact versioned trace, including JSON inputs/threshold/state |
| ModelDetails | Experiment-only dialog and Why the model highlighted this disclosure; exact index, signed terms and reference |
| ReviewerActions | Unselected native radio options, no submission or saved decision |

The primary reason names actual DCC/SPA differences and working-pattern change
when present; otherwise it uses the two largest non-zero rule terms. Exact rule
details retain the trace-based reason. Neither is a causal explanation or a
judgement about appropriateness. No severity is invented; withheld calculations
are not treated as zero. Notable changes use validated source totals
and stable activity matching; session-set differences do not invent a specific
activity move. Missing previous snapshot dates are explicitly unavailable.

The category mapping is display-only: High -> Review sooner; Medium + Low ->
Standard review; insufficient data -> Data clarification. Thresholds,
raw indices, legacy actions and export category fields are unchanged. "Review
sooner" is an illustrative label, not independently validated earlier-review need.
The target remains **synthetic amendment after review**.

Relative model wording compares each eligible index with all other eligible
indices in the filtered view, not the displayed page. "Higher/lower than most"
requires a strict majority. Ties and singleton views are explicit. This is not
confidence, calibration, probability or a causal explanation.

The information count uses seven grouped requirements from existing validators,
not a count of every field: subject link, previous version/activities, current
version/activities, snapshot date, workflow timing, due date, known completeness.
All applicable checks for a group must pass. An unknown validation finding
makes the count unavailable rather than silently treating it as complete.

## Scope and isolation

Search/service/pattern/stage scope precedes category filtering. The compact count
summary describes the displayed review view; selected categories restrict scored cards.
Matching clarification records stay visible and remain in exports. Pagination
affects display only. Reset clears filters/search/order and detail, not the
collection, experiment budget, records or fitting. Reset presentation demo also
restores the three-example collection; switching collection resets its filters.
Hidden native widget keys are
retained across navigation to prevent exports silently losing the selected scope.

Experiment results keeps the unchanged five-method evaluator and default results.
Overlap/disagreement replaces any proposed opaque "combined" ranking.
Largest mean absolute model terms describe this fitted model on the full
eligible holdout, not causal importance. Workload uses the filtered original
collection; benchmark uses the full eligible holdout regardless of filters or
demonstration selection. What-if never enters either, or the unchanged schema-2 exports.

## Styling boundaries and fallback

The style block contains constants only. Dynamic plan text uses native text,
tables/JSON or escaped Markdown; no plan/search string is interpolated into CSS
or unsafe HTML. There is no application JavaScript. Styles use a small set of
Streamlit test IDs, native input hooks and the explicit plan-card key prefix.
These are implementation hooks, **not a guaranteed public DOM contract**.
Recheck after any Streamlit upgrade. If a hook changes, the native radio, buttons,
cards, labels, dialogs and tables still function; visual/contrast checks must
be repeated before accepting a changed runtime. The native configuration is
the main theme; CSS supplies density, full-opacity captions, 14px comparison
cells with opaque text, focus treatment and narrow-header clearance.

## Accessibility verification and limits

- Automated: contrast calculations, category/text state mapping, faithful reasons,
  explicit missing findings, unknown-count fallback, escaping/static-only HTML,
  native interaction state, dialog layers, isolation and evaluator regressions.
- V7 browser baseline: representative desktop (1440px), tablet-sized (1024px) and
  narrow (390px) queue, detail, dialog, clarification, Rules vs ML and About
  renders inspected, plus scrolled comparison/clarification content. No page-level
  horizontal overflow in these checks; technical dataframes scroll within their
  native container. Measured search/order controls at 44px, View JobPlan at
  40px, and caption opacity at 1. A keyboard-focused plan button showed a 3px
  primary outline; native Enter activation opened detail in the test browser.
  The dark navigation focus outline was also visible. This is a representative
  keyboard interaction, not a complete manual traversal.
- Still required: a complete manual keyboard traversal, screen-reader names and
  announcements, modal focus return/trapping with assistive technology, zoom/
  reflow testing at user settings, high-contrast/forced-colour testing and
  clinician usability research. Native toolbar/help icons and interactive
  dataframe behaviour need explicit target-size/keyboard assessment.

The queue uses keyboard-operable buttons, labelled inputs and icon + text states.
Native comparison tables provide a text alternative; the experiment is a table,
not a chart-only presentation. Wide technical evidence tables retain native
horizontal scrolling; compact reviewer cards do not hide text in fixed columns.
AppTest and screenshots are **not an accessibility audit or full WCAG conformance**.
The separate walkthrough protocol remains **unexecuted**.

The final v7 regression run passed **99 tests** with warnings treated as errors.
Generation, validation, scoring, rules, model, evaluation and schema-2 export
engine files were also checked unchanged against v6. No dependencies were added.

V8 regression: **100 tests** with warnings treated as errors. The three-plan
queue, immediate comparison/judgement, missing-plan detail, Experiment and About
were checked at desktop/tablet/narrow sizes as applicable. Native review buttons
measured 40px and a keyboard-focused button showed the 3px outline. Minimal
toolbar configuration removed the Deploy control. Narrow header overlap and
translucent native table labels found during inspection were corrected.
These checks do not establish the two-minute understanding goal.

## Final visual direction

A restrained deep-teal rail frames light neutral content. The queue leads with
plain reasons and a clear clarification route, not mysterious scores. A focused
plan page makes observed changes readable; exact rule and model evidence is
available deliberately, without blending it. Product can inspect the synthetic
experiment separately. Every screen keeps judgement with the authorised human.
