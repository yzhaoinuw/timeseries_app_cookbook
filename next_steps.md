# Next Steps

Use this checklist alongside `work_log.md`.

## Currently Hot

**Demo README awaiting Yue's inspection on `dev`.** As of 2026-08-04 `dev` has
the hero GIF, the Demo section with the inline video player, and the captioning
pipeline under `docs/media/`. `main` has been merged in, so `dev` is ahead only
by the demo work. Remaining:

- **Yue inspects the rendered README on `dev`, then merge to `main`.** That is
  the only thing blocking this thread.
- **Keep the raw recording safe.** `~/Desktop/ts_app_demo.mov` is the input the
  whole pipeline regenerates from and is untracked. If it is lost, changing a
  caption means re-recording the demo.
- **Re-minting on re-record.** The Demo section's video is a
  `github.com/user-attachments/...` URL hosted outside the repo, not a tracked
  file. Re-running `docs/media/make_demo.sh` will not update it — Yue has to
  drag-drop the new export into the web editor again.

The threads below are optional enhancements, not active work — pick one up only
when a request reopens it.

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
