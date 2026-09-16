# Synthetic vision v2

These six hard tasks are **candidate discriminators, not proven frontier wins**.
The previous v1 hard tasks all passed GLM. Model comparisons will be performed
separately in fresh blind contexts; no models were called to build this dataset.

`fixtures/vision-v2/manifest.json` contains exactly 12 tasks: the original three
easy and three medium entries (referencing the existing v1 images), followed by
six new hard entries. The old hard tier is replaced, not appended.
`hard-manifest.json` contains only the six new hard entries.

| Hard task ID suffix | Visual reasoning and ground truth |
| --- | --- |
| `reconciliation` | Apply eight ordered amendments to six original rows; reconcile gross units, absolute rejects, release status, and integer-cent values. Independent arithmetic checks. |
| `crossing_plot` | Track three crossing series, filter intervals, rank endpoint gaps, interpolate a crossing, and integrate the third series. Exact rational arithmetic. |
| `logic_network` | Trace junction dots versus unconnected crossings through five gates; enumerate a truth table and evaluate a forced-input fault. Geometry-derived netlist, all 16 inputs checked against a reduced Boolean oracle. |
| `cube` | Fold a labeled net, reject impossible and reflected candidates, then execute three rolls. Folded face normals establish chirality and one valid choice; independent face permutations check the rolls. |
| `resources` | Combine room eligibility, technician setup/finish availability, and a shared scanner's middle phase. Exhaustive enumeration and an independent minute-occupancy oracle establish the unique earliest completion. |
| `cross_reference` | Follow shape-marked active arrows, join exact unit/lot/status and probe/revision keys, calibrate a reading, then select a dispatch band. Archived routes and near-matching rows are distractors; every lookup is unique. |

Each task retains the existing contract: `id`, `difficulty`, absolute `image`
path, `question`, and an `expected` object. Answers use exact integers, strings,
and ordered string lists with the unchanged field-level typed JSON grader.
All numerical inputs, rules, legends, units, and ordering conventions appear in
the image; prompts supply only the task and answer schema. Expected answers stay
in the manifests and are never rendered into images or included in prompts.

Original task PNGs fit within 1600×1400 and use text of at least 18px, normally
22px or larger. The contact sheet is a human QA overview of the six hard tasks;
use the original PNGs to judge readability and for evaluation. All six originals
and the contact sheet were visually inspected. PNGs contain no metadata.

From the repository root, with DejaVu Sans available at the generator's `FONT` path:

```sh
uv run --no-project --with pillow python evals/vision_hard_fixtures.py
PYTHONPATH=evals uv run --no-project --with pillow python -m unittest test_vision_hard_fixtures test_vision_suite.GradingTests test_vision_suite.FixtureTests -v
```

The tests were written and run before the generator existed (initial import
failure), then made green. They guard known answers, uniqueness, arithmetic,
topology mutations, tier counts, IDs, dimensions, font sizes, deterministic
rendering, generated artifacts, typed grading, and preservation of v1 files.
The selected regression tests are offline; they do not start the HTTP test server.

Regenerate after moving the checkout to refresh absolute image paths. The builder
requires an existing v1 manifest and images; it never regenerates v1. Use the
manifest's version for dataset identity: the unchanged runner still emits its
legacy `synthetic-vision-v1` top-level result label.
