# Project Overview

Agent/collaborator onboarding map. This repo's [`README.md`](README.md) **is** the
cookbook — it carries the full description, the architecture, the per-feature
recipes, the file map, the data contract, and the adaptation guide. This file only
adds the agent-coordination context the README doesn't cover, and points into the
README for the rest, so the two don't repeat each other.

Stack in one line: Python 3.11 / Dash 3 / Plotly 6 / `plotly-resampler` /
`pywebview`; entry point [`run_desktop_app.py`](run_desktop_app.py).

## Start in the README

- **What this repo is / how to run it** → [What you get](README.md#what-you-get) and [Quickstart](README.md#quickstart)
- **Architecture (the browser/server split + layer diagram)** → [The one big idea](README.md#the-one-big-idea)
- **How each feature works** → the [Recipe Index](README.md#recipe-index) and its recipes
- **Where each thing lives (file map)** → [Source-file map](README.md#source-file-map)
- **Data contract (what the app consumes)** → [Plugging in your own data](README.md#plugging-in-your-own-data)
- **How to adapt to a new domain** → [Adaptation checklist](README.md#adaptation-checklist)

## What Looks Active vs. Legacy

Everything in the tree is active — a fresh, single-path template with no parallel
or legacy implementations. The one coupling to respect when editing: `ts_app/app.py`
(Python) and `ts_app/assets/*.js` (browser) share a contract via
`figure.layout.meta` (`sharedXAxisKey`, `overlayTraceIndices`, `xBounds`,
`numClass`, `frameRate`) and the `dcc.Store` ids — change them together, never one
side alone.

## Tests And Fixtures

- [`tests/test_smoke.py`](tests/test_smoke.py) — covers the data contract, figure
  build + `meta` wiring, the resampler patch path, `.npz` round-trip, and label
  helpers. Run with `python -m pytest -q` (8 tests).
- Fixtures are generated, not stored: `generate_synthetic_recording()` in
  `ts_app/data.py` is the canonical sample data. No data files are committed.
- The browser JS interaction layer is **not** unit-tested. Verify it by running
  the app, or by driving the Flask routes with `app.server.test_client()` (the
  `work_log.md` entry for 2026-07-05 has a worked example).

## Questions Worth Clarifying Later

Tracked as optional, not-started threads in [`next_steps.md`](next_steps.md):

- Whether to add a browser-only deployment variant (drop pywebview, use `dcc.Upload`).
- Whether to ship a second, real-format `load_recording` example beyond the `.npz` reference.
- Whether to add CI (pytest on push) and a browser-side interaction test once the repo has collaborators.
