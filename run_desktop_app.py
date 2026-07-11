# -*- coding: utf-8 -*-
"""Desktop entrypoint: run the Dash server in a background thread and show it in
a native pywebview window (which also provides the OS file dialogs).

    python run_desktop_app.py            # launch the app
    python run_desktop_app.py --smoke    # import + version check, no window

Multi-session: each launch claims the first free port in the slot range
BASE_PORT..BASE_PORT+MAX_SESSIONS-1 and becomes an independent window in its
own process. The slot range lives here, not in ts_app.config, because the
slot must be claimed and exported (env vars below) *before* ts_app is
imported — ts_app.config reads the env at import time.
"""

import multiprocessing
import os
import socket
import sys
import threading

import webview


BASE_PORT = 8060
MAX_SESSIONS = 3
INSTANCE_SLOT_ENV = "TS_APP_INSTANCE_SLOT"
PEER_PORTS_ENV = "TS_APP_PEER_PORTS"


def claim_session_slot(base_port=BASE_PORT, max_sessions=MAX_SESSIONS):
    """Bind the first free port in the slot range and return (slot, port, socket).

    The returned socket holds the claim until the Dash server takes the port
    over; keeping it bound closes the gap in which a concurrently launching
    window could scan its way onto the same slot. The OS port table doubles as
    the "how many windows are open" counter — no lock files, and a crashed
    window frees its slot automatically. Returns (None, None, None) when every
    slot is taken.
    """
    for slot in range(max_sessions):
        port = base_port + slot
        probe_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            probe_socket.bind(("127.0.0.1", port))
        except OSError:
            probe_socket.close()
            continue
        return slot, port, probe_socket
    return None, None, None


def show_session_limit_message(max_sessions=MAX_SESSIONS):
    # Importing ts_app here is safe: this path never starts the server, and
    # with no env vars exported config falls back to slot-0 defaults.
    from ts_app.config import APP_TITLE

    message = (
        f"{max_sessions} {APP_TITLE} windows are already open. "
        "Close one of them, then launch the app again."
    )
    print(f"[startup] {message}", flush=True)
    webview.create_window(
        APP_TITLE,
        html=f"<p style='font-family: sans-serif; margin: 2em;'>{message}</p>",
        width=480,
        height=200,
        resizable=False,
    )
    start_webview()


def start_webview():
    # Windows: force the EdgeChromium renderer; elsewhere auto-select the native one.
    if sys.platform == "win32":
        webview.start(gui="edgechromium")
    else:
        webview.start()


def run_dash(app, port, probe_socket=None):
    if probe_socket is not None:
        probe_socket.close()  # release the claimed port just before Dash binds it
    app.run(
        host="127.0.0.1",
        port=port,
        debug=False,
        dev_tools_hot_reload=False,
        use_reloader=False,
    )


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)

    if "--smoke" in argv:
        from ts_app import VERSION
        from ts_app.app import app  # noqa: F401 -- importing the app is the check
        from ts_app.config import APP_TITLE

        print(f"{APP_TITLE} {VERSION} smoke check OK")
        return 0

    slot, port, probe_socket = claim_session_slot()
    if slot is None:
        show_session_limit_message()
        return 1

    # Export the slot before importing ts_app: app.py derives the per-window
    # temp/cache dir from it at import time, and the same-file peer check
    # queries the peer ports.
    os.environ[INSTANCE_SLOT_ENV] = str(slot)
    os.environ[PEER_PORTS_ENV] = ",".join(
        str(BASE_PORT + other) for other in range(MAX_SESSIONS) if other != slot
    )

    from ts_app import VERSION
    from ts_app.app import app
    from ts_app.config import APP_TITLE, WINDOW_CONFIG

    multiprocessing.freeze_support()
    thread = threading.Thread(target=run_dash, args=(app, port, probe_socket), daemon=True)
    thread.start()

    webview.settings["ALLOW_DOWNLOADS"] = True

    window_title = f"{APP_TITLE} {VERSION}"
    if slot > 0:
        window_title += f" ({slot + 1})"

    webview.create_window(
        window_title,
        f"http://127.0.0.1:{port}",
        **WINDOW_CONFIG,
    )

    start_webview()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
