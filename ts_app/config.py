# -*- coding: utf-8 -*-
"""Central configuration for the template app.

Everything a new app is likely to re-tune lives here: window chrome, the class
set used for annotation, colors, the resampler sample budget, and the feature
flags that gate the fast-navigation paths. Keeping these in one module is the
single most important adaptation surface — most domain changes touch only this
file plus ``data.py``.
"""

import os

# %% Desktop window (pywebview)
APP_TITLE = "Time Series Annotator"
WINDOW_CONFIG = {
    "width": 1600,
    "height": 1000,
    "min_size": (1200, 800),
    "resizable": True,
}
# The port slot range (BASE_PORT, MAX_SESSIONS) lives in run_desktop_app.py:
# it must be known before ts_app is imported, so it can't live here.

# %% Annotation classes
# The overlay is one integer class per label frame. Change these lists to your
# own label set; keep CLASS_KEYS aligned 1:1 with CLASS_LABELS/CLASS_COLORS.
CLASS_LABELS = ["A", "B", "C", "D"]
CLASS_KEYS = ["1", "2", "3", "4"]  # keyboard keys that apply each class
CLASS_COLORS = [
    "rgb(124, 124, 251)",  # A — blue
    "rgb(251, 124, 124)",  # B — red
    "rgb(123, 251, 123)",  # C — green
    "rgb(255, 255, 0)",    # D — yellow
]
OVERLAY_OPACITY = 1.0
UNSCORED_SENTINEL = -1  # on-disk value for "not yet labeled"; shown transparent

# %% Figure appearance / behavior
CHANNEL_LINE_COLOR = "black"
DEFAULT_N_SHOWN_SAMPLES = 2048  # points per trace the resampler keeps on screen
SAMPLING_LEVELS = {"x0.5": 1024, "x1": 2048, "x2": 4096, "x4": 8192}
RANGE_QUANTILE = 0.9999          # clip y-range to this quantile to ignore outliers
RANGE_PADDING_PERCENT = 0.2      # extra headroom above/below the y-range
HEATMAP_HEIGHT = 1_000_000       # overlay cell half-height; large enough to fill any y-range

# %% Fast-navigation paths (see COOKBOOK recipes 7-8)
# Direct restyle bypasses Dash's figure diff and calls Plotly.restyle in the
# browser. Start False (simpler) and flip True once navigation works.
ENABLE_DIRECT_PLOTLY_RESTYLE = True

# %% Synthetic demo data (see data.py). Runs with zero external files.
SYNTHETIC_DURATION_S = 3600.0
SYNTHETIC_SAMPLE_RATE = 256.0
SYNTHETIC_NUM_CHANNELS = 3
SYNTHETIC_SEED = 0
LABEL_FRAME_RATE = 1.0  # label frames per second (1 Hz = one class per second)

# %% Profiling (off by default; opt in with env var)
PROFILE_NAVIGATION = os.environ.get("TS_APP_PROFILE_NAV", "0") == "1"

# %% Multi-session (see COOKBOOK recipe 17)
# run_desktop_app.py claims a window slot (one port per app window) and
# exports these env vars before ts_app is imported. Direct imports (tests,
# scripts, --smoke) see no env vars and default to slot 0 with no peers —
# exactly the single-window behavior.


def _read_instance_slot():
    try:
        return max(0, int(os.environ.get("TS_APP_INSTANCE_SLOT", "0")))
    except ValueError:
        return 0


def _read_peer_ports():
    ports = []
    for token in os.environ.get("TS_APP_PEER_PORTS", "").split(","):
        token = token.strip()
        if token.isdigit():
            ports.append(int(token))
    return ports


INSTANCE_SLOT = _read_instance_slot()
PEER_PORTS = _read_peer_ports()

if INSTANCE_SLOT > 0:
    # Profiling stays on the first window only; later windows would
    # interleave their output with the first window's stream.
    PROFILE_NAVIGATION = False
