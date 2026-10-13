"""Render timeline.json as a flat editorial timeline SVG."""
import json
import sys
from html import escape
from pathlib import Path

spec = json.loads(Path(sys.argv[1]).read_text())
width, height = 1060, 400
x0, x1, axis_y = 60, 1000, 270
scale = (x1 - x0) / spec["axis_max"]
ink, cobalt, orange, muted = "#1c2027", "#2455ed", "#ef7134", "#5b6270"
out = [
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="t d">',
    f'<title id="t">{escape(spec["title"])}</title>',
    f'<desc id="d">{escape(spec["description"])}</desc>',
    f'<rect width="{width}" height="{height}" fill="#fcfcf8"/>',
    '<g font-family="DejaVu Sans, Verdana, sans-serif">',
    f'<text x="40" y="54" font-family="Georgia, serif" font-size="28" fill="{ink}">{escape(spec["title"])}</text>',
    f'<line x1="{x0}" y1="{axis_y}" x2="{x1}" y2="{axis_y}" stroke="{ink}" stroke-width="2"/>',
]
for m in range(0, spec["axis_max"] + 1, 10):
    x = x0 + m * scale
    out.append(f'<line x1="{x}" y1="{axis_y}" x2="{x}" y2="{axis_y + 8}" stroke="{ink}" stroke-width="2"/>')
    out.append(f'<text x="{x}" y="{axis_y + 30}" text-anchor="middle" font-size="15" fill="{muted}">{m} min</text>')
# Early events cluster near the start: stagger them downward and line their
# labels up to the right of the last early marker, joined by a short leader.
levels = [120, 160, 200]
early_x = x0 + max(e["minute"] for e in spec["events"] if e["minute"] < 10) * scale + 40
for i, e in enumerate(spec["events"]):
    x = x0 + e["minute"] * scale
    early = e["minute"] < 10
    label_y = levels[i] if early else (160 if e["kind"] == "miss" else 120)
    color = {"ok": cobalt, "miss": muted, "fail": orange}[e["kind"]]
    top = label_y - 1 if early else label_y + 8
    out.append(f'<line x1="{x}" y1="{top}" x2="{x}" y2="{axis_y}" stroke="{color}" stroke-width="2"/>')
    if early:
        out.append(f'<line x1="{x}" y1="{top}" x2="{early_x - 8}" y2="{top}" stroke="{color}" stroke-width="2"/>')
    if e["kind"] == "fail":
        out.append(f'<circle cx="{x}" cy="{axis_y}" r="10" fill="{orange}"/>')
    elif e["kind"] == "miss":
        out.append(f'<circle cx="{x}" cy="{axis_y}" r="8" fill="#fcfcf8" stroke="{muted}" stroke-width="2"/>')
    else:
        out.append(f'<rect x="{x - 7}" y="{axis_y - 7}" width="14" height="14" fill="{cobalt}"/>')
    anchor = "start" if early else "end"
    tx = early_x if early else x - 10
    out.append(f'<text x="{tx}" y="{label_y + 4}" text-anchor="{anchor}" font-size="17" fill="{ink}">{escape(e["label"])} · {e["minute"]} min</text>')
out.append(f'<text x="40" y="{height - 30}" font-size="15" fill="{muted}">{escape(spec["note"])}</text>')
out += ["</g>", "</svg>"]
Path(sys.argv[2]).write_text("\n".join(out) + "\n")
