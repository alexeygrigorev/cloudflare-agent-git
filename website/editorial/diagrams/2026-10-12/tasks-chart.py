"""Render the task tracker chart for the 12 October report from tasks-data.json."""
import json
from pathlib import Path

here = Path(__file__).parent
d = json.loads((here / "tasks-data.json").read_text())
W, H = 820, 420
x0, scale = 190, 60.0
rows = []
y = 120
for name, created, closed in zip(d["projects"], d["created"], d["closed"]):
    rows.append(f'<text x="176" y="{y + 22}" text-anchor="end" font-size="16" fill="#1c2027">{name}</text>')
    rows.append(f'<rect x="{x0}" y="{y}" width="{created * scale:.1f}" height="20" fill="#2455ed"/>'
                f'<text x="{x0 + created * scale + 8:.1f}" y="{y + 16}" font-size="14" fill="#1c2027">{created} created</text>')
    rows.append(f'<rect x="{x0}" y="{y + 24}" width="{closed * scale:.1f}" height="20" fill="none" stroke="#ef7134" stroke-width="2"/>'
                f'<text x="{x0 + closed * scale + 8:.1f}" y="{y + 40}" font-size="14" fill="#1c2027">{closed} closed</text>')
    y += 66
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="t d">
<title id="t">Tasks created and closed in one day</title>
<desc id="d">Tasks created and closed in the day before Monday morning. The launcher opened eight tasks and Agent Branches two, with none closed. Messaging opened two and closed one, and the dashboard opened none.</desc>
<rect width="{W}" height="{H}" fill="#fcfcf8"/>
<g font-family="DejaVu Sans, Verdana, sans-serif">
<text x="40" y="50" font-family="Georgia, serif" font-size="28" fill="#1c2027">Tasks created and closed in one day</text>
<rect x="40" y="70" width="16" height="16" fill="#2455ed"/><text x="64" y="84" font-size="15" fill="#1c2027">Created</text>
<rect x="180" y="70" width="16" height="16" fill="none" stroke="#ef7134" stroke-width="2"/><text x="204" y="84" font-size="15" fill="#1c2027">Closed</text>
{chr(10).join(rows)}
<text x="40" y="{H - 26}" font-size="15" fill="#4a505a">Total open tasks for that day aren't available.</text>
</g>
</svg>
'''
(here / "../../../assets/2026-10-12-tasks.svg").resolve().write_text(svg)
print("ok")
