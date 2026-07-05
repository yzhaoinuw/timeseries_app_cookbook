# -*- coding: utf-8 -*-
"""Label-array helpers: padding, contiguous-segment extraction, and export.

The label array is *the* annotation state — one integer class per label frame.
The figure renders it as a heatmap overlay; these helpers keep it the right
length and turn it into human-readable segments for export.
"""

import numpy as np
import pandas as pd

from ts_app.config import CLASS_LABELS, LABEL_FRAME_RATE, UNSCORED_SENTINEL
from ts_app.data import num_frames


def get_padded_labels(recording) -> np.ndarray:
    """Return a float label array exactly ``num_frames`` long.

    Missing/short label arrays are padded with NaN (unscored); a longer array is
    truncated. NaN renders transparent in the overlay.
    """
    n_frame = num_frames(recording)
    labels = recording.get("labels")
    if labels is None or np.size(labels) == 0:
        padded = np.full(n_frame, np.nan)
        return padded

    padded = np.asarray(labels, dtype=float).ravel()
    # On-disk sentinel -> NaN for display.
    np.place(padded, padded == UNSCORED_SENTINEL, [np.nan])
    if padded.size < n_frame:
        padded = np.pad(
            padded, (0, n_frame - padded.size), "constant", constant_values=np.nan
        )
    elif padded.size > n_frame:
        padded = padded[:n_frame]
    return padded


def labels_for_saving(labels) -> np.ndarray:
    """Convert a display label array (NaN/None for unscored) to on-disk ints."""
    arr = np.asarray(labels, dtype=float)
    np.place(arr, arr == None, [UNSCORED_SENTINEL])  # noqa: E711 (cache None round-trip)
    arr = np.nan_to_num(arr, nan=UNSCORED_SENTINEL)
    return arr.astype(int)


def get_segments(labels, frame_rate=LABEL_FRAME_RATE, start_time=0.0) -> pd.DataFrame:
    """Collapse a per-frame label array into contiguous [start, end) segments."""
    arr = np.asarray(labels, dtype=float)
    rows = []
    if arr.size:
        # Collapse every unscored frame (NaN/sentinel) to one key value so a run
        # of unscored frames stays a single segment (NaN != NaN otherwise splits).
        key = arr.copy()
        key[~np.isfinite(key)] = UNSCORED_SENTINEL
        boundaries = np.where(np.diff(key) != 0)[0] + 1
        starts = np.concatenate(([0], boundaries))
        ends = np.concatenate((boundaries, [arr.size]))
        for start, end in zip(starts, ends):
            value = arr[start]
            label_name = "unscored"
            if np.isfinite(value) and int(value) != UNSCORED_SENTINEL:
                index = int(value)
                label_name = (
                    CLASS_LABELS[index] if 0 <= index < len(CLASS_LABELS) else str(index)
                )
            rows.append(
                {
                    "start_s": start_time + start / frame_rate,
                    "end_s": start_time + end / frame_rate,
                    "duration_s": (end - start) / frame_rate,
                    "class": label_name,
                }
            )
    return pd.DataFrame(rows, columns=["start_s", "end_s", "duration_s", "class"])


def first_unscored_segment(labels, frame_rate=LABEL_FRAME_RATE, start_time=0.0):
    """Return the first unscored [start, end] region (seconds), or None."""
    arr = np.asarray(labels, dtype=float)
    unscored = ~np.isfinite(arr) | (arr == UNSCORED_SENTINEL)
    if not unscored.any():
        return None
    first = int(np.argmax(unscored))
    end = first
    while end < arr.size and unscored[end]:
        end += 1
    return {
        "start": start_time + first / frame_rate,
        "end": start_time + end / frame_rate,
        "duration": (end - first) / frame_rate,
    }
