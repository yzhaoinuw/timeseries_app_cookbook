# -*- coding: utf-8 -*-
"""Native OS Open/Save dialogs via pywebview.

These need a live pywebview window (``webview.windows[0]``), which the desktop
shell creates. The return-type normalization here is load-bearing: the same
call returns different shapes on Windows vs. macOS (see the inline note).
"""

import webview


def open_file_dialog(file_types):
    """Open a native file-open dialog and return a single path, or None.

    Parameters
    ----------
    file_types : tuple[str]
        pywebview filter strings, e.g. ``("Recordings (*.npz)",)``.
    """
    if not webview.windows:
        return None

    window = webview.windows[0]
    result = window.create_file_dialog(
        webview.FileDialog.OPEN,
        allow_multiple=False,
        file_types=tuple(file_types),
    )
    return _normalize_dialog_result(result)


def save_file_dialog(file_types, filename):
    """Open a native save dialog and return the chosen path, or None.

    Parameters
    ----------
    file_types : tuple[str]
        pywebview filter strings.
    filename : str
        Default filename suggested to the user.
    """
    if not webview.windows:
        return None

    window = webview.windows[0]
    result = window.create_file_dialog(
        webview.FileDialog.SAVE,
        save_filename=filename,
        file_types=tuple(file_types),
    )
    return _normalize_dialog_result(result)


def _normalize_dialog_result(result):
    """Collapse pywebview's platform-specific return into a plain str or None.

    IMPORTANT: on Windows ``create_file_dialog`` returns a tuple; on macOS the
    SAVE dialog returns an ``objc.pyobjc_unicode`` (a *string-like* object).
    Indexing ``result[0]`` on the macOS case grabs the first **character**, not
    the first path — hence the explicit type check.
    """
    if result is None:
        return None
    if isinstance(result, (tuple, list)):
        return result[0] if result else None
    return str(result)
