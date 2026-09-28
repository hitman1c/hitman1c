#!/usr/bin/env python3
"""Measure the dashboard composition for horizontal overflow.

Extracts the table / image blocks from README.md, rebuilds them as a page and
injects a script that reports scrollWidth. Headless Edge is then used with
--dump-dom to read the measurement back at several viewport widths.
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
raw = io.open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()

blocks = re.findall(r"<table>.*?</table>|<p align=\"center\">.*?</p>", raw,
                    re.S)
body = "\n".join(blocks)

probe = """
<script>
window.addEventListener('load', function () {
  var d = document.documentElement;
  var over = [];
  document.querySelectorAll('img,table,td').forEach(function (el) {
    var r = el.getBoundingClientRect();
    if (r.right > d.clientWidth + 1) {
      over.push(el.tagName + ':' + (el.getAttribute('src') ||
           (el.textContent||'').slice(0,20)) + '=' + Math.round(r.right));
    }
  });
  var o = document.createElement('div');
  o.id = 'metrics';
  o.textContent = JSON.stringify({
    vw: d.clientWidth,
    scrollW: d.scrollWidth,
    overflow: d.scrollWidth - d.clientWidth,
    offenders: over.slice(0, 12)
  });
  document.body.appendChild(o);
});
</script>
"""

html = ("<!doctype html><meta charset=utf-8><style>"
        "body{background:#020607;margin:0;padding:10px;"
        "font:12px monospace;color:#888}"
        "table{border-collapse:collapse}"
        "td{vertical-align:top;padding:3px}"
        "img{display:block;max-width:100%}"
        "</style><body>" + body + probe)

out = os.path.join(ROOT, "_compose.html")
io.open(out, "w", encoding="utf-8").write(html)
print("wrote %s (%d composition blocks)" % (out, len(blocks)))
