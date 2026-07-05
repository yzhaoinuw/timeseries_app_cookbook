# Project Overview

This document orients a new agent (or human collaborator) to the codebase. Keep
it current — when the active code path changes, update the relevant sections.

## What This Repo Is

**Time Series App Cookbook** is a domain-neutral, runnable *template* for building
interactive Dash + Plotly desktop apps that navigate, inspect, and annotate long
time series (millions of points per channel) smoothly. It is distilled from a
production biomedical scoring app ([Sleep Scoring App](https://github.com/yzhaoinuw/sleep_scoring))
with every domain-specific detail removed; the synthetic signals here exist only
to demonstrate the reusable interaction techniques.

Two deliverables live side by side:

1. A **runnable app** (`run_desktop_app.py` + `ts_app/`) — a pywebview desktop
   window wrapping a Dash/Flask server, with a `plotly-resampler`-backed figure
   and a browser-side interaction layer (custom pointer pan, drag-select with
   auto-pan, keypress annotation, undo).
2. A **cookbook** (`COOKBOOK.md`) — 16 numbered recipes mapping each feature to
   its file, with the design rationale and adaptation notes.

Primary stack: Python 3.11, Dash 3, Plotly 6, `plotly-resampler` 0.11,
`dash-extensions`, `pywebview`, NumPy/pandas.

## Active Runtime Path

### 1. Entrypoint

[`run_desktop_app.py`](run_desktop_app.py)

- Starts the Dash/Flask server on `127.0.0.1:PORT` in a daemon thread.
- Opens a native pywebview window pointed at that URL (which also provides the OS
  file dialogs). `--smoke` does an import/version check with no window.

### 2. Dash app

[`ts_app/app.py`](ts_app/app.py)

- Builds the app, the filesystem cache, and the `FIG_RESAMPLER` global.
- Clientside callbacks (inline JS) for instant interactions: mode switch, keyboard
  pan, selection reading, keypress annotation, overlay repaint, direct restyle.
- Server callbacks for load/demo, sampling level, undo, and save.
- Raw Flask routes `/_ts_app/resample` (live auto-pan refresh) and
  `/_ts_app/profile-log`.

### 3. Component / layout layer

[`ts_app/components.py`](ts_app/components.py)

- `home_div` (load buttons) → swapped for `visualization_div` after load.
- `backend_div`: hidden `dcc.Store` state slots + `EventListener` bridges that turn
  custom DOM events (`tsgraphrelayout`, `tsannotationselect`, `tsboutcontextmenu`,
  `keyboard`) into callback inputs.

### 4. Figure builder

[`ts_app/figure.py`](ts_app/figure.py)

- One `FigureResampler` row per channel, all forced onto one shared x-axis.
- Annotation heatmap overlay on each row.
- Publishes `sharedXAxisKey`, `overlayTraceIndices`, `xBounds`, `numClass`,
  `frameRate` into `figure.layout.meta` so the asset JS stays channel-count-agnostic.

### 5. Data + labels

- [`ts_app/data.py`](ts_app/data.py): the recording contract, the synthetic
  generator, and the pluggable `load_recording` / `save_recording` (.npz).
- [`ts_app/labels.py`](ts_app/labels.py): label padding, contiguous-segment
  extraction, sentinel conversion, export.
- [`ts_app/dialogs.py`](ts_app/dialogs.py): native Open/Save with cross-platform
  return normalization.

### 6. Browser interaction layer

[`ts_app/assets/`](ts_app/assets/) (auto-loaded by Dash, in filename order)

- `graphRelayoutCoalescer.js` — debounces zoom/pan into one `tsgraphrelayout` event.
- `graphDirectRestyle.js` — applies resampler patches via `Plotly.restyle`.
- `graphCustomPointerPan.js` — custom x+y drag pan.
- `annotationAutoPan.js` — drag-select with edge auto-pan and live trace refresh.
- `graphContextMenu.js` — right-click segment selection.
- `closeWindow.js` — unsaved-work exit guard.

## Repo Structure Map

```text
timeseries_app_cookbook/
|- AGENTS.md                 # agent startup guide (treaty)
|- project_overview.md       # this file
|- next_steps.md             # unfinished work / active threads
|- work_log.md               # session history
|- work_log_archive/         # rotated older sessions
|- README.md                 # user quickstart
|- COOKBOOK.md               # the 16-recipe design guide
|- LICENSE                   # MIT
|- requirements.txt
|- run_desktop_app.py        # desktop entrypoint
|- ts_app/
|  |- __init__.py            # VERSION
|  |- config.py              # window, classes, colors, flags, tunables
|  |- app.py                 # Dash app: callbacks, Flask routes, cache
|  |- components.py          # layout, stores, EventListeners
|  |- figure.py              # resampler figure + overlay
|  |- data.py                # recording contract, synthetic gen, loader
|  |- labels.py              # label helpers + export
|  |- dialogs.py             # native file dialogs
|  |- assets/*.js            # browser interaction layer
|- tests/
|  |- test_smoke.py          # data/figure/label/route smoke tests
```

## What Looks Active vs. Legacy

Everything in the tree is active — this is a fresh, single-path template with no
parallel or legacy implementations. When editing, the only "don't touch blindly"
note is that `ts_app/app.py` (Python) and `ts_app/assets/*.js` (browser) share a
contract via `figure.layout.meta` and the `dcc.Store` ids; change them together.

## Tests And Fixtures

- [`tests/test_smoke.py`](tests/test_smoke.py) — covers the data contract, figure
  build + `meta` wiring, the resampler patch path, `.npz` round-trip, and label
  helpers. Run with `python -m pytest -q` (8 tests).
- Fixtures are generated, not stored: `generate_synthetic_recording()` in
  `ts_app/data.py` is the canonical sample data. No data files are committed.
- The browser JS interaction layer is not unit-tested; verify it by running the
  app or by driving the Flask routes with `app.server.test_client()`.

## User Data Expectations

The app consumes one dict, the **recording contract** (top of `ts_app/data.py`):

- `channels`: list of `{name: str, values: 1-D np.ndarray, sample_rate: float}`
- `labels`: optional 1-D int array (one class per frame; `-1` unscored) or `None`
- `frame_rate`: label frames per second (e.g. `1.0`)
- `start_time`: x-axis origin in seconds

To use real data, implement `load_recording(path)` to return this dict; nothing
else cares about the source format.

## Practical Mental Model

Read in this order:

1. [`README.md`](README.md)
2. [`COOKBOOK.md`](COOKBOOK.md) — "The one big idea" and the Recipe Index
3. [`run_desktop_app.py`](run_desktop_app.py)
4. [`ts_app/app.py`](ts_app/app.py)
5. [`ts_app/figure.py`](ts_app/figure.py) and [`ts_app/components.py`](ts_app/components.py)
6. [`ts_app/assets/`](ts_app/assets/) for the browser interaction layer

## Questions Worth Clarifying Later

- Whether to add a browser-only variant (drop pywebview, use `dcc.Upload`) as a
  documented alternative deployment.
- Whether to add CI (pytest on push) once the repo has collaborators.
- Whether the template should ship a second, real-format `load_recording` example
  (e.g. CSV or EDF) beyond the `.npz` reference.
