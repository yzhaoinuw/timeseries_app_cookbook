# -*- coding: utf-8 -*-
"""Layout and the hidden plumbing every interaction rides on.

Two-phase UI: a minimal ``home_div`` (load data) is swapped for the full
``visualization_div`` once a recording is loaded. ``backend_div`` holds the
invisible engine room — the ``dcc.Store`` state slots and the ``EventListener``
bridges that turn custom DOM events (dispatched by assets/*.js) into callbacks.

Custom event names (kept namespaced to avoid collisions):
- ``tsgraphrelayout``    — coalesced zoom/pan range (assets/graphRelayoutCoalescer.js)
- ``tsannotationselect`` — a finished drag/click selection (assets/annotationAutoPan.js)
- ``tsboutcontextmenu``  — right-click on a segment (assets/graphContextMenu.js)
"""

import dash_bootstrap_components as dbc
from dash import dcc, html
from dash_extensions import EventListener

_BUTTON_STYLE = {
    "fontSize": "16px",
    "padding": "10px 16px",
    "marginLeft": "15px",
    "marginTop": "15px",
    "borderRadius": "10px",
    "borderStyle": "none",
    "backgroundColor": "lightgrey",
    "cursor": "pointer",
}

demo_button = html.Button("Load demo data", id="demo-button", style=_BUTTON_STYLE)
open_button = html.Button("Open file…", id="open-button", style=_BUTTON_STYLE)

backend_div = html.Div(
    children=[
        # Browser-side state slots.
        dcc.Store(id="recording-meta-store"),
        dcc.Store(id="visualization-ready-store"),
        dcc.Store(id="box-select-store"),
        dcc.Store(id="updated-labels-store"),
        dcc.Store(id="graph-direct-restyle-payload-store"),
        dcc.Store(id="graph-direct-restyle-status-store"),
        # Custom-event → callback bridges (Recipe 6).
        EventListener(
            id="graph-relayout-coalesced",
            events=[
                {
                    "event": "tsgraphrelayout",
                    "props": [
                        "detail.x0",
                        "detail.x1",
                        "detail.source",
                        "detail.mode",
                        "detail.profileId",
                        "detail.timeStamp",
                    ],
                }
            ],
        ),
        EventListener(
            id="graph-annotation-select",
            events=[
                {
                    "event": "tsannotationselect",
                    "props": [
                        "detail.x0",
                        "detail.x1",
                        "detail.xref",
                        "detail.yref",
                        "detail.y0",
                        "detail.y1",
                        "detail.kind",
                        "detail.timeStamp",
                    ],
                }
            ],
        ),
        EventListener(
            id="graph-contextmenu",
            events=[
                {
                    "event": "tsboutcontextmenu",
                    "props": ["detail.x", "detail.xref", "detail.yref", "detail.timeStamp"],
                }
            ],
        ),
        EventListener(
            id="keyboard",
            events=[{"event": "keydown", "props": ["key"]}],
        ),
        # One-shot timer used to clear transient status messages.
        dcc.Interval(id="interval-component", interval=1000, max_intervals=0),
    ]
)

home_div = html.Div(
    [
        html.Div([demo_button, open_button], style={"display": "flex"}),
        html.Div(id="data-upload-message", style={"marginLeft": "15px", "marginTop": "8px"}),
        backend_div,
    ]
)

graph = dcc.Graph(id="graph", config={"scrollZoom": True})

save_div = html.Div(
    style={"display": "flex", "gap": "10px", "margin": "0 10px 10px 10px"},
    children=[
        html.Button("Save Labels", id="save-button"),
        html.Button("Undo", id="undo-button", style={"visibility": "hidden"}),
    ],
)


def make_utility_div():
    return html.Div(
        style={
            "display": "flex",
            "alignItems": "center",
            "gap": "10px",
            "margin": "5px 10px 0 10px",
        },
        children=[
            html.Div("Sampling Level"),
            dcc.Dropdown(
                options=["x0.5", "x1", "x2", "x4"],
                value="x1",
                id="n-sample-dropdown",
                searchable=False,
                clearable=False,
                style={"width": "110px"},
            ),
            html.Div(
                "m: toggle navigate/annotate  ·  ←/→: pan  ·  1-4: label selection",
                style={"marginLeft": "10px", "color": "#666", "fontSize": "13px"},
            ),
        ],
    )


def make_visualization_div():
    return html.Div(
        children=[
            make_utility_div(),
            html.Div(
                children=[graph],
                style={"marginTop": "1px", "marginLeft": "20px", "marginRight": "15px",
                       "minHeight": "800px"},
            ),
            html.Div(id="annotation-message", style={"marginLeft": "10px", "minHeight": "18px"}),
            save_div,
        ]
    )


class Components:
    def __init__(self):
        self.home_div = home_div
        self.graph = graph
        self.visualization_div = make_visualization_div()
