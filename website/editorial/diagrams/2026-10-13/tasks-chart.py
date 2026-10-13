"""Render the task tracker chart for the 13 October report from tasks-data.json."""
import json
from pathlib import Path

here = Path(__file__).parent
d = json.loads((here / "tasks-data.json").read_text())
W, H = 820, 440
x0, scale = 190, 12.0
rows = []
y = 130
for name, closed, open_ in zip(d["projects"], d["closed_total"], d["open_total"]):
    rows.append(f'<text x="176" y="{y + 22}" text-anchor="end" font-size="16" fill="#1c2027">{name}</text>')
    rows.append(f'<rect x="{x0}" y="{y}" width="{closed * scale:.1f}" height="20" fill="#2455ed"/>'
                f'<text x="{x0 + closed * scale + 8:.1f}" y="{y + 16}" font-size="14" fill="#1c2027">{closed}</text>')
    rows.append(f'<rect x="{x0}" y="{y + 24}" width="{open_ * scale:.1f}" height="20" fill="none" stroke="#ef7134" stroke-width="2"/>'
                f'<text x="{x0 + open_ * scale + 8:.1f}" y="{y + 40}" font-size="14" fill="#1c2027">{open_}</text>')
    y += 66
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="t d">
<title id="t">Tasks closed and still open, by project</title>
<desc id="d">Total tasks closed and still open in each project's tracker. Agent Branches has closed the most, and the launcher has the most open. In the past day, one task was created and none were closed.</desc>
<rect width="{W}" height="{H}" fill="#fcfcf8"/>
<g font-family="DejaVu Sans, Verdana, sans-serif">
<text x="40" y="50" font-family="Georgia, serif" font-size="28" fill="#1c2027">Tasks closed and still open, so far</text>
<rect x="40" y="70" width="16" height="16" fill="#2455ed"/><text x="64" y="84" font-size="15" fill="#1c2027">Closed in total</text>
<rect x="240" y="70" width="16" height="16" fill="none" stroke="#ef7134" stroke-width="2"/><text x="264" y="84" font-size="15" fill="#1c2027">Still open</text>
{chr(10).join(rows)}
<text x="40" y="{H - 26}" font-size="15" fill="#4a505a">In the past day: {d["past_day_created"]} task created, {d["past_day_closed"]} closed.</text>
</g>
</svg>
'''
(here / "../../../assets/2026-10-13-tasks.svg").resolve().write_text(svg)
print("ok")
