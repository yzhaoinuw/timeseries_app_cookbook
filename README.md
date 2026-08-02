# Time Series App Cookbook

[![Agent Collab Treaty](https://raw.githubusercontent.com/yzhaoinuw/agent_collab_treaty/main/assets/treaty-adopted.svg)](https://github.com/yzhaoinuw/agent_collab_treaty)

A **domain-neutral, runnable template** for building interactive Dash + Plotly
desktop apps that navigate, inspect, and annotate **long time series** smoothly —
even at millions of points — using [`plotly-resampler`](https://github.com/predict-idlab/plotly-resampler).

It is distilled from a production biomedical scoring app, with every
domain-specific detail stripped out. The signals here are synthetic; the
*techniques* — resampler-backed navigation, drag-to-select with auto-pan,
keypress annotation, undo — are the point. Swap in your own data (one function)
and label set (one config file) and you have your own app.

This README is both the quickstart and the full cookbook: run it now from
[Quickstart](#quickstart), then read the [recipes](#recipe-index) for how each
feature works and how to adapt it. It is written for two readers — **agents**
adapting the app (pull only the recipes a task needs) and **human designers** who
want the *why* (nearly every non-obvious choice here fights one enemy: latency on
large signals).

## Contents

- [What you get](#what-you-get)
- [Quickstart](#quickstart)
- [Plugging in your own data](#plugging-in-your-own-data)
- [The one big idea](#the-one-big-idea) · [How to read a recipe](#how-to-read-a-recipe) · [Recipe Index](#recipe-index)
- Recipes — [Skeleton](#skeleton) (1–5) · [The bridge](#the-bridge) (6) · [Navigation](#navigation) (7–10) · [Annotation](#annotation) (11–16) · [Multi-session](#multi-session) (17)
- [Cross-cutting patterns](#cross-cutting-patterns) · [Adaptation checklist](#adaptation-checklist) · [Gotcha catalog](#gotcha-catalog) · [Source-file map](#source-file-map)
- [Real-world example](#real-world-example) · [Citation](#citation) · [Provenance & license](#provenance--license)

## What you get

- **Fast navigation on huge signals** — zoom/scroll/drag-pan and arrow-key
  stepping stay smooth because the browser only ever holds a few thousand points
  per trace; the server resamples the visible slice on demand.
- **Custom pointer pan** in both x and the hovered channel's y.
- **Annotation** — switch to select mode (`m`), then **drag**, **click**, or
  **right-click a segment** to select a region and press a number key to label
  it. The overlay updates instantly.
- **Drag-to-select with auto-pan** — drag past the edge and the view scrolls,
  fetching and drawing the newly revealed signal live, so you can select regions
  wider than the screen.
- **Undo** (one step) and **crash recovery** (reopen the same file to salvage
  unsaved labels).
- **Native Open/Save dialogs** and CSV segment export.
- **Multiple independent windows** — launch the app again for a second (or third)
  window, each in its own process with its own state; a file already open in one
  window is refused in another.

## Quickstart

```bash
# 1. Install (a virtualenv or conda env is recommended)
pip install -r requirements.txt

# 2. Run the desktop app, then click "Load demo data"
python run_desktop_app.py

# 3. Sanity checks
python run_desktop_app.py --smoke     # import + version, no window
python -m pytest -q                   # the smoke test suite
```

The demo generates 3 synthetic channels (~1 hour at 256 Hz ≈ 2.7M samples) with
a pre-filled label overlay, so there's something to navigate and re-label
immediately. No data files required.

**Keys:** `m` toggle navigate/annotate · `←`/`→` step the view · `1`–`4` label the
current selection.

## Plugging in your own data

Everything the app understands is the *recording* dict (documented in
[`ts_app/data.py`](ts_app/data.py)):

```python
recording = {
    "channels": [
        {"name": str, "values": np.ndarray, "sample_rate": float},
        ...
    ],
    "labels": np.ndarray | None,   # one int class per label frame, or None
    "frame_rate": float,           # label frames per second (e.g. 1.0)
    "start_time": float,           # x-axis origin in seconds
}
```

To use real data, replace **one function** — `load_recording(path)` in
`ts_app/data.py` — so it parses your format (EDF, WAV, Parquet, CSV, a database
query, …) and returns that dict. Nothing else in the app cares where the numbers
came from. Then adjust your label set and colors in
[`ts_app/config.py`](ts_app/config.py). The [Adaptation checklist](#adaptation-checklist)
walks the full path.

---

## The Cookbook

The rest of this document is the design rationale and a per-feature recipe book.
Every recipe points at the exact file in this repo; nothing depends on where your
signals come from or what they represent.

## The one big idea

> **Browser-authoritative interaction, server-authoritative data.**

Everything that must feel *instant* — mode switch, selection box, keypress label,
panning the view — happens **in the browser**, either as a Dash *clientside
callback* (JavaScript written inline in Python) or as a standalone *asset script*
under `ts_app/assets/`. The Python server is hit only when real data work is
unavoidable: loading a file, resampling the visible slice, saving.

This split is why the app stays responsive on multi-hour recordings. Keep it. If
you round-trip to the server for a hover, a keypress, or a drag frame, you are on
the slow path.

```
┌─────────────────────────────────────────────────────────────────┐
│  pywebview native window  (run_desktop_app.py)                    │  desktop shell
│   └─ embeds a local URL, owns native OS file dialogs              │
├─────────────────────────────────────────────────────────────────┤
│  Dash app + Flask server  (ts_app/app.py)                         │  server
│   ├─ layout & components   (components.py)                        │
│   ├─ figure builder        (figure.py)                            │
│   ├─ data contract         (data.py, labels.py)                   │
│   ├─ server-side cache     (flask_caching filesystem)             │
│   ├─ server callbacks      (load, resample-patch, undo, save)     │
│   └─ raw Flask routes      (/resample, /profile-log,              │
│                             /current-file)                        │
├─────────────────────────────────────────────────────────────────┤
│  Browser interaction layer                                        │  browser
│   ├─ clientside callbacks  (inline JS in app.py)                  │
│   ├─ asset scripts         (ts_app/assets/*.js)                   │
│   ├─ hidden dcc.Store state + EventListener bridges               │
│   └─ Plotly figure (FigureResampler-backed)                      │
└─────────────────────────────────────────────────────────────────┘
```

## How to read a recipe

| Field | Meaning |
| --- | --- |
| **Goal** | The user-visible behavior. |
| **Depends on** | Other recipes it needs. |
| **Source** | The file(s) here that implement it. |
| **Mechanism** | How it works. |
| **Adapt** | What to change for your domain. |
| **Gotchas** | The non-obvious traps. |

## Recipe Index

**Skeleton — you almost always want all of these:**

1. [Desktop shell (pywebview + threaded Dash)](#recipe-1--desktop-shell)
2. [Layout & component model](#recipe-2--layout--component-model)
3. [Server-side cache as the state store](#recipe-3--server-side-cache)
4. [Data contract, loading & native dialogs](#recipe-4--data-contract-loading--dialogs)
5. [Building the resampler figure](#recipe-5--building-the-resampler-figure)

**The bridge:**

6. [The EventListener bridge (custom DOM event → Dash callback)](#recipe-6--the-eventlistener-bridge)

**Navigation:**

7. [The relayout coalescer (the navigation backbone)](#recipe-7--the-relayout-coalescer)
8. [Resampler patch pipeline & direct restyle](#recipe-8--resampler-patch-pipeline--direct-restyle)
9. [Keyboard panning](#recipe-9--keyboard-panning)
10. [Custom pointer pan (x+y drag)](#recipe-10--custom-pointer-pan)

**Annotation:**

11. [Mode switching (navigate ↔ annotate)](#recipe-11--mode-switching)
12. [Selection: box, click, and context-menu](#recipe-12--selection)
13. [Drag-to-select with auto-pan + live trace refresh](#recipe-13--drag-to-select-with-auto-pan)
14. [Keypress annotation & the heatmap overlay](#recipe-14--keypress-annotation--overlay)
15. [Undo & crash recovery](#recipe-15--undo--crash-recovery)
16. [Saving & export](#recipe-16--saving--export)

**Multi-session — multiple independent desktop windows:**

17. [Multi-session desktop windows](#recipe-17--multi-session-desktop-windows)

**Reference:** [Cross-cutting patterns](#cross-cutting-patterns) · [Adaptation checklist](#adaptation-checklist) · [Gotcha catalog](#gotcha-catalog) · [Source-file map](#source-file-map)

---

## Skeleton

### Recipe 1 — Desktop shell

**Goal.** Ship as a native desktop window with native Open/Save dialogs.

**Depends on.** Nothing (outermost layer).

**Source.** `run_desktop_app.py` (`BASE_PORT`, `MAX_SESSIONS`), `ts_app/config.py`
(`WINDOW_CONFIG`), `ts_app/assets/closeWindow.js`.

**Mechanism.** The Dash/Flask server runs on `127.0.0.1:<port>` in a **daemon
thread**. The port comes from a **window-slot claim**: the launcher binds the
first free port in `BASE_PORT..BASE_PORT+MAX_SESSIONS-1` and holds the socket
until the server takes the port over, which is what lets several independent
windows coexist (Recipe 17 covers the full contract).
`webview.create_window(...)` opens a native window pointed at that URL.
`webview.windows[0]` is the handle the server later uses to raise native file
dialogs (Recipe 4) — the one thing a plain browser can't do. On Windows the app
forces the EdgeChromium renderer. `closeWindow.js` installs an `onbeforeunload`
guard so an accidental close warns about unsaved labels.

**Why.** A desktop shell buys native file dialogs (real OS paths, no upload size
limits) and a single-window feel while keeping the whole UI in web tech.

**Adapt.** For a browser-only app, drop pywebview, call `app.run(...)` directly,
and replace native dialogs with `dcc.Upload`. Everything else here is unchanged.

**Gotchas.** The daemon thread won't do clean-shutdown work — persist eagerly
(the cache and temp files already do).

---

### Recipe 2 — Layout & component model

**Goal.** A two-phase UI: a minimal **home** screen (load data) replaced by the
full **visualization** screen once data loads — plus the hidden plumbing.

**Source.** `ts_app/components.py`; swapped in by `create_visualization` in `app.py`.

**Mechanism.** `components.py` defines:
1. **`home_div`** — the "Load demo data" / "Open file…" buttons, a message area,
   and `backend_div`.
2. **`backend_div`** — the invisible engine room: a set of **`dcc.Store`**
   state slots (`box-select-store`, `updated-labels-store`, `recording-meta-store`,
   the direct-restyle payload/status stores), the **`EventListener`** bridges
   (Recipe 6), and a one-shot `dcc.Interval` to clear status messages.
3. **`visualization_div`** — the utility bar (sampling-level dropdown, key hints),
   the `dcc.Graph`, the annotation message line, and Save/Undo.

`suppress_callback_exceptions=True` on the app is required because callbacks
reference components that aren't in the initial layout.

**Why.** Splitting *initial* from *dynamic* layout keeps first paint tiny and
defers the heavy figure until there's data. Centralizing hidden state in one
`backend_div` means every callback's wiring lives in one file.

**Adapt.** Keep the home/visualization split. Add a `dcc.Store` for any new piece
of browser-side state you pass between callbacks. Keep the store ids stable —
they're a shared namespace between Python and the asset JS.

**Gotchas.** Components created *by* a callback (not in the initial layout) fire
their own callbacks on creation; `prevent_initial_call` doesn't protect them.
Guard with `if not n_clicks: raise PreventUpdate` (as the button callbacks do).

---

### Recipe 3 — Server-side cache

**Goal.** Per-session state (loaded file, label history, the resampler figure)
that survives across callbacks and even an app restart.

**Source.** `ts_app/app.py` — the `Cache(...)` setup, `initialize_state`, and the
`FIG_RESAMPLER` global with `store_/get_/clear_fig_resampler`.

**Mechanism.** Two tiers, chosen by whether the value is serializable:
1. **`flask_caching` filesystem cache** for JSON-ish state: `filepath`,
   `filename`, and `labels_history` (a `deque(maxlen=2)`; Recipe 15). The `~20-day`
   timeout + filesystem backend is what turns label history into crash recovery.
   The cache dir is namespaced by window slot (`slot_0`, `slot_1`, …; Recipe 17).
   The file *currently open in this process* is tracked separately in
   `_current_filepath` — a persisted cache value is recovery state, not proof
   that a restarted window still has that file open.
2. **A module-global `FIG_RESAMPLER`** for the one thing that can't be cached: the
   live `FigureResampler` object. It holds the full-resolution signal and is read
   on every zoom/pan and every auto-pan fetch, so serializing it per interaction
   would defeat the purpose. It's created in `create_fig` and read via
   `get_fig_resampler()`.

**Why.** Big/hot/singular objects → process global; small serializable session
state → filesystem cache (which also gives you free persistence).

**Adapt.** For multi-file/multi-tab, replace the single global with a dict keyed
by session id and add eviction. This template shows one recording at a time by
design; Recipe 17 scales to multiple *windows* by isolating these globals in
separate processes instead.

**Gotchas.** **`np.nan` becomes `None` when read back from the filesystem cache.**
The code accounts for this (`equal_nan=True` comparisons, `== None` handling in
`labels_for_saving`). Any NaN-bearing array you round-trip needs the same care.

---

### Recipe 4 — Data contract, loading & dialogs

**Goal.** Click → native Open dialog (or "Load demo data") → parse → validate →
render. Same idea for Save.

**Source.** `ts_app/data.py` (the recording contract, `generate_synthetic_recording`,
`load_recording`, `save_recording`), `ts_app/dialogs.py`, and in `app.py`:
`load_demo`, `choose_file`, `create_visualization`, `initialize_state`.

**Mechanism.** The load is a **two-callback handoff** through a store:
1. `load_demo` / `choose_file` (fire on a button) obtain a file path — the demo
   generates + saves a synthetic recording; "Open file…" raises a native dialog
   and refuses a file that is already open in a peer window (Recipe 17) —
   call `initialize_state`, write an ack message, and set `visualization-ready-store`.
2. `create_visualization` (fires on that store) loads via `load_recording`,
   salvages/initializes label history, builds the figure (`create_fig`), assigns
   it to `components.graph.figure`, and returns `visualization_div` to swap the
   screen. It also publishes the minimal numbers the browser needs
   (`recording-meta-store`: `start_time`, `end_time`, `frame_rate`).

The **recording contract** is the domain-neutral interface (top of `data.py`; see
[Plugging in your own data](#plugging-in-your-own-data)). `load_recording` is the
*only* function to replace for a real format.

**Why.** "Ack in callback A, do the work in callback B, chained by a store" gives
the user immediate feedback before the slow load. A minimal metadata store means
clientside math never needs the whole file.

**Adapt.** Swap `load_recording`'s body for your format; keep the returned dict
shape. Put field validation in `create_visualization`.

**Gotchas.** **Cross-platform dialog returns differ** — Windows returns a tuple,
macOS returns a string-like `objc.pyobjc_unicode` where `result[0]` is the first
*character*. `dialogs._normalize_dialog_result` handles both; don't simplify it.

---

### Recipe 5 — Building the resampler figure

**Goal.** One figure with several stacked channels sharing an x-axis, fast on
millions of points, carrying an annotation overlay.

**Source.** `ts_app/figure.py` (`build_figure`), `ts_app/labels.py` (`get_padded_labels`).

**Mechanism.**
- A `plotly_resampler.FigureResampler` wraps an N-row `make_subplots` with
  `shared_xaxes=True`. Channels are added with `hf_x`/`hf_y` and a
  `default_n_shown_samples` budget; the resampler swaps in a decimated view for
  the current zoom (Recipe 8). Downsampler is `MinMaxLTTB(parallel=True)`, which
  preserves visual extremes.
- **All traces are forced onto one shared x-axis** (`fig.update_traces(xaxis=...)`),
  giving synchronized pan/zoom and a single crosshair (`hovermode="x unified"`).
- **The annotation layer is a heatmap.** The label array (one int class per frame)
  is a `go.Heatmap` added *last* on each row. Class → color is a discrete colorscale.
- Two things are published into **`figure.layout.meta`** so the browser scripts
  stay general: `sharedXAxisKey` (e.g. `"xaxis3"`) and `overlayTraceIndices`. Change
  the channel count and the JS still finds the right axis and overlays — no edits.
  Also stashed: `xBounds` (for pan clamping), `numClass`, `frameRate`.

**Why.** `FigureResampler` is the single most important perf dependency: the
browser holds only a few thousand points per trace regardless of recording
length. The heatmap-overlay design makes "apply a label" just "edit one array and
patch a few traces" — no server round-trip.

**Adapt.** Set your channels/labels/colors in `config.py`. Keep `shared_xaxes=True`
and the overlay as the *last N traces*; the `meta`-published axis key and overlay
indices mean the interaction layer adapts automatically.

**Gotchas.** A heatmap needs a **2-D `z`** (`(1, N)`, not `(N,)`). `y0` is the
*center* of the single heatmap row and `dy` its full height, so a large `dy`
centered at 0 fills any symmetric y-range. Labels must be **padded to the frame
count** or the overlay misaligns. Unscored = `-1` on disk, `NaN` (transparent) in
display.

---

## The bridge

### Recipe 6 — The EventListener bridge

**Goal.** Let a browser DOM event you dispatch trigger a Dash callback with a
payload. This is the seam connecting the custom interaction layer to Dash.

**Source.** `ts_app/components.py` (the `EventListener` components) + the asset
scripts that `document.dispatchEvent(new CustomEvent(...))`, consumed by callbacks
in `app.py`.

**Mechanism.** `dash_extensions.EventListener` exposes a DOM event to Dash via two
props: `n_events` (increments per fire; use as `Input`) and `event` (the captured
`detail` fields you declared; use as `State`). You declare the event name and
fields; the asset dispatches a matching `CustomEvent`; a callback reads
`event["detail.x0"]` etc.

Events used here: `tsgraphrelayout` (coalesced range), `tsannotationselect`
(finished drag/click), `tsboutcontextmenu` (right-click), and `keyboard` (keydown).

**Why.** Dash's built-in graph props (`relayoutData`, `selectedData`, `clickData`)
are coarse and fire too often. Emitting your *own* semantic event ("the user
finished a selection from x0 to x1") lets the JS do the debouncing/geometry and
hand Python a clean, minimal payload — and one event can feed both a clientside
callback (instant UI) and a serverside one (data work).

**Adapt.** For any custom interaction: define a namespaced `CustomEvent` name, the
`detail` fields, a matching `EventListener`, and the callback. Send *derived*
data (times, indices) — do pixel geometry in JS where you have `_fullLayout`.

**Gotchas.** Declare every `detail` field you'll read. Scope document-level events
to the graph with `event.target.closest("#graph")` (see `graphContextMenu.js`).

---

## Navigation

### Recipe 7 — The relayout coalescer

**Goal.** Turn Plotly's per-frame `plotly_relayouting` firehose into **one
debounced signal** so the server resamples once when the view settles, not
60×/second.

**Depends on.** Recipe 5, Recipe 6 (dispatches `tsgraphrelayout`).

**Source.** `ts_app/assets/graphRelayoutCoalescer.js`; consumed by
`update_fig_resampler` in `app.py`.

**Mechanism.** The script listens to `plotly_relayouting` (continuous) and
`plotly_relayout` (final), extracts the shared-axis x-range (read from
`meta.sharedXAxisKey`), debounces to a **final** dispatch after an idle period
(shorter for keyboard moves), suppresses near-duplicate ranges, and tags each
dispatch with a `profileId`, `mode`, and `source`. **Critically, it stands down
while the custom pointer pan or annotation auto-pan is active**
(`shouldSuppress`) — those drive their own updates. It exposes
`window.tsAppGraphRelayout.{request, requestFinalOnly, suppressPlotlyRelayoutFor}`
so other gestures feed the same pipeline.

**Why.** Without coalescing, every pan fires dozens of server callbacks, each
reconstructing a patch — the app grinds. This is the most important perf
mechanism after `FigureResampler` itself.

**Adapt.** Reusable almost verbatim. Tune `FINAL_IDLE_MS` and the equality
tolerances. Route any new gesture through `tsAppGraphRelayout.request` to inherit
coalescing.

**Gotchas.** It re-attaches via `MutationObserver` because the Plotly div is
recreated on figure swaps — keep that. The self-suppression during custom
gestures is load-bearing; extend `shouldSuppress` if you add a new drag.

---

### Recipe 8 — Resampler patch pipeline & direct restyle

**Goal.** When the view settles, refresh each trace to the right detail for that
zoom — fast, minimal bytes.

**Depends on.** Recipe 5, Recipe 7.

**Source.** `ts_app/app.py`: `update_fig_resampler`, `compact_resampler_patch`,
`build_direct_restyle_payload`, the `/_ts_app/resample` route,
`RESAMPLER_CALLBACK_OUTPUT`; `ts_app/assets/graphDirectRestyle.js`; the flag
`ENABLE_DIRECT_PLOTLY_RESTYLE`.

**Mechanism.** The core computation is `fig.construct_update_data_patch({...x
range...})` (the resampler's method returning the decimated data for the new
view). There are **two delivery paths** for it, chosen at import by the flag:
1. **Dash-figure-patch** (flag off): the callback returns a Dash `Patch` on
   `graph.figure`. Simple; Dash diffs and re-applies.
2. **Direct-restyle** (flag on, the default): the callback puts the patch
   operations into `graph-direct-restyle-payload-store`; a clientside callback
   hands them to `graphDirectRestyle.js`, which calls `Plotly.restyle(...)`
   **directly**, bypassing Dash's figure reconciliation. Measurably faster.

Plus `compact_resampler_patch` trims float precision (x: 3 dp, y: 7 dp) to shrink
the payload with no visible loss.

There's also a **raw Flask GET** `/_ts_app/resample?x0=..&x1=..` returning the
patch JSON directly. The auto-pan script (Recipe 13) fetches it during a live
drag *without* going through Dash at all — the lowest-latency path.

**Why.** Each layer removes overhead from the hot path: coalescing removes
redundant calls, direct restyle removes Dash's diff, precision trimming removes
bytes, the raw route removes Dash entirely for the most latency-sensitive case.

**Adapt.** Keep `update_fig_resampler` structurally; the range keys come from
`meta.sharedXAxisKey`. Start with the flag off (simpler), flip it on once
navigation works. The raw route is only needed if you adopt auto-pan.

**Gotchas.** `graphDirectRestyle.js` forwards a whitelist of trace props
(`x`, `y`, `name`, `marker`) — widen `DATA_PROPS` if your patches touch others.
`construct_update_data_patch` reads the global resampler — it must be the object
`create_fig` built.

---

### Recipe 9 — Keyboard panning

**Goal.** Arrow keys nudge the view left/right instantly.

**Depends on.** Recipe 5, Recipe 7, the `keyboard` EventListener.

**Source.** `ts_app/app.py` — the `pan_figure` clientside callback.

**Mechanism.** On an arrow key it reads the shared-axis range (from
`meta.sharedXAxisKey`), computes a ±30% shift, applies it immediately via a
`dash_clientside.Patch` (instant view move), updates `graph.relayoutData`, and
calls `tsAppGraphRelayout.request(..., "keyboard")` so the (slower) resample is
scheduled through the coalescer with the faster keyboard idle timeout.

**Why.** The view shift feels instant because it's clientside; the data refresh
happens once after you stop pressing.

**Adapt.** Change the step fraction or bind different keys. The pattern — *move
the view clientside now, schedule the data refresh through the coalescer* — is the
template for any custom navigation.

**Gotchas.** Return `dash_clientside.no_update` for unrelated keys. Build a **new**
`relayoutData` object (spread), don't mutate the existing one.

---

### Recipe 10 — Custom pointer pan

**Goal.** Click-drag to pan in x **and** the hovered channel's y, smoothly.

**Depends on.** Recipe 5, Recipe 7.

**Source.** `ts_app/assets/graphCustomPointerPan.js`.

**Mechanism.** In `pan` mode it intercepts `pointerdown` (no modifiers, left
button, not on chrome), captures the start x-range and the y-range of the row
under the pointer, and on each `pointermove` converts pixel delta → data delta and
schedules the `Plotly.relayout` on the next animation frame. It tells the
coalescer to suppress its own handling for 250 ms so they don't fight; on
`pointerup` it triggers the resample once via `requestFinalOnly`.

**Why.** Plotly's native pan doesn't give per-row y-panning or integrate with the
coalescer's suppression. Owning the gesture lets you pan x and the hovered
channel's y together, throttled to the frame rate.

**Adapt.** Toggle with the `ENABLE` constant. The eligible y-axes are discovered
dynamically (any non-fixed, non-overlaying row axis under the pointer), so it
works for any channel count.

**Gotchas.** `isInteractiveChrome` prevents hijacking drags on the modebar/legend —
keep an equivalent guard. rAF throttling + the suppression window keep it smooth
and non-conflicting.

---

## Annotation

### Recipe 11 — Mode switching

**Goal.** One key (`m`) toggles navigate (`dragmode="pan"`) ↔ annotate
(`dragmode="select"`).

**Source.** `ts_app/app.py` — the `switch_mode` clientside callback.

**Mechanism.** On `m` it patches `figure.layout.dragmode` and clears leftover
selections/shapes when leaving select mode.

**Why.** Navigation and annotation both want the mouse, so they can't share a
mode. Nearly every interaction script gates on `dragmode` (`isSelectMode`,
`getDragMode`), so this one flag is the master switch.

**Adapt.** Rebind the key if `m` collides; add per-mode UI here.

**Gotchas.** Clear `selections` and `shapes` when leaving select mode or a stale
box lingers.

---

### Recipe 12 — Selection

**Goal.** Three ways to select a region: **drag a box**, **click a point** (small
neighborhood), or **right-click a segment** (the whole contiguous same-label run).

**Depends on.** Recipe 5, Recipe 11, Recipe 6 (context-menu event),
`recording-meta-store`.

**Source.** `ts_app/app.py` clientside callbacks `read_box_select`,
`read_click_select`, `read_bout_context_select`; `ts_app/assets/graphContextMenu.js`.

**Mechanism.** Each selection callback ends the same way: compute `[start, end]`
seconds relative to `start_time`, store them in **`box-select-store`**, draw a
rectangle `shape` for feedback, and write a status message. The context-menu path
uses `graphContextMenu.js` to convert the right-click pixel to a data-x, then walks
the overlay label array (found via `meta.overlayTraceIndices`) left/right while the
class stays equal, selecting the whole segment.

`box-select-store` is the single source of truth the annotation keypress
(Recipe 14) reads. All three methods converge on it.

**Why.** Different edits want different granularities — a precise drag, a quick
single-frame fix, or "relabel this whole segment." Funneling all three into one
`[start, end]` store means the labeling step doesn't care how you selected.

**Adapt.** Keep the convergence on one store. Add/remove selection methods freely.

**Gotchas.** Integer rounding has an edge case when `start === end`; the code
expands to a full frame deliberately. All three gate on select mode.

---

### Recipe 13 — Drag-to-select with auto-pan

**Goal.** Drag to select; near the edge the view **auto-pans**, and the newly
revealed signal is **fetched and drawn live** during the pan — so you can select
regions wider than the screen.

**Depends on.** Recipe 5, Recipe 6 (`tsannotationselect`), Recipe 8 (the raw
`/_ts_app/resample` route), Recipe 11.

**Source.** `ts_app/assets/annotationAutoPan.js` (the largest asset); consumed by
`read_annotation_auto_pan_select` in `app.py`.

**Mechanism.** It owns the whole pointer gesture in select mode:
- **Begin**: record the anchor time and the hovered row's y-range; set
  `window.tsAppAnnotationAutoPanActive = true` (coalescer stands down); capture
  the pointer.
- **Continue**: redraw the selection rectangle each frame (rAF).
- **Auto-pan**: compute edge "pressure" (0 in the middle, ramping to ±1 within
  `EDGE_PX` of an edge); while pressure ≠ 0 an rAF loop shifts the shared x-range
  proportionally to pressure² × view-width × dt, clamped to `meta.xBounds`.
- **Live refresh**: during the pan it `fetch`es `/_ts_app/resample` for the lead
  range and **merges** the incoming decimated points into the traces
  (`mergeTraceArrays`, throttled, single-flight with a pending slot) via
  `Plotly.restyle` — so the signal appears under the growing selection.
- **End**: one final `replace`-mode refresh, then dispatch `tsannotationselect`
  with the final `[x0, x1]` and whether it was a `drag` or `click`. The clientside
  callback normalizes to a selection and writes `box-select-store` — same
  convergence point as Recipe 12.

**Why.** Selecting a region wider than the viewport is otherwise impossible
without zooming out (losing detail). Auto-pan-while-dragging solves that; the live
fetch+merge avoids blank space where data hasn't loaded. It bypasses Dash (raw
`fetch`) because this loop runs every frame of a drag.

**Adapt.** The hardest recipe to port — adopt only if cross-viewport selection
matters. Tunables: `EDGE_PX`, `PAN_VIEW_WIDTH_PER_SECOND`, `TRACE_REFRESH_MS`, the
buffer fractions. Needs the raw route (Recipe 8) and `meta.xBounds` (Recipe 5).

**Gotchas.** `tsAppAnnotationAutoPanActive` must toggle around the gesture (with a
release delay) or relayouts fight. Single-flight + the stale-guard
(`requestId < latestAppliedTraceRequestId`) prevent request pileup and out-of-order
application — keep both. `CLICK_PX` decides click vs drag so a stationary press
still selects a neighborhood.

---

### Recipe 14 — Keypress annotation & overlay

**Goal.** With a region selected, press a number key to label it; the overlay
updates instantly and the change goes to undo history.

**Depends on.** Recipe 5, Recipe 12/13, the `keyboard` EventListener, Recipe 15.

**Source.** `ts_app/app.py` clientside callbacks `make_annotation` and
`update_labels`; serverside `update_labels_history`.

**Mechanism.** Two clientside steps:
1. `make_annotation` fires on a number key (only in select mode, only with a
   selection): it reads `meta.numClass`/`meta.frameRate`, copies the current label
   array (from the last overlay trace's `z[0]`), writes the class into
   `[start·frameRate, end·frameRate)`, and puts the new array in
   `updated-labels-store`, clearing the selection.
2. `update_labels` fires on that store: it patches the `z` of **every overlay
   trace** (`meta.overlayTraceIndices`) to the new array.

Separately, serverside `update_labels_history` appends to `labels_history` if the
array actually changed (`equal_nan=True`) and reveals Undo.

**Why.** The label array *is* the state; rendering it as a heatmap makes "apply a
label" just "edit an array and repaint a few traces" — no server round-trip for
the visual. Pushing to history on the same store keeps undo automatic.

**Adapt.** Map your keys → class ints in `config.py`. The overlay indices come
from `meta`, so one overlay or N both work without code changes.

**Gotchas.** `[start, end)` is half-open. The overlay index math relies on
`meta.overlayTraceIndices`, so it survives added traces (unlike hardcoded offsets).

---

### Recipe 15 — Undo & crash recovery

**Goal.** One-step undo, plus automatic salvage of unsaved labels if the app
restarts on the same file.

**Source.** `ts_app/app.py`: `initialize_state` (creates `deque(maxlen=2)`),
`update_labels_history`, `undo_annotation`, and the salvage branch in
`create_visualization`.

**Mechanism.** `labels_history` is a `deque(maxlen=2)` in the filesystem cache —
previous and current arrays. Every real change appends; `undo_annotation` restores
`history[0]` and pops. Because the cache is filesystem-backed with a long timeout,
reopening the **same** file finds the last history entry and loads it instead of
the file's on-disk labels; a **different** file resets the deque.

**Why.** `maxlen=2` is a deliberate scope choice — one-step undo covers "oops,
wrong label" cheaply. Filesystem persistence turns the same structure into crash
recovery for free.

**Adapt.** For multi-level undo, raise `maxlen` and walk back one step at a time
(weigh memory — each entry is a full label array).

**Gotchas.** History round-trips through the cache, so comparisons use
`equal_nan=True` and the `== None` handling in `labels_for_saving`.

---

### Recipe 16 — Saving & export

**Goal.** Save labels back to disk via a native Save dialog, and export a segment
table when fully labeled.

**Source.** `ts_app/app.py::save_labels`; `ts_app/labels.py` (`labels_for_saving`,
`get_segments`, `first_unscored_segment`); `ts_app/data.py::save_recording`.

**Mechanism.** On Save: reload the recording, replace its labels with the latest
history array (NaN/None → `-1`), write a temp `.npz`, then a native Save dialog
copies it to the chosen path. If fully labeled (no unscored segment), it builds a
segment table and offers a second dialog for a `.csv`. A one-shot `dcc.Interval`
clears the status message after a few seconds.

**Adapt.** Swap the writer and the derived export. Keep the "temp file then copy
to the dialog path" pattern — it decouples computation from the save location and
survives a cancelled dialog.

**Gotchas.** Convert display sentinels (`NaN`) back to the on-disk sentinel (`-1`)
before saving. Guard the button's initial fire.

---

## Multi-session

### Recipe 17 — Multi-session desktop windows

**Goal.** Run up to three independent app windows on one computer without shared
callback globals, cache/temp-file collisions, or the same recording open twice.

**Depends on.** Recipe 1 (the launcher), Recipe 3 (cache and process globals),
Recipe 4 (file loading).

**Source.** `run_desktop_app.py` (`BASE_PORT`, `MAX_SESSIONS`,
`claim_session_slot`); `ts_app/config.py` (`INSTANCE_SLOT`, `PEER_PORTS`); in
`ts_app/app.py`: the per-slot `TEMP_PATH`, `set_/get_current_filepath`,
`find_peer_session_with_file`, the `/_ts_app/current-file` route, and the peer
check in `choose_file`. Regression coverage: `tests/test_multi_session.py`.

**Mechanism.** One **process per window**; a tiny port-slot protocol handles only
the cross-process concerns:

1. **Claim a slot before importing `ts_app`.** `claim_session_slot()` binds the
   first free port in `BASE_PORT..BASE_PORT+MAX_SESSIONS-1` and holds the socket
   until the Dash server takes the port over, so two launchers can't race onto
   the same slot. The OS port table doubles as the "how many windows are open"
   counter — no lock files, and a crashed window frees its slot automatically.
   If every slot is bound, a small pywebview notice explains the window limit.
2. **Export the process identity.** Before any `ts_app` import, the launcher
   writes `TS_APP_INSTANCE_SLOT` and `TS_APP_PEER_PORTS`; `ts_app/config.py`
   reads them once at import time. Missing env vars mean slot 0 with no peers —
   exactly the single-window behavior, so tests, scripts, and `--smoke` need no
   changes. This is also why the slot range lives in the launcher: config can't
   provide a value that must be known before config is imported.
3. **Namespace disk state by slot.** `TEMP_PATH` (and with it the filesystem
   cache and temp exports) becomes `…/ts_app_data/slot_<N>`. Ordinary module
   globals — the Dash app, `FIG_RESAMPLER`, the components — need nothing:
   separate processes isolate them for free.
4. **Separate recovery state from live state.** Cache entries persist across
   restarts on purpose (crash recovery, Recipe 15). The `/current-file` peer
   endpoint therefore reports the process-local `_current_filepath` (initially
   `None`), never the cached `filepath` — otherwise a restarted blank window
   would falsely claim its previous recording.
5. **Refuse a file already open in a peer.** Before `initialize_state`,
   `choose_file` queries each peer port's `/_ts_app/current-file` with a short
   timeout. Only a response identifying itself as this app counts; paths are
   normalized before comparison; a match returns a user-facing refusal. Dead
   windows stop answering, so a crashed window's claim evaporates with it.

**Why.** A session-aware Dash server would need every cache key, component
singleton, resampler global, callback, and generated artifact to carry a session
id. One process per window lets the operating system do the isolation, leaving
only identity, capacity, and same-file detection to the port-slot protocol.

**Adapt.**
- Change `BASE_PORT` / `MAX_SESSIONS` together in the launcher; window titles,
  peer ports, and slot dirs all derive from them.
- Namespace any new generated-artifact directory or persistent cache by slot too
  (the reference app does this for its per-window video-clip folders).
- If your launcher does pre-import work that patches the package on disk (e.g. a
  startup auto-updater), make it atomic against new windows by binding *all*
  peer ports for the duration — the reference app's launcher shows the pattern.
- For a browser-hosted multi-user deployment, do **not** copy this
  port-per-window design; use authenticated session ids and session-keyed state.

**Gotchas.**
- **Port occupancy is a bind question, not a connection question.** A starting
  peer owns a bound socket before it listens; `socket.create_connection()` would
  miss it. Probe with `bind`.
- **Persistent is not active.** Recovery cache keys may be days old; peer
  coordination must use process-local state (point 4 above).
- Any unrelated process holding a slot port reduces window capacity. This is
  intentionally conservative.
- The same-file check is advisory, not an atomic lock: two selections made at
  the same instant can both pass. The accepted race avoids stale lock files.

---

## Cross-cutting patterns

- **Clientside for feel, serverside for data.** If an interaction can run from
  data already in the browser (figure, stores), do it clientside. Hit the server
  only for loading, resampling, and saving.
- **Stores are the wiring.** Hidden `dcc.Store`s pass data between callbacks
  (client and server). Treat the set of stores as your app's state schema.
- **Converge many inputs on one store.** Box/click/context/drag all write
  `box-select-store`; labeling reads only that.
- **Ack-then-work handoff.** A slow action is two callbacks: paint "working…" and
  set a trigger store; then do the work.
- **Emit your own semantic DOM events** (Recipe 6) instead of fighting Plotly's
  coarse built-ins.
- **Publish layout facts in `figure.layout.meta`** (shared axis key, overlay trace
  indices, x-bounds) so the browser scripts adapt to different channel counts
  without edits.
- **Coalesce, then compute.** Never let a per-frame gesture drive per-frame server
  work — route it through the coalescer.
- **Guard dynamic-component callbacks** with `if not n_clicks: raise PreventUpdate`.
- **`allow_duplicate=True`** on any output multiple callbacks target (many target
  `graph.figure` and `annotation-message`).
- **Assets auto-load.** Any `.js` in `ts_app/assets/` is served and run
  automatically. Scripts self-guard (`if (window.tsAppX) return;`) and re-attach
  via `MutationObserver` because the graph div is recreated on figure swaps.

---

## Adaptation checklist

1. **Shell** (Recipe 1): keep pywebview, or drop it for browser-only + `dcc.Upload`.
2. **Data contract** (Recipe 4): implement `load_recording` for your format;
   return the recording dict. Set required-field validation in
   `create_visualization`.
3. **Figure** (Recipe 5): set channels/labels/colors and `default_n_shown_samples`
   in `config.py`. The `meta`-published axis key + overlay indices mean the JS
   adapts to your channel count automatically.
4. **State** (Recipe 3): list session state → cache; the resampler → global.
5. **Navigation**: the coalescer (7) + resampler pipeline (8) are near-verbatim
   reusable. Add keyboard pan (9) and/or custom pan (10).
6. **Annotation** (optional): mode switch (11) → selection methods (12, +13 for
   long selections) → keypress labeling (14) → undo (15). All converge on one
   store and one label array.
7. **Save/export** (16) as needed.
8. **Multi-session** (17), if users open several recordings side by side: pick
   the slot range in the launcher, namespace every persistent/generated path by
   slot, and keep recovery state separate from live state.

**Minimum viable viewer** (no annotation): Recipes 1–8 — a fast, zoomable,
pannable multi-channel viewer on huge signals.
**Add annotation**: Recipes 11, 12, 14, 15 (+13 for long selections).

---

## Gotcha catalog

- **macOS vs Windows file dialogs** return different types; `result[0]` on macOS
  grabs a character. Normalize (Recipe 4).
- **`np.nan` → `None`** when read back from the filesystem cache. Use
  `equal_nan=True` and `== None` handling (Recipe 3).
- **Heatmaps need 2-D `z`** (`(1, N)`) (Recipe 5).
- **Label array must be padded to the frame count** (Recipe 5).
- **Overlay indices come from `meta.overlayTraceIndices`** — don't hardcode
  offsets (Recipes 5, 14).
- **Half-open `[start, end)`** annotation range (Recipe 14).
- **Coalescer self-suppression** must wrap every custom drag/auto-pan (Recipes 7,
  10, 13).
- **Dynamic-component callbacks** need the manual `n_clicks` guard (Recipe 2).
- **`allow_duplicate=True`** on shared outputs.
- **Re-attach via `MutationObserver`** — the Plotly div is replaced on figure
  swaps (Recipes 7, 10).
- **Clear `selections`/`shapes`** when leaving select mode or after labeling
  (Recipes 11, 14).
- **Sentinel round-trip**: unscored is `-1` on disk, `NaN` in display (Recipes 5, 16).
- **A bound port may not be listening yet.** Detect peer windows with bind
  attempts, not connections (Recipe 17).
- **Persistent cache state is not live process state.** Never report a recovered
  filepath as a window's current file after a restart (Recipe 17).

---

## Source-file map

| Concern | File |
| --- | --- |
| Desktop shell / entrypoint, window-slot claim | `run_desktop_app.py` |
| Config (window, classes, flags, session slot env) | `ts_app/config.py` |
| Dash app, callbacks, Flask routes, cache | `ts_app/app.py` |
| Multi-session coordination | `run_desktop_app.py`, `ts_app/config.py`, `ts_app/app.py` |
| Layout, stores, EventListeners | `ts_app/components.py` |
| Figure builder (resampler + overlay) | `ts_app/figure.py` |
| Data contract, synthetic gen, loader | `ts_app/data.py` |
| Label padding, segments, export | `ts_app/labels.py` |
| Native dialogs | `ts_app/dialogs.py` |
| Relayout coalescing | `ts_app/assets/graphRelayoutCoalescer.js` |
| Direct restyle | `ts_app/assets/graphDirectRestyle.js` |
| Custom pointer pan | `ts_app/assets/graphCustomPointerPan.js` |
| Drag-select + auto-pan | `ts_app/assets/annotationAutoPan.js` |
| Context-menu select | `ts_app/assets/graphContextMenu.js` |
| Exit guard | `ts_app/assets/closeWindow.js` |
| Smoke tests (data/figure/label/routes) | `tests/test_smoke.py` |
| Multi-session tests (slots/peers/refusal) | `tests/test_multi_session.py` |

For agent-coordination context (active-vs-legacy notes, test/fixture details, open
questions), see [`project_overview.md`](project_overview.md).

---

## Real-world example

This template is distilled from **[Sleep Scoring App](https://github.com/yzhaoinuw/sleep_scoring)**,
a production desktop app for annotating multi-hour EEG/EMG recordings. To see
these recipes carrying a real domain — a spectrogram panel, model-assisted
prediction, video-clip playback, and a MATLAB `.mat` data contract — read its
`app_src/` alongside this template. The interaction layer is the same; this repo
strips it to the reusable, domain-neutral core.

## Citation

If you build on this template in research, use GitHub's **Cite this repository**
button or the [CITATION.cff](CITATION.cff) file to obtain an APA or BibTeX entry.

<!-- After the first GitHub Release is published and Zenodo mints the DOI, add the
     DOI badge under the title at the top of this README, and replace this comment
     block with the paragraph below, filling in the concept DOI:

Each release is archived on Zenodo. Cite the concept DOI
[10.5281/zenodo.XXXXXXXX](https://doi.org/10.5281/zenodo.XXXXXXXX), which resolves
to the newest release; use a release's own DOI only when you need to pin the exact
version you ran.
-->

## Provenance & license

The interaction patterns here (coalesced navigation, direct restyle, auto-pan
drag-select, keypress annotation) are the transferable innovations this template
exists to share — see [Real-world example](#real-world-example) for the app they
were distilled from.

Released under the MIT License — see [`LICENSE`](LICENSE).
