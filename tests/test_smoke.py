# -*- coding: utf-8 -*-
"""Smoke tests for the template: data contract, figure/meta wiring, the
resampler patch path, save/load round-trip, and label helpers."""

import numpy as np

from ts_app.data import (
    generate_synthetic_recording,
    load_recording,
    num_frames,
    recording_duration,
    save_recording,
)
from ts_app.figure import build_figure
from ts_app.labels import (
    first_unscored_segment,
    get_padded_labels,
    get_segments,
    labels_for_saving,
)


def _small_recording(**kwargs):
    params = dict(duration_s=90, sample_rate=32, num_channels=3, seed=3)
    params.update(kwargs)
    return generate_synthetic_recording(**params)


def test_app_imports_and_registers_callbacks():
    import ts_app.app as app_module

    assert len(app_module.app.callback_map) > 10
    rules = {str(r) for r in app_module.app.server.url_map.iter_rules()}
    assert "/_ts_app/resample" in rules
    assert "/_ts_app/profile-log" in rules


def test_synthetic_recording_contract():
    recording = _small_recording(num_channels=3)
    assert len(recording["channels"]) == 3
    for channel in recording["channels"]:
        assert channel["values"].ndim == 1
        assert channel["values"].size > 0
        assert channel["sample_rate"] > 0
    assert num_frames(recording) == recording_duration(recording)


def test_figure_meta_and_overlay_indices():
    recording = _small_recording(num_channels=4)
    fig = build_figure(recording, "demo", n_shown_samples=1024)
    meta = fig.layout.meta
    # 4 channels -> shared bottom axis is x4/xaxis4.
    assert meta["sharedXAxisKey"] == "xaxis4"
    assert meta["sharedXAxisId"] == "x4"
    # Overlays are the last n_rows traces.
    n_rows = len(recording["channels"])
    assert meta["overlayTraceIndices"] == list(
        range(len(fig.data) - n_rows, len(fig.data))
    )
    assert meta["numClass"] == 4
    assert meta["xBounds"][0] < meta["xBounds"][1]


def test_resampler_patch_produces_operations():
    recording = _small_recording()
    fig = build_figure(recording, "demo", n_shown_samples=1024)
    key = fig.layout.meta["sharedXAxisKey"]
    patch = fig.construct_update_data_patch(
        {f"{key}.range[0]": 5.0, f"{key}.range[1]": 25.0}
    )
    assert patch.to_plotly_json().get("operations")


def test_npz_roundtrip_preserves_data():
    recording = _small_recording()
    recording["labels"] = np.array([0, 1, 2, 3, 0], dtype=float)
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "rec.npz"
        save_recording(recording, path)
        loaded = load_recording(str(path))
    assert len(loaded["channels"]) == len(recording["channels"])
    assert loaded["channels"][0]["name"] == recording["channels"][0]["name"]
    np.testing.assert_allclose(
        loaded["channels"][0]["values"], recording["channels"][0]["values"]
    )
    np.testing.assert_array_equal(loaded["labels"], recording["labels"])


def test_padding_and_saving_sentinels():
    recording = _small_recording(prefill_labels=False)
    padded = get_padded_labels(recording)
    assert padded.size == num_frames(recording)
    assert np.isnan(padded).all()  # unscored -> NaN for display
    saved = labels_for_saving(padded)
    assert (saved == -1).all()  # NaN -> on-disk sentinel


def test_segments_and_first_unscored():
    labels = np.array([0, 0, 1, 1, 1, np.nan, np.nan], dtype=float)
    segments = get_segments(labels, frame_rate=1.0, start_time=0.0)
    assert list(segments["class"]) == ["A", "B", "unscored"]
    assert list(segments["duration_s"]) == [2.0, 3.0, 2.0]
    unscored = first_unscored_segment(labels)
    assert unscored == {"start": 5.0, "end": 7.0, "duration": 2.0}


def test_smoke_entrypoint():
    import run_desktop_app

    assert run_desktop_app.main(["--smoke"]) == 0
