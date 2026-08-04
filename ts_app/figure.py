# -*- coding: utf-8 -*-
"""Build the interactive figure: one row per channel, a shared x-axis, and an
annotation heatmap overlay on every row.

Two design choices make the whole interaction layer simple:

1. **One shared x-axis.** Every trace is forced onto the bottom row's x-axis, so
   pan/zoom/crosshair stay synchronized across rows. Its layout key (e.g.
   ``"xaxis3"``) is written into ``layout.meta.sharedXAxisKey`` so the browser
   scripts don't hardcode an axis number — change the channel count and the JS
   still works.
2. **The overlay is a heatmap.** The label array (one int class per frame) is
   drawn as a ``go.Heatmap`` added *last* on each row. Its trace indices go into
   ``layout.meta.overlayTraceIndices`` so annotation code patches exactly those
   traces without guessing.

Notes
-----
- A heatmap needs a 2-D ``z`` (shape ``(1, N)``), never ``(N,)``.
- ``y0`` is the *center* of the single heatmap row and ``dy`` its full height, so
  a large ``dy`` centered at 0 fills any symmetric y-range.
"""

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from plotly_resampler import FigureResampler
from plotly_resampler.aggregation import MinMaxLTTB

from ts_app.config import (
    CHANNEL_LINE_COLOR,
    CLASS_COLORS,
    CLASS_LABELS,
    DEFAULT_N_SHOWN_SAMPLES,
    HEATMAP_HEIGHT,
    OVERLAY_OPACITY,
    RANGE_PADDING_PERCENT,
    RANGE_QUANTILE,
)
from ts_app.data import recording_duration, x_bounds
from ts_app.labels import get_padded_labels


def _discrete_colorscale(num_class):
    """Even discrete colorscale mapping class 0..num_class-1 to CLASS_COLORS."""
    colors = CLASS_COLORS[:num_class]
    if num_class == 1:
        return [[0, colors[0]], [1, colors[0]]]
    stops = []
    for i, color in enumerate(colors):
        stops.append([i / (num_class - 1), color])
    return stops


def _symmetric_range(values):
    lower = np.nanquantile(values, 1 - RANGE_QUANTILE)
    upper = np.nanquantile(values, RANGE_QUANTILE)
    span = max(abs(lower), abs(upper))
    if not np.isfinite(span) or span == 0:
        span = 1.0
    return [-span * (1 + RANGE_PADDING_PERCENT), span * (1 + RANGE_PADDING_PERCENT)]


def build_figure(recording, plot_name="", n_shown_samples=DEFAULT_N_SHOWN_SAMPLES):
    channels = recording["channels"]
    n_rows = len(channels)
    start_time = float(recording.get("start_time", 0.0))
    frame_rate = float(recording.get("frame_rate", 1.0))
    duration = recording_duration(recording)
    end_time = start_time + duration
    num_class = min(len(CLASS_LABELS), len(CLASS_COLORS))

    labels = get_padded_labels(recording)
    overlay_z = [labels.tolist()]  # 2-D z for the heatmap

    fig = FigureResampler(
        make_subplots(
            rows=n_rows,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.06,
            subplot_titles=[channel["name"] for channel in channels],
            row_heights=[1 / n_rows] * n_rows,
        ),
        default_n_shown_samples=n_shown_samples,
        default_downsampler=MinMaxLTTB(parallel=True),
    )

    # 1) One line trace per channel (high-frequency, resampler-managed).
    for row, channel in enumerate(channels, start=1):
        values = channel["values"]
        sample_rate = float(channel["sample_rate"])
        time = start_time + np.arange(values.size) / sample_rate
        fig.add_trace(
            go.Scattergl(
                name=channel["name"],
                line=dict(width=1, color=CHANNEL_LINE_COLOR),
                mode="lines",
                showlegend=False,
                hovertemplate="<b>t</b>: %{x:.2f}s<br><b>y</b>: %{y:.3f}<extra></extra>",
            ),
            hf_x=time,
            hf_y=values,
            row=row,
            col=1,
        )

    # 2) Legend swatches for the class colors (off-screen markers on row 1).
    for i in range(num_class):
        fig.add_trace(
            go.Scatter(
                x=[start_time - 1e6],
                y=[0],
                name=f"{CLASS_LABELS[i]}: {i + 1}",
                mode="markers",
                marker=dict(size=8, color=CLASS_COLORS[i], symbol="square"),
                showlegend=True,
            ),
            row=1,
            col=1,
        )

    # 3) Annotation overlay: the same heatmap on every channel row, added LAST.
    colorscale = _discrete_colorscale(num_class)
    overlay_trace_indices = []
    for row in range(1, n_rows + 1):
        fig.add_trace(
            go.Heatmap(
                x0=start_time + 0.5 / frame_rate,
                dx=1 / frame_rate,
                y0=0,
                dy=HEATMAP_HEIGHT,
                z=overlay_z,
                name="Labels",
                hoverinfo="none",
                colorscale=colorscale,
                showscale=False,
                opacity=OVERLAY_OPACITY,
                zmin=0,
                zmax=num_class - 1,
                showlegend=False,
                xgap=0.05,
            ),
            row=row,
            col=1,
        )
        overlay_trace_indices.append(len(fig.data) - 1)

    # Force everything onto the bottom row's x-axis so navigation is synchronized.
    shared_axis_id = f"x{n_rows}"          # trace assignment + shape xref
    shared_axis_key = f"xaxis{n_rows}"     # layout key: layout[key].range
    fig.update_traces(xaxis=shared_axis_id)

    for row in range(1, n_rows + 1):
        fig.update_xaxes(range=[start_time, end_time], row=row, col=1)
    fig.update_xaxes(
        title_text="<b>Time (s)</b>",
        title_standoff=10,
        tickformat="digits",
        row=n_rows,
        col=1,
    )
    for row, channel in enumerate(channels, start=1):
        fig.update_yaxes(range=_symmetric_range(channel["values"]), row=row, col=1)

    fig.update_layout(
        autosize=True,
        height=800,
        margin=dict(t=64, l=10, r=5, b=20),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="rgba(255,255,255,0.6)"),
        title=dict(text=plot_name, font=dict(size=16), x=0.03, xanchor="left"),
        # The legend lives in the top margin, opposite the title: anchored to the
        # figure *container* (not the plot area) so it never rides down over row 1
        # the way a paper-referenced legend does, and so its position is
        # independent of the figure height.
        legend=dict(
            orientation="h",
            xref="paper",
            x=1.0,
            xanchor="right",
            yref="container",
            y=0.985,
            yanchor="top",
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=10),
        ),
        modebar_remove=["lasso2d", "zoom", "autoScale"],
        dragmode="pan",
        clickmode="event",
        meta={
            "sharedXAxisKey": shared_axis_key,
            "sharedXAxisId": shared_axis_id,
            "overlayTraceIndices": overlay_trace_indices,
            "numClass": num_class,
            "frameRate": frame_rate,
            "xBounds": x_bounds(recording),
        },
    )
    fig.update_annotations(font_size=13)  # subplot titles
    return fig
