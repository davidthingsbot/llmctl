# Ten additional vision candidates

These are **uncalibrated candidates** for a blind local GLM versus frontier comparison. The `hard` label describes the intended difficulty, not a measured result. No model was queried, no service was run, and no discrimination claim is supported yet.

The generator is independent of `vision_hard_fixtures.py` and does not import or modify it. The only delivered paths are `vision_extra_fixtures.py`, `test_vision_extra_fixtures.py`, this document, and `fixtures/vision-candidates-extra10/`.

## Assets and contract

- [Manifest](fixtures/vision-candidates-extra10/manifest.json): exactly ten tasks, version `synthetic-vision-candidates-extra10-v1`.
- [Contact sheet](fixtures/vision-candidates-extra10/contact-sheet.png): thumbnail overview, not an evaluation input.
- Ten individual PNGs named after the IDs below. These are the evaluation inputs.
- Each task has `id`, `difficulty: "hard"`, an absolute `image` path, `question`, and an `expected` dictionary, compatible with the existing `vision_suite.py` runner.
- Thirty total exact field checks use the existing `vision_suite.grade` function, with no custom grading or answer normalization. Lists have prescribed order; bit strings, cell references, wire codes, and site names have prescribed spelling. Numeric outputs are JSON integers.
- All inputs, constraints, units, ordering conventions, and boundary rules are in the individual images. Text questions only identify the requested operation and JSON output fields. Expected dictionaries are local grading data, never image or question content.
- Full task images range from 1400×1100 to 1500×1200 and 1400×1400. All are within 1600×1400. Source text uses fonts of at least 18 px, with bounds checked during rendering. The 1600×1400 contact sheet necessarily reduces source text; use the individual PNGs for reading or evaluation.

| ID | Visual reasoning | Independent validation |
| --- | --- | --- |
| `extra01_rotated_dimensions` | Bind rotated dimension arrows to two hole centers and local axes | Coordinate subtraction, squared distance, rigid-rotation distance preservation |
| `extra02_scaled_plate_holes` | Recover an L-shaped region and two holes from a scaled grid | Enumerate occupied cells and exposed edges independently of polygon area/perimeter formulas |
| `extra03_closed_road_route` | Plan a route with closures, positive costs, and a mandatory stop | Exhaustively enumerate simple routes and prove the optimum is unique; verify road counts and grid geometry |
| `extra04_permuted_stack_legend` | Decode a shared color/symbol legend despite changing stack order | Recompute category totals, unique winning site, and four segments per site |
| `extra05_formula_cell_binding` | Follow pictured formulas, ranges, absolute references, and arithmetic dependencies | Explicit arithmetic oracle plus a separate parser of the rendered formula strings |
| `extra06_failed_directed_links` | Follow arrow directions and remove failed links | Independent reachability expansion, shortest hop distance, and link count |
| `extra07_clock_edge_binding` | Bind reset, enable, and data values to marked clock edges | Independent interval-based simulation, including coincident transitions and initial state |
| `extra08_connector_view_reflection` | Reflect front pin locations into a keyed rear view | Verify the front/rear bijection and unique wire-code count |
| `extra09_footnote_exclusions` | Combine row status, category footnotes, exclusions, percentages, and caps | Independent eligibility filtering and reimbursement arithmetic |
| `extra10_sequential_token_tracking` | Track identical tokens through four panels by joint movement constraints | Enumerate every assignment between frames; prove uniqueness despite multiple local options; verify counts and bounds |

Roads have no crossings away from circular junctions. Network links use explicit arrowheads and have no crossings. The connector views explicitly keep the key at the top and identify viewing sides. Waveform rules explicitly specify synchronous reset priority and post-transition sampling at coincident edges. Geometric lengths distinguish grid squares from centimeters and count hole boundaries. Tracking cells use uppercase column letters and row digits.

## Rebuild and test

From the repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --no-project --with pillow python evals/test_vision_extra_fixtures.py
PYTHONDONTWRITEBYTECODE=1 uv run --no-project --with pillow python evals/vision_extra_fixtures.py
```

This shell required `/home/david/.hermes/bin` on `PATH` to locate the already-installed `uv`. The renderer uses `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf`. Tests create and clean a temporary subdirectory inside the assigned fixture directory. Rebuilds overwrite only these generated assets, and refresh the absolute paths after moving the repository. PNG byte determinism is checked for repeated builds in the same environment; cross-version Pillow/font byte identity is not assumed.

The runner can consume the existing manifest without invoking either fixture generator. During later authorized calibration, send only each task's `question` and individual `image`; keep `expected` private to grading. Use identical settings and inputs for both models and compare per-field and per-task results before selecting candidates. No calibration was performed during this task.

## Test-first evidence

The tests were written before the generator. The first required test command exited 1 with:

```text
ModuleNotFoundError: No module named 'vision_extra_fixtures'
```

The first complete implementation produced a meaningful red result:

```text
FAIL: test_map_unique_optimum_by_exhaustive_simple_paths
AssertionError: 23 not less than 23
Ran 14 tests in 1.095s
FAILED (failures=1)
```

Two routes tied. Increasing the pictured G–K road cost from 4 to 5 made the optimum unique; the unchanged exhaustive uniqueness assertion then passed:

```text
Ran 14 tests in 1.103s
OK
```

A fifteenth test was subsequently added to evaluate the actual displayed spreadsheet formulas independently, guarding against formula-text drift. The final required test command exited 0:

```text
Ran 15 tests in 1.100s
OK
```

All ten full-resolution images and the contact sheet were visually inspected. Final asset inventory: ten task PNGs, one contact-sheet PNG, and one manifest with ten tasks and thirty graded fields. No temporary tooling or test directories remain.
