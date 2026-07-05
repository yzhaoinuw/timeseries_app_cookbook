/*
 * Relayout coalescer (COOKBOOK Recipe 7) — the navigation backbone.
 *
 * Plotly fires `plotly_relayouting` on every animation frame of a zoom/pan.
 * This turns that firehose into a single debounced `tsgraphrelayout` custom
 * event so the server resamples once, when the view settles, instead of 60x/s.
 * It also exposes `window.tsAppGraphRelayout` so other gestures (keyboard pan,
 * custom pointer pan, auto-pan) feed the same coalescing pipeline, and it
 * stands down while those custom gestures drive their own updates.
 */
(function () {
    "use strict";

    if (window.tsAppGraphRelayout) {
        return;
    }

    const EVENT_NAME = "tsgraphrelayout";
    const GRAPH_ID = "graph";
    const PROFILE_LOG_ENDPOINT = "/_ts_app/profile-log";
    const DUPLICATE_DISPATCH_WINDOW_MS = 250;
    const FINAL_IDLE_MS = 450;
    const KEYBOARD_FINAL_IDLE_MS = 120;
    const RELEASE_FINAL_DELAY_MS = 25;
    const RANGE_EQUAL_ABS_TOLERANCE = 0.05;
    const RANGE_EQUAL_REL_TOLERANCE = 0.00005;

    let finalTimer = null;
    let lastDispatch = null;
    let attachedPlot = null;
    let profileId = 0;
    let suppressUntil = 0;

    function findPlot() {
        const root = document.getElementById(GRAPH_ID);
        return root ? root.querySelector(".js-plotly-plot") : null;
    }

    function sharedAxisKey(plot) {
        const meta =
            (plot && plot.layout && plot.layout.meta) ||
            (plot && plot._fullLayout && plot._fullLayout.meta);
        return (meta && meta.sharedXAxisKey) || "xaxis";
    }

    function postProfileLog(payload) {
        const body = JSON.stringify(payload);
        if (navigator.sendBeacon) {
            const blob = new Blob([body], { type: "application/json" });
            if (navigator.sendBeacon(PROFILE_LOG_ENDPOINT, blob)) {
                return;
            }
        }
        window
            .fetch(PROFILE_LOG_ENDPOINT, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body,
                keepalive: true,
            })
            .catch(function () {});
    }

    function readRange(data, key, index) {
        const bracketKey = `${key}[${index}]`;
        if (data[bracketKey] !== undefined) {
            return data[bracketKey];
        }
        const range = data[key];
        return Array.isArray(range) ? range[index] : undefined;
    }

    function extractXRange(relayoutData) {
        if (!relayoutData) {
            return null;
        }
        const key = `${sharedAxisKey(attachedPlot)}.range`;
        let x0 = readRange(relayoutData, key, 0);
        let x1 = readRange(relayoutData, key, 1);
        if (x0 === undefined || x1 === undefined) {
            x0 = readRange(relayoutData, "xaxis.range", 0);
            x1 = readRange(relayoutData, "xaxis.range", 1);
        }
        x0 = Number(x0);
        x1 = Number(x1);
        if (!Number.isFinite(x0) || !Number.isFinite(x1) || x0 === x1) {
            return null;
        }
        return [Math.min(x0, x1), Math.max(x0, x1)];
    }

    function rangesNearlyEqual(a, b) {
        if (!a || !b) {
            return false;
        }
        const width = Math.max(Math.abs(a[1] - a[0]), Math.abs(b[1] - b[0]), 1);
        const tolerance = Math.max(RANGE_EQUAL_ABS_TOLERANCE, width * RANGE_EQUAL_REL_TOLERANCE);
        return Math.abs(a[0] - b[0]) <= tolerance && Math.abs(a[1] - b[1]) <= tolerance;
    }

    function dispatchRange(range, source, mode) {
        const now = Date.now();
        if (
            lastDispatch &&
            lastDispatch.mode === mode &&
            rangesNearlyEqual([lastDispatch.x0, lastDispatch.x1], range) &&
            now - lastDispatch.timeStamp < DUPLICATE_DISPATCH_WINDOW_MS
        ) {
            return;
        }
        lastDispatch = { x0: range[0], x1: range[1], mode, timeStamp: now };
        document.dispatchEvent(
            new CustomEvent(EVENT_NAME, {
                detail: {
                    x0: range[0],
                    x1: range[1],
                    source,
                    mode,
                    profileId: ++profileId,
                    timeStamp: now,
                },
            })
        );
    }

    function requestFinal(range, source, delay) {
        window.clearTimeout(finalTimer);
        finalTimer = window.setTimeout(function () {
            dispatchRange(range, source || "plotly", "final");
        }, delay);
    }

    function request(relayoutData, source) {
        const range = extractXRange(relayoutData);
        if (!range) {
            return;
        }
        const delay = source === "keyboard" ? KEYBOARD_FINAL_IDLE_MS : FINAL_IDLE_MS;
        requestFinal(range, source, delay);
    }

    function requestFinalOnly(relayoutData, source, delay) {
        const range = extractXRange(relayoutData);
        if (range) {
            requestFinal(range, source, delay === undefined ? 0 : delay);
        }
    }

    function shouldSuppress() {
        const customPan = Boolean(
            window.tsAppCustomPointerPan && window.tsAppCustomPointerPan.isActive === true
        );
        return customPan || window.tsAppAnnotationAutoPanActive === true || Date.now() < suppressUntil;
    }

    function suppressPlotlyRelayoutFor(durationMs) {
        suppressUntil = Math.max(suppressUntil, Date.now() + durationMs);
    }

    function attachPlotlyListener() {
        const plot = findPlot();
        if (!plot || plot === attachedPlot || typeof plot.on !== "function") {
            return;
        }
        window.clearTimeout(finalTimer);
        lastDispatch = null;
        attachedPlot = plot;
        plot.on("plotly_relayouting", function (relayoutData) {
            if (!shouldSuppress()) {
                request(relayoutData, "plotly-moving");
            }
        });
        plot.on("plotly_relayout", function (relayoutData) {
            if (!shouldSuppress()) {
                requestFinalOnly(relayoutData, "plotly", RELEASE_FINAL_DELAY_MS);
            }
        });
    }

    window.tsAppGraphRelayout = { request, requestFinalOnly, suppressPlotlyRelayoutFor };
    window.tsAppProfileLog = postProfileLog;

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", attachPlotlyListener);
    } else {
        attachPlotlyListener();
    }
    // The Plotly div is recreated on figure swaps, so re-attach on DOM changes.
    new MutationObserver(attachPlotlyListener).observe(document.documentElement, {
        childList: true,
        subtree: true,
    });
})();
