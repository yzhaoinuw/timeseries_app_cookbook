# Work Log

Prepend new session notes to the top of this file.

Rotation policy: the live log holds at most the **5 most recent unique calendar dates**. When a new date would push the file past 5 unique dates, move the oldest 5 dates as a chunk into a new file at `work_log_archive/work_log_<earliest>_to_<latest>.md`. The live file always holds at most 5 unique dates; each archive file always holds exactly 5.

If today's date already has a `## YYYY-MM-DD` header at the top, add a new `###` session subsection under it rather than starting a second `## YYYY-MM-DD` header for the same date.

Update this log at the end of any substantive work session unless the user explicitly asks not to document it. Substantive work includes file edits, meaningful validation or debugging, technical decisions or reversals, reusable discoveries, branch/PR/release state changes, or follow-up work that future agents need. Log useful experiments even when the code was reverted; skip casual Q&A, trivial one-off commands, and pure scratch work with no future coordination value.

<!--
Each session entry follows this shape:

## YYYY-MM-DD

### Short title for what was done (model + version, effort/thinking mode, token budget if known)

- bullet describing what was added or changed
- another bullet — keep them high-level and user/agent-facing, not implementation play-by-play
- if relevant, intended profiling signal or measurement:
  - what to look for in logs / output
  - what numbers were observed
- Verification:
  - the exact command(s) that were actually run
  - what passed / what was confirmed

Model / effort / token info goes in the parentheses after the `###` title when available from the system. Use whatever the model or interface actually reports — do not estimate or hallucinate. Omit any field that the interface does not surface.

- **Model**: the version string the interface reports (e.g. `grok-4.3`, `gpt-4o`, `claude-opus-4-7`).
- **Effort / thinking mode**: the effort knob the interface reports (e.g. `high`, `low`, `extended thinking`). Omit if no such knob exists or its setting is not surfaced.
- **Token budget**: **output tokens for the session** (output + thinking/reasoning tokens for models that report them separately, e.g. Claude with extended thinking). This is the cleanest cross-agent proxy for "amount produced." Omit if the interface does not surface a count.

Purely human-driven work can use `(human)`. Mixed human + agent sessions can combine them, e.g. `(human + grok-4.3, high)`.

Keep the parenthetical compact. Examples:
- `(grok-4.3, high, ~18k out)`
- `(gpt-4o, high, ~22k out)`
- `(claude-opus-4-7, extended thinking, ~30k out)`
- `(grok-4.3, low)`

Newest entry goes on top. If the session did multiple distinct pieces of work, use multiple `###` subsections under one `##` date header.
-->

## 2026-08-04

### Captioned demo video added to the README on `dev` (claude-opus-5)

- Added a **Demo** section to the README, directly above "What you get", plus a
  Contents entry. It shows a poster frame that links to the 56-second captioned
  walkthrough (scroll-zoom, drag-pan, mode switch, the four selection gestures,
  keypress labeling, undo, save).
- Committed two media files under a new `docs/media/`:
  - `ts_app_demo.mp4` — 1600px, 15fps, CRF 24, 4.2MB README export.
  - `ts_app_demo_poster.png` — frame at t=34s of the captioned master, 1200px.
- Embedding decision: GitHub does **not** render an inline player for a committed
  mp4 referenced by relative path — the link opens the blob page, which does play.
  The poster-image-linking-to-the-video pattern was chosen so the README shows
  something visual without the upload step. A true inline autoplay player needs a
  `github.com/user-attachments/...` URL, which only Yue can mint by drag-dropping
  the mp4 into the web editor (the pattern already used in `sleep_scoring`).
- The clip was recorded against the `main` build (title bar reads 0.1.1); `dev` is
  still 0.1.0 and lacks main's legend-overlap / right-click fix. Cosmetic only for
  inspection purposes.
- The captioning pipeline (`make_banners.py` + the ffmpeg filtergraph recipe) is
  still only on `~/Desktop/ts_app_demo_captioning/` and is **not** tracked here —
  see `next_steps.md`.
- Verification:
  - `python -m pytest -q` → 26 passed
  - `python run_desktop_app.py --smoke` → OK
  - `ffprobe` on the export → 1600x986, 15fps, 55.5s, 4.17MB

## 2026-07-10

### Multi-session support ported from the reference app (claude-fable-5)

- Ported the reference app's (sleep_scoring) multi-session architecture into the
  template: up to three independent desktop windows, one process per window.
  `run_desktop_app.py` now claims a port slot (`BASE_PORT` 8060–8062) before
  importing `ts_app` and exports `TS_APP_INSTANCE_SLOT` / `TS_APP_PEER_PORTS`;
  `ts_app/config.py` reads them at import time (defaults preserve single-window
  behavior for tests/scripts/--smoke); `ts_app/app.py` namespaces the temp/cache
  dir by slot, tracks the process-local current file, serves
  `/_ts_app/current-file` for peers, and refuses a file already open in another
  window. Later windows get a numbered title and profiling forced off.
- Left out the reference app's updater peer-guards, legacy temp adoption, and
  per-slot video dirs — the template has no updater, no installed base, and no
  video feature. The updater-exclusion pattern is noted in the recipe's Adapt
  section instead.
- Documented it as README Recipe 17 (new Multi-session group) and threaded it
  through the contents, recipe index, recipes 1/3/4, adaptation checklist,
  gotcha catalog, and source-file map. Added the launcher/env-contract reminder
  to `AGENTS.md` and the new test file to `project_overview.md`.
- Config change: `PORT` moved out of `ts_app/config.py` into the launcher as
  `BASE_PORT` — the slot must be claimed before `ts_app` can be imported, so
  config cannot own it.
- Verification:
  - `python -m pytest -q` — 26 passed (8 smoke + 18 new multi-session tests
    covering slot claiming, the env contract, the current-file endpoint,
    peer lookup, and the choose_file refusal)
  - `python run_desktop_app.py --smoke` — OK

## 2026-07-05

### Doc reconciliation: merge cookbook into README (claude-fable-5)

- Collapsed overlapping docs. The per-feature cookbook (`COOKBOOK.md`) was merged
  into `README.md` — since the repo is a cookbook, its README now *is* the
  cookbook: quickstart up top, then the recipes and reference material, with a
  table of contents. `COOKBOOK.md` was deleted.
- Folded the duplicated file map / data contract / adaptation guidance into single
  README sections (the file map appeared in three docs before).
- Compacted `project_overview.md` to only the agent-coordination content
  (active-vs-legacy, tests/fixtures, open questions) plus a pointer block into the
  README sections; removed the parts the README now covers.
- Updated the `COOKBOOK.md` pointer in `AGENTS.md` to reference the README.
- Verification:
  - `treaty validate .` -> `Treaty validation passed.`
  - Confirmed no remaining `COOKBOOK.md` references except the historical work-log
    entry below.

### Initial template build + treaty adoption (claude-fable-5)

- Created this repository as a standalone, domain-neutral template distilled from
  the Sleep Scoring App. Built the full runnable app under `ts_app/`: desktop
  shell (`run_desktop_app.py`), Dash app with clientside + server callbacks and
  two Flask routes (`app.py`), layout/stores/event-bridges (`components.py`), the
  resampler figure with annotation overlay (`figure.py`), the recording contract +
  synthetic generator + pluggable loader (`data.py`), label helpers (`labels.py`),
  native dialogs (`dialogs.py`), and the browser interaction layer
  (`assets/*.js`: relayout coalescer, direct restyle, custom pointer pan,
  drag-select auto-pan, context menu, close guard).
- Key generalization vs. the source app: the shared x-axis id and overlay trace
  indices are no longer hardcoded — the figure publishes them in
  `figure.layout.meta` and every asset JS reads from there, so a different channel
  count needs no JS edits.
- Wrote `README.md` (quickstart + recording contract) and `COOKBOOK.md` (16
  numbered recipes). Added MIT `LICENSE`.
- Fixed a real bug caught by the smoke tests: `get_segments` split runs of
  unscored (NaN) frames into separate segments because `np.diff` treats
  `nan != 0` as `True`; now collapses NaN to one key before diffing.
- Adopted the Agent Collab Treaty (copier `v0.3.3`): filled `AGENTS.md`
  (runtime, common tasks, project-specific reminders), `project_overview.md`, and
  `next_steps.md`; added the tri-color adoption badge to `README.md`.
- Verification:
  - env `sleep_scoring_dash3.0` (Dash 3.3, plotly 6.5, plotly-resampler 0.11).
  - `date +%Y-%m-%d` -> `2026-07-05`.
  - `python -m pytest -q` -> `8 passed, 1 warning` (pre-existing `flask_caching`
    deprecation).
  - `python run_desktop_app.py --smoke` -> `Time Series Annotator 0.1.0 smoke check OK`.
  - Imported `ts_app.app` -> 15 callbacks registered; routes `/_ts_app/resample`
    and `/_ts_app/profile-log` present.
  - Drove the Flask layer via `app.server.test_client()`: `GET /` -> 200;
    `GET /_ts_app/resample?x0=50&x1=110` -> 200 JSON with 9 patch operations;
    bad input -> 400.
  - Pushed to `origin/main` (`github.com/yzhaoinuw/timeseries_app_cookbook`):
    initial template commit, then `Add MIT license`.
