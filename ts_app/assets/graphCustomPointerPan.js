/*
 * Custom pointer pan (COOKBOOK Recipe 10).
 *
 * In "pan" dragmode, replaces Plotly's native pan with an rAF-throttled pointer
 * pan that moves x AND the y of whichever channel row the pointer is over. It
 * routes the settled range through the coalescer and suppresses the coalescer's
 * own relayout handling during the drag so the two don't fight.
 */
(function () {
    "use strict";

    if (window.tsAppCustomPointerPan) {
        return;
    }

    const GRAPH_ID = "graph";
    const ENABLE = true;

    let attachedPlot = null;
    let dragState = null;
    let pendingClientX = null;
    let pendingClientY = null;
    let rafId = null;

    function findPlot() {
        const root = document.getElementById(GRAPH_ID);
        return root ? root.querySelector(".js-plotly-plot") : null;
    }

    function sharedAxisKey(plot) {
        const meta = (plot && plot.layout && plot.layout.meta) || (plot && plot._fullLayout && plot._fullLayout.meta);
        return (meta && meta.sharedXAxisKey) || "xaxis";
    }

    function isInteractiveChrome(target) {
        return Boolean(
            target &&
                target.closest &&
                target.closest(".modebar, .legend, .rangeslider-container, .select-outline")
        );
    }

    function getXAxis(plot) {
        return plot && plot._fullLayout && plot._fullLayout[sharedAxisKey(plot)];
    }

    function getPointerYAxis(plot, clientY) {
        if (!plot || !plot._fullLayout) {
            return null;
        }
        const rect = plot.getBoundingClientRect();
        const plotY = clientY - rect.top;
        const keys = Object.keys(plot._fullLayout).filter((key) => /^yaxis[0-9]*$/.test(key));
        for (const axisName of keys) {
            const axis = plot._fullLayout[axisName];
            const offset = axis && Number(axis._offset);
            const length = axis && Number(axis._length);
            if (
                axis &&
                !axis.fixedrange &&
                !axis.overlaying &&
                Number.isFinite(offset) &&
                Number.isFinite(length) &&
                plotY >= offset &&
                plotY <= offset + length
            ) {
                return { axis, axisName: axisName === "yaxis" ? "yaxis" : axisName };
            }
        }
        return null;
    }

    function getDragMode(plot) {
        const layout = (plot && plot.layout) || {};
        const fullLayout = (plot && plot._fullLayout) || {};
        return layout.dragmode || fullLayout.dragmode;
    }

    function canPan(plot, event) {
        if (!ENABLE || !plot || event.button !== 0) {
            return false;
        }
        if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) {
            return false;
        }
        if (isInteractiveChrome(event.target)) {
            return false;
        }
        return getDragMode(plot) === "pan";
    }

    function stopNativeDrag(event) {
        event.preventDefault();
        event.stopPropagation();
        if (typeof event.stopImmediatePropagation === "function") {
            event.stopImmediatePropagation();
        }
    }

    function currentRange(axis) {
        if (!axis || !Array.isArray(axis.range) || axis.range.length !== 2) {
            return null;
        }
        const x0 = Number(axis.range[0]);
        const x1 = Number(axis.range[1]);
        if (!Number.isFinite(x0) || !Number.isFinite(x1) || x0 === x1) {
            return null;
        }
        return [x0, x1];
    }

    function applyPendingPan() {
        rafId = null;
        if (!dragState || pendingClientX === null || pendingClientY === null || !window.Plotly) {
            return;
        }
        const xkey = dragState.xkey;
        const dx = pendingClientX - dragState.startClientX;
        const width = dragState.startXRange[1] - dragState.startXRange[0];
        const shift = -dx * (width / dragState.xAxisLength);
        const nextXRange = [dragState.startXRange[0] + shift, dragState.startXRange[1] + shift];
        const relayout = {};
        relayout[`${xkey}.range[0]`] = nextXRange[0];
        relayout[`${xkey}.range[1]`] = nextXRange[1];

        if (dragState.startYRange && dragState.yAxisName && dragState.yAxisLength) {
            const dy = pendingClientY - dragState.startClientY;
            const yWidth = dragState.startYRange[1] - dragState.startYRange[0];
            const yShift = dy * (yWidth / dragState.yAxisLength);
            relayout[`${dragState.yAxisName}.range[0]`] = dragState.startYRange[0] + yShift;
            relayout[`${dragState.yAxisName}.range[1]`] = dragState.startYRange[1] + yShift;
        }

        dragState.latestRange = nextXRange;
        if (window.tsAppGraphRelayout && window.tsAppGraphRelayout.suppressPlotlyRelayoutFor) {
            window.tsAppGraphRelayout.suppressPlotlyRelayoutFor(250);
        }
        window.Plotly.relayout(dragState.plot, relayout);
    }

    function schedulePan(clientX, clientY) {
        pendingClientX = clientX;
        pendingClientY = clientY;
        if (rafId === null) {
            rafId = window.requestAnimationFrame(applyPendingPan);
        }
    }

    function onPointerMove(event) {
        if (!dragState) {
            return;
        }
        stopNativeDrag(event);
        schedulePan(event.clientX, event.clientY);
    }

    function requestFinalRange() {
        if (!dragState || !dragState.latestRange || !window.tsAppGraphRelayout) {
            return;
        }
        if (window.tsAppGraphRelayout.suppressPlotlyRelayoutFor) {
            window.tsAppGraphRelayout.suppressPlotlyRelayoutFor(500);
        }
        const [x0, x1] = dragState.latestRange;
        const relayout = {};
        relayout[`${dragState.xkey}.range[0]`] = x0;
        relayout[`${dragState.xkey}.range[1]`] = x1;
        window.tsAppGraphRelayout.requestFinalOnly(relayout, "custom-drag", 0);
    }

    function clearDragState() {
        if (rafId !== null) {
            window.cancelAnimationFrame(rafId);
            rafId = null;
        }
        pendingClientX = null;
        pendingClientY = null;
        dragState = null;
        window.tsAppCustomPointerPan.isActive = false;
    }

    function onPointerUp(event) {
        if (!dragState) {
            return;
        }
        stopNativeDrag(event);
        schedulePan(event.clientX, event.clientY);
        if (rafId !== null) {
            window.cancelAnimationFrame(rafId);
            applyPendingPan();
        }
        requestFinalRange();
        clearDragState();
        window.removeEventListener("pointermove", onPointerMove, true);
        window.removeEventListener("pointerup", onPointerUp, true);
        window.removeEventListener("pointercancel", onPointerUp, true);
    }

    function onPointerDown(event) {
        const plot = attachedPlot;
        if (!canPan(plot, event)) {
            return;
        }
        const axis = getXAxis(plot);
        const range = currentRange(axis);
        const axisLength = axis && Number(axis._length);
        if (!range || !Number.isFinite(axisLength) || axisLength <= 0) {
            return;
        }
        const yMatch = getPointerYAxis(plot, event.clientY);
        const yRange = yMatch ? currentRange(yMatch.axis) : null;
        const yAxisLength = yMatch && Number(yMatch.axis._length);

        stopNativeDrag(event);
        window.tsAppCustomPointerPan.isActive = true;
        dragState = {
            plot,
            xkey: sharedAxisKey(plot),
            startClientX: event.clientX,
            startClientY: event.clientY,
            startXRange: range,
            startYRange: yRange && Number.isFinite(yAxisLength) && yAxisLength > 0 ? yRange : null,
            xAxisLength: axisLength,
            yAxisLength: Number.isFinite(yAxisLength) && yAxisLength > 0 ? yAxisLength : null,
            yAxisName: yMatch ? yMatch.axisName : null,
            latestRange: range,
        };
        pendingClientX = event.clientX;
        pendingClientY = event.clientY;
        window.addEventListener("pointermove", onPointerMove, true);
        window.addEventListener("pointerup", onPointerUp, true);
        window.addEventListener("pointercancel", onPointerUp, true);
    }

    function attachPlotlyListener() {
        const plot = findPlot();
        if (!plot || plot === attachedPlot) {
            return;
        }
        attachedPlot = plot;
        plot.addEventListener("pointerdown", onPointerDown, true);
    }

    window.tsAppCustomPointerPan = { enabled: ENABLE, isActive: false };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", attachPlotlyListener);
    } else {
        attachPlotlyListener();
    }
    new MutationObserver(attachPlotlyListener).observe(document.documentElement, {
        childList: true,
        subtree: true,
    });
})();
