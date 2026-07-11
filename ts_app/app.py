# -*- coding: utf-8 -*-
"""The Dash app: layout wiring, the browser interaction layer (clientside
callbacks + custom-event bridges), the fast resampler-refresh path, and the
server callbacks for loading, sampling-level, undo, and saving.

Read alongside COOKBOOK.md — most functions here map 1:1 to a numbered recipe.
The guiding split: anything that must feel instant runs in the browser
(clientside callbacks / assets JS); the server is hit only for real data work.
"""

import json
import os
import shutil
import tempfile
import time
from collections import deque
from pathlib import Path
from urllib.request import urlopen

import dash
import dash_bootstrap_components as dbc
import numpy as np
from dash import Dash, clientside_callback
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
from flask import abort, request
from flask_caching import Cache
from plotly.utils import PlotlyJSONEncoder

from ts_app import VERSION
from ts_app.components import Components
from ts_app.config import (
    APP_TITLE,
    ENABLE_DIRECT_PLOTLY_RESTYLE,
    INSTANCE_SLOT,
    PEER_PORTS,
    PROFILE_NAVIGATION,
    SAMPLING_LEVELS,
)
from ts_app.data import (
    generate_synthetic_recording,
    load_recording,
    recording_duration,
    save_recording,
)
from ts_app.dialogs import open_file_dialog, save_file_dialog
from ts_app.figure import build_figure
from ts_app.labels import (
    first_unscored_segment,
    get_padded_labels,
    get_segments,
    labels_for_saving,
)

components = Components()

app = Dash(
    __name__,
    title=f"{APP_TITLE} {VERSION}",
    suppress_callback_exceptions=True,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
)
app.layout = components.home_div

# Each app window is its own process on its own slot (Recipe 17); a per-slot
# dir keeps the windows' caches and temp exports from clobbering each other.
TEMP_PATH = Path(tempfile.gettempdir()) / "ts_app_data" / f"slot_{INSTANCE_SLOT}"
TEMP_PATH.mkdir(parents=True, exist_ok=True)

# The one big hot in-memory object: the resampler figure (holds full-res data).
# Not cacheable, so it lives as a process global (single recording at a time).
FIG_RESAMPLER = None
RESAMPLER_PATCH_X_DECIMALS = 3
RESAMPLER_PATCH_Y_DECIMALS = 7

cache = Cache(
    app.server,
    config={
        "CACHE_TYPE": "filesystem",
        "CACHE_DIR": TEMP_PATH,
        "CACHE_THRESHOLD": 30,
        "CACHE_DEFAULT_TIMEOUT": 20 * 24 * 3600,  # ~20 days -> survives a restart
    },
)


# %% resampler figure storage -------------------------------------------------
def store_fig_resampler(fig):
    global FIG_RESAMPLER
    FIG_RESAMPLER = fig


def get_fig_resampler():
    return FIG_RESAMPLER


def clear_fig_resamplers():
    global FIG_RESAMPLER
    FIG_RESAMPLER = None


def create_fig(recording, plot_name, n_shown_samples=2048):
    fig = build_figure(recording, plot_name, n_shown_samples)
    store_fig_resampler(fig)
    return fig


# %% meta helpers -------------------------------------------------------------
def _fig_meta(fig):
    meta = getattr(getattr(fig, "layout", None), "meta", None)
    return meta if isinstance(meta, dict) else {}


def shared_axis_key(fig):
    return _fig_meta(fig).get("sharedXAxisKey", "xaxis")


def fig_x_bounds(fig):
    bounds = _fig_meta(fig).get("xBounds")
    if isinstance(bounds, (list, tuple)) and len(bounds) == 2:
        try:
            x0, x1 = float(bounds[0]), float(bounds[1])
        except (TypeError, ValueError):
            return None
        if np.isfinite(x0) and np.isfinite(x1) and x1 > x0:
            return [x0, x1]
    return None


def clamp_x_range_to_bounds(x0, x1, bounds):
    low, high = min(x0, x1), max(x0, x1)
    if not bounds:
        return [low, high]
    bound_low, bound_high = bounds
    width = high - low
    if width >= bound_high - bound_low:
        return [bound_low, bound_high]
    clamped_low = min(max(low, bound_low), bound_high - width)
    return [clamped_low, clamped_low + width]


def compact_resampler_patch(update_patch):
    """Trim float precision in resampler trace updates to shrink the payload."""
    if not hasattr(update_patch, "_operations"):
        return update_patch
    for operation in update_patch._operations:
        location = operation.get("location", [])
        if len(location) < 3 or location[0] != "data":
            continue
        prop = location[2]
        if prop == "x":
            decimals = RESAMPLER_PATCH_X_DECIMALS
        elif prop == "y":
            decimals = RESAMPLER_PATCH_Y_DECIMALS
        else:
            continue
        value = operation.get("params", {}).get("value")
        if value is None:
            continue
        try:
            operation["params"]["value"] = np.round(
                np.asarray(value, dtype=float), decimals
            ).tolist()
        except (TypeError, ValueError):
            continue
    return update_patch


def build_direct_restyle_payload(update_patch):
    if not hasattr(update_patch, "to_plotly_json"):
        return update_patch
    return {
        "applyPath": "direct-restyle",
        "operations": update_patch.to_plotly_json().get("operations", []),
    }


# %% cache / session state ----------------------------------------------------
PEER_QUERY_TIMEOUT_SECONDS = 0.5

# The file open in this window, reported by the peer current-file endpoint.
# Process state, not the filesystem cache: cache entries persist across
# restarts of a slot, and a stale filepath would make peers refuse a file
# that is no longer open anywhere (Recipe 17).
_current_filepath = None


def set_current_filepath(filepath):
    global _current_filepath
    _current_filepath = filepath


def get_current_filepath():
    return _current_filepath


def _normalize_path(filepath):
    return os.path.normcase(os.path.normpath(os.path.abspath(filepath)))


def find_peer_session_with_file(filepath):
    """Return the port of a live app window that already has filepath open.

    Dead windows stop answering their port, so a crashed window's claim on a
    file evaporates with it; no lock files are involved. Anything else bound
    to a peer port is ignored unless it identifies as this app.
    """
    target = _normalize_path(filepath)
    for port in PEER_PORTS:
        url = f"http://127.0.0.1:{port}/_ts_app/current-file"
        try:
            with urlopen(url, timeout=PEER_QUERY_TIMEOUT_SECONDS) as response:
                payload = json.load(response)
        except (OSError, ValueError):
            continue
        if not isinstance(payload, dict) or payload.get("app") != "ts_app":
            continue
        peer_file = payload.get("filepath")
        if peer_file and _normalize_path(peer_file) == target:
            return port
    return None


def clear_temp_artifacts(keep_stem):
    for temp_file in TEMP_PATH.iterdir():
        if temp_file.suffix in (".npz", ".csv") and temp_file.stem != keep_stem:
            try:
                temp_file.unlink()
            except OSError:
                pass


def initialize_state(filepath):
    set_current_filepath(filepath)
    cache.set("filepath", filepath)
    prev_filename = cache.get("filename")
    filename = Path(filepath).stem
    if prev_filename is None or prev_filename != filename:
        cache.set("labels_history", deque(maxlen=2))
    cache.set("filename", filename)
    clear_temp_artifacts(filename)
    clear_fig_resamplers()


def recording_metadata(recording):
    start = float(recording.get("start_time", 0.0))
    return {
        "start_time": start,
        "end_time": start + recording_duration(recording),
        "frame_rate": float(recording.get("frame_rate", 1.0)),
    }


# %% Flask routes (lowest-latency data paths) ---------------------------------
@app.server.get("/_ts_app/current-file")
def current_file():
    """Report which file this window has open, for peer same-file checks.

    Reads process state rather than the filesystem cache so a freshly
    restarted window never reports the previous run's file (Recipe 17).
    """
    return {"app": "ts_app", "filepath": get_current_filepath() or ""}


@app.server.get("/_ts_app/resample")
def resample_graph_data():
    """Return a resampler data patch for a given x-range, for direct browser
    restyle (used by the auto-pan live refresh, Recipe 13)."""
    try:
        x0 = float(request.args["x0"])
        x1 = float(request.args["x1"])
    except (KeyError, TypeError, ValueError):
        abort(400)
    if not np.isfinite(x0) or not np.isfinite(x1) or x0 == x1:
        abort(400)

    fig = get_fig_resampler()
    if fig is None:
        abort(404)

    key = shared_axis_key(fig)
    x_range = clamp_x_range_to_bounds(x0, x1, fig_x_bounds(fig))
    update_patch = fig.construct_update_data_patch(
        {f"{key}.range[0]": x_range[0], f"{key}.range[1]": x_range[1]}
    )
    update_patch = compact_resampler_patch(update_patch)
    patch_json = (
        update_patch.to_plotly_json()
        if hasattr(update_patch, "to_plotly_json")
        else update_patch
    )
    payload = json.dumps(patch_json, cls=PlotlyJSONEncoder, separators=(",", ":"))
    return app.server.response_class(
        payload, mimetype="application/json", headers={"Cache-Control": "no-store"}
    )


@app.server.post("/_ts_app/profile-log")
def browser_profile_log():
    if not PROFILE_NAVIGATION:
        return ("", 204)
    payload = request.get_json(silent=True) or {}
    event = payload.get("event", "browser")
    details = [f"{k}={v}" for k, v in payload.items() if k != "event" and v is not None]
    print(f"[{event}] " + ", ".join(details), flush=True)
    return ("", 204)


# %% clientside callbacks (instant browser interactions) ----------------------

# switch_mode: 'm' toggles navigate (pan) <-> annotate (select)
app.clientside_callback(
    """
    function(n_events, event, figure) {
        const no_update = dash_clientside.no_update;
        if (!event || !figure) return [no_update, no_update];
        const key = event.key;
        if (key !== "m" && key !== "M") return [no_update, no_update];

        const patched = new dash_clientside.Patch;
        if (figure.layout.dragmode === "pan") {
            patched.assign(["layout", "dragmode"], "select");
            return [patched.build(), "Annotate mode: drag or click to select, then press 1-4."];
        }
        patched.assign(["layout", "selections"], null);
        patched.assign(["layout", "shapes"], null);
        patched.assign(["layout", "dragmode"], "pan");
        return [patched.build(), "Navigate mode: drag to pan, scroll to zoom, arrow keys to step."];
    }
    """,
    Output("graph", "figure"),
    Output("annotation-message", "children"),
    Input("keyboard", "n_events"),
    State("keyboard", "event"),
    State("graph", "figure"),
)

# pan_figure: arrow keys step the view; refresh is scheduled through the coalescer
clientside_callback(
    """
    function(n_events, event, relayout, figure) {
        const no_update = dash_clientside.no_update;
        if (!event || !figure) return [no_update, no_update];
        const meta = figure.layout.meta || {};
        const xkey = meta.sharedXAxisKey || "xaxis";
        let range = (figure.layout[xkey] || {}).range;
        if (relayout && relayout[xkey + ".range[0]"] !== undefined && relayout[xkey + ".range[1]"] !== undefined) {
            range = [relayout[xkey + ".range[0]"], relayout[xkey + ".range[1]"]];
        }
        if (!range) return [no_update, no_update];

        const x0 = range[0], x1 = range[1], w = x1 - x0;
        let next = null;
        if (event.key === "ArrowRight") next = [x0 + w * 0.3, x1 + w * 0.3];
        else if (event.key === "ArrowLeft") next = [x0 - w * 0.3, x1 - w * 0.3];
        if (!next) return [no_update, no_update];

        const patched = new dash_clientside.Patch;
        patched.assign(["layout", xkey, "range"], next);
        const nextRelayout = { ...(relayout || {}) };
        nextRelayout[xkey + ".range[0]"] = next[0];
        nextRelayout[xkey + ".range[1]"] = next[1];
        if (window.tsAppGraphRelayout) {
            window.tsAppGraphRelayout.request(nextRelayout, "keyboard");
        }
        return [patched.build(), nextRelayout];
    }
    """,
    Output("graph", "figure", allow_duplicate=True),
    Output("graph", "relayoutData"),
    Input("keyboard", "n_events"),
    State("keyboard", "event"),
    State("graph", "relayoutData"),
    State("graph", "figure"),
    prevent_initial_call=True,
)

# apply a direct Plotly.restyle payload in the browser (Recipe 8)
clientside_callback(
    """
    function(payload) {
        if (!payload) return dash_clientside.no_update;
        if (!window.tsAppDirectRestyle) {
            return { ok: false, error: "tsAppDirectRestyle asset not loaded", timeStamp: Date.now() };
        }
        try {
            const result = window.tsAppDirectRestyle.apply(payload);
            return { ...result, timeStamp: Date.now() };
        } catch (error) {
            return { ok: false, error: String(error), timeStamp: Date.now() };
        }
    }
    """,
    Output("graph-direct-restyle-status-store", "data"),
    Input("graph-direct-restyle-payload-store", "data"),
    prevent_initial_call=True,
)

# clear_display: wipe the status line after the one-shot interval elapses
clientside_callback(
    """
    function(n_intervals) { return n_intervals === 5 ? "" : dash_clientside.no_update; }
    """,
    Output("annotation-message", "children", allow_duplicate=True),
    Input("interval-component", "n_intervals"),
    prevent_initial_call=True,
)

# read_box_select: Plotly box selection -> [start, end] seconds in box-select-store
app.clientside_callback(
    """
    function(selectedData, figure, metadata) {
        const no_update = dash_clientside.no_update;
        if (!figure || !metadata) return [no_update, no_update, no_update];
        const selections = figure.layout.selections;
        if (!selections || selections.length === 0) return [no_update, no_update, no_update];

        const patched = new dash_clientside.Patch;
        if (selections.length > 1) patched.assign(["layout", "selections"], [selections[selections.length - 1]]);
        patched.assign(["layout", "shapes"], null);

        const sel = selections[selections.length - 1];
        let start = Math.min(sel.x0, sel.x1), end = Math.max(sel.x0, sel.x1);
        const t0 = metadata.start_time, t1 = metadata.end_time;
        if (end < t0 || start > t1) return [[], patched.build(), `Out of range. Select between ${t0} and ${t1}.`];

        let sr = Math.round(start), er = Math.round(end);
        sr = Math.max(sr, t0); er = Math.min(er, t1);
        if (sr === er) {
            if (sr - start > end - er) { er = Math.ceil(start); sr = Math.floor(start); }
            else { er = Math.ceil(end); sr = Math.floor(end); }
        }
        const fs = sr - t0, fe = er - t0;
        return [[fs, fe], patched.build(), `Selected [${fs}, ${fe}] (${fe - fs} s). Press 1-4 to label.`];
    }
    """,
    Output("box-select-store", "data"),
    Output("graph", "figure", allow_duplicate=True),
    Output("annotation-message", "children", allow_duplicate=True),
    Input("graph", "selectedData"),
    State("graph", "figure"),
    State("recording-meta-store", "data"),
    prevent_initial_call=True,
)

# read_annotation_auto_pan_select: finished custom drag/click (from annotationAutoPan.js)
app.clientside_callback(
    """
    function(n_events, event, figure, metadata) {
        const no_update = dash_clientside.no_update;
        if (!n_events || !event || !figure || !metadata) return [no_update, no_update, no_update];
        if (figure.layout.dragmode !== "select") return [no_update, no_update, no_update];

        const rawX0 = Number(event["detail.x0"]), rawX1 = Number(event["detail.x1"]);
        if (!Number.isFinite(rawX0) || !Number.isFinite(rawX1) || rawX0 === rawX1) return [no_update, no_update, no_update];

        const t0 = Number(metadata.start_time), t1 = Number(metadata.end_time);
        let start = Math.min(rawX0, rawX1), end = Math.max(rawX0, rawX1);
        const patched = new dash_clientside.Patch;
        patched.assign(["layout", "selections"], null);

        if (end < t0 || start > t1) {
            patched.assign(["layout", "shapes"], null);
            return [[], patched.build(), `Out of range. Select between ${t0} and ${t1}.`];
        }

        let sr = Math.round(start), er = Math.round(end);
        if (sr === er) {
            if (sr - start > end - er) { er = Math.ceil(start); sr = Math.floor(start); }
            else { er = Math.ceil(end); sr = Math.floor(end); }
        }
        sr = Math.max(sr, t0); er = Math.min(er, t1);
        if (er <= sr) { if (sr < t1) er = sr + 1; else if (er > t0) sr = er - 1; }
        sr = Math.max(sr, t0); er = Math.min(er, t1);
        if (er <= sr) {
            patched.assign(["layout", "shapes"], null);
            return [[], patched.build(), `Out of range. Select between ${t0} and ${t1}.`];
        }

        let y0 = Number(event["detail.y0"]), y1 = Number(event["detail.y1"]);
        if (!Number.isFinite(y0) || !Number.isFinite(y1)) { y0 = -30; y1 = 30; }

        const box = {
            type: "rect", xref: event["detail.xref"] || "x", yref: event["detail.yref"] || "y",
            x0: sr, x1: er, y0: y0, y1: y1,
            fillcolor: "rgba(99, 110, 250, 0.14)",
            line: { color: "rgba(99, 110, 250, 0.95)", width: 1, dash: "dot" }, layer: "above"
        };
        patched.assign(["layout", "shapes"], [box]);
        const fs = sr - t0, fe = er - t0;
        return [[fs, fe], patched.build(), `Selected [${fs}, ${fe}] (${fe - fs} s). Press 1-4 to label.`];
    }
    """,
    Output("box-select-store", "data", allow_duplicate=True),
    Output("graph", "figure", allow_duplicate=True),
    Output("annotation-message", "children", allow_duplicate=True),
    Input("graph-annotation-select", "n_events"),
    State("graph-annotation-select", "event"),
    State("graph", "figure"),
    State("recording-meta-store", "data"),
    prevent_initial_call=True,
)

# read_click_select: a bare click selects a small neighborhood
app.clientside_callback(
    """
    function(clickData, figure, metadata) {
        const no_update = dash_clientside.no_update;
        if (!figure || !metadata) return [no_update, no_update, no_update];

        const patched = new dash_clientside.Patch;
        patched.assign(["layout", "shapes"], null);
        if (!clickData || figure.layout.dragmode === "pan") return [[], patched.build(), ""];
        patched.assign(["layout", "selections"], null);

        const meta = figure.layout.meta || {};
        const xkey = meta.sharedXAxisKey || "xaxis";
        const xClick = clickData.points[0].x;
        const range = (figure.layout[xkey] || {}).range || [metadata.start_time, metadata.end_time];
        const delta = (range[1] - range[0]) * 0.005;
        const t0 = metadata.start_time, t1 = metadata.end_time;
        const x0 = Math.floor(xClick - delta / 2), x1 = Math.ceil(xClick + delta / 2);

        const trace = figure.data[clickData.points[0].curveNumber] || {};
        const box = {
            type: "rect", xref: trace.xaxis || meta.sharedXAxisId || "x",
            yref: trace.yaxis || "y", x0: x0, x1: x1, y0: -30, y1: 30,
            line: { width: 1, dash: "dot" }
        };
        patched.assign(["layout", "shapes"], [box]);
        const fs = Math.max(x0, t0) - t0, fe = Math.min(x1, t1) - t0;
        return [[fs, fe], patched.build(), `Selected [${fs}, ${fe}] (${fe - fs} s). Press 1-4 to label.`];
    }
    """,
    Output("box-select-store", "data", allow_duplicate=True),
    Output("graph", "figure", allow_duplicate=True),
    Output("annotation-message", "children", allow_duplicate=True),
    Input("graph", "clickData"),
    State("graph", "figure"),
    State("recording-meta-store", "data"),
    prevent_initial_call=True,
)

# read_bout_context_select: right-click selects the whole contiguous same-label run
app.clientside_callback(
    """
    function(n_events, event, figure, metadata) {
        const no_update = dash_clientside.no_update;
        if (!event || !figure || !metadata) return [no_update, no_update, no_update];
        if (figure.layout.dragmode !== "select") return [no_update, no_update, no_update];

        const xClick = event["detail.x"];
        if (xClick === undefined || xClick === null || Number.isNaN(xClick)) return [no_update, no_update, no_update];

        const meta = figure.layout.meta || {};
        const fr = meta.frameRate || 1;
        const overlay = meta.overlayTraceIndices || [];
        const last = figure.data[overlay[overlay.length - 1]];
        const labels = last && last.z && last.z[0];
        if (!Array.isArray(labels) || labels.length === 0) return [no_update, no_update, no_update];

        const t0 = metadata.start_time, t1 = metadata.end_time;
        const clicked = Math.max(0, Math.min(labels.length - 1, Math.floor((xClick - t0) * fr)));
        const keyOf = (v) => (v === null || v === undefined || Number.isNaN(v)) ? "u" : String(v);
        const target = keyOf(labels[clicked]);
        let start = clicked, end = clicked + 1;
        while (start > 0 && keyOf(labels[start - 1]) === target) start -= 1;
        while (end < labels.length && keyOf(labels[end]) === target) end += 1;

        const absStart = Math.max(t0 + start / fr, t0), absEnd = Math.min(t0 + end / fr, t1);
        const yref = event["detail.yref"] || "y";
        const box = {
            type: "rect", xref: event["detail.xref"] || meta.sharedXAxisId || "x", yref: yref,
            x0: absStart, x1: absEnd, y0: -30, y1: 30, line: { width: 2, dash: "solid" }
        };
        const patched = new dash_clientside.Patch;
        patched.assign(["layout", "selections"], null);
        patched.assign(["layout", "shapes"], [box]);
        const fs = absStart - t0, fe = absEnd - t0;
        return [[fs, fe], patched.build(), `Selected segment [${fs}, ${fe}] (${fe - fs} s). Press 1-4 to label.`];
    }
    """,
    Output("box-select-store", "data", allow_duplicate=True),
    Output("graph", "figure", allow_duplicate=True),
    Output("annotation-message", "children", allow_duplicate=True),
    Input("graph-contextmenu", "n_events"),
    State("graph-contextmenu", "event"),
    State("graph", "figure"),
    State("recording-meta-store", "data"),
    prevent_initial_call=True,
)

# update_labels: repaint every overlay heatmap from a new label array
app.clientside_callback(
    """
    function(labels, figure) {
        const no_update = dash_clientside.no_update;
        if (!labels || !Array.isArray(labels) || !figure) return [no_update, no_update];
        const patched = new dash_clientside.Patch;
        const wrapped = [labels];
        const overlay = (figure.layout.meta && figure.layout.meta.overlayTraceIndices) || [];
        for (const idx of overlay) patched.assign(["data", idx, "z"], wrapped);
        patched.assign(["layout", "selections"], null);
        patched.assign(["layout", "shapes"], null);
        return [patched.build(), ""];
    }
    """,
    Output("graph", "figure", allow_duplicate=True),
    Output("annotation-message", "children", allow_duplicate=True),
    Input("updated-labels-store", "data"),
    State("graph", "figure"),
    prevent_initial_call=True,
)

# make_annotation: number keys write the selected class into the label array
app.clientside_callback(
    """
    function(n_events, event, box, figure) {
        const no_update = dash_clientside.no_update;
        if (!event || !box || box.length === 0 || !figure) return [no_update, no_update];
        if (figure.layout.dragmode !== "select") return [no_update, no_update];

        const meta = figure.layout.meta || {};
        const numClass = meta.numClass || 4;
        const fr = meta.frameRate || 1;
        const labelInt = parseInt(event.key, 10) - 1;
        if (!(labelInt >= 0 && labelInt < numClass)) return [no_update, no_update];

        const overlay = meta.overlayTraceIndices || [];
        const last = figure.data[overlay[overlay.length - 1]];
        const labels = [...last.z[0]];
        let start = Math.round(box[0] * fr), end = Math.round(box[1] * fr);
        start = Math.max(0, start); end = Math.min(labels.length, end);
        for (let i = start; i < end; i++) labels[i] = labelInt;
        return [labels, []];
    }
    """,
    Output("updated-labels-store", "data", allow_duplicate=True),
    Output("box-select-store", "data", allow_duplicate=True),
    Input("keyboard", "n_events"),
    State("keyboard", "event"),
    State("box-select-store", "data"),
    State("graph", "figure"),
    prevent_initial_call=True,
)


# %% server callbacks ---------------------------------------------------------
@app.callback(
    Output("data-upload-message", "children", allow_duplicate=True),
    Output("visualization-ready-store", "data", allow_duplicate=True),
    Input("demo-button", "n_clicks"),
    prevent_initial_call=True,
)
def load_demo(n_clicks):
    if not n_clicks:
        raise PreventUpdate
    recording = generate_synthetic_recording()
    demo_path = TEMP_PATH / "demo.npz"
    save_recording(recording, demo_path)
    initialize_state(str(demo_path))
    return "Generating visualization… this may take a few seconds.", "vis"


@app.callback(
    Output("data-upload-message", "children", allow_duplicate=True),
    Output("visualization-ready-store", "data", allow_duplicate=True),
    Input("open-button", "n_clicks"),
    prevent_initial_call=True,
)
def choose_file(n_clicks):
    if not n_clicks:
        raise PreventUpdate
    selected = open_file_dialog(("Recordings (*.npz)",))
    if selected is None:
        raise PreventUpdate
    if find_peer_session_with_file(selected) is not None:
        message = (
            f'"{Path(selected).name}" is already open in another {APP_TITLE} '
            "window. Please select a different file, or close it in the other "
            "window first."
        )
        return message, dash.no_update
    initialize_state(selected)
    return "Loading… this may take a few seconds.", "vis"


@app.callback(
    Output("data-upload-message", "children", allow_duplicate=True),
    Output("recording-meta-store", "data"),
    Input("visualization-ready-store", "data"),
    prevent_initial_call=True,
)
def create_visualization(ready):
    path = cache.get("filepath")
    filename = cache.get("filename")
    try:
        recording = load_recording(path)
    except (NotImplementedError, OSError, ValueError) as error:
        return f"Could not load file: {error}", {}

    labels_history = cache.get("labels_history")
    if labels_history:
        recording["labels"] = labels_history[-1]  # salvage unsaved work
    else:
        labels = get_padded_labels(recording)
        labels_history.append(labels)
        cache.set("labels_history", labels_history)

    fig = create_fig(recording, filename)
    components.graph.figure = fig
    return components.visualization_div, recording_metadata(recording)


RESAMPLER_CALLBACK_OUTPUT = (
    Output("graph-direct-restyle-payload-store", "data")
    if ENABLE_DIRECT_PLOTLY_RESTYLE
    else Output("graph", "figure", allow_duplicate=True)
)


@app.callback(
    RESAMPLER_CALLBACK_OUTPUT,
    Input("graph-relayout-coalesced", "n_events"),
    State("graph-relayout-coalesced", "event"),
    prevent_initial_call=True,
)
def update_fig_resampler(_n_events, relayout_event):
    """On a settled zoom/pan, recompute the visible slice and ship a patch."""
    if not relayout_event:
        return dash.no_update
    try:
        x0 = float(relayout_event.get("detail.x0"))
        x1 = float(relayout_event.get("detail.x1"))
    except (TypeError, ValueError):
        return dash.no_update

    fig = get_fig_resampler()
    if fig is None:
        return dash.no_update

    key = shared_axis_key(fig)
    started = time.perf_counter()
    update_patch = fig.construct_update_data_patch(
        {f"{key}.range[0]": min(x0, x1), f"{key}.range[1]": max(x0, x1)}
    )
    update_patch = compact_resampler_patch(update_patch)

    if PROFILE_NAVIGATION:
        print(
            f"[resampler] x_width={abs(x1 - x0):.1f}s "
            f"construct={(time.perf_counter() - started) * 1000:.1f}ms",
            flush=True,
        )

    if ENABLE_DIRECT_PLOTLY_RESTYLE:
        return build_direct_restyle_payload(update_patch)
    return update_patch


@app.callback(
    Output("graph", "figure", allow_duplicate=True),
    Input("n-sample-dropdown", "value"),
    prevent_initial_call=True,
)
def change_sampling_level(sampling_level):
    if sampling_level is None:
        return dash.no_update
    n_samples = SAMPLING_LEVELS[sampling_level]
    recording = load_recording(cache.get("filepath"))
    labels_history = cache.get("labels_history")
    if labels_history:
        recording["labels"] = labels_history[-1]
    fig = create_fig(recording, cache.get("filename"), n_shown_samples=n_samples)
    return fig


@app.callback(
    Output("updated-labels-store", "data", allow_duplicate=True),
    Output("undo-button", "style"),
    Input("undo-button", "n_clicks"),
    prevent_initial_call=True,
)
def undo_annotation(n_clicks):
    if not n_clicks:
        raise PreventUpdate
    labels_history = cache.get("labels_history")
    labels = labels_history[0]
    labels_history.pop()
    cache.set("labels_history", labels_history)
    return np.asarray(labels, dtype=float).tolist(), {"visibility": "hidden"}


@app.callback(
    Output("undo-button", "style", allow_duplicate=True),
    Input("updated-labels-store", "data"),
    prevent_initial_call=True,
)
def update_labels_history(updated_labels):
    hidden = {"visibility": "hidden"}
    if not updated_labels:
        return hidden
    labels_history = cache.get("labels_history")
    updated = np.asarray(updated_labels, dtype=float)
    if np.array_equal(np.asarray(labels_history[-1], dtype=float), updated, equal_nan=True):
        return hidden
    labels_history.append(updated)
    cache.set("labels_history", labels_history)
    return {"visibility": "visible"}


@app.callback(
    Output("annotation-message", "children", allow_duplicate=True),
    Output("interval-component", "max_intervals"),
    Input("save-button", "n_clicks"),
    prevent_initial_call=True,
)
def save_labels(n_clicks):
    if not n_clicks:
        raise PreventUpdate

    filename = cache.get("filename")
    recording = load_recording(cache.get("filepath"))
    metadata = recording_metadata(recording)

    labels_history = cache.get("labels_history")
    labels_display = labels_history[-1] if labels_history else get_padded_labels(recording)
    labels = labels_for_saving(labels_display)
    recording["labels"] = labels

    temp_npz = TEMP_PATH / f"{filename}_labeled.npz"
    save_recording(recording, temp_npz)

    save_path = save_file_dialog(("Recordings (*.npz)",), f"{filename}_labeled.npz")
    if not save_path:
        return "Save canceled.", 5
    shutil.copy(temp_npz, save_path)
    message = f"Saved labeled recording to {save_path}."

    # Export a segment table too, when fully labeled.
    unscored = first_unscored_segment(
        labels_display, metadata["frame_rate"], metadata["start_time"]
    )
    if unscored is None:
        segments = get_segments(labels, metadata["frame_rate"], metadata["start_time"])
        temp_csv = TEMP_PATH / f"{filename}_segments.csv"
        segments.to_csv(temp_csv, index=False)
        csv_path = save_file_dialog(("CSV (*.csv)",), f"{filename}_segments.csv")
        if csv_path:
            shutil.copy(temp_csv, csv_path)
            message += f"\nSaved segment table to {csv_path}."
    else:
        message += (
            f"\nUnscored region [{unscored['start']}, {unscored['end']}]"
            f" ({unscored['duration']} s) — label everything to export the segment table."
        )
    return message, 5
