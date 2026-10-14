# Demo diagrams

Open [index.html](index.html#architecture) to show one picture at a time. Use arrow keys or buttons to change scenes, or open a scene's direct URL fragment. The gallery works as a local file or through the server command in the [recording script](../demo-recording-script.md).

These pictures explain architecture, concurrent work and the fixture safety states. They don't claim a live run succeeded. The authenticated client remains on a user-owned computer, while Cloudflare hosts storage and coordination.

Each figure has an editable JSON specification, an accessible SVG and a matching PNG. The JSON selects diagram-creator's `editorial` style, matching the site's warm paper, ink and cobalt palette.

Regenerate both formats with the diagram-creator skill:

```bash
uv run diagram-creator architecture.json architecture.svg
uv run diagram-creator coordination-layer.json coordination-layer.svg
uv run diagram-creator coordination-layer.json coordination-layer.png
uv run diagram-creator cloudflare-roles.json cloudflare-roles.svg
uv run diagram-creator cloudflare-roles.json cloudflare-roles.png
uv run diagram-creator architecture.json architecture.png
uv run diagram-creator workflow.json workflow.svg
uv run diagram-creator workflow.json workflow.png
uv run diagram-creator safety.json safety.svg
uv run diagram-creator safety.json safety.png
```

Run these commands in the diagram-creator checkout, using absolute input and output paths when the assets are elsewhere. The PNG exporter uses Chromium. Keep the JSON and generated files together, and change the JSON rather than editing an SVG.

On narrow screens, the labels stay full size and you can scroll across the picture. Text and position explain each distinction, so color is supplementary. Safety cards are wider than workflow cards because they contain three related evidence fields.
