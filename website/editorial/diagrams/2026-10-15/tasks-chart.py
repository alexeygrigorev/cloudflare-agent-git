"""Render the narrow task tracker chart for the 15 October report from tasks-data.json."""
import json
from pathlib import Path

here = Path(__file__).parent
d = json.loads((here / "tasks-data.json").read_text())
W = 600
x0, scale = 40, 60.0
rows = []
y = 190
for name, created, closed, open_ in zip(d["projects"], d["created_past_day"], d["closed_past_day"], d["open_now"]):
    rows.append(f'<text x="{x0}" y="{y}" font-size="28" fill="#1c2027">{name}</text>'
                f'<text x="{W - 40}" y="{y}" text-anchor="end" font-size="28" fill="#1c2027">{open_}</text>')
    rows.append(f'<rect x="{x0}" y="{y + 14}" width="{max(created * scale, 3):.1f}" height="22" fill="#2455ed"/>'
                f'<text x="{x0 + max(created * scale, 3) + 10:.1f}" y="{y + 33}" font-size="26" fill="#1c2027">{created} created</text>')
    rows.append(f'<rect x="{x0 + 240}" y="{y + 14}" width="{max(closed * scale, 3):.1f}" height="22" fill="none" stroke="#ef7134" stroke-width="2"/>'
                f'<text x="{x0 + 240 + max(closed * scale, 3) + 10:.1f}" y="{y + 33}" font-size="26" fill="#1c2027">{closed} closed</text>')
    y += 96
H = y + 70
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="t d">
<title id="t">Tasks created and closed since yesterday morning, and open now</title>
<desc id="d">The counts start yesterday morning and cover only part of the day. So far, agents opened one task in the main repository and no tracker closed any. The right column shows each tracker's open tasks.</desc>
<rect width="{W}" height="{H}" fill="#fcfcf8"/>
<g font-family="DejaVu Sans, Verdana, sans-serif">
<text x="40" y="60" font-family="Georgia, serif" font-size="36" fill="#1c2027">Tasks since yesterday</text>
<text x="40" y="104" font-size="26" fill="#4a505a">Covers only part of the day</text>
<text x="{W - 40}" y="150" text-anchor="end" font-size="26" fill="#4a505a">Open now</text>
{chr(10).join(rows)}
<text x="40" y="{H - 30}" font-size="26" fill="#4a505a">No cancelled tasks were found.</text>
</g>
</svg>
'''
(here / "../../../assets/2026-10-15-tasks.svg").resolve().write_text(svg)
print(W, H)
