"""Render caption banner PNGs for overlaying on the demo video."""

from PIL import Image, ImageDraw, ImageFont

VIDEO_W = 2854
FONT_SIZE = 96
PAD_X, PAD_Y = 48, 28
RADIUS = 26
BG = (10, 10, 10, 175)
FG = (255, 255, 255, 255)
FONT_PATH = "/System/Library/Fonts/HelveticaNeue.ttc"

CAPTIONS = [
    ("Scroll to zoom", 0.0, 5.0),
    ("Panning by dragging", 6.0, 9.0),
    ("Switch mode", 12.0, 13.98),
    ("Select an area by box select", 14.0, 22.0),
    ("Select a segment by right click", 26.0, 27.98),
    ("Select continuously by dragging", 28.0, 35.0),
    ("Select a thin strip by single click", 41.0, 43.5),
    ("Undo an annotation", 44.0, 46.5),
    ("Save annotation", 50.0, 55.0),
]


def find_bold_face(path):
    for i in range(20):
        try:
            f = ImageFont.truetype(path, FONT_SIZE, index=i)
        except OSError:
            break
        family, style = f.getname()
        if style == "Bold":
            return f
    return ImageFont.truetype(path, FONT_SIZE, index=0)


font = find_bold_face(FONT_PATH)
print("Using font face:", font.getname())

for n, (text, start, end) in enumerate(CAPTIONS, 1):
    probe = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    left, top, right, bottom = probe.textbbox((0, 0), text, font=font)
    text_w, text_h = right - left, bottom - top
    box_w, box_h = text_w + 2 * PAD_X, text_h + 2 * PAD_Y

    img = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((0, 0, box_w - 1, box_h - 1), radius=RADIUS, fill=BG)
    draw.text((PAD_X - left, PAD_Y - top), text, font=font, fill=FG)
    img.save(f"cap_{n}.png")
    print(f"cap_{n}.png  {box_w}x{box_h}  {start}-{end}s  {text!r}")

# Emit the ffmpeg filtergraph for compositing all banners.
chains = []
prev = "0:v"
for n, (_, start, end) in enumerate(CAPTIONS, 1):
    out = f"v{n}"
    chains.append(
        f"[{prev}][{n}:v]overlay=(main_w-overlay_w)/2:50:"
        f"enable='between(t,{start},{end})'[{out}]"
    )
    prev = out
graph = ";".join(chains)
with open("overlay_graph.txt", "w") as fh:
    fh.write(graph)
print("\nfiltergraph written to overlay_graph.txt, final label:", prev)
