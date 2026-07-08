#!/usr/bin/env python3
"""Render a Protein of the Week issue JSON into an HTML page, and refresh the archive.

Deterministic: no API calls, no network. Safe to run in CI after research.py, and
easy to preview locally.

    mamba run -n phyla-site python scripts/potw/render.py 002-insulin.json
    mamba run -n phyla-site python scripts/potw/render.py --all          # re-render every issue
    mamba run -n phyla-site python scripts/potw/render.py 002-insulin.json --set-latest

Issue No. 1 (GFP) is the hand-authored launch page at potw.html (served at
phylatech.com/potw) and is left alone unless you pass --set-latest. Issues 2+ render to
potw-<NNN>-<slug>.html at the site root. protein-of-the-week.html is a redirect alias to
/potw. Every render refreshes the archive list on all POTW pages (the region between the
POTW:ARCHIVE markers).
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ISSUES_DIR = HERE / "issues"
ANNOUNCE_DIR = HERE / "announcements"
SITE_ROOT = HERE.parent.parent  # repo root (worktree)
CANONICAL = SITE_ROOT / "potw.html"

ARCHIVE_START = "<!-- POTW:ARCHIVE:START -->"
ARCHIVE_END = "<!-- POTW:ARCHIVE:END -->"


def esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def issue_href(number: int, slug: str) -> str:
    return "potw.html" if number == 1 else f"potw-{number:03d}-{slug}.html"


def announce_href(period_id: str) -> str:
    return f"potw-{period_id}.html"


def announced_ids() -> set:
    """Period ids with a drafted announcement, so pages can link to their kickoff."""
    if not ANNOUNCE_DIR.exists():
        return set()
    return {p.stem for p in ANNOUNCE_DIR.glob("*.json")}


def load_all_issues() -> list[dict]:
    issues = []
    for p in sorted(ISSUES_DIR.glob("*.json")):
        issues.append(json.loads(p.read_text()))
    issues.sort(key=lambda d: d.get("number", 0), reverse=True)
    return issues


def _arch_row(d: dict, current_number: int) -> str:
    n, slug = d["number"], d["slug"]
    current = ' current" aria-current="page' if n == current_number else ""
    return (
        f'          <a class="arch{current}" href="{issue_href(n, slug)}">\n'
        f'            <span class="arch-no">No. {n:03d}</span>\n'
        f'            <span class="arch-name">{esc(d["protein"])}'
        f'<span class="binomial">{esc(_organism(d["binomial"]))}</span></span>\n'
        f'            <span class="arch-date">{esc(d["date_display"])}</span>\n'
        f"          </a>"
    )


def render_archive(issues: list[dict], current_number: int) -> str:
    """Group issues by season then collection, preserving incoming (newest-first) order.

    Issues with no season (off-calendar --protein runs) collect into a trailing,
    header-less group, so nothing is ever dropped from the archive.
    """
    announced = announced_ids()
    order: list[str] = []
    seasons: dict[str, dict] = {}
    for d in issues:
        s, c = d.get("season") or {}, d.get("collection") or {}
        sl, cl = s.get("label", ""), c.get("label", "")
        if sl not in seasons:
            seasons[sl] = {"ref": s, "col_order": [], "cols": {}}
            order.append(sl)
        grp = seasons[sl]
        if cl not in grp["cols"]:
            grp["cols"][cl] = {"ref": c, "rows": []}
            grp["col_order"].append(cl)
        grp["cols"][cl]["rows"].append(_arch_row(d, current_number))

    blocks = []
    for sl in order:
        grp = seasons[sl]
        body = []
        for cl in grp["col_order"]:
            col = grp["cols"][cl]
            if cl:
                cref = col["ref"]
                period = cref.get("period", "")
                period_span = f'<span class="arch-collection-period">{esc(period)}</span>' if period else ""
                cid = cref.get("id", "")
                name_el = (
                    f'<a class="arch-collection-name" href="{announce_href(cid)}">{esc(cl)}</a>'
                    if cid and cid in announced
                    else f'<span class="arch-collection-name">{esc(cl)}</span>'
                )
                body.append(f'            <div class="arch-collection-head">{name_el}{period_span}</div>')
            body.extend(col["rows"])
        body_html = "\n".join(body)
        if sl:
            s = grp["ref"]
            kicker = f'<span class="arch-season-kicker">{esc(s.get("period", ""))}</span>' if s.get("period") else ""
            blurb = f'<span class="arch-season-blurb">{esc(s.get("blurb", ""))}</span>' if s.get("blurb") else ""
            sid = s.get("id", "")
            name_el = (
                f'<a class="arch-season-name" href="{announce_href(sid)}">{esc(sl)}</a>'
                if sid and sid in announced
                else f'<span class="arch-season-name">{esc(sl)}</span>'
            )
            blocks.append(
                '          <div class="arch-season">\n'
                f'            <div class="arch-season-head">{kicker}{name_el}{blurb}</div>\n'
                f"{body_html}\n"
                "          </div>"
            )
        else:
            blocks.append(body_html)
    return "\n".join(blocks)


def _organism(binomial: str) -> str:
    """Trim a source line like 'from Aequorea victoria, the crystal jelly' to the binomial."""
    s = binomial.strip()
    for prefix in ("from ", "From "):
        if s.startswith(prefix):
            s = s[len(prefix):]
    return s.split(",")[0].strip()


def update_archive_in_file(path: Path, issues: list[dict], current_number: int) -> None:
    if not path.exists():
        return
    text = path.read_text()
    if ARCHIVE_START not in text or ARCHIVE_END not in text:
        return
    rows = render_archive(issues, current_number)
    pre, _, rest = text.partition(ARCHIVE_START)
    _, _, post = rest.partition(ARCHIVE_END)
    new = f"{pre}{ARCHIVE_START}\n{rows}\n          {ARCHIVE_END}{post}"
    path.write_text(new)


PEPTIDE_MOTIF = """<svg class="peptide" viewBox="0 0 320 120" role="img" aria-labelledby="pepTitle pepDesc">
            <title id="pepTitle">Peptide chain</title>
            <desc id="pepDesc">A stylized peptide backbone: a folded chain of residues with one highlighted.</desc>
            <path d="M 20 84 L 52 44 L 84 84 L 116 44 L 148 84 L 180 44 L 212 84 L 244 44 L 276 84 L 300 60"
                  fill="none" stroke="var(--ink)" stroke-width="1.4" stroke-linecap="round" opacity="0.75"/>
            <g fill="var(--parchment)" stroke="var(--ink)" stroke-width="1.3">
              <circle cx="20" cy="84" r="6"/><circle cx="52" cy="44" r="6"/><circle cx="84" cy="84" r="6"/>
              <circle cx="116" cy="44" r="6"/><circle cx="180" cy="44" r="6"/><circle cx="212" cy="84" r="6"/>
              <circle cx="244" cy="44" r="6"/><circle cx="276" cy="84" r="6"/>
            </g>
            <circle cx="148" cy="84" r="7.5" fill="var(--tannin)" stroke="var(--tannin)"/>
          </svg>"""


# Story-timeline styles and reveal script. Kept as plain strings (not f-strings) so the
# CSS/JS braces need no escaping; interpolated into the page template by name.
TIMELINE_CSS = """
    /* === Story timeline === */
    .timeline { max-width: 62ch; list-style: none; }
    .tl-item { position: relative; display: grid; grid-template-columns: 5rem 1fr; column-gap: 1.5rem; align-items: baseline; padding: 0 0 1.5rem 1.75rem; }
    .tl-item:last-child { padding-bottom: 0; }
    .tl-item::before { content: ""; position: absolute; left: 3px; top: 0.55rem; bottom: 0; width: 1px; background: var(--ink-hairline); }
    .tl-item:last-child::before { display: none; }
    .tl-item::after { content: ""; position: absolute; left: 0; top: 0.4rem; width: 7px; height: 7px; border-radius: 50%; background: var(--parchment); border: 1.5px solid var(--tannin); }
    .tl-year { font-variation-settings: "wdth" 95, "wght" 600; color: var(--tannin); font-variant-numeric: tabular-nums; font-size: 0.9375rem; white-space: nowrap; line-height: 1.5; }
    .tl-title { display: block; font-variation-settings: "wdth" 100, "wght" 600; color: var(--ink); font-size: 1.0625rem; letter-spacing: -0.005em; line-height: 1.3; margin-bottom: 0.3rem; }
    .tl-detail { display: block; font-size: 0.9375rem; color: var(--ink-soft); line-height: 1.55; }
    .timeline.reveal .tl-item { opacity: 0; transform: translateY(10px); transition: opacity 620ms cubic-bezier(0.16, 1, 0.3, 1), transform 620ms cubic-bezier(0.16, 1, 0.3, 1); }
    .timeline.reveal .tl-item.shown { opacity: 1; transform: none; }
    @media (max-width: 600px) { .tl-item { grid-template-columns: 4rem 1fr; column-gap: 1rem; } }"""

TIMELINE_SCRIPT = """  <script>
    /* Timeline: a restrained, staggered reveal on scroll. Progressive enhancement,
       the section stays fully legible with no JS or with reduced motion. */
    (function () {
      var tl = document.querySelector('.timeline');
      if (!tl || !('IntersectionObserver' in window)) return;
      if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
      tl.classList.add('reveal');
      var items = tl.querySelectorAll('.tl-item');
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) {
          if (e.isIntersecting) { e.target.classList.add('shown'); io.unobserve(e.target); }
        });
      }, { threshold: 0.2, rootMargin: '0px 0px -10% 0px' });
      items.forEach(function (it, i) { it.style.transitionDelay = Math.min(i * 70, 420) + 'ms'; io.observe(it); });
    })();
  </script>"""

# Collection/season band (the "this month / this season" ribbon under the masthead).
BAND_CSS = """
    /* === Collection / season band === */
    .collection-band { border-bottom: 1px solid var(--ink-hairline); background: var(--parchment-mid); }
    .collection-band .wrap { display: flex; flex-wrap: wrap; gap: 0.5rem 2.5rem; padding-block: 0.8rem; }
    .cb-item { display: flex; align-items: baseline; gap: 0.6rem; }
    .cb-kicker { font-size: 0.6875rem; font-variation-settings: "wdth" 100, "wght" 600; letter-spacing: 0.14em; text-transform: uppercase; color: var(--tannin); white-space: nowrap; }
    .cb-label { font-variation-settings: "wdth" 95, "wght" 600; color: var(--ink); font-size: 0.9375rem; white-space: nowrap; }
    .cb-blurb { font-size: 0.8125rem; color: var(--ink-soft); }
    a.cb-label { text-decoration: none; border-bottom: 1px solid var(--ink-hairline-strong); }
    a.cb-label:hover { color: var(--tannin); border-color: var(--tannin); }
    @media (max-width: 640px) { .cb-blurb { display: none; } }"""


def _band_item(kicker: str, ref: dict, announced: set) -> str:
    label = esc(ref.get("label", ""))
    rid = ref.get("id", "")
    label_el = (
        f'<a class="cb-label" href="{announce_href(rid)}">{label}</a>'
        if rid and rid in announced
        else f'<span class="cb-label">{label}</span>'
    )
    return (
        f'        <span class="cb-item"><span class="cb-kicker">{kicker}</span>'
        f'{label_el}'
        f'<span class="cb-blurb">{esc(ref.get("blurb", ""))}</span></span>'
    )


def _collection_band(issue: dict) -> str:
    """Render the 'this month / this season' ribbon, or '' when the issue has no theme."""
    coll, seas = issue.get("collection"), issue.get("season")
    if not coll and not seas:
        return ""
    announced = announced_ids()
    items = []
    if coll:
        items.append(_band_item("This month", coll, announced))
    if seas:
        items.append(_band_item("This season", seas, announced))
    inner = "\n".join(items)
    return (
        '  <div class="collection-band">\n'
        '    <div class="wrap">\n'
        f'{inner}\n'
        "    </div>\n"
        "  </div>"
    )


ARCHIVE_GROUP_CSS = """
    /* === Grouped archive (season > collection > issues) === */
    .arch-season { border-top: 1px solid var(--ink-hairline-strong); margin-top: 2rem; padding-top: 1.5rem; }
    .arch-season:first-child { border-top: none; margin-top: 0; padding-top: 0; }
    .arch-season-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 0.35rem 0.9rem; margin-bottom: 0.4rem; }
    .arch-season-kicker { font-size: 0.6875rem; font-variation-settings: "wdth" 100, "wght" 600; letter-spacing: 0.14em; text-transform: uppercase; color: var(--ink-soft); font-variant-numeric: tabular-nums; }
    .arch-season-name { font-variation-settings: "wdth" 95, "wght" 700; font-size: 1.25rem; letter-spacing: -0.015em; color: var(--ink); }
    .arch-season-blurb { font-size: 0.875rem; color: var(--ink-soft); flex-basis: 100%; max-width: 60ch; }
    .arch-collection-head { display: flex; align-items: baseline; gap: 0.75rem; margin-top: 1.15rem; padding-bottom: 0.15rem; }
    .arch-collection-name { font-size: 0.75rem; font-variation-settings: "wdth" 100, "wght" 600; letter-spacing: 0.14em; text-transform: uppercase; color: var(--tannin); }
    .arch-collection-period { font-size: 0.75rem; color: var(--ink-soft); font-variant-numeric: tabular-nums; }
    a.arch-season-name { text-decoration: none; }
    a.arch-season-name:hover { color: var(--tannin); }
    a.arch-collection-name { text-decoration: none; border-bottom: 1px solid transparent; }
    a.arch-collection-name:hover { border-color: var(--tannin); }"""

ANNOUNCEMENT_CSS = """
    /* === Kickoff (announcement) page === */
    .kickoff { padding-block: clamp(3rem, 7vw, 5rem) clamp(3rem, 6vw, 5rem); }
    .kickoff .issue-line { display: inline-flex; align-items: center; gap: 0.625rem; margin-bottom: 1.5rem; flex-wrap: wrap; }
    .kickoff .issue-line::before { content: ""; display: inline-block; width: 28px; height: 1px; background: var(--tannin); }
    .kickoff h1 { font-size: clamp(2.5rem, 6vw, 4.25rem); margin-bottom: 1.25rem; max-width: 20ch; }
    .kickoff .dek { font-size: 1.375rem; line-height: 1.4; color: var(--ink-soft); max-width: 46ch; margin-bottom: clamp(2rem, 4vw, 3rem); }
    .kickoff-body { max-width: 62ch; }
    .kickoff-body p { font-size: 1.0625rem; line-height: 1.65; color: var(--ink-soft); margin-bottom: 1rem; }
    .kickoff-body p:last-child { margin-bottom: 0; }
    .kickoff-features { margin-top: clamp(2.5rem, 5vw, 3.5rem); padding-top: 1.75rem; border-top: 1px solid var(--ink-hairline); }
    .kickoff-features > .label { display: block; margin-bottom: 1rem; }
    .feature-list { list-style: none; max-width: 62ch; }
    .feat { display: grid; grid-template-columns: minmax(0, 15rem) 1fr; gap: 0.4rem 1.75rem; align-items: baseline; padding-block: 0.9rem; border-bottom: 1px solid var(--ink-hairline); }
    .feat:first-child { border-top: 1px solid var(--ink-hairline); }
    .feat-name { font-variation-settings: "wdth" 95, "wght" 600; color: var(--ink); font-size: 1.0625rem; }
    a.feat-name { text-decoration: none; border-bottom: 1px solid var(--ink-hairline-strong); }
    a.feat-name:hover { color: var(--tannin); border-color: var(--tannin); }
    .feat-note { font-size: 0.9375rem; color: var(--ink-soft); line-height: 1.5; }
    .kickoff-back { margin-top: clamp(2.5rem, 5vw, 3.5rem); }
    @media (max-width: 600px) { .feat { grid-template-columns: 1fr; gap: 0.2rem; } }"""


def _announcement_band(ann: dict) -> str:
    """For a month kickoff, a ribbon linking up to its season; empty for a season kickoff."""
    parent = ann.get("parent")
    if ann.get("kind") == "collection" and parent:
        item = _band_item("This season", parent, announced_ids())
        return f'  <div class="collection-band">\n    <div class="wrap">\n{item}\n    </div>\n  </div>'
    return ""


def render_announcement(ann: dict) -> str:
    """Render a month or season kickoff announcement into a standalone HTML page."""
    kind = ann.get("kind", "collection")
    period = esc(ann.get("period", ""))
    label = esc(ann.get("label", ""))
    heading = esc(ann.get("heading", ""))
    dek = esc(ann.get("dek", ""))
    paras = "\n".join(f"            <p>{esc(p)}</p>" for p in ann.get("paragraphs", []))
    feats = []
    for f in ann.get("features", []):
        name, note, href = esc(f.get("name", "")), esc(f.get("note", "")), f.get("href", "")
        name_el = f'<a class="feat-name" href="{esc(href)}">{name}</a>' if href else f'<span class="feat-name">{name}</span>'
        feats.append(f'            <li class="feat">{name_el}<span class="feat-note">{note}</span></li>')
    features_html = "\n".join(feats)
    kicker = "The season ahead" if kind == "season" else "The month ahead"
    feat_label = "This season's collections" if kind == "season" else "In this collection"
    band = _announcement_band(ann)
    period_id = ann.get("period_id", "")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{label}: Protein of the Week, Phyla Technologies</title>
  <link rel="icon" type="image/svg+xml" href="favicon.svg">
  <meta name="description" content="{dek}">
  <link rel="canonical" href="https://phylatech.com/{announce_href(period_id)}">
  <meta name="view-transition" content="same-origin">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wdth,wght@12..96,75..100,300..800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="styles.css">
  <style>
    .masthead {{ border-bottom: 1px solid var(--ink-hairline); background: var(--parchment); }}
    .masthead-inner {{ display: flex; align-items: baseline; justify-content: space-between; gap: 1.5rem; padding-block: 1.25rem; flex-wrap: wrap; }}
    .masthead .column-name {{ font-size: 0.75rem; font-variation-settings: "wdth" 100, "wght" 600; letter-spacing: 0.22em; text-transform: uppercase; color: var(--tannin); }}
{BAND_CSS}
{ANNOUNCEMENT_CSS}
  </style>
</head>
<body>
  <a href="#main" class="skip-link">Skip to main content</a>

  <header class="masthead">
    <div class="wrap masthead-inner">
      <a href="index.html" class="wordmark" aria-label="Phyla Technologies, home">
        <span class="wordmark-name">Phyla</span>
        <span class="wordmark-sub">Technologies</span>
      </a>
      <span class="column-name">Protein of the Week</span>
    </div>
  </header>
{band}
  <main id="main">
    <section class="kickoff">
      <div class="wrap">
        <span class="issue-line label">{kicker} &nbsp;&middot;&nbsp; {period}</span>
        <h1 class="display">{heading}</h1>
        <p class="dek">{dek}</p>
        <div class="kickoff-body">
{paras}
        </div>
        <div class="kickoff-features">
          <span class="label">{feat_label}</span>
          <ol class="feature-list">
{features_html}
          </ol>
        </div>
        <p class="kickoff-back"><a class="link-arrow" href="potw.html">The latest issue <span class="arrow">&rarr;</span></a></p>
      </div>
    </section>
  </main>

  <footer class="site-footer">
    <div class="wrap footer-inner">
      <div class="footer-etymology">
        <em>Phyla</em>, plural of <em>phylum</em>. Kingdom, phylum, class, order, family, genus, species: the Linnaean ladder for naming the living world. Every model we ship is, underneath, a way of sorting it.
      </div>
      <div class="footer-meta">&copy; 2026 Phyla Technologies</div>
      <div class="footer-links">
        <a href="index.html">Main site</a>
        <a href="potw.html">Protein of the Week</a>
      </div>
    </div>
  </footer>
</body>
</html>
"""


def render_page(issue: dict, issues: list[dict]) -> str:
    n = issue["number"]
    facts = "\n".join(
        f'            <div class="fact"><dd class="value">{esc(f["value"])}</dd>'
        f'<dt class="label">{esc(f["label"])}</dt></div>'
        for f in issue["facts"]
    )
    movements = []
    for i, m in enumerate(issue["movements"], start=1):
        paras = "\n".join(f"            <p>{esc(p)}</p>" for p in m["paragraphs"])
        movements.append(
            f'          <div class="movement">\n'
            f'            <span class="movement-num">&sect; {i:02d} &nbsp; {esc(m["kicker"])}</span>\n'
            f'            <h2>{esc(m["heading"])}</h2>\n{paras}\n          </div>'
        )
    movements_html = "\n".join(movements)
    meanwhile = "\n".join(
        f'              <div class="ml"><span class="when">{esc(x["when"])}</span>'
        f'<span class="what">{esc(x["what"])}</span></div>'
        for x in issue["meanwhile"]
    )
    timeline = "\n".join(
        f'          <li class="tl-item">\n'
        f'            <span class="tl-year">{esc(m["year"])}</span>\n'
        f'            <span class="tl-body"><span class="tl-title">{esc(m["title"])}</span>'
        f'<span class="tl-detail">{esc(m["detail"])}</span></span>\n'
        f'          </li>'
        for m in issue["timeline"]
    )
    archive_rows = render_archive(issues, n)
    org = esc(_organism(issue["binomial"]))
    band = _collection_band(issue)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Protein of the Week: {esc(issue["protein"])}, Phyla Technologies</title>
  <link rel="icon" type="image/svg+xml" href="favicon.svg">
  <meta name="description" content="Protein of the Week No. {n:03d} from Phyla Technologies: {esc(issue["dek"])}">
  <meta name="view-transition" content="same-origin">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wdth,wght@12..96,75..100,300..800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="styles.css">
  <style>
    /* Generated by scripts/potw/render.py. Page-specific styles for a POTW issue. */
    .masthead {{ border-bottom: 1px solid var(--ink-hairline); background: var(--parchment); }}
    .masthead-inner {{ display: flex; align-items: baseline; justify-content: space-between; gap: 1.5rem; padding-block: 1.25rem; flex-wrap: wrap; }}
    .masthead .column-name {{ font-size: 0.75rem; font-variation-settings: "wdth" 100, "wght" 600; letter-spacing: 0.22em; text-transform: uppercase; color: var(--tannin); }}
    .issue {{ padding-block: clamp(3rem, 7vw, 5rem) clamp(2rem, 4vw, 3rem); }}
    .issue-line {{ display: inline-flex; align-items: center; gap: 0.625rem; margin-bottom: 1.5rem; flex-wrap: wrap; }}
    .issue-line::before {{ content: ""; display: inline-block; width: 28px; height: 1px; background: var(--tannin); }}
    .issue-grid {{ display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(0, 1fr); gap: clamp(2rem, 5vw, 4.5rem); align-items: center; }}
    .issue h1 {{ font-size: clamp(2.5rem, 6vw, 4.25rem); margin-bottom: 1rem; }}
    .issue .binomial {{ font-style: italic; font-variation-settings: "wdth" 95, "wght" 500; color: var(--tannin); font-size: 1.1875rem; margin-bottom: 1.25rem; }}
    .issue .dek {{ font-size: 1.1875rem; line-height: 1.55; color: var(--ink-soft); max-width: 42ch; }}
    .peptide {{ width: 100%; max-width: 320px; height: auto; display: block; margin-inline: auto; }}
    .facts {{ display: grid; grid-template-columns: repeat(4, auto); justify-content: start; column-gap: clamp(1.5rem, 4vw, 3.5rem); margin-top: clamp(2rem, 4vw, 3rem); padding-top: 2rem; border-top: 1px solid var(--ink-hairline); }}
    .fact {{ padding-right: clamp(1.5rem, 4vw, 3.5rem); border-right: 1px solid var(--ink-hairline-strong); }}
    .fact:last-child {{ border-right: none; padding-right: 0; }}
    .fact .value {{ display: block; font-size: clamp(1.25rem, 2.6vw, 1.75rem); font-variation-settings: "wdth" 95, "wght" 600; color: var(--ink); letter-spacing: -0.02em; line-height: 1.05; }}
    .fact .label {{ display: block; margin-top: 0.5rem; font-size: 0.6875rem; }}
    .article {{ max-width: 68ch; }}
    .article .movement {{ margin-bottom: clamp(2.5rem, 5vw, 3.5rem); }}
    .article h2 {{ font-variation-settings: "wdth" 100, "wght" 600; font-size: clamp(1.375rem, 2.4vw, 1.75rem); letter-spacing: -0.015em; line-height: 1.15; margin-bottom: 1rem; }}
    .article .movement-num {{ font-size: 0.6875rem; font-variation-settings: "wdth" 100, "wght" 600; letter-spacing: 0.14em; text-transform: uppercase; color: var(--ink-soft); display: block; margin-bottom: 0.6rem; }}
    .article p {{ font-size: 1.0625rem; line-height: 1.65; color: var(--ink-soft); margin-bottom: 1rem; }}
    .pullquote {{ border-top: 1px solid var(--ink-hairline); border-bottom: 1px solid var(--ink-hairline); padding-block: 1.5rem; margin-block: 2rem; max-width: 68ch; }}
    .pullquote p {{ font-size: clamp(1.25rem, 2.4vw, 1.625rem); line-height: 1.3; letter-spacing: -0.015em; color: var(--ink); font-variation-settings: "wdth" 95, "wght" 500; }}
    .meanwhile {{ max-width: 68ch; }}
    .meanwhile .ml {{ display: grid; grid-template-columns: 5.5rem 1fr; gap: 1rem; padding-block: 0.8rem; border-bottom: 1px solid var(--ink-hairline); align-items: baseline; }}
    .meanwhile .ml:first-child {{ border-top: 1px solid var(--ink-hairline); }}
    .meanwhile .ml .when {{ font-variation-settings: "wdth" 95, "wght" 600; color: var(--tannin); font-variant-numeric: tabular-nums; }}
    .meanwhile .ml .what {{ font-size: 0.9375rem; color: var(--ink-soft); line-height: 1.5; }}
    .byline {{ margin-top: clamp(2.5rem, 5vw, 3.5rem); padding-top: 1.5rem; border-top: 1px solid var(--ink-hairline); font-size: 0.875rem; color: var(--ink-soft); font-style: italic; max-width: 60ch; }}
    .archive-list {{ border-top: 1px solid var(--ink-hairline); }}
    .arch {{ display: grid; grid-template-columns: auto 1fr auto; gap: 1rem 1.5rem; align-items: baseline; padding-block: 1.1rem; border-bottom: 1px solid var(--ink-hairline); text-decoration: none; color: inherit; }}
    .arch .arch-no {{ font-size: 0.6875rem; font-variation-settings: "wdth" 100, "wght" 600; letter-spacing: 0.14em; text-transform: uppercase; color: var(--ink-soft); }}
    .arch .arch-name {{ font-size: 1.0625rem; font-variation-settings: "wdth" 100, "wght" 600; color: var(--ink); letter-spacing: -0.005em; }}
    .arch .arch-name .binomial {{ font-style: italic; font-variation-settings: "wdth" 95, "wght" 500; color: var(--ink-soft); font-size: 0.9375rem; margin-left: 0.5rem; }}
    .arch .arch-date {{ font-size: 0.8125rem; color: var(--ink-soft); font-variant-numeric: tabular-nums; }}
    .arch.current .arch-no {{ color: var(--tannin); }}
    @media (max-width: 820px) {{ .issue-grid {{ grid-template-columns: 1fr; gap: 2.25rem; }} .issue-visual {{ order: -1; }} }}
    @media (max-width: 600px) {{ .facts {{ grid-template-columns: 1fr 1fr; row-gap: 1.5rem; }} .fact:nth-child(2) {{ border-right: none; padding-right: 0; }} .meanwhile .ml {{ grid-template-columns: 4.5rem 1fr; }} .arch {{ grid-template-columns: auto 1fr; }} .arch .arch-date {{ grid-column: 2; }} }}
{TIMELINE_CSS}
{BAND_CSS}
{ARCHIVE_GROUP_CSS}
  </style>
</head>
<body>
  <a href="#main" class="skip-link">Skip to main content</a>

  <header class="masthead">
    <div class="wrap masthead-inner">
      <a href="index.html" class="wordmark" aria-label="Phyla Technologies, home">
        <span class="wordmark-name">Phyla</span>
        <span class="wordmark-sub">Technologies</span>
      </a>
      <span class="column-name">Protein of the Week</span>
    </div>
  </header>
{band}
  <main id="main">
    <section class="issue">
      <div class="wrap">
        <span class="issue-line label">No. {n:03d} &nbsp;&middot;&nbsp; {esc(issue["date_display"])}</span>
        <div class="issue-grid">
          <div class="issue-text">
            <h1 class="display">{esc(issue["protein"])}</h1>
            <p class="binomial">{esc(issue["binomial"])}</p>
            <p class="dek">{esc(issue["dek"])}</p>
          </div>
          <div class="issue-visual">
          {PEPTIDE_MOTIF}
          </div>
        </div>
        <dl class="facts">
{facts}
        </dl>
      </div>
    </section>

    <section id="article">
      <div class="wrap">
        <div class="article">
{movements_html}
          <div class="pullquote"><p>{esc(issue["pull_quote"])}</p></div>
          <div class="movement">
            <span class="movement-num">&sect; &nbsp; Meanwhile</span>
            <h2>{esc(issue["meanwhile_heading"])}</h2>
            <div class="meanwhile">
{meanwhile}
            </div>
          </div>
        </div>
        <p class="byline">{esc(issue["byline"])}</p>
      </div>
    </section>

    <!-- STORY TIMELINE -->
    <section id="timeline">
      <div class="wrap">
        <div class="section-head">
          <span class="label">&sect; &nbsp; The chronology</span>
          <h2 class="headline">{esc(issue["timeline_heading"])}</h2>
        </div>
        <ol class="timeline">
{timeline}
        </ol>
      </div>
    </section>

    <section id="archive">
      <div class="wrap">
        <div class="section-head">
          <span class="label">&sect; &nbsp; The archive</span>
          <h2 class="headline">Every protein, every week.</h2>
        </div>
        <div class="archive-list">
          {ARCHIVE_START}
{archive_rows}
          {ARCHIVE_END}
        </div>
      </div>
    </section>
  </main>

  <footer class="site-footer">
    <div class="wrap footer-inner">
      <div class="footer-etymology">
        <em>Phyla</em>, plural of <em>phylum</em>. Kingdom, phylum, class, order, family, genus, species: the Linnaean ladder for naming the living world. Every model we ship is, underneath, a way of sorting it.
      </div>
      <div class="footer-meta">&copy; 2026 Phyla Technologies</div>
      <div class="footer-links">
        <a href="index.html">Main site</a>
        <a href="https://www.linkedin.com/company/phylatech" target="_blank" rel="noopener noreferrer">LinkedIn</a>
        <a href="https://github.com/orgs/phylatech" target="_blank" rel="noopener noreferrer">GitHub</a>
      </div>
    </div>
  </footer>

{TIMELINE_SCRIPT}
</body>
</html>
"""


def render_announcement_file(path: Path) -> None:
    ann = json.loads(path.read_text())
    dest = SITE_ROOT / announce_href(ann["period_id"])
    dest.write_text(render_announcement(ann))
    print(f"Wrote {dest.relative_to(SITE_ROOT)}", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser(description="Render a POTW issue or announcement JSON to HTML.")
    ap.add_argument("issue", nargs="?", help="Issue JSON filename (in scripts/potw/issues/) or path.")
    ap.add_argument("--all", action="store_true", help="Re-render every issue (2+) and every announcement.")
    ap.add_argument("--announcement", help="Render one announcement (id like 2026-07 / 2026-q3, or a path).")
    ap.add_argument("--set-latest", action="store_true", help="Also write this issue to potw.html (the canonical page, served at /potw).")
    args = ap.parse_args()

    all_issues = load_all_issues()

    # Which announcements to (re-)render this run.
    ann_targets: list[Path] = []
    if args.announcement:
        p = Path(args.announcement)
        if not p.exists():
            p = ANNOUNCE_DIR / (args.announcement if args.announcement.endswith(".json") else f"{args.announcement}.json")
        if not p.exists():
            print(f"Announcement not found: {args.announcement}", file=sys.stderr)
            return 1
        ann_targets = [p]
    elif args.all and ANNOUNCE_DIR.exists():
        ann_targets = sorted(ANNOUNCE_DIR.glob("*.json"))

    # Which issues to render this run.
    if args.all:
        targets = [d for d in all_issues if d["number"] != 1]
    elif args.issue:
        p = Path(args.issue)
        if not p.exists():
            p = ISSUES_DIR / args.issue
        targets = [json.loads(p.read_text())]
    elif args.announcement:
        targets = []  # announcement-only run
    else:
        print("Pass an issue filename, --announcement <id>, or --all.", file=sys.stderr)
        return 1

    if not all_issues and not ann_targets:
        print("Nothing to render (no issues in scripts/potw/issues/).", file=sys.stderr)
        return 1

    for issue in targets:
        n, slug = issue["number"], issue["slug"]
        page = render_page(issue, all_issues)
        if n == 1 and not args.set_latest:
            print(f"No. {n:03d} is the hand-authored launch page; skipping (use --set-latest to overwrite).", file=sys.stderr)
        else:
            dest = CANONICAL if (args.set_latest and issue is targets[0]) else (SITE_ROOT / issue_href(n, slug))
            dest.write_text(page)
            print(f"Wrote {dest.relative_to(SITE_ROOT)}", file=sys.stderr)

    for ann_path in ann_targets:
        render_announcement_file(ann_path)

    # Refresh the archive region on every POTW page (kickoff links appear once drafted).
    if all_issues:
        update_archive_in_file(CANONICAL, all_issues, current_number=_canonical_number(all_issues, args))
        for d in all_issues:
            if d["number"] != 1:
                update_archive_in_file(SITE_ROOT / issue_href(d["number"], d["slug"]), all_issues, current_number=d["number"])
        print("Archive lists refreshed.", file=sys.stderr)
    return 0


def _canonical_number(all_issues: list[dict], args) -> int:
    # The canonical page currently shows GFP (No. 1) unless --set-latest promoted another.
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
