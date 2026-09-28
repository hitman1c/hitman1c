#!/usr/bin/env python3
"""Validate the generated SECHABA.OS dashboard assets.

Checks each SVG for:
  * well-formed XML
  * no external references (fonts / images / scripts) -- GitHub blocks these
    inside an <img>, so they would silently render as a blank box
  * no text or shape escaping the viewBox
  * no glyph outside the safe set (box drawing, emoji and dingbats fall back
    inconsistently across platforms, so they are rejected here)
"""
import glob
import os
import sys
import xml.etree.ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SVG = "{http://www.w3.org/2000/svg}"
ADV = 0.60
HERE = os.path.dirname(os.path.abspath(__file__))

# U+00B7 middle dot, arrows, U+00D7 multiply, U+2014 em dash.
ALLOWED_NON_ASCII = {0x00B7, 0x00D7, 0x2014,
                     0x2190, 0x2191, 0x2192, 0x2193}

FORBIDDEN = ("<image", "<script", "xlink:href", 'href="http', 'src="http',
             "@import", "<foreignObject", "url(http", "<use ")


def check_text(root, name, w, h):
    issues = 0
    for t in root.iter(SVG + "text"):
        s = t.text or ""
        size = float(t.get("font-size", 10))
        ls = float(t.get("letter-spacing", 0) or 0)
        x = float(t.get("x", 0))
        y = float(t.get("y", 0))
        anchor = t.get("text-anchor", "start")
        wid = len(s) * (size * ADV) + ls * len(s)

        if anchor == "start":
            lo, hi = x, x + wid
        elif anchor == "end":
            lo, hi = x - wid, x
        else:
            lo, hi = x - wid / 2, x + wid / 2

        if lo < -0.5:
            print("FAIL %-28s text clips left edge  y=%.0f  %r"
                  % (name, y, s[:44]))
            issues += 1
        if hi > w + 0.5:
            print("FAIL %-28s text overflows right by %.1fpx  y=%.0f  %r"
                  % (name, hi - w, y, s[:44]))
            issues += 1
        if y > h + 0.5:
            print("FAIL %-28s text below canvas  y=%.0f  %r"
                  % (name, y, s[:44]))
            issues += 1
        for ch in s:
            cp = ord(ch)
            if cp > 127 and cp not in ALLOWED_NON_ASCII:
                print("FAIL %-28s unsafe glyph U+%04X in %r" % (name, cp, s))
                issues += 1
    return issues


def check_shapes(root, name, w, h):
    issues = 0
    for r in root.iter(SVG + "rect"):
        x = float(r.get("x", 0))
        y = float(r.get("y", 0))
        rw = float(r.get("width", 0))
        rh = float(r.get("height", 0))
        if x + rw > w + 0.5:
            print("FAIL %-28s rect overflows right by %.1fpx  y=%.0f"
                  % (name, x + rw - w, y))
            issues += 1
        if y + rh > h + 0.5:
            print("FAIL %-28s rect overflows bottom by %.1fpx  x=%.0f"
                  % (name, y + rh - h, x))
            issues += 1
    return issues


def main():
    files = sorted(glob.glob(os.path.join(HERE, "*.svg")))
    if not files:
        print("no svg assets found in %s" % HERE)
        return 1
    fail = 0
    for path in files:
        name = os.path.basename(path)
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as e:
            print("FAIL %-28s malformed XML: %s" % (name, e))
            fail += 1
            continue

        w = float(root.get("width"))
        h = float(root.get("height"))
        issues = 0
        for bad in FORBIDDEN:
            if bad in raw:
                print("FAIL %-28s blocked construct %r" % (name, bad))
                issues += 1
        issues += check_text(root, name, w, h)
        issues += check_shapes(root, name, w, h)
        fail += issues
        if not issues:
            print("ok   %-28s %4dx%-4d %6d B" % (name, w, h, len(raw)))

    print()
    if fail:
        print("%d problem(s) across %d assets" % (fail, len(files)))
        return 1
    print("all %d assets valid" % len(files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
