# -*- coding: utf-8 -*-
"""Desktop entrypoint: run the Dash server in a background thread and show it in
a native pywebview window (which also provides the OS file dialogs).

    python run_desktop_app.py            # launch the app
    python run_desktop_app.py --smoke    # import + version check, no window
"""

import multiprocessing
import sys
import threading

import webview


def run_dash(app, port):
    app.run(
        host="127.0.0.1",
        port=port,
        debug=False,
        dev_tools_hot_reload=False,
        use_reloader=False,
    )


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)

    from ts_app import VERSION
    from ts_app.app import app
    from ts_app.config import APP_TITLE, PORT, WINDOW_CONFIG

    if "--smoke" in argv:
        print(f"{APP_TITLE} {VERSION} smoke check OK")
        return 0

    multiprocessing.freeze_support()
    thread = threading.Thread(target=run_dash, args=(app, PORT), daemon=True)
    thread.start()

    webview.settings["ALLOW_DOWNLOADS"] = True
    webview.create_window(
        f"{APP_TITLE} {VERSION}",
        f"http://127.0.0.1:{PORT}",
        **WINDOW_CONFIG,
    )

    # Windows: force the EdgeChromium renderer; elsewhere auto-select the native one.
    if sys.platform == "win32":
        webview.start(gui="edgechromium")
    else:
        webview.start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
