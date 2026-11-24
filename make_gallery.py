#!/usr/bin/env python3
"""Build docs/index.html (the gallery, also served by GitHub Pages) from catalog.json: every effect grouped by category,
with its GIF demo, look, best use, other names and the command. Run again after every new effect."""
import html, json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GROUPS = [("transition", "Transitions", "Joins between two clips."),
          ("title", "Titles and text", "Animated words over a clip."),
          ("fx", "Looks and overlays", "Effects on one clip.")]


def card(e):
    vids = "".join(f'<img src="{html.escape(d.removeprefix("docs/"))}" loading="lazy" alt="{html.escape(e["name"])}">' for d in e["demo"])
    tags = "".join(f"<span>{html.escape(a)}</span>" for a in e["aliases"])
    mood = ", ".join(e.get("mood", []))
    return f"""<article id="{e['id']}"><div class="vids">{vids}</div><div class="txt">
<h3><b>{e['id']}</b> {html.escape(e['name'])}</h3>
<p>{html.escape(e['look'])}</p>
<p><i>Best for:</i> {html.escape(e['use_for'])}. <i>Mood:</i> {html.escape(mood)}. <i>Length:</i> {str(e['frames']) + ' frames' if e['frames'] else 'any length'}.</p>
<div class="tags">{tags}</div>
<code>{html.escape(e['command'])}</code></div></article>"""


def readme_tables(cat):
    """The effect tables of README.md (between the EFFECTS markers): GIF, ID and name, look, best use, command."""
    out = []
    for kind, title, blurb in GROUPS:
        items = [e for e in cat if e["kind"] == kind]
        out.append(f"### {title} ({len(items)})\n\n{blurb}\n\n| Demo | Effect | Look and best use |\n|---|---|---|")
        for e in items:
            gifs = " ".join(f'<img src="{d}" width="150">' for d in e["demo"])
            names = ", ".join(e["aliases"][:5])
            out.append(f"| {gifs} | **{e['id']}** {e['name']}<br><sub>also: {names}</sub> | {e['look']}<br>**Best for:** {e['use_for']}<br>`{e['command'].split('  |  ')[0]}` |")
        out.append("")
    return "\n".join(out)


def main():
    cat = json.loads((HERE / "catalog.json").read_text())["effects"]
    nav, body = [], []
    for kind, title, blurb in GROUPS:
        items = [e for e in cat if e["kind"] == kind]
        if not items:
            continue
        nav.append(f'<a href="#{kind}">{title} ({len(items)})</a>')
        body.append(f'<section id="{kind}"><h2>{title}</h2><p class="blurb">{blurb}</p>' + "".join(card(e) for e in items) + "</section>")
    page = f"""<!doctype html><html><head><meta charset="utf-8"><title>VFX for Claude Code</title>
<meta name="viewport" content="width=device-width,initial-scale=1"><style>
body{{font:15px/1.5 -apple-system,Helvetica,sans-serif;background:#111;color:#eee;margin:0;padding:24px}}
h1{{margin:0 0 6px}} nav a{{color:#f0a060;margin-right:18px}} input{{width:340px;padding:8px;border-radius:8px;border:0;margin:12px 0}}
section{{margin-top:28px}} h2{{border-bottom:1px solid #333;padding-bottom:6px}} .blurb{{color:#999}}
article{{display:flex;gap:18px;background:#1b1b1b;border-radius:14px;padding:14px;margin:14px 0}}
.vids{{display:flex;gap:8px}} img{{width:180px;height:320px;object-fit:cover;border-radius:10px;background:#000}}
h3{{margin:0 0 6px}} h3 b{{color:#f0a060}} .tags span{{display:inline-block;background:#2a2a2a;border-radius:20px;padding:2px 10px;margin:2px;font-size:13px}}
code{{display:block;background:#000;padding:8px;border-radius:8px;margin-top:8px;font-size:12px;white-space:pre-wrap}}
</style></head><body><h1>VFX for Claude Code</h1><p>40 video effects as Python code. Ask Claude Code for one in plain words. <a style="color:#f0a060" href="https://github.com/Robj1925/vfx-for-claude-code">GitHub</a> · <a style="color:#f0a060" href="https://www.skool.com/ai-academy-with-robby-6849/about">🎞️ The full AI editing workflow, step by step (AI Academy on Skool)</a></p>
<nav>{''.join(nav)}</nav>
<input id="q" placeholder="Search: glow, glitch, step in, premium..." oninput="f()">
{''.join(body)}
<script>function f(){{const q=document.getElementById('q').value.toLowerCase().split(' ').filter(Boolean);
document.querySelectorAll('article').forEach(a=>{{const t=a.innerText.toLowerCase();a.style.display=q.every(w=>t.includes(w))?'flex':'none'}})}}</script>
</body></html>"""
    (HERE / "docs" / "index.html").write_text(page)
    rd = HERE / "README.md"
    if rd.exists():
        t = rd.read_text()
        a, b = "<!-- EFFECTS:START -->", "<!-- EFFECTS:END -->"
        if a in t and b in t:
            t = t[: t.index(a) + len(a)] + "\n" + readme_tables(cat) + "\n" + t[t.index(b):]
            rd.write_text(t)
    print("docs/index.html:", len(cat), "effects")


if __name__ == "__main__":
    main()
