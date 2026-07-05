/*
 * Context-menu selection (COOKBOOK Recipe 12).
 *
 * Right-click inside the plot converts the pixel to a data-x (via the shared
 * axis' p2l) and dispatches `tsboutcontextmenu`. A clientside callback then
 * selects the whole contiguous same-label segment under the cursor.
 */
(function () {
    "use strict";

    const EVENT_NAME = "tsboutcontextmenu";
    const GRAPH_ID = "graph";

    function sharedAxis(fullLayout) {
        const meta = fullLayout && fullLayout.meta;
        const key = (meta && meta.sharedXAxisKey) || "xaxis";
        return fullLayout[key] || fullLayout.xaxis;
    }

    function nearestPrimaryYAxis(fullLayout, clientY, plotRect) {
        const plotY = clientY - plotRect.top;
        let nearest = null;
        let nearestDistance = Infinity;
        Object.keys(fullLayout)
            .filter((key) => /^yaxis[0-9]*$/.test(key))
            .map((key) => fullLayout[key])
            .filter(
                (axis) =>
                    axis &&
                    axis._id &&
                    !axis.overlaying &&
                    Number.isFinite(axis._offset) &&
                    Number.isFinite(axis._length)
            )
            .forEach((axis) => {
                const top = axis._offset;
                const bottom = axis._offset + axis._length;
                if (plotY >= top && plotY <= bottom) {
                    nearest = axis;
                    nearestDistance = 0;
                    return;
                }
                const distance = Math.min(Math.abs(plotY - top), Math.abs(plotY - bottom));
                if (distance < nearestDistance) {
                    nearest = axis;
                    nearestDistance = distance;
                }
            });
        return nearest ? nearest._id : "y";
    }

    document.addEventListener(
        "contextmenu",
        function (event) {
            const root = event.target.closest ? event.target.closest(`#${GRAPH_ID}`) : null;
            if (!root) {
                return;
            }
            event.preventDefault();
            event.stopPropagation();

            const plot = root.querySelector(".js-plotly-plot");
            if (!plot || !plot._fullLayout) {
                return;
            }
            const xaxis = sharedAxis(plot._fullLayout);
            if (!xaxis || typeof xaxis.p2l !== "function") {
                return;
            }
            const plotRect = plot.getBoundingClientRect();
            const plotX = event.clientX - plotRect.left - xaxis._offset;
            if (plotX < 0 || plotX > xaxis._length) {
                return;
            }
            document.dispatchEvent(
                new CustomEvent(EVENT_NAME, {
                    detail: {
                        x: xaxis.p2l(plotX),
                        xref: xaxis._id || "x",
                        yref: nearestPrimaryYAxis(plot._fullLayout, event.clientY, plotRect),
                        timeStamp: event.timeStamp,
                    },
                })
            );
        },
        true
    );
})();
