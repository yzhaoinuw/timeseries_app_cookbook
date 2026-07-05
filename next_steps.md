# Next Steps

Use this checklist alongside `work_log.md`.

## Currently Hot

Nothing in flight. The template is complete, tested, documented, licensed, and
pushed to `origin/main`. The threads below are optional enhancements, not active
work — pick one up only when a request reopens it.

## Optional enhancements (paused / not started)

Status: not started

- **Browser-only deployment variant.** Document (and optionally scaffold) a
  no-pywebview mode: run `app.run(...)` directly and swap native dialogs for
  `dcc.Upload`. The interaction layer is deployment-agnostic, so this is mostly a
  shell + loader change. Called out in `project_overview.md` → Questions.
- **A second, real-format `load_recording` example.** The template only reads the
  `.npz` it writes. A CSV or EDF worked example would make the "replace one
  function" adaptation path more concrete for adopters.
- **CI.** Add a GitHub Actions workflow running `python -m pytest -q` on push once
  the repo has collaborators.
- **Browser-side interaction tests.** The `ts_app/assets/*.js` gestures are only
  verified by hand / via the Flask routes today. A Playwright (or similar) smoke
  test driving a drag-select and a keypress annotation would close that gap.

## Background / Paused

None yet — this is the initial state of the repo.
