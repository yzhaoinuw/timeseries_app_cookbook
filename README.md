# Time Series App Cookbook

[![Agent Collab Treaty](https://raw.githubusercontent.com/yzhaoinuw/agent_collab_treaty/main/assets/treaty-adopted.svg)](https://github.com/yzhaoinuw/agent_collab_treaty)

A **domain-neutral, runnable template** for building interactive Dash + Plotly
desktop apps that let a user navigate, inspect, and annotate **long time series**
smoothly — even at millions of points — using [`plotly-resampler`](https://github.com/predict-idlab/plotly-resampler).

It is distilled from a production biomedical scoring app, with every
domain-specific detail stripped out. The signals here are synthetic; the
*techniques* — the resampler-backed navigation, drag-to-select with auto-pan,
keypress annotation, undo — are the point. Swap in your own data and label set
and you have your own app.

Read [`COOKBOOK.md`](COOKBOOK.md) for the design rationale and a per-feature
recipe book. This README is just how to run and adapt it.

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
[`ts_app/config.py`](ts_app/config.py).

## Repo layout

| Path | Purpose |
| --- | --- |
| `run_desktop_app.py` | Desktop entrypoint: threaded Dash server in a pywebview window. |
| `ts_app/config.py` | Window, class labels/colors, resampler budget, feature flags. |
| `ts_app/data.py` | The recording contract, synthetic generator, pluggable loader. |
| `ts_app/dialogs.py` | Native Open/Save dialogs (cross-platform normalization). |
| `ts_app/figure.py` | Resampler-backed multi-channel figure + annotation overlay. |
| `ts_app/labels.py` | Label padding, segment extraction, export helpers. |
| `ts_app/components.py` | Layout, hidden stores, custom-event bridges. |
| `ts_app/app.py` | Dash app: interaction callbacks, fast resampler path, Flask routes. |
| `ts_app/assets/*.js` | The browser interaction layer (auto-loaded by Dash). |
| `tests/` | Smoke tests for the data/figure/label paths. |
| `COOKBOOK.md` | The design rationale and per-feature recipes. |

## Adapting further

Start with the [Adaptation checklist](COOKBOOK.md#adaptation-checklist) in the
cookbook. In short: change `config.py` (window, classes, colors, sample budget)
and `data.py` (your loader) for most apps; the interaction layer
(`app.py` + `assets/*.js`) is meant to be reused as-is. Because the shared x-axis
and overlay trace indices are published in `figure.layout.meta`, the JavaScript
adapts to a different channel count without edits.

## Real-world example

This template is distilled from **[Sleep Scoring App](https://github.com/yzhaoinuw/sleep_scoring)**,
a production desktop app for annotating multi-hour EEG/EMG recordings. To see
these recipes carrying a real domain — a spectrogram panel, model-assisted
prediction, video-clip playback, and a MATLAB `.mat` data contract — read its
`app_src/` alongside this template. The interaction layer is the same; this repo
strips it to the reusable, domain-neutral core.

## Provenance & license

The interaction patterns here (coalesced navigation, direct restyle, auto-pan
drag-select, keypress annotation) are the transferable innovations this template
exists to share — see [Real-world example](#real-world-example) for the app they
were distilled from.

Released under the MIT License — see [`LICENSE`](LICENSE).
