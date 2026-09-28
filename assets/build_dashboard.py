#!/usr/bin/env python3
"""
SECHABA.OS -- cyber operations dashboard asset builder.

Renders the panel set described in AGENTS.md into standalone SVG files that
GitHub can display inside a profile README via <img>.

Why generated: the reference composition is a dense multi-column grid with
pixel-tight spacing. Hand-maintaining 30 panels of absolute coordinates is
unmaintainable, so the geometry is computed here instead.

Design constraints honoured:
  * No external resources (fonts / images / scripts). Everything is inlined so
    the SVGs render identically inside an <img> tag, where external fetches
    are blocked by the browser.
  * No box-drawing, emoji or dingbat glyphs -- those fall back inconsistently
    across platforms. Shell prompts are drawn as vector paths instead.
  * Panel heights auto-fit their content, so adding a line of text can never
    silently push copy outside the border.
  * Text width is estimated at 0.60 * font-size, the monospace advance ratio
    every monospace font honours closely.

Usage:  python assets/build_dashboard.py
"""

import math
import os
import re

# --------------------------------------------------------------------------
# Canvas
# --------------------------------------------------------------------------

W = 1024
GUT = 14
BOTTOM_PAD = 12

# Column geometry derived from the reference architecture.
HALF_L, HALF_R = 332, 682
SIXTY, FORTY = 604, 406
THIRD = 328

# --------------------------------------------------------------------------
# Palette
# --------------------------------------------------------------------------

BG = "#020607"        # page
PANEL = "#071012"     # card fill
PANEL2 = "#0A1416"    # nested box fill

GREEN = "#00FF66"     # system / status / commands
CYAN = "#00E5FF"      # engineering / interface
PINK = "#FF0055"      # protocol / offensive
PURPLE = "#9B4DFF"    # AI / agentic
TEXT = "#D8E4E6"      # body copy
MUTED = "#738688"     # metadata

MONO = ("'JetBrains Mono','Fira Code',ui-monospace,SFMono-Regular,Consolas,"
        "'DejaVu Sans Mono',monospace")
ADV = 0.60            # monospace advance ratio

GLOW = {"g": GREEN, "c": CYAN, "p": PINK, "v": PURPLE, "m": MUTED}
GLOW_KEY = {GREEN: "g", CYAN: "c", PINK: "p", PURPLE: "v",
            "#FFB800": "m", MUTED: "m"}

# Theme-adaptive rendering. Panels are drawn with the dark palette as their
# presentation attributes, plus a <style> block that overrides those colours
# via CSS variables when the viewer's page prefers a light scheme
# (@media (prefers-color-scheme: light)). This is the part of SMIL -- and
# CSS -- that GitHub allows inside an <img>: it resolves against the
# embedding page's theme, so the same file renders correctly on both.
TCOL = {BG: "--bg", PANEL: "--panel", PANEL2: "--panel2",
        GREEN: "--grn", CYAN: "--cyn", PINK: "--pnk", PURPLE: "--pur",
        TEXT: "--txt", MUTED: "--mut",
        "#FFB800": "--amb", "#04161A": "--pill"}
LIGHT = {"--bg": "#FFFFFF", "--panel": "#F6F8FA", "--panel2": "#EAF0F3",
         "--grn": "#0A7A35", "--cyn": "#0B6F8D", "--pnk": "#C01352",
         "--pur": "#7733CC", "--txt": "#1F2328", "--mut": "#59636E",
         "--amb": "#B7791F", "--pill": "#E4EEF1"}


def col(v):
    """Map a palette colour to a theme CSS variable (others pass through)."""
    t = TCOL.get(v)
    return ("var(%s)" % t) if t else v


def theme_style():
    """Inline stylesheet: dark defaults on :root, light overrides."""
    root = "".join("%s:%s;" % (v, k) for k, v in TCOL.items())
    light = "".join("%s:%s;" % (v, c) for v, c in LIGHT.items())
    return ("<style>:root{%s}@media (prefers-color-scheme: light)"
            "{:root{%s}}</style>" % (root, light))

BRAND = {
    "Java": "#ED8B00", "Python": "#3776AB", "JavaScript": "#F7DF1E",
    "TypeScript": "#3178C6", "C#": "#239120", "C++": "#00599C",
    "PHP": "#777BB4", "SQL": "#4479A1", "Bash": "#4EAA25",
    "HTML5": "#E34F26", "CSS3": "#1572B6", "React": "#61DAFB",
    "Node.js": "#339933", "Flask": "#C3C7CE", ".NET": "#512BD4",
    "MySQL": "#4479A1", "PostgreSQL": "#4169E1",
    "Linux": "#FCC624", "KALI": "#367BF0", "REDHAT": "#EE0000",
    "Wireshark": "#1679A7", "Nmap": "#468847", "BURP": "#FF6633",
    "ZAP": "#00A6E0", "NETCAT": "#8B949E", "METASPLOIT": "#FF003C",
}

GLOW_INV = {"JavaScript": "c", "Linux": "c", "KALI": "c", "Wireshark": "c",
            "Nmap": "g", "BURP": "p", "ZAP": "c", "METASPLOIT": "p",
            "Python": "c", "REDHAT": "p", "React": "c"}


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def tw(s, size, ls=0):
    """Estimated rendered width of a monospace string."""
    n = len(str(s))
    return n * size * ADV + n * ls


NUM = re.compile(r"-?\d+(?:\.\d+)?")
TOK = re.compile(r"[MmLlHhVvCcSsQqTtZz]|-?\d+(?:\.\d+)?")
ARGC = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2}


def path_bbox(d):
    """Bounding box of an SVG path, honouring relative commands.

    A naive max() over every number in the string mixes the x and y
    extents, which silently inflates auto-fitted canvas heights.
    """
    toks = TOK.findall(d)
    xs, ys = [], []
    cx = cy = 0.0
    start = (0.0, 0.0)
    cmd = None
    i = 0
    while i < len(toks):
        t = toks[i]
        if t.isalpha():
            cmd = t
            i += 1
            if cmd in "Zz":
                cx, cy = start
                continue
        if cmd is None:
            i += 1
            continue
        rel = cmd.islower()
        up = cmd.upper()
        args = [float(v) for v in toks[i:i + ARGC[up]]]
        i += ARGC[up]
        if len(args) < ARGC[up]:
            break
        if up == "M":
            nx, ny = (cx + args[0], cy + args[1]) if rel else args[:2]
            cx, cy = nx, ny
            start = (cx, cy)
            cmd = "l" if rel else "L"   # implicit lineto for extra pairs
        elif up == "L":
            cx, cy = ((cx + args[0], cy + args[1]) if rel else args[:2])
        elif up == "H":
            cx = cx + args[0] if rel else args[0]
        elif up == "V":
            cy = cy + args[0] if rel else args[0]
        else:  # C / S / Q / T -- only the end point is needed
            cx, cy = ((cx + args[-2], cy + args[-1]) if rel
                      else args[-2:])
        xs.append(cx)
        ys.append(cy)
    if not xs:
        return 0.0, 0.0
    return max(xs), max(ys)


# --------------------------------------------------------------------------
# Canvas
# --------------------------------------------------------------------------

class Canvas:
    def __init__(self, w, h, bg=BG, title=""):
        self.w = w
        self.h = h
        self.bg = bg
        self.title = title
        self.e = []
        self.mx = 0.0
        self.my = 0.0

    def _bump(self, x, y):
        self.mx = max(self.mx, x)
        self.my = max(self.my, y)

    # -- primitives --------------------------------------------------------

    def rect(self, x, y, w, h, rx=6, fill="none", stroke=None, sw=1,
             op=1, sop=1, glow=None):
        a = ('<rect x="%s" y="%s" width="%s" height="%s" rx="%s" fill="%s"'
             % (x, y, w, h, rx, col(fill)))
        if stroke:
            a += ' stroke="%s" stroke-width="%s" stroke-opacity="%s"' % (
                col(stroke), sw, sop)
        if op != 1:
            a += ' opacity="%s"' % op
        if glow:
            a += ' filter="url(#g%s)"' % glow
        self.e.append(a + "/>")
        self._bump(x + w, y + h)

    def text(self, x, y, s, size=10, fill=TEXT, anchor="start", weight=None,
             ls=None, op=1, glow=None):
        a = ('<text x="%s" y="%s" font-size="%s" fill="%s" text-anchor="%s"'
             ' xml:space="preserve"' % (x, y, size, col(fill), anchor))
        if weight:
            a += ' font-weight="%s"' % weight
        if ls:
            a += ' letter-spacing="%s"' % ls
        if op != 1:
            a += ' opacity="%s"' % op
        if glow:
            a += ' filter="url(#g%s)"' % glow
        self.e.append(a + ">%s</text>" % esc(s))
        wid = tw(s, size) + (ls or 0) * len(str(s))
        if anchor == "start":
            hi = x + wid
        elif anchor == "end":
            self._bump(x, y + size * 0.28)
            hi = x - wid
        else:
            self._bump(x + wid / 2, y + size * 0.28)
            hi = x + wid / 2
        self._bump(hi, y + size * 0.28)

    def line(self, x1, y1, x2, y2, stroke=MUTED, sw=1, op=1, sop=None):
        sop = op if sop is None else sop
        self.e.append('<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" '
                      'stroke-width="%s" stroke-opacity="%s"/>'
                      % (x1, y1, x2, y2, col(stroke), sw, sop))
        self._bump(max(x1, x2), max(y1, y2))

    def path(self, d, fill="none", stroke=None, sw=1, sop=1, op=1,
             glow=None, cap="round", join="round"):
        a = '<path d="%s" fill="%s"' % (d, col(fill))
        if stroke:
            a += (' stroke="%s" stroke-width="%s" stroke-opacity="%s" '
                  'stroke-linecap="%s" stroke-linejoin="%s"'
                  % (col(stroke), sw, sop, cap, join))
        if op != 1:
            a += ' opacity="%s"' % op
        if glow:
            a += ' filter="url(#g%s)"' % glow
        self.e.append(a + "/>")
        self._bump(*path_bbox(d))

    def dot(self, cx, cy, r, fill, op=1, glow=None):
        a = '<circle cx="%s" cy="%s" r="%s" fill="%s"' % (cx, cy, r, col(fill))
        if op != 1:
            a += ' opacity="%s"' % op
        if glow:
            a += ' filter="url(#g%s)"' % glow
        self.e.append(a + "/>")
        self._bump(cx + r, cy + r)

    # -- animation (SMIL) ---------------------------------------------------
    # SMIL <animate> runs inside an <img> SVG, where <script> and external
    # fetches are blocked. All effects here are opacity / transform based, so
    # they are compositor-friendly and never re-rasterise a path.

    def _reattach(self, a):
        """Turn the last element into `<el>..anim..</el>`.

        Handles both self-closing primitives (`<rect .../>`) and text
        elements (`<text ...>..</text>`).
        """
        base = self.e[-1]
        tag = base[1:base.index(" ")]
        if base.endswith("/>"):
            self.e[-1] = base[:-2] + ">" + a + "/></" + tag + ">"
        else:
            close = "</" + tag + ">"
            assert base.endswith(close)
            self.e[-1] = base[:-len(close)] + a + "/>" + close

    def animate(self, attr, values, dur, keyTimes=None, begin=None,
                repeat="indefinite", fill=None):
        a = '<animate attributeName="%s" values="%s" dur="%s"' % (
            attr, values, dur)
        if keyTimes:
            a += ' keyTimes="%s"' % keyTimes
        if begin:
            a += ' begin="%s"' % begin
        a += ' repeatCount="%s"' % repeat
        if fill:
            a += ' fill="%s"' % fill
        self._reattach(a)

    def blink(self):
        """Hard on/off blink for orbs and cursors already baseline-visible."""
        self.animate("opacity", "1;1;0;0", "1.1s", keyTimes="0;0.45;0.55;1")

    def pulse(self, lo=0.55, hi=1.0, dur="2.4s", begin=None):
        """Soft breathe for status LEDs / badges."""
        self.animate("opacity", "%s;%s;%s" % (lo, hi, lo), dur, begin=begin)

    def reveal(self, at, dur="0.25s"):
        """Reveal the most recently drawn (opacity-0) element once, later."""
        self.animate("opacity", "0;1", dur, begin="%ss" % at,
                     repeat="1", fill="freeze")

    def cursor(self, x, bl, h=9, w=4.5, col=GREEN, off=0.0):
        """Blinking block insertion cursor sitting on text baseline `bl`."""
        self.rect(x, bl - h + 1, w, h, rx=1, fill=col, op=0)
        t = off + 1.6
        kt = ("0;%s;%s;%s;%s;1" % (
            round(off / t, 3), round((off + 0.05) / t, 3),
            round((off + 0.8) / t, 3), round((off + 0.9) / t, 3)))
        self.animate("opacity", "0;0;1;1;0;0", "%ss" % round(t, 2),
                     keyTimes=kt)

    def slide(self, values, dur="6.5s", begin=None):
        """Animate the last element's translation through `values`."""
        a = ('<animateTransform attributeName="transform" type="translate" '
             'values="%s" dur="%s"' % (values, dur))
        if begin:
            a += ' begin="%s"' % begin
        a += ' repeatCount="indefinite"/>'
        self._reattach(a)

    # -- output ------------------------------------------------------------

    def render(self):
        defs = ['<defs>', theme_style()]
        for k, gcol in GLOW.items():
            defs.append(
                '<filter id="g%s" x="-60%%" y="-60%%" width="220%%" '
                'height="220%%"><feGaussianBlur stdDeviation="2.2" '
                'result="b"/><feMerge><feMergeNode in="b"/><feMergeNode '
                'in="SourceGraphic"/></feMerge></filter>' % k)
        defs.append(
            '<linearGradient id="wg" x1="0" y1="0" x2="1" y2="0">'
            '<stop offset="0" stop-color="%s"/><stop offset="0.55" '
            'stop-color="%s"/><stop offset="1" stop-color="%s"/>'
            '</linearGradient>' % (col(GREEN), col(CYAN), col(PINK)))
        defs.append(
            '<linearGradient id="wfill" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0" stop-color="%s" stop-opacity="0.30"/>'
            '<stop offset="1" stop-color="%s" stop-opacity="0.02"/>'
            '</linearGradient>' % (col(GREEN), col(PINK)))
        defs.append("</defs>")
        return ('<svg xmlns="http://www.w3.org/2000/svg" width="%s" '
                'height="%s" viewBox="0 0 %s %s" role="img">%s'
                '<title>%s</title>'
                '<rect width="%s" height="%s" fill="%s"/>%s</svg>'
                % (self.w, self.h, self.w, self.h, "".join(defs),
                   esc(self.title), self.w, self.h, col(self.bg),
                   "".join(self.e)))


# --------------------------------------------------------------------------
# Chrome
# --------------------------------------------------------------------------

def panel(c, x, y, w, h, accent, title=None, glow=None, pad=14,
          fill=PANEL, r=9, title_size=12, sub=None):
    """Thin neon card. Returns the y coordinate where content may start."""
    c.rect(x, y, w, h, rx=r, fill=fill, stroke=accent, sw=1, sop=0.5)
    if glow:
        c.rect(x, y, w, h, rx=r, stroke=accent, sw=1, sop=0.16, glow=glow)
    cy = y + pad
    if title is not None:
        c.text(x + pad, cy + title_size, title, title_size, accent,
               weight="600", ls=0.8)
        c.line(x + pad, cy + title_size + 7, x + w - pad,
               cy + title_size + 7, accent, 1, 0.3)
        cy += title_size + 15
        if sub:
            c.text(x + pad, cy + 9, sub, 9, MUTED)
            cy += 17
    return cy + 2


def terminal(c, x, y, w, h, accent, path, glow=None, r=9, dots=True):
    """Kali-style window with a title bar. Returns content start y."""
    c.rect(x, y, w, h, rx=r, fill=PANEL, stroke=accent, sw=1, sop=0.5)
    if glow:
        c.rect(x, y, w, h, rx=r, stroke=accent, sw=1, sop=0.16, glow=glow)
    c.line(x + r, y + 21, x + w - r, y + 21, accent, 1, 0.3)
    if dots:
        for i, col in enumerate((PINK, "#FFB800", GREEN)):
            c.dot(x + 14 + i * 12, y + 11, 3.2, col, 0.85)
    c.text(x + 56, y + 15, path, 10, accent, op=0.95)
    return y + 33


def prompt(c, x, y, cmd, s=10, col=GREEN):
    """Shell prompt with the corner bracket drawn as vector strokes.

    Avoids U+2514 / U+2500, which are missing from some monospace fonts.
    """
    c.path("M %s %s L %s %s L %s %s" % (x, y, x, y - 5, x + 6, y - 5),
           stroke=col, sw=1.1, sop=0.9)
    c.line(x + 6, y - 5, x + 15, y - 5, stroke=col, sw=1.1, sop=0.9)
    c.text(x + 19, y, "$", s, col, weight="700")
    if cmd:
        c.text(x + 19 + tw("$ ", s), y, cmd, s, col, weight="600")
    return x + 19 + tw("$ ", s) + (tw(cmd, s) if cmd else 0)


def tri_down(c, cx, y, r, col, op=1.0):
    c.path("M %s %s L %s %s L %s %s Z" % (cx - r, y - r * 1.6, cx + r,
                                          y - r * 1.6, cx, y),
           fill=col, op=op)


def tri_right(c, cx, cy, r, col, op=1.0):
    c.path("M %s %s L %s %s L %s %s Z" % (cx - r * 1.6, cy - r, cx - r * 1.6,
                                          cy + r, cx, cy),
           fill=col, op=op)


def check(c, x, y, col=GREEN, s=1.0):
    """Vector checkmark -- safer than the U+2713 glyph."""
    c.path("M %s %s L %s %s L %s %s" % (x, y + 3.4 * s, x + 2.6 * s,
                                        y + 6 * s, x + 6.6 * s, y),
           stroke=col, sw=1.5 * s, glow="g")


def _wrap(s, size, maxw):
    words, line, out = str(s).split(" "), "", []
    for wd in words:
        t = (line + " " + wd).strip()
        if tw(t, size) > maxw and line:
            out.append(line)
            line = wd
        else:
            line = t
    if line:
        out.append(line)
    return out


def para(c, x, y, w, s, size=8, color=MUTED, lh=11):
    for i, ln in enumerate(_wrap(s, size, w)):
        c.text(x, y + i * lh, ln, size, color)
    return y + len(_wrap(s, size, w)) * lh


def vflow(c, x, y, w, items, accent, bh=28, gap=15, size=10, fill=PANEL2):
    """Vertical chain of boxes joined by arrows."""
    cx = x + w / 2
    for i, it in enumerate(items):
        yy = y + i * (bh + gap)
        c.rect(x, yy, w, bh, rx=5, fill=fill, stroke=accent, sw=1, sop=0.45)
        c.text(cx, yy + bh / 2 + size * 0.36, it, size, TEXT, anchor="middle")
        if i < len(items) - 1:
            ay = yy + bh
            c.line(cx, ay + 2, cx, ay + gap - 5, accent, 1.1, 0.7)
            tri_down(c, cx, ay + gap, 3.4, accent, 0.85)
    return y + len(items) * bh + (len(items) - 1) * gap


def bullets(c, x, y, w, items, accent, cols=2, size=10, rh=18, colgap=12):
    colw = (w - (cols - 1) * colgap) / cols
    for i, it in enumerate(items):
        cc, rr = i % cols, i // cols
        bx = x + cc * (colw + colgap)
        by = y + rr * rh
        c.rect(bx, by + size * 0.28, 4, 4, rx=1, fill=accent, op=0.9)
        c.text(bx + 9, by + size, it, size, TEXT)
    rows = (len(items) + cols - 1) // cols
    return y + rows * rh


def chips(c, x, y, w, labels, size=9, rh=20, gap=6, vgap=6, h=18,
          palette=None, text_fill=None):
    """Wrapping small rectangular chips; brand colours when supplied."""
    cx, cy = x, y
    for lb in labels:
        col = (palette or {}).get(lb, MUTED)
        cw = tw(lb, size) + 14
        if cx + cw > x + w and cx > x:
            cx = x
            cy += rh + vgap
        c.rect(cx, cy, cw, h, rx=4, fill=col, stroke=col, sw=1, sop=0.85,
               op=0.16)
        c.text(cx + cw / 2, cy + h / 2 + size * 0.36, lb, size,
               text_fill or col, anchor="middle")
        cx += cw + gap
    return cy + h


def wave_path(x0, x1, ybase, amp, period, phase, steps=200):
    pts = []
    for i in range(steps + 1):
        t = i / steps
        x = x0 + (x1 - x0) * t
        y = ybase + amp * math.sin(2 * math.pi * (x / period) + phase)
        pts.append("%s %s" % (round(x, 2), round(y, 2)))
    return "M " + " L ".join(pts)


def wave_fill(x0, x1, ybase, amp, period, phase, bottom, steps=200):
    p = wave_path(x0, x1, ybase, amp, period, phase, steps)
    return "%s L %s %s L %s %s Z" % (p, x1, bottom, x0, bottom)


# --------------------------------------------------------------------------
# Block-letter font (drawn as rects -> font independent, true "ASCII" feel)
# --------------------------------------------------------------------------

GLYPHS = {
    "A": (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "B": ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    "C": (".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."),
    "E": ("#####", "#....", "#....", "###..", "#....", "#....", "#####"),
    "H": ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "I": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"),
    "N": ("#...#", "##..#", "##..#", "#.#.#", "#..##", "#..##", "#...#"),
    "O": (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "S": (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    "T": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
}


def block_word(c, word, x, y, p, col, glow="g"):
    adv = 6 * p
    for i, ch in enumerate(word):
        rows = GLYPHS.get(ch)
        if not rows:
            continue
        ox = x + i * adv
        for ry, row in enumerate(rows):
            for rx, cell in enumerate(row):
                if cell == "#":
                    c.rect(ox + rx * p, y + ry * p, p, p, rx=0, fill=col,
                           op=0.95, glow=glow)
    return len(word) * adv - p


def block_width(word, p):
    return len(word) * 6 * p - p


# --------------------------------------------------------------------------
# Dragon motif
# --------------------------------------------------------------------------

DRAGON_BODY = ("M 92 30 L 80 24 L 68 26 L 60 34 L 52 44 L 38 48 L 26 54 "
               "L 12 60 L 2 66 L 14 66 L 28 64 L 40 68 L 52 68 L 60 64 "
               "L 64 54 L 74 44 L 84 40")
DRAGON_HIND = "M 40 68 L 38 84 L 44 90 L 48 90 L 46 84 L 48 68"
DRAGON_FORE = "M 60 64 L 60 80 L 66 86 L 70 86 L 67 80 L 68 64"
DRAGON_WING = "M 52 44 L 26 10 L 50 20 L 62 30 L 58 42"
DRAGON_WING2 = "M 52 44 L 40 22 L 58 40"
DRAGON_HORN1 = "M 80 24 L 78 15"
DRAGON_HORN2 = "M 74 25 L 70 16"
DRAGON_TAIL = "M 12 60 L 4 52 L 10 54"


def dragon(c, x, y, s, col=GREEN, glow="g"):
    """Angular neon dragon motif.

    The path data is authored in a 0-100 local box and baked into absolute
    coordinates here, so the auto-fit extent tracking stays accurate (an SVG
    <g transform> would hide the real bounds from it).
    """
    k = s / 100.0

    def P(d, close=True):
        nums = [float(v) for v in NUM.findall(d)]
        pts = [(round(x + nums[i] * k, 2), round(y + nums[i + 1] * k, 2))
               for i in range(0, len(nums), 2)]
        out = "M %s %s" % pts[0]
        for p in pts[1:]:
            out += " L %s %s" % p
        return out + (" Z" if close else "")

    c.path(P(DRAGON_BODY), fill=col, stroke=col, sw=1.2, sop=0.95, op=0.16,
           glow=glow)
    c.path(P(DRAGON_HIND), fill=col, stroke=col, sw=1, sop=0.85, op=0.12)
    c.path(P(DRAGON_FORE), fill=col, stroke=col, sw=1, sop=0.85, op=0.12)
    c.path(P(DRAGON_WING), fill=col, stroke=col, sw=1.1, sop=0.9, op=0.1,
           glow=glow)
    c.path(P(DRAGON_TAIL, close=False), stroke=col, sw=1, sop=0.7)
    c.path(P(DRAGON_WING2, close=False), stroke=col, sw=0.9, sop=0.5)
    c.path(P(DRAGON_HORN1, close=False), stroke=col, sw=1, sop=0.8)
    c.path(P(DRAGON_HORN2, close=False), stroke=col, sw=1, sop=0.8)
    c.dot(x + 0.78 * s, y + 0.30 * s, 0.022 * s, PINK, 1, "p")


# ==========================================================================
# ASSETS  -- every builder takes an optional height so the build loop can
# auto-fit the panel to its content.
# ==========================================================================

def a_hero_boot(h=None):
    h = h or 196
    c = Canvas(212, h, title="SECHABA.OS boot sequence log")
    y = 16
    at = 0.0
    for line in ("Initializing Sechaba.OS...",
                 "Loading security protocols...",
                 "Establishing secure connection...",
                 "Identity verified..."):
        c.text(12, y, ">", 9, GREEN, weight="700")
        c.text(24, y, line, 9, GREEN, op=0)
        c.reveal(at)
        y += 14
        at += 0.35
    c.text(12, y, "ACCESS GRANTED", 10, GREEN, weight="700", ls=1.2,
           glow="g", op=0)
    c.reveal(at)
    y += 24
    c.line(12, y - 12, 200, y - 12, GREEN, 1, 0.28)
    at += 0.45
    for r in ("SOFTWARE ENGINEER", "CYBERSECURITY", "ETHICAL HACKING",
              "SECURITY ENGINEERING", "LINUX & NETWORK SECURITY",
              "AGENTIC ENGINEERING"):
        c.text(12, y, ">", 9, CYAN, weight="700")
        c.text(24, y, r, 9, CYAN, op=0)
        c.reveal(at)
        y += 14
        at += 0.22
    c.cursor(24 + tw("AGENTIC ENGINEERING", 9) + 2, y - 14, h=8, w=4,
             off=at)
    c.rect(12, y + 4, 26, 5, rx=2, fill=GREEN, op=0.8, glow="g")
    c.text(44, y + 10, "booting", 8, MUTED)
    return c


def a_hero_station(h=None):
    h = h or 196
    c = Canvas(536, h, title="SECHABA STATION hero wordmark")
    c.rect(0, 0, 536, h, rx=9, fill=PANEL, stroke=GREEN, sw=1, sop=0.5)
    c.rect(0, 0, 536, h, rx=9, stroke=GREEN, sw=1, sop=0.14, glow="g")

    p = 9
    w1 = block_width("SECHABA", p)
    top = max(26, (h - (2 * 7 * p + 12 + 46)) / 2)
    block_word(c, "SECHABA", (536 - w1) / 2, top, p, GREEN)
    block_word(c, "STATION", (536 - w1) / 2, top + 7 * p + 12, p, GREEN)
    c.text(268, top + 14 * p + 22, "SECHABA.OS", 11, CYAN, anchor="middle",
           ls=3.2, weight="600")
    c.text(268, top + 14 * p + 40,
           "> Build  \u00B7  Secure  \u00B7  Automate  \u00B7  Improve"
           "  \u00B7  Repeat", 9.5, GREEN, anchor="middle", ls=0.6)

    for (cx, cy, dx, dy) in ((8, 8, 1, 1), (528, 8, -1, 1),
                             (8, h - 8, 1, -1), (528, h - 8, -1, -1)):
        c.path("M %s %s h %s M %s %s v %s"
               % (cx + dx * 12, cy, dx * 12, cx, cy + dy * 8, dy * 8),
               stroke=CYAN, sw=1, sop=0.4)
    return c


def a_hero_profile(h=None):
    h = h or 196
    c = Canvas(256, h, title="Kali terminal identity profile")
    y = terminal(c, 0, 0, 256, h, GREEN, "sechaba@kali:~/profile", "g")
    pad = 12
    steps = [("whoami", "SECHABA SEABATA", CYAN, 10.5, True),
             ("id", "uid=software-engineer", TEXT, 8.5, False),
             (None, "gid=security", TEXT, 8.5, False),
             (None, "groups=linux,networking,", TEXT, 8.5, False),
             (None, "cybersecurity,red-team,agents", TEXT, 8.5, False),
             ("hostname", "sechaba-01", CYAN, 9, False),
             ("role", "Software Engineer \u00B7 Cybersecurity", TEXT, 8, False),
             (None, "Ethical Hacking \u00B7 Security Eng.", TEXT, 8, False),
             (None, "Linux & Network Security \u00B7 Agents", TEXT, 8, False)]
    reveal_at = [0.2, 0.6, 0.9, 1.2, 1.45, 1.8, 2.1, 2.4, 2.7]
    for k, (cmd, out, col, sz, big) in enumerate(steps):
        if cmd:
            y += 3
            prompt(c, pad, y, cmd, 8.5)
            y += 13
        c.text(pad, y, out, sz, col, weight="600" if big else None,
               ls=0.8 if big else None, glow="c" if big else None, op=0)
        c.reveal(reveal_at[k])
        y += 8
    y += 2
    prompt(c, pad, y, "status", 8.5)
    y += 14
    for i, s in enumerate(("[ONLINE]", "[ACCESS GRANTED]",
                           "[SYSTEMS OPERATIONAL]")):
        c.text(pad, y, s, 9, GREEN, weight="700", glow="g")
        c.pulse(0.55, 1.0, "2.2s", begin="%ss" % (3.0 + i * 0.35))
        y += 13
    c.cursor(pad + tw("[SYSTEMS OPERATIONAL]", 9) + 2, y - 13, h=8, w=4,
             off=3.6)
    return c


def a_wave_top(h=None):
    h = h or 84
    c = Canvas(W, h, title="Neon cyber energy wave")
    base = h / 2
    c.path(wave_fill(-4, W + 4, base, 15, 420, 0.0, h), fill="url(#wfill)")
    c.path(wave_path(-4, W + 4, base, 15, 420, 0.0), stroke="url(#wg)",
           sw=2, sop=0.95, glow="g")
    c.path(wave_path(-4, W + 4, base + 4, 9, 300, 2.1), stroke=PINK, sw=1.4,
           sop=0.7, glow="p")
    c.path(wave_path(-4, W + 4, base - 6, 7, 250, 4.0), stroke=CYAN, sw=1,
           sop=0.45)
    c.slide("0 0; 10 0; 0 0", dur="8s")
    return c


def a_wave_bottom(h=None):
    h = h or 128
    c = Canvas(W, h, title="Neon cyber energy wave, footer")
    base = h * 0.58
    c.path(wave_fill(-4, W + 4, base, 26, 520, 0.9, h), fill="url(#wfill)")
    c.path(wave_path(-4, W + 4, base, 26, 520, 0.9), stroke="url(#wg)",
           sw=2.4, sop=1, glow="g")
    c.path(wave_path(-4, W + 4, base + 8, 15, 360, 3.0), stroke=PINK, sw=1.8,
           sop=0.8, glow="p")
    c.path(wave_path(-4, W + 4, base - 10, 12, 300, 5.2), stroke=CYAN, sw=1.2,
           sop=0.5)
    c.path(wave_path(-4, W + 4, base + 16, 10, 280, 6.1), stroke=PINK, sw=1,
           sop=0.35)
    c.slide("0 0; -12 0; 0 0", dur="9s")
    return c


def a_identity(h=None):
    h = h or 200
    c = Canvas(SIXTY, h, title="Identity and secure connection panel")
    y = panel(c, 0, 0, SIXTY, h, CYAN, "IDENTITY / SECURE CONNECTION", "c")
    dragon(c, 26, y + 14, 100)
    c.pulse(0.3, 1.0, "3.4s")
    tx = 146
    c.text(tx, y + 8, "KALI", 9, GREEN, ls=2.4, weight="700")
    c.text(tx, y + 22, "DRAGON", 9, GREEN, ls=2.4, weight="700", op=0.8)

    ty = y + 48
    for line in ("establishing connection...", "verifying identity...",
                 "loading security protocols...", "access granted."):
        granted = line.startswith("access")
        c.text(tx, ty, ">", 9, GREEN, weight="700")
        c.text(tx + 12, ty, line, 9.5, GREEN if granted else TEXT,
               weight="600" if granted else None, glow="g" if granted else None)
        if granted:
            c.pulse(0.7, 1.0, "2.8s")
            c.cursor(tx + 12 + tw("access granted.", 9.5) + 2, ty, h=8, w=4)
        ty += 15

    ty += 6
    c.text(tx, ty, "SECHABA SEABATA", 16, CYAN, weight="700", ls=1.2,
           glow="c")
    ty += 19
    c.text(tx, ty, "SOFTWARE ENGINEER  \u00B7  CYBERSECURITY", 9, TEXT, ls=0.4)
    c.text(tx, ty + 13, "ETHICAL HACKING  \u00B7  SECURITY ENGINEERING", 9,
           TEXT, ls=0.4)
    ty += 32
    c.rect(tx, ty - 7, 8, 8, rx=2, fill=GREEN, op=0.9, glow="g")
    c.text(tx + 14, ty, "Maseru, Lesotho", 9.5, GREEN)
    c.text(tx + 14 + tw("Maseru, Lesotho", 9.5), ty, "  \u00B7  LSO", 9.5,
           MUTED)
    ty += 12
    c.line(tx, ty, SIXTY - 16, ty, CYAN, 1, 0.25)
    ty = para(c, tx, ty + 14, SIXTY - 16 - tx,
              "Security research and offensive-security activities are "
              "conducted within authorized, controlled and educational "
              "environments.", 8, MUTED, 11)
    return c


def a_system_status(h=None):
    h = h or 200
    c = Canvas(FORTY, h, title="systemctl status sechaba")
    y = terminal(c, 0, 0, FORTY, h, GREEN, "sechaba@kali:~/operations", "g")
    ex = prompt(c, 14, y, "systemctl status sechaba", 9.5)
    c.cursor(ex, y, h=8, w=4, off=0.5)
    y += 16
    for i, s in enumerate(("SOFTWARE ENGINEERING", "CYBERSECURITY",
                           "ETHICAL HACKING", "LINUX & NETWORK SECURITY",
                           "SECURITY ENGINEERING", "AGENTIC ENGINEERING")):
        c.text(14, y, s, 9, TEXT)
        c.text(FORTY - 14, y, "[ ACTIVE ]", 9, GREEN, anchor="end",
               weight="700", glow="g")
        c.pulse(0.6, 1.0, "2.2s", begin="%ss" % (0.8 + i * 0.3))
        y += 15
    y += 5
    c.line(14, y - 9, FORTY - 14, y - 9, GREEN, 1, 0.3)
    c.text(14, y + 5, "Loaded: loaded (/etc/init.d/sechaba)", 8.5, MUTED)
    c.text(14, y + 18, "Active: active (running)", 8.5, GREEN, weight="600")
    c.dot(FORTY - 20, y + 14, 3.4, GREEN, 1, "g")
    c.pulse(0.5, 1.0, "2.4s", begin="1.4s")
    return c


def a_engineering(h=None):
    h = h or 480
    c = Canvas(HALF_L, h, title="Software engineering dashboard panel")
    y = panel(c, 0, 0, HALF_L, h, PINK, "SOFTWARE ENGINEERING", "p",
              title_size=15)
    c.text(14, y + 2, "Software Engineer Intern at Africa Code Academy",
           8.5, TEXT)
    c.text(14, y + 14, "Computing Honours \u2014 Software Engineering at "
           "Botho University", 8.5, TEXT, op=0.85)
    y = para(c, 14, y + 30, HALF_L - 28,
             "Building web applications and real-world software systems with "
             "focus on architecture, databases, security, infrastructure, "
             "automation and deployment.", 8, MUTED, 11)
    y += 10

    core_h = 148
    c.rect(12, y, HALF_L - 24, core_h, rx=7, fill=PANEL2, stroke=CYAN,
           sw=1, sop=0.45)
    c.text(24, y + 16, "ENGINEERING CORE", 9, CYAN, weight="700", ls=1.4)
    c.line(24, y + 22, HALF_L - 24, y + 22, CYAN, 1, 0.25)
    bullets(c, 24, y + 34, HALF_L - 48,
            ["Software Engineering", "System Design", "Frontend Engineering",
             "API Development", "Testing", "Git", "Secure Development",
             "System Architecture", "Backend Engineering",
             "Database Engineering", "Authentication", "CI/CD", "Deployment"],
            CYAN, cols=2, size=8.5, rh=15.5, colgap=10)
    y += core_h + 16

    groups = [("Languages", ["Java", "Python", "JavaScript", "TypeScript",
                             "C#", "C++", "PHP", "SQL", "Bash"]),
              ("Frontend", ["HTML5", "CSS3", "React"]),
              ("Backend & Databases", ["Node.js", "Flask", ".NET", "MySQL",
                                       "PostgreSQL"])]
    for gname, items in groups:
        c.text(14, y, gname.upper(), 8, PINK, weight="700", ls=1.2, op=0.9)
        c.rect(14, y + 4, 5, 5, rx=1, fill=PINK, op=0.9)
        y = chips(c, 14, y + 10, HALF_L - 28, items, size=8.5, h=16, rh=16,
                  gap=5, vgap=5, palette=BRAND,
                  text_fill="#04121A") + 14
    c.line(14, y - 4, HALF_L - 14, y - 4, PINK, 1, 0.22)
    c.text(14, y + 10, "TOP LANGUAGES", 8.5, PINK, weight="700", ls=1.2)
    para(c, 14, y + 21, HALF_L - 28,
         "Live telemetry rendered in the README column below \u2014 real "
         "account data, never hardcoded.", 7.5, MUTED, 10)
    return c


def a_thread(h=None):
    h = h or 300
    c = Canvas(248, h, title="Operational thread: how the disciplines connect")
    y = panel(c, 0, 0, 248, h, GREEN, "OPERATIONAL THREAD", "g",
              title_size=11.5)
    items = ["SOFTWARE ENGINEERING", "SYSTEMS & ARCHITECTURE",
             "LINUX & NETWORKING", "CYBERSECURITY", "ETHICAL HACKING",
             "SECURITY ENGINEERING", "AI ENGINEERING", "AGENTIC ENGINEERING"]
    end = vflow(c, 14, y, 220, items, GREEN, bh=21, gap=9, size=8.5, )
    c.line(14, end + 12, 234, end + 12, GREEN, 1, 0.25)
    ty = end + 26
    for t in ("Build systems", "Understand how they fail",
              "Understand how they are attacked", "Secure them",
              "Engineer them with AI"):
        c.text(124, ty, t, 8, CYAN, anchor="middle", op=0.9)
        ty += 11
    return c


def a_soc(h=None):
    h = h or 300
    c = Canvas(424, h, title="Security operations centre capability grid")
    y = panel(c, 0, 0, 424, h, CYAN, "SECURITY OPERATIONS CENTER", "c",
              title_size=13)
    items = ["Cybersecurity", "Offensive Security", "Application Security",
             "Network Security", "API Security", "Security Automation",
             "Vulnerability Assessment", "Ethical Hacking",
             "Defensive Security", "Web Security", "Linux Security",
             "Security Engineering", "Threat Analysis"]
    bullets(c, 14, y + 4, 396, items, CYAN, cols=2, size=9, rh=19, colgap=16)
    return c


def _grid_flow(c, x, y, w, items, accent, per_row=4, bw=76, gap=5,
               size=7.5, lh=9):
    """Boxes laid out per_row wide, joined left to right by arrows.

    The box height grows to fit the tallest wrapped label so nothing is ever
    clipped, and `bw` is derived from the available width.
    """
    bw = min(bw, (w - (per_row - 1) * gap) / per_row)
    bh = max(24, max(len(_wrap(it, size, bw - 8)) for it in items) * lh + 8)
    for i, it in enumerate(items):
        col, row = i % per_row, i // per_row
        bx = x + col * (bw + gap)
        by = y + row * (bh + 15)
        c.rect(bx, by, bw, bh, rx=5, fill=PANEL2, stroke=accent, sw=1,
               sop=0.45)
        words = _wrap(it, size, bw - 8)
        oy = by + bh / 2 - (len(words) - 1) * lh / 2 + size * 0.36
        for wi, word in enumerate(words):
            c.text(bx + bw / 2, oy + wi * lh, word, size, TEXT,
                   anchor="middle")
        if col < per_row - 1 and i < len(items) - 1:
            ax = bx + bw + gap / 2
            c.line(ax, by + bh / 2, ax + 3, by + bh / 2, accent, 1, 0.7)
            tri_right(c, ax + 4, by + bh / 2, 2.6, accent, 0.85)
    rows = (len(items) - 1) // per_row + 1
    return y + rows * (bh + 15)


def a_offensive(h=None):
    h = h or 200
    c = Canvas(332, h, title="Offensive security workflow")
    y = panel(c, 0, 0, 332, h, PINK, "OFFENSIVE SECURITY", "p",
              title_size=11.5)
    items = ["Reconnaissance", "Enumeration", "Attack Surface Analysis",
             "Vulnerability Discovery", "Controlled Exploitation",
             "Privilege Escalation", "Post-Exploitation", "Reporting"]
    y = _grid_flow(c, 14, y, 304, items, PINK, 4, 76, 24, 5, 7.5) + 8
    c.line(14, y, 318, y, PINK, 1, 0.22)
    y += 14
    for s in ("Target: authorized engagement", "Scope: confirmed",
              "Authorization: verified", "Proceeding..."):
        c.text(14, y, "[+]", 8, GREEN, weight="700")
        c.text(34, y, s, 8, TEXT)
        if s == "Proceeding...":
            c.pulse(0.55, 1.0, "2.0s", begin="1.2s")
            c.cursor(34 + tw(s, 8) + 1, y, h=7, w=3.5, off=1.6)
        y += 12
    return c


def a_defensive(h=None):
    h = h or 200
    c = Canvas(340, h, title="Defensive security workflow")
    y = panel(c, 0, 0, 340, h, GREEN, "DEFENSIVE SECURITY", "g",
              title_size=11.5)
    items = ["Detection", "Analysis", "Threat ID", "Hardening", "Monitoring",
             "Incident Response", "Improvement"]
    y = _grid_flow(c, 14, y, 312, items, GREEN, 4, 62, 24, 5, 7.5) + 8
    c.line(14, y, 326, y, GREEN, 1, 0.22)
    y += 14
    c.text(14, y, "Understand attacks. Understand systems. Build secure "
           "software.", 8, TEXT)
    c.text(14, y + 13, "That is security engineering.", 8, CYAN,
           weight="600")
    return c


def a_threat_model(h=None):
    h = h or 250
    c = Canvas(220, h, title="Threat model chain")
    y = panel(c, 0, 0, 220, h, PINK, "THREAT MODEL", "p", title_size=10.5)
    items = ["ASSETS", "THREATS", "ATTACK SURFACE", "VULNERABILITIES", "RISK",
             "CONTROLS", "MONITORING"]
    y = vflow(c, 14, y, 192, items, PINK, bh=17, gap=7, size=8) + 14
    c.line(14, y - 6, 206, y - 6, PINK, 1, 0.22)
    c.text(110, y + 8, "Identify \u00B7 Prioritise \u00B7 Control", 7.5, MUTED,
           anchor="middle")
    return c


def a_web_security(h=None):
    h = h or 250
    c = Canvas(220, h, title="Web security topic coverage")
    y = panel(c, 0, 0, 220, h, CYAN, "WEB SECURITY", "c", title_size=10.5)
    items = ["Authentication", "Authorization", "Access Control", "Injection",
             "XSS", "CSRF", "SSRF", "API Security", "Session Security",
             "Security Misconfiguration"]
    y = bullets(c, 14, y, 192, items, CYAN, cols=1, size=8.5, rh=14.5) + 8
    c.line(14, y - 4, 206, y - 4, CYAN, 1, 0.22)
    c.text(14, y + 9, "Application \u2192 Attack Surface", 7.5, MUTED)
    c.text(14, y + 20, "\u2192 Vulnerability \u2192 Mitigation", 7.5, MUTED)
    return c


def a_arsenal(h=None):
    h = h or 250
    c = Canvas(222, h, title="Security arsenal summary")
    y = panel(c, 0, 0, 222, h, GREEN, "SECURITY ARSENAL", "g",
              title_size=10.5)
    groups = [("SYSTEMS", "Linux \u00B7 Kali \u00B7 Red Hat \u00B7 Bash"),
              ("NETWORK", "Nmap \u00B7 Wireshark \u00B7 Netcat"),
              ("WEB", "Burp Suite \u00B7 OWASP ZAP"),
              ("TESTING", "Metasploit"),
              ("AUTOMATION", "Python \u00B7 Bash \u00B7 Git")]
    for gname, items in groups:
        c.text(14, y, gname, 7.5, PINK, weight="700", ls=1, op=0.9)
        for wi, ln in enumerate(_wrap(items, 8, 194)):
            c.text(14, y + 11 + wi * 10, ln, 8, TEXT)
        y += 11 + len(_wrap(items, 8, 194)) * 10 + 7
    c.line(14, y, 208, y, GREEN, 1, 0.22)
    c.text(14, y + 12, "Authorized environments only.", 7.5, MUTED)
    return c


def a_tool_icons(h=None):
    h = h or 212
    c = Canvas(W, h, title="Security tool icon grid")
    c.rect(0, 0, W, h, rx=9, fill=PANEL, stroke=GREEN, sw=1, sop=0.4)
    tools = ["Linux", "KALI", "REDHAT", "Wireshark", "Nmap", "BURP", "ZAP",
             "NETCAT", "METASPLOIT", "PYTHON", "BASH"]
    size, gap = 84, 12
    for ri, row in enumerate([tools[:7], tools[7:]]):
        total = len(row) * size + (len(row) - 1) * gap
        x = (W - total) / 2
        y = 16 + ri * (size + 12)
        for t in row:
            col = BRAND.get(t, GREEN)
            c.rect(x, y, size, size, rx=8, fill=PANEL2, stroke=col, sw=1,
                   sop=0.75)
            c.rect(x, y, size, size, rx=8, stroke=col, sw=1, sop=0.18,
                   glow=GLOW_INV.get(t))
            words = _wrap(t, 9, size - 12)
            oy = y + size / 2 - (len(words) - 1) * 6 + 3.5
            for wi, word in enumerate(words):
                c.text(x + size / 2, oy + wi * 12, word, 9,
                       "#04121A" if t == "JavaScript" else col,
                       anchor="middle", weight="600", ls=0.6)
            x += size + gap
    return c


def a_labs(h=None):
    h = h or 220
    c = Canvas(328, h, title="Security labs directory tree")
    y = terminal(c, 0, 0, 328, h, GREEN, "sechaba@kali:~/security-labs", "g")
    ex = prompt(c, 14, y, "tree", 9.5)
    c.cursor(ex, y, h=8, w=4, off=0.4)
    y += 16
    labs = ["/linux-security", "/network-security", "/web-security",
            "/reconnaissance", "/enumeration", "/penetration-testing",
            "/forensics", "/ctf", "/security-automation"]
    tx, ty = 20, y + 6
    c.line(tx, ty + 4, tx, ty + (len(labs) - 1) * 15 + 4, GREEN, 1, 0.3)
    for i, lb in enumerate(labs):
        yy = ty + i * 15
        c.line(tx, yy + 4, tx + 8, yy + 4, GREEN, 1, 0.3)
        c.rect(tx + 12, yy, 7, 7, rx=1.5, fill=GREEN, op=0.35)
        c.text(tx + 24, yy + 7, lb, 8.5, TEXT)
    c.line(14, h - 24, 314, h - 24, GREEN, 1, 0.22)
    c.text(14, h - 12, "Each lab documents objective \u00B7 environment "
           "\u00B7 tools \u00B7 method \u00B7 findings", 7, MUTED)
    return c


def a_research(h=None):
    h = h or 220
    c = Canvas(328, h, title="Security research directory")
    y = terminal(c, 0, 0, 328, h, CYAN, "sechaba@kali:~/research", "c")
    ex = prompt(c, 14, y, "ls", 9.5)
    c.cursor(ex, y, h=8, w=4, off=0.4)
    y += 16
    dirs = ["security-writeups/", "vulnerability-analyses/", "lab-findings/",
            "technical-notes/", "security-experiments/",
            "defensive-recommendations/"]
    for i, d in enumerate(dirs):
        yy = y + 4 + i * 17
        c.text(20, yy, ">", 8, GREEN, weight="700")
        c.text(32, yy, d, 9, CYAN)
    c.line(14, h - 30, 314, h - 30, CYAN, 1, 0.22)
    c.text(14, h - 18, "Write-ups, vulnerability analyses, lab findings", 7,
           MUTED)
    c.text(14, h - 8, "and technical notes.", 7, MUTED)
    return c


def a_ai_agent(h=None):
    h = h or 220
    c = Canvas(348, h, title="Agentic engineering agent loop")
    y = panel(c, 0, 0, 348, h, PURPLE, "AI / AGENT SYSTEMS", "v",
              title_size=11.5)
    stages = ["HUMAN", "CONTEXT", "AGENT", "TOOLS", "EXECUTION", "TESTING",
              "REVIEW", "IMPROVEMENT"]
    bw, bh, gx, gy = 148, 18, 16, 9
    for i, s in enumerate(stages):
        col = 0 if i < 4 else 1
        row = i % 4
        bx = 14 + col * (bw + gx)
        by = y + row * (bh + gy)
        c.rect(bx, by, bw, bh, rx=4, fill=PANEL2, stroke=PURPLE, sw=1,
               sop=0.5)
        c.text(bx + bw / 2, by + bh / 2 + 3, s, 8.5, TEXT, anchor="middle")
        if i < len(stages) - 1:
            if i < 3:
                c.line(bx + bw, by + bh / 2, bx + bw + 5, by + bh / 2,
                       PURPLE, 1, 0.7)
                tri_right(c, bx + bw + 7, by + bh / 2, 2.4, PURPLE, 0.85)
            elif i == 3:
                mid = bx + bw + gx + bw / 2
                c.line(bx + bw / 2, by + bh, bx + bw / 2, by + bh + 4,
                       PURPLE, 1, 0.7)
                c.line(bx + bw / 2, by + bh + 4, mid, by + bh + 4, PURPLE,
                       1, 0.7)
                c.line(mid, by + bh + 4, mid, by + bh + 8, PURPLE, 1, 0.7)
                tri_down(c, mid, by + bh + 9, 2.8, PURPLE, 0.85)
            else:
                c.line(bx - gx / 2, by + bh / 2, bx - 3, by + bh / 2, PURPLE,
                       1, 0.7)
                tri_right(c, bx - 1, by + bh / 2, 2.4, PURPLE, 0.85)
    ey = y + 4 * (bh + gy) + 4
    c.line(14, ey - 6, 334, ey - 6, PURPLE, 1, 0.22)
    c.text(14, ey + 7, "VIBE CODING \u2192 AI-ASSISTED DEVELOPMENT "
           "\u2192 AGENTIC ENGINEERING", 7.5, PURPLE, weight="600")
    c.text(14, ey + 19, "Agents \u00B7 skills \u00B7 MCP \u00B7 memory "
           "\u00B7 context \u00B7 spec-driven", 7.5, MUTED)
    return c


def a_ctf(h=None):
    h = h or 230
    c = Canvas(SIXTY, h, title="CTF challenge arena")
    y = panel(c, 0, 0, SIXTY, h, CYAN, "CTF // CAPTURE THE FLAG", "c",
              title_size=12.5)
    c.text(14, y + 2, "CTF CHALLENGE ARENA", 9, GREEN, weight="700", ls=1.6)
    c.text(14 + tw("CTF CHALLENGE ARENA", 9, 1.6) + 14, y + 2,
           "categories tracked", 8, MUTED)
    y += 12
    cats = ["WEB", "LINUX", "NETWORKING", "CRYPTO", "FORENSICS", "OSINT",
            "REVERSE ENGINEERING", "PRIVILEGE ESCALATION"]
    cx, cy = 14, y
    for cat in cats:
        cw = tw(cat, 8.5) + 22
        if cx + cw > SIXTY - 14 and cx > 14:
            cx = 14
            cy += 30
        c.rect(cx, cy, cw, 24, rx=12, fill="#04161A", stroke=CYAN, sw=1,
               sop=0.7)
        c.text(cx + cw / 2, cy + 15.5, cat, 8.5, CYAN, anchor="middle",
               weight="600", ls=0.5)
        cx += cw + 8
    ny = cy + 40
    c.line(14, ny - 10, SIXTY - 14, ny - 10, CYAN, 1, 0.22)
    c.text(14, ny + 2, "Documentation structure", 8, GREEN, weight="700",
           ls=1)
    c.text(14, ny + 14, "Platform \u00B7 Challenge \u00B7 Category "
           "\u00B7 Difficulty \u00B7 Date \u00B7 Write-up", 8, TEXT)
    c.text(14, ny + 27, "Challenges are listed only once actually solved "
           "\u2014 nothing is fabricated.", 7.5, MUTED)
    return c


def a_missions(h=None):
    h = h or 280
    c = Canvas(W, h, title="Mission cards: engineered systems")
    m = 6
    c.text(m, 16, "MISSIONS // ENGINEERED SYSTEMS", 12, PINK, weight="700",
           ls=1.6)
    c.line(m, 24, W - m, 24, PINK, 1, 0.25)
    cards = [
        ("MISSION // 001", "DEVICE MANAGEMENT", "SECHABA LAPTOP TRACKER",
         ["Track organizational devices and", "accountability.",
          "React \u00B7 TypeScript \u00B7 Database",
          "Authentication \u00B7 Access Control"]),
        ("MISSION // 002", "TENDER & PROCUREMENT", "PROCUREMENT WORKFLOWS",
         ["Structure and track complex tender", "processes.",
          "Users \u00B7 Auth \u00B7 APIs \u00B7 Dashboards",
          "Databases \u00B7 Business logic"]),
        ("MISSION // 003", "TIC-TAC-TOE", "ACA BY SECHABA",
         ["Build an interactive web game.", "Web technologies."]),
    ]
    cw = (W - 2 * m - 2 * GUT) / 3
    top, ch = 36, 150
    for i, (num, cat, ttl, lines) in enumerate(cards):
        x = m + i * (cw + GUT)
        c.rect(x, top, cw, ch, rx=8, fill=PANEL, stroke=GREEN, sw=1, sop=0.5)
        c.rect(x, top, cw, ch, rx=8, stroke=GREEN, sw=1, sop=0.14, glow="g")
        c.text(x + 14, top + 18, num, 8.5, GREEN, weight="700", ls=1.2)
        c.text(x + 14, top + 36, cat, 11, CYAN, weight="700", ls=0.5)
        c.text(x + 14, top + 50, ttl, 8, MUTED, ls=0.4)
        c.line(x + 14, top + 58, x + cw - 14, top + 58, GREEN, 1, 0.22)
        for li, ln in enumerate(lines):
            c.text(x + 14, top + 74 + li * 13, ln, 8, TEXT)
        pw = tw("[ COMPLETED ]", 8) + 20
        c.rect(x + 14, top + ch - 28, pw, 17, rx=8, fill=GREEN, op=0.16,
               stroke=GREEN, sw=1, sop=0.7)
        c.text(x + 14 + pw / 2, top + ch - 16, "[ COMPLETED ]", 8, GREEN,
               anchor="middle", weight="700")
        c.pulse(0.65, 1.0, "2.6s", begin="%ss" % (0.8 + i * 0.6))

    sy = top + ch + 16
    sh = 66
    c.rect(m, sy, 486, sh, rx=8, fill=PANEL, stroke=GREEN, sw=1, sop=0.35)
    c.text(m + 14, sy + 17, "MISSION 001 \u00B7 BUSINESS FLOW", 8, GREEN,
           weight="700", ls=1.2)
    qs = ["What devices do we have?",
          "Who is responsible for them?",
          "What is their current status?",
          "Can the organization account for them?"]
    for i, q in enumerate(qs):
        col, row = i % 2, i // 2
        check(c, m + 16 + col * 240, sy + 30 + row * 17, GREEN, 0.85)
        c.text(m + 30 + col * 240, sy + 36 + row * 17, q, 8, TEXT)

    bx = m + 486 + GUT
    bw = W - m - bx
    c.rect(bx, sy, bw, sh, rx=8, fill=PANEL, stroke=PINK, sw=1, sop=0.35)
    c.text(bx + 14, sy + 17, "MISSION 003 \u00B7 DEPLOYED", 8, PINK,
           weight="700", ls=1.2)
    c.text(bx + 14, sy + 36, "tic-tac-toe-aca-by-sechaba.vercel.app", 8, CYAN)
    c.text(bx + 14, sy + 51, "Playable \u2014 live link in the README.", 7.5,
           MUTED)
    return c


def a_education(h=None):
    h = h or 220
    c = Canvas(W, h, title="Education, active modules and research")
    c.rect(0, 0, W, h, rx=9, fill=PANEL, stroke=PINK, sw=1, sop=0.5)
    c.rect(0, 0, W, h, rx=9, stroke=PINK, sw=1, sop=0.14, glow="p")
    cols = [(14, 356, "BOTHO UNIVERSITY", GREEN,
             ["Computing Honours", "Software Engineering"], None),
            (388, 296, "ACTIVE MODULES", CYAN, None,
             ["Software Architecture", "Cybersecurity", "Linux",
              "Networking", "AI Agents", "MCP", "Agent Skills",
              "Context Engineering", "System Design", "Ethical Hacking"]),
            (702, 308, "ACTIVE RESEARCH", PURPLE, None,
             ["Security", "AI Agents", "Agent Skills",
              "Context Engineering", "Spec-Driven Development",
              "Knowledge Graphs", "Multi-Agent Systems"])]
    for x, w, title, col, sub, items in cols:
        c.text(x, 22, title, 10, col, weight="700", ls=1.2)
        c.line(x, 28, x + w - 10, 28, col, 1, 0.28)
        yy = 44
        if sub:
            for s in sub:
                c.text(x, yy, s, 10.5, TEXT, weight="600")
                yy += 17
            yy = para(c, x, yy + 4, w - 10,
                      "Topics: programming \u00B7 databases \u00B7 algorithms "
                      "\u00B7 systems \u00B7 architecture \u00B7 cybersecurity",
                      7.5, MUTED, 10)
        if items:
            bullets(c, x, yy, w - 10, items, col, cols=2, size=8.5, rh=16)
    c.line(14, h - 36, W - 14, h - 36, PINK, 1, 0.25)
    c.text(14, h - 21, "PROFESSIONAL EXPERIENCE", 8, PINK, weight="700",
           ls=1.2)
    c.text(14, h - 9, "Software Engineer Intern \u2014 Africa Code Academy",
           8.5, TEXT)
    c.text(388, h - 9, "Building, securing and automating \u2014 "
           "continuously expanding across the engineering spectrum.", 8, MUTED)
    return c


def a_contact(h=None):
    h = h or 200
    c = Canvas(FORTY, h, title="Contact and connect terminal")
    y = terminal(c, 0, 0, FORTY, h, GREEN, "sechaba@kali:~/contact", "g")
    ex = prompt(c, 14, y, "./connect.sh", 9.5)
    c.cursor(ex, y, h=8, w=4, off=0.4)
    y += 16
    for line, col in (("Initiating secure connection...", TEXT),
                      ("Encrypting channel...", TEXT),
                      ("Connection established.", GREEN)):
        c.text(14, y, ">", 8.5, GREEN, weight="700")
        c.text(26, y, line, 8.5, col, weight="600" if col == GREEN else None,
               glow="g" if col == GREEN else None)
        if col == GREEN:
            c.pulse(0.7, 1.0, "2.6s")
        y += 13
    y += 5
    c.line(14, y - 8, FORTY - 14, y - 8, GREEN, 1, 0.25)
    for lbl, a, b, col in (("PORTFOLIO", "sechabaseabataportfolio", ".netlify.app",
                            CYAN),
                           ("EMAIL", "sebatasechaba0", "@gmail.com", GREEN)):
        c.text(14, y, lbl, 8, MUTED, ls=0.6)
        c.text(92, y, a, 8.5, col)
        c.text(92 + tw(a, 8.5), y, b, 8.5, MUTED)
        y += 15
    c.text(14, y, "STATUS", 8, MUTED, ls=0.6)
    c.dot(84, y - 3, 3.4, GREEN, 1, "g")
    c.pulse(0.5, 1.0, "2.4s", begin="1.0s")
    c.text(94, y, "ONLINE", 8.5, GREEN, weight="700", op=0)
    c.reveal(1.6)
    c.text(14, y + 17, "Buttons below are live links.", 7.5, MUTED)
    return c


def a_footer(h=None):
    h = h or 104
    c = Canvas(W, h, title="Footer slogan and shutdown sequence")
    c.text(W / 2, 26, "BUILD  \u2192  SECURE  \u2192  AUTOMATE  \u2192  "
           "IMPROVE  \u2192  REPEAT", 15, GREEN, anchor="middle",
           weight="700", ls=1.6, glow="g")
    c.line(0, 40, W, 40, GREEN, 1, 0.2)
    for i, (l, v) in enumerate((("Profile", "hitman1c"),
                                ("Portfolio", "netlify.app"),
                                ("Email", "gmail.com"))):
        c.text(14, 58 + i * 13, l, 8, MUTED)
        c.text(80, 58 + i * 13, v, 8, CYAN)
    sx, sw_ = 548, W - 548 - 14
    c.rect(sx, 48, sw_, 46, rx=7, fill=PANEL, stroke=GREEN, sw=1, sop=0.45)
    for i, l in enumerate(("> SECURITY SESSION TERMINATED",
                           "> CONNECTION CLOSED",
                           "> SHUTDOWN SEQUENCE INITIATED...")):
        c.text(sx + 14, 64 + i * 12, l, 8.5, GREEN, weight="600")
    c.cursor(sx + 14 + tw("> SHUTDOWN SEQUENCE INITIATED...", 8.5) + 2,
             64 + 2 * 12, h=8, w=4, off=1.4)
    return c


def _a_protocol(label, accent, note=None, h=None):
    h = h or (46 if note else 34)
    c = Canvas(W, h, title="Protocol divider: %s" % label)
    c.rect(0, 0, W, h, rx=7, fill=PANEL, stroke=accent, sw=1, sop=0.45)
    c.rect(0, 0, 4, h, rx=2, fill=accent, op=0.9, glow=GLOW_KEY[accent])
    label_y = 22 if note else h / 2 + 4
    c.text(18, label_y, ">> %s <<" % label, 12, accent,
           weight="700", ls=1.4)
    c.cursor(18 + tw(">> %s <<" % label, 12, 1.4) + 2, label_y, h=10, w=5,
             off=0.5)
    if note:
        c.text(18, 36, note, 8.5, MUTED)
    c.rect(0, 9, 4, h - 18, fill=accent, op=0.35)
    c.slide("0 0; %s 0" % (W + 8), dur="6s")
    return c


# --------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------

ASSETS = [
    ("hero-boot.svg", a_hero_boot),
    ("hero-station.svg", a_hero_station),
    ("hero-profile.svg", a_hero_profile),
    ("wave-top.svg", a_wave_top),
    ("wave-bottom.svg", a_wave_bottom),
    ("identity.svg", a_identity),
    ("system-status.svg", a_system_status),
    ("engineering.svg", a_engineering),
    ("operational-thread.svg", a_thread),
    ("security-operations.svg", a_soc),
    ("offensive-security.svg", a_offensive),
    ("defensive-security.svg", a_defensive),
    ("threat-model.svg", a_threat_model),
    ("web-security.svg", a_web_security),
    ("security-arsenal.svg", a_arsenal),
    ("tool-icons.svg", a_tool_icons),
    ("security-labs.svg", a_labs),
    ("security-research.svg", a_research),
    ("agentic-engineering.svg", a_ai_agent),
    ("ctf-arena.svg", a_ctf),
    ("missions.svg", a_missions),
    ("education.svg", a_education),
    ("connect.svg", a_contact),
    ("footer.svg", a_footer),
]

PROTOS = [
    ("proto-01.svg", "SECURITY PROTOCOL // 01 \u2014 SYSTEM CORE",
     "Entering System Core \u00B7 Navigating Engineering Modules", PINK),
    ("proto-02.svg", "SECURITY PROTOCOL // 02 \u2014 VECTOR PATH",
     "Mapping Attack Surface \u00B7 Analysing Defence Posture", PINK),
    ("proto-03.svg", "AI PROTOCOL // 03 \u2014 AGENT SYSTEMS",
     "Initialising agent sandbox \u00B7 loading agent contexts", PURPLE),
    ("proto-04.svg", "MISSION CONTROL // 04 \u2014 OPERATIONS",
     "Deployed systems and their operational status", PINK),
    ("proto-05.svg", "SYSTEM PROTOCOL // 05 \u2014 EDUCATION",
     "Academic background and currently active modules", PINK),
    ("proto-06.svg", "NETWORK PROTOCOL // 06 \u2014 CONNECT",
     "Opening an encrypted channel", GREEN),
]

# Panels that share a row in the README are normalised to a common height so
# the grid does not read as ragged.
ROW_GROUPS = [
    ["hero-boot.svg", "hero-station.svg", "hero-profile.svg"],
    ["identity.svg", "system-status.svg"],
    ["offensive-security.svg", "defensive-security.svg"],
    ["threat-model.svg", "web-security.svg", "security-arsenal.svg"],
    ["security-labs.svg", "security-research.svg", "agentic-engineering.svg"],
]


def build():
    here = os.path.dirname(os.path.abspath(__file__))
    built = {}

    for name, fn in ASSETS:
        c = fn()
        need = c.my + BOTTOM_PAD
        if need > c.h:
            c = fn(math.ceil(need))
        built[name] = c

    for name, label, note, col in PROTOS:
        fn = (lambda lb, nt, cl: (lambda h=None: _a_protocol(lb, cl, nt, h)))(
            label, note, col)
        c = fn()
        need = c.my + 8
        if need > c.h:
            c = fn(math.ceil(need))
        built[name] = c

    # normalise row heights
    for group in ROW_GROUPS:
        target = max(math.ceil(built[n].my + BOTTOM_PAD) for n in group)
        for n in group:
            fn = dict(ASSETS)[n]
            c = fn(target)
            if c.my + BOTTOM_PAD > target:
                target = math.ceil(c.my + BOTTOM_PAD)
        for n in group:
            built[n] = dict(ASSETS)[n](target)

    for name, c in built.items():
        with open(os.path.join(here, name), "w", encoding="utf-8") as fh:
            fh.write(c.render())
    print("wrote %d assets to %s" % (len(built), here))
    for name in sorted(built):
        c = built[name]
        print("  %-28s %4dx%-4d" % (name, c.w, c.h))


if __name__ == "__main__":
    build()
