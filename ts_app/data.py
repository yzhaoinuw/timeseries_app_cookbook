# -*- coding: utf-8 -*-
"""The recording contract, a synthetic generator, and a pluggable loader.

A *recording* is the one data structure the whole app understands. It is
deliberately domain-neutral::

    recording = {
        "channels": [
            {"name": str, "values": 1-D np.ndarray (float), "sample_rate": float},
            ...
        ],
        "labels": Optional[1-D np.ndarray],  # one int class per label frame,
                                             # UNSCORED_SENTINEL where unlabeled,
                                             # or None when nothing is labeled yet
        "frame_rate": float,                 # label frames per second (e.g. 1.0)
        "start_time": float,                 # x-axis origin, in seconds
    }

To adapt the app to real data, implement :func:`load_recording` for your format
so it returns this dict. Nothing downstream cares where the numbers came from.
"""

import math

import numpy as np

from ts_app.config import (
    LABEL_FRAME_RATE,
    SYNTHETIC_DURATION_S,
    SYNTHETIC_NUM_CHANNELS,
    SYNTHETIC_SAMPLE_RATE,
    SYNTHETIC_SEED,
    UNSCORED_SENTINEL,
)


def recording_duration(recording) -> int:
    """Whole-second duration spanned by the longest channel."""
    end = 0
    for channel in recording["channels"]:
        values = channel["values"]
        sample_rate = float(channel["sample_rate"])
        if values.size and sample_rate > 0:
            end = max(end, math.ceil((values.size - 1) / sample_rate))
    return int(end)


def num_frames(recording) -> int:
    """Number of label frames covering the recording at ``frame_rate``."""
    frame_rate = float(recording.get("frame_rate", LABEL_FRAME_RATE))
    return int(math.ceil(recording_duration(recording) * frame_rate))


def _synthetic_signal(kind, time, rng):
    """Return one channel's samples with a distinct visual character so
    navigation and zoom show something interesting at every scale."""
    n = time.size
    if kind == 0:
        # Fast oscillation + slow amplitude modulation + noise.
        envelope = 1.0 + 0.6 * np.sin(2 * np.pi * time / 240.0)
        signal = envelope * (
            np.sin(2 * np.pi * 6.0 * time) + 0.5 * np.sin(2 * np.pi * 11.0 * time)
        )
        signal += 0.3 * rng.standard_normal(n)
        signal *= 40.0
    elif kind == 1:
        # Quiet baseline punctuated by random high-amplitude bursts.
        signal = 0.2 * rng.standard_normal(n)
        burst_starts = rng.integers(0, n, size=max(1, n // 200_000))
        for start in burst_starts:
            width = int(rng.integers(2_000, 20_000))
            end = min(n, start + width)
            signal[start:end] += rng.uniform(3, 8) * np.sin(
                2 * np.pi * 30.0 * time[start:end]
            )
        signal *= 25.0
    else:
        # Slow drift with occasional transients.
        signal = np.cumsum(rng.standard_normal(n)) / math.sqrt(n) * 30.0
        signal += 0.15 * rng.standard_normal(n)

    return signal.astype(float)


def _prefill_labels(n, rng, num_class):
    """Blocky pseudo-ground-truth so the overlay looks alive on load."""
    labels = np.empty(n, dtype=float)
    index = 0
    while index < n:
        block = int(rng.integers(30, 300))
        labels[index : index + block] = int(rng.integers(0, num_class))
        index += block
    return labels


def generate_synthetic_recording(
    duration_s=SYNTHETIC_DURATION_S,
    sample_rate=SYNTHETIC_SAMPLE_RATE,
    num_channels=SYNTHETIC_NUM_CHANNELS,
    seed=SYNTHETIC_SEED,
    frame_rate=LABEL_FRAME_RATE,
    prefill_labels=True,
    num_class=4,
) -> dict:
    """Return a multi-channel recording with millions of points and no files.

    With the defaults (3 channels, 256 Hz, 1 hour) this is ~2.7M samples, enough
    to make the resampler earn its keep.
    """
    rng = np.random.default_rng(seed)
    n = int(round(duration_s * sample_rate))
    time = np.arange(n) / sample_rate

    names = [f"Channel {chr(ord('A') + i)}" for i in range(num_channels)]
    channels = []
    for i, name in enumerate(names):
        values = _synthetic_signal(i % 3, time, rng)
        channels.append(
            {"name": name, "values": values, "sample_rate": float(sample_rate)}
        )

    n_frame = int(math.ceil((n - 1) / sample_rate * frame_rate))
    labels = _prefill_labels(n_frame, rng, num_class) if prefill_labels else None

    return {
        "channels": channels,
        "labels": labels,
        "frame_rate": float(frame_rate),
        "start_time": 0.0,
    }


def save_recording(recording, path) -> None:
    """Persist a recording to a ``.npz`` (the example format this template reads)."""
    payload = {
        "frame_rate": np.asarray(recording.get("frame_rate", LABEL_FRAME_RATE)),
        "start_time": np.asarray(recording.get("start_time", 0.0)),
        "num_channels": np.asarray(len(recording["channels"])),
    }
    labels = recording.get("labels")
    payload["labels"] = (
        np.asarray(labels, dtype=float) if labels is not None else np.array([])
    )
    for i, channel in enumerate(recording["channels"]):
        payload[f"ch{i}_name"] = np.asarray(channel["name"])
        payload[f"ch{i}_values"] = np.asarray(channel["values"], dtype=float)
        payload[f"ch{i}_rate"] = np.asarray(float(channel["sample_rate"]))
    np.savez_compressed(path, **payload)


def load_recording(path) -> dict:
    """Load a recording from disk and return the recording contract.

    This template only knows how to read the ``.npz`` layout written by
    :func:`save_recording`. **This is the function to replace** when adapting to
    a real format (EDF, WAV, Parquet, CSV, a database query, ...): parse your
    file and return the dict documented at the top of this module. Everything
    else in the app is format-agnostic.
    """
    path = str(path)
    if not path.lower().endswith(".npz"):
        raise NotImplementedError(
            "load_recording only reads .npz in this template. Replace this "
            "function to parse your own format and return the recording dict "
            "documented in data.py."
        )

    with np.load(path, allow_pickle=False) as data:
        num_channels = int(data["num_channels"])
        channels = []
        for i in range(num_channels):
            channels.append(
                {
                    "name": str(data[f"ch{i}_name"]),
                    "values": np.asarray(data[f"ch{i}_values"], dtype=float),
                    "sample_rate": float(data[f"ch{i}_rate"]),
                }
            )
        labels = np.asarray(data["labels"], dtype=float)
        if labels.size == 0:
            labels = None
        return {
            "channels": channels,
            "labels": labels,
            "frame_rate": float(data["frame_rate"]),
            "start_time": float(data["start_time"]),
        }


def x_bounds(recording):
    """[start, end] wall-clock seconds spanned by the recording, or None."""
    start = float(recording.get("start_time", 0.0))
    end = start + recording_duration(recording)
    if not (math.isfinite(start) and math.isfinite(end)) or end <= start:
        return None
    return [start, end]


# Keep the sentinel importable from here too, so callers have one place to look.
__all__ = [
    "recording_duration",
    "num_frames",
    "generate_synthetic_recording",
    "save_recording",
    "load_recording",
    "x_bounds",
    "UNSCORED_SENTINEL",
]
