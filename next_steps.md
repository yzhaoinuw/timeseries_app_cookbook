# Next Steps

Use this checklist alongside `work_log.md`.

## Currently Hot

**Demo video awaiting Yue's inspection on `dev`.** The README Demo section and
`docs/media/` landed on `dev` on 2026-08-04. Open follow-ups once Yue has looked:

- **Decide the final embed method.** Today it is a poster image linking to the
  committed mp4 (opens GitHub's blob player). The alternatives are (a) Yue
  drag-drops the mp4 into the web editor for a real inline autoplay player via a
  `user-attachments` URL, or (b) a short committed GIF cut from
  `ts_app_demo_captioned.mp4` — GIFs do autoplay inline; keep well under ~10MB.
  Yue floated the 14–35s selection sequence as the flashiest stretch.
- **Port to `main` once approved.** `main` is the publicly rendered README.
- **Track the captioning pipeline.** `make_banners.py` (caption text + timings)
  and the ffmpeg overlay recipe live only on `~/Desktop/ts_app_demo_captioning/`.
  Yue wanted them kept for future demos — decide whether they belong in this repo
  (e.g. `docs/media/`) before the Desktop copy is lost. Local ffmpeg has no
  libass/freetype, hence the PNG-banner-plus-`overlay` approach.

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
