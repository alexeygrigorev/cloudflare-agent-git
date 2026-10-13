"""Render the rehearsal test chart for the 12 October report from tests-data.json."""
import json
from pathlib import Path

here = Path(__file__).parent
d = json.loads((here / "tests-data.json").read_text())
W, H = 900, 330
x0, scale = 230, 1.4
rows = []
y = 120
for label, passed, failed in zip(d["labels"], d["passed"], d["failed"]):
    pw = passed * scale
    fw = max(failed * scale, 0)
    rows.append(f'<text x="214" y="{y + 26}" text-anchor="end" font-size="16" fill="#1c2027">{label}</text>')
    rows.append(f'<rect x="{x0}" y="{y}" width="{pw:.1f}" height="40" fill="#2455ed"/>')
    if failed:
        rows.append(f'<rect x="{x0 + pw:.1f}" y="{y}" width="{fw + 6:.1f}" height="40" fill="#ef7134"/>')
        note = f"{passed} passed, {failed} failed"
    else:
        note = f"{passed} passed"
    rows.append(f'<text x="{x0 + pw + fw + 16:.1f}" y="{y + 26}" font-size="15" fill="#1c2027">{note}</text>')
    y += 70
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="t d">
<title id="t">Test runs in the three-agent rehearsal</title>
<desc id="d">The first check ran 321 tests across the three pairs of agents, and 2 failed. After agent B fixed its code, all 323 passed. Counts are test runs, not unique tests.</desc>
<rect width="{W}" height="{H}" fill="#fcfcf8"/>
<g font-family="DejaVu Sans, Verdana, sans-serif">
<text x="40" y="50" font-family="Georgia, serif" font-size="28" fill="#1c2027">Test runs in the three-agent rehearsal</text>
<rect x="40" y="70" width="16" height="16" fill="#2455ed"/><text x="64" y="84" font-size="15" fill="#1c2027">Passed</text>
<rect x="160" y="70" width="16" height="16" fill="#ef7134"/><text x="184" y="84" font-size="15" fill="#1c2027">Failed</text>
{chr(10).join(rows)}
<text x="40" y="{H - 26}" font-size="15" fill="#4a505a">Test runs across the three pairs of agents, not unique tests.</text>
</g>
</svg>
'''
(here / "../../../assets/2026-10-12-tests.svg").resolve().write_text(svg)
print("ok")
