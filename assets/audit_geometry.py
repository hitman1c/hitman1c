#!/usr/bin/env python3
"""Geometry audit for the SECHABA.OS assets.

Rasterised previews cannot be eyeballed in this environment, so readability is
checked structurally instead:

  * every text run sits inside the panel it belongs to (not on a border)
  * no two text runs overlap
  * no two filled shapes overlap (chips, cards, pills)
  * every panel actually contains content
"""
import glob
import os
import sys
import xml.etree.ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SVG = "{http://www.w3.org/2000/svg}"
ADV = 0.60
TOL = 1.5          # px of tolerated overlap
HERE = os.path.dirname(os.path.abspath(__file__))

# Purely decorative wave ribbons -- intentionally text-free.
DECORATIVE = {"wave-top.svg", "wave-bottom.svg"}


def f(v, d=0.0):
    return float(v) if v is not None else d


def text_boxes(root):
    out = []
    for t in root.iter(SVG + "text"):
        s = t.text or ""
        if not s.strip():
            continue
        size = f(t.get("font-size"), 10)
        ls = f(t.get("letter-spacing"), 0)
        x, y = f(t.get("x")), f(t.get("y"))
        wid = len(s) * (size * ADV) + ls * len(s)
        anchor = t.get("text-anchor", "start")
        if anchor == "start":
            x0 = x
        elif anchor == "end":
            x0 = x - wid
        else:
            x0 = x - wid / 2
        # baseline y; cap height ~0.72em above, descender ~0.22em below
        out.append((x0, y - size * 0.74, x0 + wid, y + size * 0.24, s))
    return out


def solid_rects(root):
    """Filled (non-stroke-only) rectangles -- chips, pills, cards."""
    out = []
    for r in root.iter(SVG + "rect"):
        fill = r.get("fill", "none")
        if fill in ("none",):
            continue
        w, h = f(r.get("width")), f(r.get("height"))
        if w < 8 or h < 8:
            continue
        out.append((f(r.get("x")), f(r.get("y")), w, h, fill))
    return out


def overlap(a, b, tol=TOL):
    ox = min(a[2], b[2]) - max(a[0], b[0])
    oy = min(a[3], b[3]) - max(a[1], b[1])
    if ox > tol and oy > tol:
        return ox, oy
    return None


def audit(path):
    name = os.path.basename(path)
    with open(path, encoding="utf-8") as fh:
        root = ET.fromstring(fh.read())
    w, h = f(root.get("width")), f(root.get("height"))
    issues = []

    texts = text_boxes(root)
    rects = solid_rects(root)

    # containment: the outermost drawn card (or the canvas) bounds the content
    bounds = (0.0, 0.0, w, h)
    for (x, y, rw, rh, fill) in rects:
        if rw >= w * 0.92 and rh >= h * 0.80:
            bounds = (x, y, x + rw, y + rh)
    for (x0, y0, x1, y1, s) in texts:
        if (x0 < bounds[0] - TOL or x1 > bounds[2] + TOL
                or y0 < bounds[1] - 6 or y1 > bounds[3] + TOL):
            issues.append("text outside panel bounds: %r "
                          "(box %.1f,%.1f-%.1f,%.1f vs %.1f,%.1f-%.1f,%.1f)"
                          % (s[:44], x0, y0, x1, y1, *bounds))

    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            hit = overlap(texts[i], texts[j])
            if hit:
                issues.append("text collision (%.1fx%.1fpx): %r  <>  %r"
                              % (hit[0], hit[1], texts[i][4][:30],
                                 texts[j][4][:30]))

    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            a, b = rects[i], rects[j]
            ba, bb = (a[0], a[1], a[0] + a[2], a[1] + a[3]), \
                     (b[0], b[1], b[0] + b[2], b[1] + b[3])
            # ignore nested cards (one fully inside the other)
            if (ba[0] <= bb[0] + 1 and ba[1] <= bb[1] + 1
                    and ba[2] >= bb[2] - 1 and ba[3] >= bb[3] - 1):
                continue
            if (bb[0] <= ba[0] + 1 and bb[1] <= ba[1] + 1
                    and bb[2] >= ba[2] - 1 and bb[3] >= ba[3] - 1):
                continue
            hit = overlap(ba, bb)
            if hit:
                issues.append("shape overlap (%.1fx%.1fpx): %s at "
                              "(%.0f,%.0f %.0fx%.0f)  vs  (%.0f,%.0f %.0fx%.0f)"
                              % (hit[0], hit[1], a[4], a[0], a[1], a[2], a[3],
                                 b[0], b[1], b[2], b[3]))

    if not texts and name not in DECORATIVE:
        issues.append("panel contains no text")
    return name, w, h, len(texts), issues


def main():
    files = sorted(glob.glob(os.path.join(HERE, "*.svg")))
    total = 0
    for path in files:
        name, w, h, n, issues = audit(path)
        total += len(issues)
        if issues:
            print("FAIL %s" % name)
            for msg in issues:
                print("       %s" % msg)
        else:
            print("ok   %-28s %4dx%-4d %3d text runs" % (name, w, h, n))
    print()
    print("%d geometry problem(s)" % total if total
          else "geometry clean across %d assets" % len(files))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
