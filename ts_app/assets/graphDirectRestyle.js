/*
 * Direct restyle (COOKBOOK Recipe 8).
 *
 * Applies a resampler data patch by calling Plotly.restyle() directly, bypassing
 * Dash's figure reconciliation. Measurably faster for large trace updates. The
 * server hands the patch operations to `graph-direct-restyle-payload-store`; a
 * clientside callback forwards them here.
 */
(function () {
    "use strict";

    if (window.tsAppDirectRestyle) {
        return;
    }

    const GRAPH_ID = "graph";
    const DATA_PROPS = new Set(["x", "y", "name", "marker"]);

    function findPlot() {
        const root = document.getElementById(GRAPH_ID);
        return root ? root.querySelector(".js-plotly-plot") : null;
    }

    function operationValue(operation) {
        return operation && operation.params ? operation.params.value : undefined;
    }

    function buildTraceUpdates(operations) {
        const traceUpdates = new Map();
        for (const operation of operations) {
            const location = operation.location || [];
            if (location.length < 3 || location[0] !== "data" || !DATA_PROPS.has(location[2])) {
                continue;
            }
            const traceIndex = Number(location[1]);
            if (!Number.isInteger(traceIndex)) {
                continue;
            }
            const update = traceUpdates.get(traceIndex) || {};
            update[location[2]] = operationValue(operation);
            traceUpdates.set(traceIndex, update);
        }
        return traceUpdates;
    }

    function buildRestyleArgs(traceUpdates) {
        const traceIndices = Array.from(traceUpdates.keys()).sort((a, b) => a - b);
        const propNames = new Set();
        for (const update of traceUpdates.values()) {
            for (const name of Object.keys(update)) {
                propNames.add(name);
            }
        }
        const restyleUpdate = {};
        for (const name of propNames) {
            restyleUpdate[name] = traceIndices.map((index) => {
                const update = traceUpdates.get(index);
                return update ? update[name] : undefined;
            });
        }
        return { restyleUpdate, traceIndices };
    }

    function apply(payload) {
        const operations = (payload && payload.operations) || [];
        const plot = findPlot();
        if (!plot || !window.Plotly) {
            return { ok: false, error: "Plotly graph not ready" };
        }
        const { restyleUpdate, traceIndices } = buildRestyleArgs(buildTraceUpdates(operations));
        if (!traceIndices.length) {
            return { ok: true, traceCount: 0, operationCount: operations.length };
        }
        Promise.resolve(window.Plotly.restyle(plot, restyleUpdate, traceIndices)).catch(function (error) {
            console.error("tsAppDirectRestyle failed", error);
        });
        return { ok: true, traceCount: traceIndices.length, operationCount: operations.length };
    }

    window.tsAppDirectRestyle = { apply };
})();
