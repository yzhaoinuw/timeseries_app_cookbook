# Demo media & the pipeline that builds it

Everything here exists to produce the two demo assets in the top-level
[`README.md`](../../README.md): the hero GIF under the badges, and the full
walkthrough video in its [Demo](../../README.md#demo) section.

## What each file is for

| File | Purpose |
| --- | --- |
| `ts_app_demo.gif` | The hero GIF at the top of the main README. 800px, 10fps, 48-color palette, ~3MB — a 21-second cut of the selection sequence. **The only media file tracked in this repo.** |
| `make_demo.sh` | Runs the whole pipeline end to end: caption banners → captioned master → downscaled mp4 export → hero GIF. Start here. |
| `make_banners.py` | Step 1 of that pipeline, and the file to edit when you want different captions. The `CAPTIONS` list holds each caption's text and its start/end time in seconds. Also emits the ffmpeg filtergraph (`overlay_graph.txt`) that composites the banners. |

## Rebuilding

```bash
python3 -m venv venv && ./venv/bin/pip install pillow
PY=./venv/bin/python ./make_demo.sh ~/Desktop/ts_app_demo.mov
```

To change what the captions say, edit `CAPTIONS` in `make_banners.py` and re-run.
To change which stretch of the recording becomes the GIF, edit the `GIF_START` /
`GIF_DUR` variables at the top of `make_demo.sh`.

## Where the source videos live

The raw screen recording (~66MB) and the captioned master (~21MB) are **not
tracked** — they are too large to be worth versioning, and every asset in the
README can be regenerated from the raw recording with the command above. They
live on the maintainer's machine under `~/Desktop/`. Keep the raw recording
somewhere durable; without it the pipeline has nothing to caption.

## How the two assets get into the README

They embed by two different mechanisms, and the difference matters:

- **The GIF is committed and referenced by relative path.** GitHub renders
  committed GIFs inline and autoplays them. Keep it well under ~10MB or
  GitHub's image proxy may refuse to serve it.
- **The video is a `github.com/user-attachments/...` URL, not a repo file.** A
  committed `.mp4` referenced by relative path does *not* produce an inline
  player — the link just opens the blob page. An inline player requires
  drag-dropping the mp4 into GitHub's web editor, which mints that attachment
  URL and hosts the file outside the repo. Only a human signed into GitHub can
  do this; it cannot be scripted. That is why `make_demo.sh` writes the export
  next to the source video rather than into this folder.

If the demo is ever re-recorded, the video URL in the main README has to be
re-minted the same way — regenerating files here will not update it.

## Caption rendering note

Homebrew's ffmpeg is built without libass/freetype, so the `ass` and `drawtext`
filters are unavailable. Captions are therefore rendered by Pillow into
transparent PNG banners and composited with core `overlay` filters, one per
caption, gated by `enable='between(t,start,end)'`. If you move to an ffmpeg
build that *does* have libass, this whole two-step dance collapses into a
subtitle filter — but the current approach has no dependency beyond Pillow.
