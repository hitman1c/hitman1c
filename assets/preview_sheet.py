#!/usr/bin/env python3
"""Build a single contact-sheet HTML page embedding every dashboard panel.

Used for visual review: rasterise the sheet with headless Edge and inspect
the result.  Not part of the shipped README.
"""
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "_preview.html")

ORDER = [
    "hero-boot.svg", "hero-station.svg", "hero-profile.svg", "wave-top.svg",
    "identity.svg", "system-status.svg",
    "proto-01.svg",
    "engineering.svg", "operational-thread.svg", "security-operations.svg",
    "proto-02.svg",
    "offensive-security.svg", "defensive-security.svg",
    "threat-model.svg", "web-security.svg", "security-arsenal.svg",
    "tool-icons.svg",
    "security-labs.svg", "security-research.svg", "agentic-engineering.svg",
    "ctf-arena.svg",
    "proto-03.svg", "proto-04.svg",
    "missions.svg",
    "proto-05.svg",
    "education.svg",
    "wave-bottom.svg", "connect.svg",
    "proto-06.svg",
    "footer.svg",
]

present = {os.path.basename(p) for p in glob.glob(os.path.join(HERE, "*.svg"))}
missing = [n for n in ORDER if n not in present]
extra = sorted(present - set(ORDER) - {"_preview.html"})
if missing:
    print("WARNING missing from contact sheet: %s" % missing)
if extra:
    print("WARNING not in contact sheet order: %s" % extra)

rows, cur, widths = [], [], []


def flush():
    if cur:
        rows.append((list(cur), sum(widths)))
        cur.clear()
        widths.clear()


for name in ORDER:
    if name not in present:
        continue
    head = open(os.path.join(HERE, name), encoding="utf-8").read(400)
    w = int(head.split('width="', 1)[1].split('"', 1)[0])
    cur.append((name, w))
    widths.append(w + 10)
    if len(cur) == 3:
        flush()
flush()

parts = ["<!doctype html><meta charset=utf-8>",
         "<style>body{background:#000;margin:0;padding:8px;"
         "font:11px monospace;color:#666}"
         "table{border-collapse:collapse;width:100%}"
         "td{vertical-align:top;padding:4px}"
         "img{display:block}</style><table>"]
for cells, total in rows:
    parts.append("<tr>")
    for name, w in cells:
        parts.append('<td><img src="%s" width="%d">'
                     '<div>%s %dx</div></td>'
                     % (os.path.join(HERE, name).replace("\\", "/"), w, name,
                        w))
    parts.append("</tr>")
parts.append("</table>")

with open(OUT, "w", encoding="utf-8") as fh:
    fh.write("".join(parts))
print("wrote %s" % OUT)
