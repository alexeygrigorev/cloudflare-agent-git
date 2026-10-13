"""Render agents.json as a flat editorial bar chart SVG."""
import json
import sys
from html import escape
from pathlib import Path

spec = json.loads(Path(sys.argv[1]).read_text())
groups = spec["groups"]
width, row_h, top = 1000, 54, 120
height = top + row_h * len(groups) + 70
label_x, bar_x, unit = 360, 380, 200
out = [
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="t d">',
    f'<title id="t">{escape(spec["title"])}</title>',
    f'<desc id="d">{escape(spec["description"])}</desc>',
    f'<rect width="{width}" height="{height}" fill="#fcfcf8"/>',
    '<g font-family="DejaVu Sans, Verdana, sans-serif">',
    f'<text x="40" y="54" font-family="Georgia, serif" font-size="28" fill="#1c2027">{escape(spec["title"])}</text>',
    '<rect x="40" y="76" width="16" height="16" fill="#2455ed"/>',
    '<text x="64" y="90" font-size="15" fill="#1c2027">Agents, by what they delivered</text>',
]
for i, g in enumerate(groups):
    y = top + i * row_h
    w = g["agents"] * unit
    out.append(f'<text x="{label_x}" y="{y + 22}" text-anchor="end" font-size="17" fill="#1c2027">{escape(g["label"])}</text>')
    out.append(f'<rect x="{bar_x}" y="{y + 4}" width="{w}" height="26" fill="#2455ed"/>')
    out.append(f'<text x="{bar_x + w + 10}" y="{y + 23}" font-size="16" fill="#1c2027">{g["agents"]}</text>')
out.append(f'<text x="40" y="{height - 30}" font-size="14" fill="#5b6270">{escape(spec["note"])}</text>')
out += ["</g>", "</svg>"]
Path(sys.argv[2]).write_text("\n".join(out) + "\n")
