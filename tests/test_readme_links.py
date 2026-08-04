# -*- coding: utf-8 -*-
"""Guards the README's internal links.

Two kinds of link keep this document navigable, and both rot silently:

* **Line anchors** (`ts_app/app.py#L233`) — the recipes link straight at the
  function they describe. The moment anything above that function shifts, the
  link points at the wrong code and nothing complains.
* **Section anchors** (`#recipe-7--the-relayout-coalescer`) — the Contents and
  Recipe Index are built entirely from these. Rename a heading and they
  silently dead-end.

These tests re-derive both from the tree, so a refactor or a heading rename
turns a stale link into a test failure instead of a wrong jump for the reader.
"""

import pathlib
import re

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = [REPO_ROOT / "README.md", REPO_ROOT / "docs" / "media" / "README.md"]

# [text](target) and ![text](target), for any non-external target.
LINK_RE = re.compile(r"!?\[([^\]]+)\]\((?!https?://|mailto:)([^)\s]+)\)")
HEADING_RE = re.compile(r"^#{1,6}\s+(.*?)\s*$", re.MULTILINE)
LINE_ANCHOR_RE = re.compile(r"L(\d+)")


def slugify(heading):
    """GitHub's heading-anchor algorithm.

    Lowercase, drop everything that is not alphanumeric/space/hyphen, then
    swap spaces for hyphens. Note an em dash is *removed* rather than replaced,
    which is why "Recipe 1 — Desktop shell" anchors as "recipe-1--desktop-shell"
    with a double hyphen.
    """
    text = heading.replace("`", "").lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    return text.replace(" ", "-")


def _links():
    for doc in DOCS:
        for text, target in LINK_RE.findall(doc.read_text()):
            path, _, anchor = target.partition("#")
            yield doc, text, path, anchor


def _symbol(text):
    """The identifier a link's text points at, or None if it names no symbol."""
    # `ts_app/app.py::save_labels` -> save_labels; strip backticks and prose.
    text = text.split("::")[-1].replace("`", "").strip()
    parts = text.split()
    if not parts:
        return None
    token = parts[0]
    # Bare paths and prose labels ("asset scripts") name no symbol. Flask
    # routes ("/_ts_app/resample") do, and are worth checking.
    if "/" in token and not token.startswith("/_"):
        return None
    return token


ALL_LINKS = list(_links())
FILE_LINKS = [ln for ln in ALL_LINKS if ln[2]]
LINE_ANCHORS = [ln for ln in ALL_LINKS if LINE_ANCHOR_RE.fullmatch(ln[3])]
SECTION_ANCHORS = [
    ln for ln in ALL_LINKS if ln[3] and not LINE_ANCHOR_RE.fullmatch(ln[3])
]


def _ids(links):
    return [f"{d.name}:{p or 'self'}{'#' + a if a else ''}" for d, _, p, a in links]


def test_link_inventory_is_populated():
    """Tripwire: if a regex breaks, the parametrized tests would pass empty."""
    assert len(LINE_ANCHORS) > 30
    assert len(SECTION_ANCHORS) > 20


@pytest.mark.parametrize("doc,text,path,anchor", FILE_LINKS, ids=_ids(FILE_LINKS))
def test_link_target_exists(doc, text, path, anchor):
    target = (doc.parent / path).resolve()
    assert target.exists(), f"{doc.name} links to a missing path: {path}"


@pytest.mark.parametrize(
    "doc,text,path,anchor", LINE_ANCHORS, ids=_ids(LINE_ANCHORS)
)
def test_line_anchor_still_points_at_the_symbol(doc, text, path, anchor):
    lineno = int(LINE_ANCHOR_RE.fullmatch(anchor).group(1))
    lines = (doc.parent / path).read_text().splitlines()
    assert lineno <= len(lines), (
        f"{doc.name} links to {path}#L{lineno}, but that file has "
        f"{len(lines)} lines"
    )

    symbol = _symbol(text)
    if symbol is None:
        return
    line = lines[lineno - 1]
    assert symbol in line, (
        f"{doc.name} links {symbol!r} to {path}#L{lineno}, but that line is:\n"
        f"    {line.strip()!r}\n"
        f"It probably moved — re-point the anchor."
    )


@pytest.mark.parametrize(
    "doc,text,path,anchor", SECTION_ANCHORS, ids=_ids(SECTION_ANCHORS)
)
def test_section_anchor_matches_a_heading(doc, text, path, anchor):
    target = (doc.parent / path) if path else doc
    headings = HEADING_RE.findall(target.read_text())
    slugs = {slugify(h) for h in headings}
    assert anchor in slugs, (
        f"{doc.name} links to #{anchor} in {target.name}, which has no such "
        f"heading. Closest headings: "
        f"{sorted(s for s in slugs if s[:6] == anchor[:6]) or sorted(slugs)[:5]}"
    )
