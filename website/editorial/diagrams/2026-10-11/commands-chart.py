"""Render the command check chart for the 11 October report from commands-data.json."""
import json
from pathlib import Path

here = Path(__file__).parent
d = json.loads((here / "commands-data.json").read_text())
W, H = 820, 470
x0, scale = 200, 4.0
parts = []
y = 120
for name, n in zip(d["parts"], d["tests_passed"]):
    parts.append(f'<text x="{x0 - 14}" y="{y + 17}" text-anchor="end" font-size="16" fill="#1c2027">{name}</text>'
                 f'<rect x="{x0}" y="{y}" width="{n * scale:.1f}" height="24" fill="#2455ed"/>'
                 f'<text x="{x0 + n * scale + 8:.1f}" y="{y + 18}" font-size="15" fill="#1c2027">{n} passed</text>')
    y += 40
y += 30
checks = [f'<text x="40" y="{y}" font-family="Georgia, serif" font-size="20" fill="#1c2027">Other checks</text>']
y += 34
for i, (what, result) in enumerate(d["checks"]):
    open_ = i == len(d["checks"]) - 1
    mark = (f'<circle cx="50" cy="{y - 5}" r="7" fill="none" stroke="#ef7134" stroke-width="2"/>' if open_
            else f'<circle cx="50" cy="{y - 5}" r="7" fill="#2455ed"/>')
    checks.append(f'{mark}<text x="68" y="{y}" font-size="16" fill="#1c2027">{what}</text>'
                  f'<text x="330" y="{y}" font-size="16" fill="#4a505a">{result}</text>')
    y += 30
total = sum(d["tests_passed"])
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="t d">
<title id="t">The documented commands on one machine</title>
<desc id="d">All {total} tests passed: 114 for the Cloudflare version, 16 for the Git helper and 64 for the local version. On this machine, the server let signed-in requests through and refused anonymous ones. Six commands were still unchecked.</desc>
<rect width="{W}" height="{H}" fill="#fcfcf8"/>
<g font-family="DejaVu Sans, Verdana, sans-serif">
<text x="40" y="50" font-family="Georgia, serif" font-size="28" fill="#1c2027">{total} tests passed on one machine</text>
<text x="40" y="84" font-size="15" fill="#4a505a">Tests passed, by part of the entry</text>
{chr(10).join(parts)}
{chr(10).join(checks)}
</g>
</svg>
'''
(here / "../../../assets/2026-10-11-commands.svg").resolve().write_text(svg)
print("ok")
