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
import datetime as dt
import html
import json
import math
import os
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ISSUES_DIR = HERE / "issues"
ANNOUNCE_DIR = HERE / "announcements"
QUEUE_PATH = HERE / "proteins.json"
SITE_ROOT = HERE.parent.parent  # repo root (worktree)
CANONICAL = SITE_ROOT / "potw.html"
CATALOGUE = SITE_ROOT / "potw-catalogue.html"
FIELD_GUIDE = SITE_ROOT / "potw-field-guide.html"

ARCHIVE_START = "<!-- POTW:ARCHIVE:START -->"
ARCHIVE_END = "<!-- POTW:ARCHIVE:END -->"


def esc(s: str) -> str:
    return html.escape(str(s), quote=True)


_CITE_RE = re.compile(r"\[(\d{1,3})\]")


def _cite(text: str, ref_count: int) -> str:
    """Escape prose, then turn [n] markers into superscript links to #ref-n (in range only)."""
    def repl(m: "re.Match") -> str:
        n = int(m.group(1))
        if 1 <= n <= ref_count:
            return f'<sup class="cite"><a href="#ref-{n}">{n}</a></sup>'
        return m.group(0)
    return _CITE_RE.sub(repl, esc(text))


def _host(url: str) -> str:
    """'https://doi.org/10.x/y' -> 'doi.org'."""
    return re.sub(r"^https?://(www\.)?", "", url).split("/")[0]


def _friendly_date(iso: str) -> str:
    """'2026-07-13' -> 'Mon 13 Jul'. Returns the input unchanged if it is not an ISO date."""
    try:
        d = dt.date.fromisoformat(iso)
    except ValueError:
        return iso
    return d.strftime("%a %#d %b" if os.name == "nt" else "%a %-d %b")


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


# --- Calendar helpers (kept local so render.py needs no API deps; mirror research.py) ---

def load_queue() -> dict:
    return json.loads(QUEUE_PATH.read_text()) if QUEUE_PATH.exists() else {}


def _spec_slug(spec: dict) -> str:
    return spec.get("slug") or re.sub(r"[^a-z0-9]+", "-", spec["protein"].lower()).strip("-")


def iter_specimens(queue: dict):
    """Yield (number, specimen, collection, season) in calendar order; number = 1-based position."""
    number = 0
    for season in queue.get("seasons", []):
        for collection in season.get("collections", []):
            for specimen in collection.get("specimens", []):
                number += 1
                yield number, specimen, collection, season


def _is_drafted(number: int, spec: dict) -> bool:
    slug = _spec_slug(spec)
    return spec.get("status") == "published" or (ISSUES_DIR / f"{number:03d}-{slug}.json").exists()


def _reveal_iso(number: int, anchor: str) -> str:
    try:
        return (dt.date.fromisoformat(anchor) + dt.timedelta(days=7 * (number - 1))).isoformat()
    except ValueError:
        return ""


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
    .tl-item.has-photo .tl-body { display: flex; gap: 1.25rem; align-items: flex-start; }
    .tl-item.has-photo .tl-text { flex: 1 1 auto; min-width: 0; }
    .tl-photo { flex: 0 0 112px; margin: 0; }
    .tl-photo img { width: 112px; height: 140px; object-fit: cover; display: block; border: 1px solid var(--ink-hairline-strong); filter: grayscale(0.25) sepia(0.1) contrast(0.96); background: var(--parchment-mid); }
    .tl-photo figcaption { margin-top: 0.32rem; font-size: 0.5625rem; line-height: 1.35; color: var(--ink-soft); }
    .tl-photo figcaption a { color: var(--ink-soft); text-decoration: none; border-bottom: 1px solid var(--ink-hairline); }
    .tl-photo figcaption a:hover { color: var(--ink); }
    .timeline.reveal .tl-item { opacity: 0; transform: translateY(10px); transition: opacity 620ms cubic-bezier(0.16, 1, 0.3, 1), transform 620ms cubic-bezier(0.16, 1, 0.3, 1); }
    .timeline.reveal .tl-item.shown { opacity: 1; transform: none; }
    @media (max-width: 600px) { .tl-item { grid-template-columns: 4rem 1fr; column-gap: 1rem; } .tl-item.has-photo .tl-body { gap: 0.85rem; } .tl-photo { flex-basis: 82px; } .tl-photo img { width: 82px; height: 102px; } }"""

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
    a.feat.feat-sealed { text-decoration: none; opacity: 0.7; transition: opacity 160ms ease-out; }
    a.feat.feat-sealed:hover { opacity: 1; }
    .feat-when { font-variation-settings: "wdth" 95, "wght" 600; color: var(--tannin); font-variant-numeric: tabular-nums; position: relative; padding-left: 1.15rem; }
    .feat-when::before { content: ""; position: absolute; left: 0; top: 0.2em; width: 0.72em; height: 0.72em; border: 1.5px solid var(--tannin); border-radius: 50%; opacity: 0.5; }
    .feat-opens { display: block; margin-top: 0.15rem; font-size: 0.8125rem; color: var(--ink-soft); font-variant-numeric: tabular-nums; }
    .kickoff-back { margin-top: clamp(2.5rem, 5vw, 3.5rem); }
    @media (max-width: 600px) { .feat { grid-template-columns: 1fr; gap: 0.2rem; } }"""

TEASER_SCRIPT = """  <script>
    /* Sealed teasers: turn the opening date into a relative countdown. */
    (function () {
      var els = document.querySelectorAll('.feat-when[data-reveal]');
      if (!els.length) return;
      var today = new Date(); today.setHours(0, 0, 0, 0);
      els.forEach(function (el) {
        var iso = (el.getAttribute('data-reveal') || '').split('-');
        if (iso.length !== 3) return;
        var d = new Date(+iso[0], +iso[1] - 1, +iso[2]); d.setHours(0, 0, 0, 0);
        var days = Math.round((d - today) / 86400000);
        if (days > 1) el.textContent = 'Opens in ' + days + ' days';
        else if (days === 1) el.textContent = 'Opens tomorrow';
        else if (days === 0) el.textContent = 'Opens today';
      });
    })();
  </script>"""

SUBSCRIBE_CSS = """
    /* === Subscribe CTA === */
    .subscribe { border-top: 1px solid var(--ink-hairline); }
    .sub-grid { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr); gap: clamp(2rem, 5vw, 4rem); align-items: start; }
    .sub-form { display: flex; flex-direction: column; gap: 1.1rem; max-width: 34rem; }
    .sub-cadence { display: flex; flex-direction: column; gap: 0.6rem; }
    .sub-cadence label { display: flex; align-items: baseline; gap: 0.6rem; font-size: 0.9375rem; color: var(--ink-soft); cursor: pointer; }
    .sub-cadence input { accent-color: var(--tannin); }
    .sub-cadence b { color: var(--ink); font-variation-settings: "wdth" 100, "wght" 600; }
    .sub-row { display: flex; gap: 0.6rem; flex-wrap: wrap; }
    .sub-row input[type=email] { flex: 1 1 15rem; padding: 0.75rem 0.9rem; border: 1px solid var(--ink-hairline-strong); background: var(--parchment-pale); color: var(--ink); border-radius: 0; font-size: 0.9375rem; }
    .sub-social { display: flex; flex-direction: column; gap: 0.75rem; align-items: flex-start; }
    .sub-note { margin-top: 1.5rem; font-size: 0.8125rem; color: var(--ink-soft); max-width: 62ch; }
    .sub-note code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.9em; background: var(--parchment-mid); padding: 0.05em 0.35em; }
    .follow-btn { display: inline-flex; align-items: center; gap: 0.5rem; padding: 0.65rem 1.2rem; border: 1px solid var(--ink-hairline-strong); color: var(--ink); text-decoration: none; font-size: 0.9375rem; font-variation-settings: "wdth" 100, "wght" 500; transition: border-color 180ms ease-out, color 180ms ease-out; }
    .follow-btn:hover { border-color: var(--tannin); color: var(--tannin); }
    @media (max-width: 720px) { .sub-grid { grid-template-columns: 1fr; } }"""

SUBSCRIBE_HTML = """    <section class="subscribe" id="subscribe">
      <div class="wrap">
        <div class="section-head">
          <span class="label">&sect; &nbsp; The dispatch</span>
          <h2 class="headline">Never miss a reveal.</h2>
          <p class="body">The catalogue stays sealed: each specimen opens only on its week. Subscribe to <em>The Naturalist's Dispatch</em> and every reveal comes to you the moment it opens, so you follow the whole series without ever checking back. A specimen every week, a collection every month, a season every quarter: choose your cadence.</p>
        </div>
        <div class="sub-grid">
          <form class="sub-form" method="post" action="https://example.com/REPLACE-WITH-YOUR-EMAIL-ENDPOINT" target="_blank" rel="noopener noreferrer">
            <div class="sub-cadence">
              <label><input type="radio" name="cadence" value="weekly" checked> <span><b>Weekly</b> &middot; every protein, as it is revealed</span></label>
              <label><input type="radio" name="cadence" value="monthly"> <span><b>Monthly</b> &middot; the collection kickoff</span></label>
              <label><input type="radio" name="cadence" value="quarterly"> <span><b>Quarterly</b> &middot; the season preview</span></label>
            </div>
            <div class="sub-row">
              <input type="email" name="email" placeholder="you@lab.org" aria-label="Email address" required>
              <button class="btn-primary" type="submit">Subscribe</button>
            </div>
          </form>
          <div class="sub-social">
            <span class="label">Or follow on social</span>
            <a class="follow-btn" href="https://www.linkedin.com/company/phylatech" target="_blank" rel="noopener noreferrer"><span>LinkedIn</span><span aria-hidden="true">&rarr;</span></a>
            <a class="follow-btn" href="https://x.com/phylatech" target="_blank" rel="noopener noreferrer"><span>X</span><span aria-hidden="true">&rarr;</span></a>
          </div>
        </div>
        <p class="sub-note">Email delivery is not wired up yet. Point the form's <code>action</code> at your provider (Buttondown, Mailchimp, ConvertKit, or similar); see scripts/potw/README.md.</p>
      </div>
    </section>"""

REVEAL_CSS = """
    /* === First-visit reveal modal === */
    .reveal-modal[hidden] { display: none; }
    .reveal-modal { position: fixed; inset: 0; z-index: 200; display: grid; place-items: center; padding: 1.5rem; }
    .reveal-backdrop { position: absolute; inset: 0; background: oklch(22% 0.02 70 / 0.55); animation: reveal-fade 320ms ease-out both; }
    .reveal-card { position: relative; z-index: 1; width: 100%; max-width: 30rem; background: var(--parchment-pale); border: 1px solid var(--ink-hairline-strong); padding: clamp(1.75rem, 4vw, 2.75rem); box-shadow: 0 24px 64px -24px oklch(22% 0.02 70 / 0.45); animation: reveal-rise 560ms cubic-bezier(0.16, 1, 0.3, 1) both; }
    .reveal-flush { display: block; width: 34px; height: 1px; background: var(--tannin); margin-bottom: 1.1rem; }
    .reveal-eyebrow { font-size: 0.6875rem; font-variation-settings: "wdth" 100, "wght" 600; letter-spacing: 0.16em; text-transform: uppercase; color: var(--tannin); display: block; }
    .reveal-no { display: block; margin-top: 0.5rem; font-size: 0.75rem; letter-spacing: 0.06em; text-transform: uppercase; color: var(--ink-soft); font-variant-numeric: tabular-nums; }
    .reveal-name { font-variation-settings: "wdth" 95, "wght" 700; font-size: clamp(1.75rem, 4vw, 2.5rem); line-height: 1.05; letter-spacing: -0.02em; color: var(--ink); margin: 0.75rem 0; animation: reveal-name 720ms 140ms cubic-bezier(0.16, 1, 0.3, 1) both; }
    .reveal-dek { font-size: 1rem; line-height: 1.5; color: var(--ink-soft); }
    .reveal-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 1rem 1.5rem; margin-top: 1.75rem; }
    .reveal-close { position: absolute; top: 0.6rem; right: 0.8rem; font-size: 1.5rem; line-height: 1; color: var(--ink-soft); padding: 0.2rem 0.4rem; }
    .reveal-close:hover { color: var(--ink); }
    @keyframes reveal-fade { from { opacity: 0; } }
    @keyframes reveal-rise { from { opacity: 0; transform: translateY(18px) scale(0.985); } }
    @keyframes reveal-name { from { opacity: 0; clip-path: inset(0 100% 0 0); } to { opacity: 1; clip-path: inset(0 0 0 0); } }"""

REVEAL_SCRIPT = """  <script>
    /* First visit of the week: reveal this week's protein once, then remember (per ISO week). */
    (function () {
      var modal = document.getElementById('revealModal');
      if (!modal) return;
      var iso = (modal.getAttribute('data-issue-date') || '').split('-');
      if (iso.length !== 3) return;
      function weekKey(d) {
        var t = new Date(d.getFullYear(), d.getMonth(), d.getDate());
        t.setDate(t.getDate() - ((t.getDay() + 6) % 7) + 3);
        var firstThu = new Date(t.getFullYear(), 0, 4);
        var wk = 1 + Math.round(((t - firstThu) / 86400000 - 3 + ((firstThu.getDay() + 6) % 7)) / 7);
        return t.getFullYear() + '-W' + wk;
      }
      var issue = new Date(+iso[0], +iso[1] - 1, +iso[2]);
      var thisWeek = weekKey(new Date());
      if (weekKey(issue) !== thisWeek) return;
      var key = 'potw-revealed-' + thisWeek + '-' + (modal.getAttribute('data-slug') || '');
      try { if (localStorage.getItem(key)) return; } catch (e) {}
      function close() {
        modal.hidden = true;
        modal.setAttribute('aria-hidden', 'true');
        try { localStorage.setItem(key, '1'); } catch (e) {}
        document.removeEventListener('keydown', onKey);
      }
      function onKey(e) { if (e.key === 'Escape') close(); }
      modal.hidden = false;
      modal.setAttribute('aria-hidden', 'false');
      document.addEventListener('keydown', onKey);
      var els = modal.querySelectorAll('[data-close]');
      for (var i = 0; i < els.length; i++) els[i].addEventListener('click', close);
    })();
  </script>"""


def _reveal_modal(n: int, issue: dict) -> str:
    """The once-a-week reveal dialog for an issue page (shown by REVEAL_SCRIPT)."""
    return (
        f'  <div class="reveal-modal" id="revealModal" hidden aria-hidden="true" '
        f'data-issue-date="{esc(issue.get("date_iso", ""))}" data-slug="{esc(issue.get("slug", ""))}">\n'
        '    <div class="reveal-backdrop" data-close></div>\n'
        '    <div class="reveal-card" role="dialog" aria-modal="true" aria-labelledby="revealName">\n'
        '      <button class="reveal-close" data-close aria-label="Close">&times;</button>\n'
        '      <span class="reveal-flush"></span>\n'
        "      <span class=\"reveal-eyebrow\">This week's protein</span>\n"
        f'      <span class="reveal-no">No. {n:03d} &nbsp;&middot;&nbsp; {esc(issue.get("date_display", ""))}</span>\n'
        f'      <h2 class="reveal-name" id="revealName">{esc(issue["protein"])}</h2>\n'
        f'      <p class="reveal-dek">{esc(issue["dek"])}</p>\n'
        '      <div class="reveal-actions">\n'
        "        <button class=\"btn-primary\" data-close>Read this week's issue</button>\n"
        '        <a class="link-arrow" href="#subscribe" data-close>Follow the series <span class="arrow">&rarr;</span></a>\n'
        '      </div>\n'
        '    </div>\n'
        '  </div>'
    )


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
    is_month = kind == "collection"
    feats = []
    for f in ann.get("features", []):
        note = esc(f.get("note", ""))
        revealed = f.get("revealed", True)
        reveal = f.get("reveal", "")
        if is_month and not revealed:
            # Sealed protein: tease the schedule, never the name. The row is a CTA to subscribe.
            friendly = esc(_friendly_date(reveal)) if reveal else "soon"
            feats.append(
                '            <li><a class="feat feat-sealed" href="#subscribe">'
                f'<span class="feat-name feat-when" data-reveal="{esc(reveal)}">Opens {friendly}</span>'
                '<span class="feat-note">Sealed until then. Subscribe to catch the reveal.</span></a></li>'
            )
        else:
            name = esc(f.get("name", ""))
            href = f.get("href", "")
            name_el = f'<a class="feat-name" href="{esc(href)}">{name}</a>' if href else f'<span class="feat-name">{name}</span>'
            extra = f' <span class="feat-opens">Opens {esc(reveal)}</span>' if (not revealed and reveal) else ""
            feats.append(f'            <li class="feat">{name_el}<span class="feat-note">{note}{extra}</span></li>')
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
{SUBSCRIBE_CSS}
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
        <p class="kickoff-back"><a class="link-arrow" href="potw.html">The latest issue <span class="arrow">&rarr;</span></a> &nbsp;&nbsp; <a class="link-arrow" href="potw-catalogue.html">The full catalogue <span class="arrow">&rarr;</span></a></p>
      </div>
    </section>

{SUBSCRIBE_HTML}
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

{TEASER_SCRIPT}
</body>
</html>
"""


STRUCTURE_CSS = """
    /* === Structure viewer (the specimen) === */
    .structure-figure { margin-top: 0.5rem; }
    .specimen { position: relative; width: 100%; max-width: 620px; margin-inline: auto; aspect-ratio: 4 / 3; border: 1px solid var(--ink-hairline-strong); background: var(--parchment-pale); overflow: hidden; }
    .specimen-stage { position: absolute; inset: 0; }
    .specimen-stage canvas { display: block; }
    .specimen-fallback { position: absolute; inset: 0; display: flex; flex-direction: column; background: var(--parchment-pale); }
    .specimen-still { flex: 1 1 auto; min-height: 0; width: 100%; object-fit: contain; padding: 4%; filter: grayscale(0.3) sepia(0.16) contrast(0.97); }
    .specimen-fallback-bar { flex: 0 0 auto; display: flex; flex-direction: column; gap: 0.15rem; text-align: center; padding: 0.5rem 1rem 0.7rem; border-top: 1px solid var(--ink-hairline); font-size: 0.8125rem; color: var(--ink-soft); }
    .specimen-fallback a { color: var(--tannin); }
    .specimen-credit { font-size: 0.625rem; color: var(--ink-soft); }
    .specimen-why { font-size: 0.6875rem; color: var(--ink-soft); }
    .specimen-caption { margin-top: 0.9rem; font-size: 0.8125rem; font-style: italic; color: var(--ink-soft); text-align: center; max-width: 62ch; margin-inline: auto; }
    .specimen-caption a { color: var(--tannin); font-style: normal; text-decoration: none; border-bottom: 1px solid var(--ink-hairline-strong); }
    .specimen-caption a:hover { border-color: var(--tannin); }
    /* Colony-ripple loader: hairline rings spreading from a point, like a culture on agar. */
    .loader { position: absolute; inset: 0; margin: auto; width: 72px; height: 72px; display: grid; place-items: center; pointer-events: none; }
    .loader[hidden] { display: none; }
    .loader span { position: absolute; inset: 0; margin: auto; width: 100%; height: 100%; border: 1px solid var(--tannin); border-radius: 50%; opacity: 0; animation: colony-ripple 2.2s cubic-bezier(0.2, 0.6, 0.3, 1) infinite; }
    .loader span:nth-child(2) { animation-delay: 0.73s; }
    .loader span:nth-child(3) { animation-delay: 1.46s; }
    .loader em { width: 8px; height: 8px; border-radius: 50%; background: var(--tannin); }
    @keyframes colony-ripple { 0% { transform: scale(0.12); opacity: 0; } 25% { opacity: 0.5; } 100% { transform: scale(1); opacity: 0; } }
    @media (prefers-reduced-motion: reduce) { .loader span { animation: none; opacity: 0.32; transform: scale(0.66); } .loader span:nth-child(3) { transform: scale(0.9); } }"""

REFERENCES_CSS = """
    /* === Inline citations + references === */
    .cite { font-size: 0.7em; line-height: 0; vertical-align: super; margin-left: 0.08em; font-variation-settings: "wght" 600; white-space: nowrap; }
    .cite a { color: var(--tannin); text-decoration: none; }
    .cite a:hover { text-decoration: underline; }
    .references { border-top: 1px solid var(--ink-hairline); }
    .ref-list { list-style: none; max-width: 70ch; }
    .ref-item { display: grid; grid-template-columns: 1.6rem 1fr; gap: 0.9rem; padding-block: 0.7rem; border-bottom: 1px solid var(--ink-hairline); font-size: 0.9375rem; line-height: 1.5; scroll-margin-top: 1.5rem; }
    .ref-item:first-child { border-top: 1px solid var(--ink-hairline); }
    .ref-item:target { background: var(--parchment-mid); }
    .ref-num { color: var(--tannin); font-variant-numeric: tabular-nums; font-variation-settings: "wdth" 95, "wght" 600; }
    .ref-title { color: var(--ink); }
    .ref-src { color: var(--ink-soft); font-style: italic; }
    .ref-body a { color: var(--tannin); text-decoration: none; border-bottom: 1px solid var(--ink-hairline-strong); white-space: nowrap; }
    .ref-body a:hover { border-color: var(--tannin); }
    .ref-foot { margin-top: 1.5rem; font-size: 0.8125rem; color: var(--ink-soft); font-style: italic; max-width: 60ch; }"""

STRUCTURE_SCRIPT = """  <script>
    /* Structure viewer. The goal is to show the ACTUAL rotating 3D structure as widely as
       possible, so every step cascades through fallbacks before giving up:
         - the 3Dmol library:  vendored (same-origin) -> 3Dmol.org -> jsDelivr
         - the structure file:  vendored PDB (same-origin) -> RCSB
       Only if every one of those routes fails do we reveal the static structure image.
       This makes the viewer resilient to a blocked CDN, a stale/broken cached asset, an
       ad-blocker, or a flaky network: whichever route works first wins. */
    (function () {
      var stage = document.getElementById('pdbStage');
      if (!stage) return;
      var specimen = stage.closest('.specimen');
      var pdb = (specimen.getAttribute('data-pdb') || '').trim();
      var loader = document.getElementById('pdbLoader');
      var fallback = document.getElementById('pdbFallback');
      var why = document.getElementById('pdbWhy');
      if (!pdb || !('fetch' in window)) { showStill('This browser cannot load the interactive view.'); return; }

      var LIBS = [
        'assets/potw/vendor/3Dmol-min.js',
        'https://3Dmol.org/build/3Dmol-min.js',
        'https://cdn.jsdelivr.net/npm/3dmol@2.4.2/build/3Dmol-min.js'
      ];
      var PDBS = [
        'assets/potw/pdb/' + pdb.toLowerCase() + '.pdb',
        'https://files.rcsb.org/download/' + pdb.toUpperCase() + '.pdb'
      ];
      var started = false, rendered = false;

      function showStill(reason) {
        if (rendered) return;            /* never cover a live render */
        if (loader) loader.hidden = true;
        if (fallback) fallback.hidden = false;
        if (reason) { try { console.warn('[POTW structure] ' + reason); } catch (e) {} if (why) why.textContent = reason; }
      }

      /* Walk the library sources until one leaves a working $3Dmol on the page. */
      function loadLib(i) {
        if (window.$3Dmol) return build();
        if (i >= LIBS.length) return showStill('The 3D viewer library could not be loaded from any source.');
        var s = document.createElement('script');
        s.src = LIBS[i]; s.async = true;
        s.onload = function () { window.$3Dmol ? build() : loadLib(i + 1); };
        s.onerror = function () { loadLib(i + 1); };
        document.head.appendChild(s);
      }

      /* Walk the PDB sources until one returns text. */
      function fetchPdb(i) {
        if (i >= PDBS.length) return Promise.reject(new Error('The structure file could not be downloaded from any source.'));
        return fetch(PDBS[i]).then(function (r) {
          if (!r.ok) throw new Error('HTTP ' + r.status);
          return r.text();
        }).then(function (t) {
          if (!t || t.length < 200) throw new Error('empty response');
          return t;
        }, function () { return fetchPdb(i + 1); });
      }

      function build() {
        var viewer;
        try { viewer = $3Dmol.createViewer(stage, { backgroundColor: 0xf7f3e9 }); }
        catch (e) { return showStill('This browser has WebGL (3D graphics) turned off, so the interactive structure cannot be drawn.'); }
        fetchPdb(0).then(function (data) {
          viewer.addModel(data, 'pdb');
          viewer.setStyle({}, { cartoon: { color: '#8a5730' } });
          viewer.addStyle({ hetflag: true }, { stick: { color: '#c0893e', radius: 0.22 } });
          viewer.zoomTo();
          viewer.render();
          rendered = true;
          if (loader) loader.hidden = true;
          if (fallback) fallback.hidden = true;
          if (!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches)) viewer.spin('y', 0.35);
          window.addEventListener('resize', function () { try { viewer.resize(); } catch (e) {} });
        }).catch(function (e) { showStill((e && e.message) || 'The structure could not be drawn.'); });
      }

      function start() { if (started) return; started = true; loadLib(0); }

      if ('IntersectionObserver' in window) {
        var io = new IntersectionObserver(function (es) {
          es.forEach(function (e) { if (e.isIntersecting) { start(); io.disconnect(); } });
        }, { rootMargin: '300px' });
        io.observe(specimen);
        /* Safety net: if the observer never fires (odd scroll containers, hidden tab that
           later shows, etc.), kick it off anyway so the viewer isn't stuck waiting. */
        setTimeout(function () { if (!started) start(); }, 3000);
      } else { start(); }
    })();
  </script>"""


def _structure_section(issue: dict) -> str:
    """The interactive 3D structure section, rendered only when the issue has a PDB id."""
    pdb = (issue.get("pdb_id") or "").strip()
    if not pdb:
        return ""
    pu = esc(pdb.upper())
    rcsb = f"https://www.rcsb.org/structure/{pu}"
    note = esc(issue.get("pdb_note") or f"Structure from the RCSB Protein Data Bank.")
    pdb_low = esc(pdb.lower())
    credit = esc(issue.get("pdb_still_credit", ""))
    credit_html = f'<span class="specimen-credit">{credit}</span>' if credit else ""
    return (
        '    <section id="structure">\n'
        '      <div class="wrap">\n'
        '        <div class="section-head">\n'
        '          <span class="label">&sect; &nbsp; The specimen</span>\n'
        '          <h2 class="headline">Turn it over in your hand.</h2>\n'
        '        </div>\n'
        '        <div class="structure-figure">\n'
        f'          <div class="specimen" data-pdb="{pu}">\n'
        '            <div class="specimen-stage" id="pdbStage"></div>\n'
        '            <div class="loader" id="pdbLoader" role="status" aria-label="Loading the 3D structure">\n'
        '              <span></span><span></span><span></span><em></em>\n'
        '            </div>\n'
        '            <div class="specimen-fallback" id="pdbFallback" hidden>\n'
        f'              <img class="specimen-still" src="assets/potw/pdb/{pdb_low}-still.png" alt="Structure of {esc(issue["protein"])} (PDB {pu})" loading="lazy" onerror="this.remove()">\n'
        '              <div class="specimen-fallback-bar">\n'
        f'                <span>Interactive view unavailable. <a href="{rcsb}" target="_blank" rel="noopener noreferrer">Open PDB {pu} at RCSB &rarr;</a></span>\n'
        f'                {credit_html}\n'
        '                <span class="specimen-why" id="pdbWhy"></span>\n'
        '              </div>\n'
        '            </div>\n'
        '          </div>\n'
        f'          <p class="specimen-caption">{note} PDB <a href="{rcsb}" target="_blank" rel="noopener noreferrer">{pu}</a>. Drag to rotate, scroll to zoom.</p>\n'
        '        </div>\n'
        '      </div>\n'
        '    </section>'
    )


def _references_section(issue: dict) -> str:
    """The numbered references list, rendered only when the issue carries sources."""
    refs = issue.get("references") or []
    if not refs:
        return ""
    items = []
    for i, r in enumerate(refs, start=1):
        title = esc(r.get("title", ""))
        source = f' <span class="ref-src">{esc(r.get("source", ""))}</span>' if r.get("source") else ""
        url = r.get("url", "")
        link = f' <a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{esc(_host(url))} &rarr;</a>' if url else ""
        items.append(
            f'          <li class="ref-item" id="ref-{i}">'
            f'<span class="ref-num">{i}.</span>'
            f'<span class="ref-body"><span class="ref-title">{title}</span>{source}{link}</span></li>'
        )
    inner = "\n".join(items)
    return (
        '    <section id="references">\n'
        '      <div class="wrap">\n'
        '        <div class="section-head">\n'
        '          <span class="label">&sect; &nbsp; Sources</span>\n'
        '          <h2 class="headline">Where this comes from.</h2>\n'
        '        </div>\n'
        f'        <ol class="ref-list">\n{inner}\n        </ol>\n'
        '        <p class="ref-foot">Each issue is drafted by a research harness and checked against these sources before it ships. Follow any link to read further.</p>\n'
        '      </div>\n'
        '    </section>'
    )


CATALOGUE_CSS = """
    /* === Catalogue (browse the whole series) === */
    .catalogue .cat-progress { display: flex; align-items: center; gap: 0.9rem; margin-top: 1.5rem; max-width: 32rem; }
    .cat-progress-track { flex: 1; height: 3px; background: var(--ink-hairline); position: relative; }
    .cat-progress-fill { position: absolute; inset: 0 auto 0 0; background: var(--tannin); }
    .cat-progress-label { font-size: 0.6875rem; font-variation-settings: "wght" 600; letter-spacing: 0.13em; text-transform: uppercase; color: var(--ink-soft); font-variant-numeric: tabular-nums; white-space: nowrap; }
    .cat-latest { margin-top: 1.5rem; }
    .cat-hook { margin-top: 1rem; font-size: 0.9375rem; color: var(--ink-soft); max-width: 60ch; }
    .cat-hook a { color: var(--tannin); text-decoration: none; border-bottom: 1px solid var(--ink-hairline-strong); font-variation-settings: "wght" 600; }
    .cat-hook a:hover { border-color: var(--tannin); }
    .cat-season { border-top: 1px solid var(--ink-hairline-strong); margin-top: clamp(2.5rem, 5vw, 3.75rem); padding-top: clamp(1.75rem, 4vw, 2.5rem); }
    .cat-season-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 0.4rem 1rem; margin-bottom: 0.35rem; }
    .cat-season-kicker { font-size: 0.6875rem; font-variation-settings: "wght" 600; letter-spacing: 0.14em; text-transform: uppercase; color: var(--ink-soft); font-variant-numeric: tabular-nums; }
    .cat-season-name { font-variation-settings: "wdth" 95, "wght" 700; font-size: clamp(1.5rem, 3vw, 2rem); letter-spacing: -0.02em; color: var(--ink); text-decoration: none; }
    a.cat-season-name:hover { color: var(--tannin); }
    .cat-season-blurb { flex-basis: 100%; font-size: 0.9375rem; color: var(--ink-soft); max-width: 62ch; }
    .cat-collection { margin-top: 1.6rem; }
    .cat-collection-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 0.3rem 0.85rem; margin-bottom: 0.65rem; }
    .cat-collection-name { font-size: 0.75rem; font-variation-settings: "wght" 600; letter-spacing: 0.14em; text-transform: uppercase; color: var(--tannin); text-decoration: none; }
    a.cat-collection-name { border-bottom: 1px solid transparent; }
    a.cat-collection-name:hover { border-color: var(--tannin); }
    .cat-collection-month { font-size: 0.75rem; color: var(--ink-soft); font-variant-numeric: tabular-nums; }
    .cat-collection-blurb { flex-basis: 100%; font-size: 0.8125rem; color: var(--ink-soft); }
    .cat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1px; background: var(--ink-hairline); border: 1px solid var(--ink-hairline); }
    @media (max-width: 760px) { .cat-grid { grid-template-columns: repeat(2, 1fr); } }
    @media (max-width: 440px) { .cat-grid { grid-template-columns: 1fr; } }
    .cat-cell { display: flex; flex-direction: column; min-height: 118px; padding: 0.9rem 1rem 1.05rem; background: var(--parchment); text-decoration: none; color: inherit; }
    .cat-no { font-size: 0.625rem; font-variation-settings: "wght" 600; letter-spacing: 0.14em; text-transform: uppercase; color: var(--ink-soft); font-variant-numeric: tabular-nums; }
    .cat-body { margin-top: auto; display: flex; flex-direction: column; gap: 0.3rem; padding-top: 0.75rem; }
    .cat-name { font-variation-settings: "wdth" 95, "wght" 600; font-size: 1.0625rem; letter-spacing: -0.01em; color: var(--ink); line-height: 1.2; }
    .cat-org { display: block; font-style: italic; font-variation-settings: "wdth" 95, "wght" 400; font-size: 0.8125rem; color: var(--ink-soft); margin-top: 0.15rem; }
    .cat-date { font-size: 0.75rem; color: var(--ink-soft); font-variant-numeric: tabular-nums; }
    a.cat-cell.is-live { transition: background 160ms ease-out; }
    a.cat-cell.is-live:hover { background: var(--parchment-pale); }
    a.cat-cell.is-live:hover .cat-name { color: var(--tannin); }
    .cat-cell.is-current { box-shadow: inset 3px 0 0 var(--tannin); }
    .cat-cell.is-current .cat-no { color: var(--tannin); }
    .cat-cell.is-sealed { background: var(--parchment-mid); }
    a.cat-cell.is-sealed { transition: background 160ms ease-out; }
    a.cat-cell.is-sealed:hover { background: var(--parchment-deep); }
    a.cat-cell.is-sealed:hover .cat-sealed-note { color: var(--tannin); }
    .cat-seal { width: 13px; height: 13px; border-radius: 50%; border: 1.5px solid var(--tannin); opacity: 0.45; }
    .cat-when { font-variation-settings: "wdth" 95, "wght" 600; font-size: 0.9375rem; color: var(--tannin); font-variant-numeric: tabular-nums; }
    .cat-sealed-note { font-size: 0.75rem; color: var(--ink-soft); transition: color 160ms ease-out; }
    .cat-cell.is-preview-sealed { border: 1px dashed var(--ink-hairline-strong); }
    .cat-preview-banner { background: var(--tannin); color: var(--parchment-pale); text-align: center; font-size: 0.8125rem; font-variation-settings: "wght" 600; letter-spacing: 0.04em; padding: 0.55rem 1rem; }"""

CATALOGUE_SCRIPT = """  <script>
    /* Sealed cells: turn the reveal date into a live countdown. */
    (function () {
      var els = document.querySelectorAll('.cat-when[data-reveal]');
      if (!els.length) return;
      var today = new Date(); today.setHours(0, 0, 0, 0);
      els.forEach(function (el) {
        var iso = (el.getAttribute('data-reveal') || '').split('-');
        if (iso.length !== 3) return;
        var d = new Date(+iso[0], +iso[1] - 1, +iso[2]); d.setHours(0, 0, 0, 0);
        var days = Math.round((d - today) / 86400000);
        if (days > 1) el.textContent = 'Opens in ' + days + ' days';
        else if (days === 1) el.textContent = 'Opens tomorrow';
        else if (days === 0) el.textContent = 'Opens today';
      });
    })();
  </script>"""


def _cat_cell(number: int, spec: dict, drafted: bool, current_number: int, anchor: str,
              issues_by_slug: dict, preview: bool) -> str:
    slug = _spec_slug(spec)
    if drafted:
        issue = issues_by_slug.get(slug)
        org = f'<span class="cat-org">{esc(_organism(issue["binomial"]))}</span>' if issue else ""
        date = f'<span class="cat-date">{esc(issue["date_display"])}</span>' if issue else ""
        cur = " is-current" if number == current_number else ""
        body = f'<span class="cat-body"><span class="cat-name">{esc(spec["protein"])}{org}</span>{date}</span>'
        return f'<a class="cat-cell is-live{cur}" href="{issue_href(number, slug)}"><span class="cat-no">No. {number:03d}</span>{body}</a>'
    rev = _reveal_iso(number, anchor)
    friendly = esc(_friendly_date(rev)) if rev else "soon"
    if preview:
        body = f'<span class="cat-body"><span class="cat-name">{esc(spec["protein"])}</span><span class="cat-date">Opens {friendly}</span></span>'
        return f'<div class="cat-cell is-live is-preview-sealed"><span class="cat-no">No. {number:03d}</span>{body}</div>'
    body = (
        '<span class="cat-body"><span class="cat-seal" aria-hidden="true"></span>'
        f'<span class="cat-when" data-reveal="{esc(rev)}">Opens {friendly}</span>'
        '<span class="cat-sealed-note">Sealed. Subscribe to catch it.</span></span>'
    )
    return f'<a class="cat-cell is-sealed" href="#subscribe"><span class="cat-no">No. {number:03d}</span>{body}</a>'


CATALOGUE_TREE_CSS = """
    /* === Catalogue view toggle + classification tree === */
    .cat-viewtabs { display: inline-flex; border: 1px solid var(--ink-hairline-strong); margin-top: 1.6rem; }
    .cat-tab { padding: 0.4rem 1.15rem; font-size: 0.75rem; font-variation-settings: "wght" 600; letter-spacing: 0.12em; text-transform: uppercase; color: var(--ink-soft); border-right: 1px solid var(--ink-hairline-strong); background: var(--parchment); transition: background 160ms ease-out, color 160ms ease-out; }
    .cat-tab:last-child { border-right: none; }
    .cat-tab.is-active { background: var(--tannin); color: var(--parchment-pale); }
    .cat-panel[hidden] { display: none; }
    .tree-scroll { overflow-x: auto; margin-top: 1.75rem; border: 1px solid var(--ink-hairline); background: var(--parchment-pale); padding: 1.25rem 0.75rem; }
    .tree-svg { display: block; width: 100%; min-width: 760px; height: auto; }
    .tree-scroll-radial { overflow-x: hidden; padding: 1rem; }
    .tree-radial { display: block; width: 100%; max-width: 640px; height: auto; margin-inline: auto; }
    .tree-radial a { text-decoration: none; }
    .tree-radial a:hover .tree-leaf { fill: var(--tannin-deep); text-decoration: underline; }
    .tree-root { font-variation-settings: "wght" 600; font-size: 10px; letter-spacing: 0.14em; fill: var(--ink-soft); }
    .tree-season { font-variation-settings: "wdth" 95, "wght" 600; font-size: 12px; fill: var(--tannin); }
    .tree-coll { font-variation-settings: "wght" 600; font-size: 9px; letter-spacing: 0.1em; fill: var(--ink-soft); }
    .tree-leaf { font-style: italic; font-variation-settings: "wdth" 95, "wght" 400; font-size: 11px; fill: var(--tannin); }
    .tree-svg a { text-decoration: none; }
    .tree-svg a:hover .tree-leaf { fill: var(--tannin-deep); text-decoration: underline; }
    .tree-note { margin-top: 1.1rem; font-size: 0.875rem; line-height: 1.55; color: var(--ink-soft); max-width: 64ch; }"""

CATALOGUE_TREE_SCRIPT = """  <script>
    /* Catalogue grid/tree toggle. Static views; no layout work client-side. */
    (function () {
      var tabs = document.querySelectorAll('.cat-tab');
      var panels = document.querySelectorAll('.cat-panel');
      if (!tabs.length) return;
      function show(v) {
        tabs.forEach(function (t) { var on = t.getAttribute('data-view') === v; t.classList.toggle('is-active', on); t.setAttribute('aria-selected', on ? 'true' : 'false'); });
        panels.forEach(function (p) { p.hidden = p.getAttribute('data-panel') !== v; });
      }
      tabs.forEach(function (t) { t.addEventListener('click', function () { show(t.getAttribute('data-view')); }); });
    })();
  </script>"""


def _catalogue_tree_svg(queue: dict, issues_by_slug: dict, anchor: str) -> str:
    """The catalogue as a static classification tree (horizontal dendrogram).

    Root -> seasons -> collections -> specimen leaves. Published specimens are named,
    linked leaves; sealed specimens are unlabeled 'bud' tips (embargo-safe: no name in
    the source, only a reveal-date title). Deterministic, no client-side layout.
    """
    ROOT_X, SEASON_X, COLL_X, LEAF_X = 52, 250, 468, 684
    LABEL_X = LEAF_X + 12
    STEP, COLL_GAP, SEASON_GAP, TOP, WIDTH = 15, 8, 16, 34, 1060

    links, dots, labels, leaves = [], [], [], []
    y = TOP
    num = 0
    season_pts = []
    for si, season in enumerate(queue.get("seasons", [])):
        if si:
            y += SEASON_GAP
        coll_pts = []
        for ci, coll in enumerate(season.get("collections", [])):
            if ci:
                y += COLL_GAP
            leaf_ys = []
            for spec in coll.get("specimens", []):
                num += 1
                ly = y
                y += STEP
                leaf_ys.append(ly)
                if _is_drafted(num, spec):
                    nm = esc(spec["protein"])
                    dots.append(f'<circle cx="{LEAF_X}" cy="{ly}" r="3.2" fill="var(--tannin)"/>')
                    leaves.append(
                        f'<a href="{issue_href(num, _spec_slug(spec))}"><title>No. {num:03d}: {nm}</title>'
                        f'<text class="tree-leaf" x="{LABEL_X}" y="{ly}" dy="0.32em">{nm}</text></a>'
                    )
                else:
                    rev = _reveal_iso(num, anchor)
                    fr = esc(_friendly_date(rev)) if rev else "soon"
                    dots.append(
                        f'<circle cx="{LEAF_X}" cy="{ly}" r="2.6" fill="var(--parchment)" '
                        f'stroke="var(--ink-soft)" stroke-width="1" opacity="0.6">'
                        f'<title>No. {num:03d}: opens {fr}</title></circle>'
                    )
            cy = sum(leaf_ys) / len(leaf_ys)
            coll_pts.append(cy)
            dots.append(f'<circle cx="{COLL_X}" cy="{cy:.1f}" r="2.8" fill="var(--ink-soft)"/>')
            labels.append(
                f'<text class="tree-coll" x="{COLL_X - 8}" y="{cy - 5:.1f}" text-anchor="end">'
                f'{esc(coll["label"].upper())}</text>'
            )
            for ly in leaf_ys:
                links.append(f'<path d="M {LEAF_X},{ly} H {COLL_X} V {cy:.1f}"/>')
        scy = sum(coll_pts) / len(coll_pts)
        season_pts.append(scy)
        dots.append(f'<circle cx="{SEASON_X}" cy="{scy:.1f}" r="3.4" fill="var(--tannin)"/>')
        labels.append(
            f'<text class="tree-season" x="{SEASON_X - 10}" y="{scy - 6:.1f}" text-anchor="end">'
            f'{esc(season["label"])}</text>'
        )
        for cy in coll_pts:
            links.append(f'<path d="M {COLL_X},{cy:.1f} H {SEASON_X} V {scy:.1f}"/>')
    rcy = sum(season_pts) / len(season_pts)
    dots.append(f'<circle cx="{ROOT_X}" cy="{rcy:.1f}" r="4" fill="var(--tannin)"/>')
    labels.append(f'<text class="tree-root" x="{ROOT_X}" y="16">PROTEIN OF THE WEEK</text>')
    for scy in season_pts:
        links.append(f'<path d="M {SEASON_X},{scy:.1f} H {ROOT_X} V {rcy:.1f}"/>')

    height = int(y + TOP)
    return (
        f'<svg class="tree-svg" viewBox="0 0 {WIDTH} {height}" role="img" '
        f'aria-label="The Protein of the Week catalogue drawn as a classification tree">'
        f'<g fill="none" stroke="var(--ink-hairline-strong)" stroke-width="1">{"".join(links)}</g>'
        f'<g>{"".join(dots)}</g>'
        f'<g>{"".join(labels)}</g>'
        f'<g>{"".join(leaves)}</g>'
        "</svg>"
    )


def _catalogue_unrooted_svg(queue: dict, issues_by_slug: dict, anchor: str) -> str:
    """The same classification drawn as an unrooted, radial tree.

    No fixed root direction: the series sits as a faint hub at the center, seasons
    radiate outward, collections branch, and specimens are the leaf tips around the
    rim. Same embargo behavior as the rooted view: published specimens are named,
    linked leaves; sealed weeks are unlabeled buds. Deterministic, no client layout.
    """
    SIZE = 940
    C = SIZE / 2
    R_SEASON, R_COLL, R_LEAF, LABEL_PAD = 96, 210, 322, 9
    GAP_DEG = 12.0
    start = -90.0 + GAP_DEG / 2.0
    sweep = 360.0 - GAP_DEG

    total_leaves = sum(
        len(c.get("specimens", []))
        for s in queue.get("seasons", [])
        for c in s.get("collections", [])
    )
    if not total_leaves:
        return f'<svg class="tree-radial" viewBox="0 0 {SIZE} {SIZE}"></svg>'

    def pt(r: float, deg: float) -> tuple[float, float]:
        rad = math.radians(deg)
        return (C + r * math.cos(rad), C + r * math.sin(rad))

    def radial_text(deg: float) -> tuple[float, str]:
        """(rotation, text-anchor) so labels read outward and never upside down."""
        if 90.0 < (deg % 360.0) < 270.0:
            return deg + 180.0, "end"
        return deg, "start"

    links, dots, labels, leaves = [], [], [], []
    num = 0
    leaf_i = 0
    season_angles = []
    for season in queue.get("seasons", []):
        coll_angles = []
        for coll in season.get("collections", []):
            spec_angles = []
            for spec in coll.get("specimens", []):
                num += 1
                ang = start + (leaf_i + 0.5) * sweep / total_leaves
                leaf_i += 1
                spec_angles.append(ang)
                lx, ly = pt(R_LEAF, ang)
                if _is_drafted(num, spec):
                    nm = esc(spec["protein"])
                    dots.append(f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="3.2" fill="var(--tannin)"/>')
                    tx, ty = pt(R_LEAF + LABEL_PAD, ang)
                    rot, anc = radial_text(ang)
                    leaves.append(
                        f'<a href="{issue_href(num, _spec_slug(spec))}"><title>No. {num:03d}: {nm}</title>'
                        f'<text class="tree-leaf" x="{tx:.1f}" y="{ty:.1f}" text-anchor="{anc}" dy="0.32em" '
                        f'transform="rotate({rot:.1f} {tx:.1f} {ty:.1f})">{nm}</text></a>'
                    )
                else:
                    rev = _reveal_iso(num, anchor)
                    fr = esc(_friendly_date(rev)) if rev else "soon"
                    dots.append(
                        f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="2.4" fill="var(--parchment)" '
                        f'stroke="var(--ink-soft)" stroke-width="1" opacity="0.6">'
                        f'<title>No. {num:03d}: opens {fr}</title></circle>'
                    )
            cang = sum(spec_angles) / len(spec_angles)
            coll_angles.append(cang)
            ccx, ccy = pt(R_COLL, cang)
            dots.append(
                f'<circle cx="{ccx:.1f}" cy="{ccy:.1f}" r="2.8" fill="var(--ink-soft)">'
                f'<title>{esc(coll["label"])}</title></circle>'
            )
            for ang in spec_angles:
                lx, ly = pt(R_LEAF, ang)
                links.append(f'<path d="M {ccx:.1f},{ccy:.1f} L {lx:.1f},{ly:.1f}"/>')
        sang = sum(coll_angles) / len(coll_angles)
        season_angles.append(sang)
        scx, scy = pt(R_SEASON, sang)
        dots.append(f'<circle cx="{scx:.1f}" cy="{scy:.1f}" r="3.4" fill="var(--tannin)"/>')
        srot, sanc = radial_text(sang)
        labels.append(
            f'<text class="tree-season" x="{scx:.1f}" y="{scy:.1f}" text-anchor="{sanc}" dy="-0.55em" '
            f'transform="rotate({srot:.1f} {scx:.1f} {scy:.1f})">{esc(season["label"])}</text>'
        )
        for cang in coll_angles:
            ccx, ccy = pt(R_COLL, cang)
            links.append(f'<path d="M {scx:.1f},{scy:.1f} L {ccx:.1f},{ccy:.1f}"/>')
    for sang in season_angles:
        scx, scy = pt(R_SEASON, sang)
        links.append(f'<path d="M {C:.1f},{C:.1f} L {scx:.1f},{scy:.1f}"/>')
    dots.append(f'<circle cx="{C:.1f}" cy="{C:.1f}" r="2.6" fill="var(--ink-soft)" opacity="0.5"/>')

    return (
        f'<svg class="tree-radial" viewBox="0 0 {SIZE} {SIZE}" role="img" '
        f'aria-label="The Protein of the Week catalogue drawn as an unrooted radial tree">'
        f'<g fill="none" stroke="var(--ink-hairline-strong)" stroke-width="1">{"".join(links)}</g>'
        f'<g>{"".join(dots)}</g>'
        f'<g>{"".join(labels)}</g>'
        f'<g>{"".join(leaves)}</g>'
        "</svg>"
    )


def render_catalogue(preview: bool = False) -> str:
    """The full series as one browsable page: seasons, collections, and specimen cells.

    Published specimens are named and linked; upcoming ones are sealed teasers with a
    countdown (build-time embargo, same gate as the kickoffs). preview=True reveals every
    name for editorial review and is not meant to be published.
    """
    queue = load_queue()
    anchor = queue.get("anchor_date", "2026-07-06")
    announced = announced_ids()
    issues_by_slug = {d.get("slug"): d for d in load_all_issues()}

    num_of, drafted_nums, total = {}, [], 0
    for number, spec, _c, _s in iter_specimens(queue):
        num_of[id(spec)] = number
        total += 1
        if _is_drafted(number, spec):
            drafted_nums.append(number)
    revealed = len(drafted_nums)
    sealed = total - revealed
    current_number = max(drafted_nums) if drafted_nums else 0

    seasons_html = []
    for season in queue.get("seasons", []):
        sid = season.get("id", "")
        sname = esc(season["label"])
        sname_el = (f'<a class="cat-season-name" href="{announce_href(sid)}">{sname}</a>'
                    if sid in announced else f'<span class="cat-season-name">{sname}</span>')
        colls_html = []
        for coll in season.get("collections", []):
            cid = coll.get("id", "")
            cname = esc(coll["label"])
            cname_el = (f'<a class="cat-collection-name" href="{announce_href(cid)}">{cname}</a>'
                        if cid in announced else f'<span class="cat-collection-name">{cname}</span>')
            cells = [
                _cat_cell(num_of[id(spec)], spec, _is_drafted(num_of[id(spec)], spec),
                          current_number, anchor, issues_by_slug, preview)
                for spec in coll.get("specimens", [])
            ]
            colls_html.append(
                '        <div class="cat-collection">\n'
                f'          <div class="cat-collection-head">{cname_el}'
                f'<span class="cat-collection-month">{esc(coll.get("month", ""))}</span>'
                f'<span class="cat-collection-blurb">{esc(coll.get("blurb", ""))}</span></div>\n'
                '          <div class="cat-grid">\n            '
                + "\n            ".join(cells)
                + '\n          </div>\n        </div>'
            )
        seasons_html.append(
            '      <div class="cat-season">\n        <div class="wrap">\n'
            f'          <div class="cat-season-head"><span class="cat-season-kicker">{esc(season.get("quarter", ""))}</span>'
            f'{sname_el}<span class="cat-season-blurb">{esc(season.get("blurb", ""))}</span></div>\n'
            + "\n".join(colls_html)
            + '\n        </div>\n      </div>'
        )
    seasons_block = "\n".join(seasons_html)
    tree_svg = _catalogue_tree_svg(queue, issues_by_slug, anchor)
    unrooted_svg = _catalogue_unrooted_svg(queue, issues_by_slug, anchor)
    pct = round(100 * revealed / total) if total else 0
    banner = '  <div class="cat-preview-banner">Editorial preview: shows unrevealed names. Not for publishing.</div>\n' if preview else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>The catalogue: Protein of the Week, Phyla Technologies</title>
  <link rel="icon" type="image/svg+xml" href="favicon.svg">
  <meta name="description" content="The full Protein of the Week series: a protein every week, gathered into monthly collections and quarterly seasons. One is revealed each week.">
  <meta name="view-transition" content="same-origin">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wdth,wght@12..96,75..100,300..800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="styles.css">
  <style>
    .masthead {{ border-bottom: 1px solid var(--ink-hairline); background: var(--parchment); }}
    .masthead-inner {{ display: flex; align-items: baseline; justify-content: space-between; gap: 1.5rem; padding-block: 1.25rem; flex-wrap: wrap; }}
    .masthead .column-name {{ font-size: 0.75rem; font-variation-settings: "wdth" 100, "wght" 600; letter-spacing: 0.22em; text-transform: uppercase; color: var(--tannin); }}
{CATALOGUE_CSS}
{CATALOGUE_TREE_CSS}
{SUBSCRIBE_CSS}
  </style>
</head>
<body>
  <a href="#main" class="skip-link">Skip to main content</a>
{banner}
  <header class="masthead">
    <div class="wrap masthead-inner">
      <a href="index.html" class="wordmark" aria-label="Phyla Technologies, home">
        <span class="wordmark-name">Phyla</span>
        <span class="wordmark-sub">Technologies</span>
      </a>
      <a class="column-name" href="potw.html" style="text-decoration: none;">Protein of the Week</a>
    </div>
  </header>

  <main id="main">
    <section class="catalogue">
      <div class="wrap">
        <div class="section-head">
          <span class="label">&sect; &nbsp; The catalogue</span>
          <h2 class="headline">The whole series, in order.</h2>
          <p class="body">A new protein every week, gathered into monthly collections and quarterly seasons. One specimen is revealed each week; the rest stay sealed until their date.</p>
        </div>
        <div class="cat-progress"><span class="cat-progress-track"><span class="cat-progress-fill" style="width: {pct}%"></span></span><span class="cat-progress-label">{revealed} of {total} revealed</span></div>
        <p class="cat-latest"><a class="link-arrow" href="potw.html">Read the latest issue <span class="arrow">&rarr;</span></a> &nbsp;&nbsp; <a class="link-arrow" href="potw-field-guide.html">The field guide <span class="arrow">&rarr;</span></a></p>
        <p class="cat-hook">{sealed} of the {total} are still sealed. You cannot skip the line, but you need not check back: <a href="#subscribe">have each one delivered the week it opens &rarr;</a></p>
        <div class="cat-viewtabs" role="tablist" aria-label="Catalogue view">
          <button class="cat-tab is-active" type="button" data-view="grid" role="tab" aria-selected="true">Grid</button>
          <button class="cat-tab" type="button" data-view="tree" role="tab" aria-selected="false">Tree</button>
          <button class="cat-tab" type="button" data-view="unrooted" role="tab" aria-selected="false">Unrooted</button>
        </div>
      </div>
      <div class="cat-panel" data-panel="grid">
{seasons_block}
      </div>
      <div class="cat-panel" data-panel="tree" hidden>
        <div class="wrap">
          <div class="tree-scroll">
{tree_svg}
          </div>
          <p class="tree-note">Root to leaf: the series, its quarterly seasons, its monthly collections, and every specimen. Published specimens open as named leaves; sealed weeks are buds, one opening each week. Switch to the grid for reveal dates.</p>
        </div>
      </div>
      <div class="cat-panel" data-panel="unrooted" hidden>
        <div class="wrap">
          <div class="tree-scroll tree-scroll-radial">
{unrooted_svg}
          </div>
          <p class="tree-note">The same classification with no fixed root: the series is the faint hub at the center, seasons radiate outward, and each specimen is a leaf on the rim. Named tips are published; buds are still sealed. Hover a node for its collection or reveal date.</p>
        </div>
      </div>
    </section>

{SUBSCRIBE_HTML}
  </main>

  <footer class="site-footer">
    <div class="wrap footer-inner">
      <div class="footer-etymology">
        <em>Phyla</em>, plural of <em>phylum</em>. Kingdom, phylum, class, order, family, genus, species: the Linnaean ladder for naming the living world. Every model we ship is, underneath, a way of sorting it.
      </div>
      <div class="footer-meta">&copy; 2026 Phyla Technologies</div>
      <div class="footer-links">
        <a href="index.html">Main site</a>
        <a href="potw.html">Latest issue</a>
      </div>
    </div>
  </footer>

{CATALOGUE_SCRIPT}
{CATALOGUE_TREE_SCRIPT}
</body>
</html>
"""


def render_catalogue_file(preview: bool = False) -> None:
    dest = (SITE_ROOT / "potw-catalogue-preview.html") if preview else CATALOGUE
    dest.write_text(render_catalogue(preview=preview))
    print(f"Wrote {dest.relative_to(SITE_ROOT)}", file=sys.stderr)


FIELD_GUIDE_CSS = """
    /* === Field guide (Topicpile atlas placeholder) === */
    .fg-plate { position: relative; margin-top: clamp(1.5rem, 4vw, 2.5rem); border: 1px solid var(--ink-hairline-strong); background: var(--parchment-pale); aspect-ratio: 16 / 8; overflow: hidden; }
    .fg-plate .atlas-svg { position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0.62; }
    .fg-status { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; padding: 1.25rem; }
    .fg-status-card { background: var(--parchment); border: 1px solid var(--ink-hairline-strong); padding: 1.4rem 1.75rem; max-width: 34rem; text-align: center; display: flex; flex-direction: column; gap: 0.55rem; }
    .fg-status-card .label { color: var(--tannin); }
    .fg-status-line { font-variation-settings: "wdth" 95, "wght" 600; font-size: clamp(1.125rem, 2.4vw, 1.5rem); letter-spacing: -0.015em; color: var(--ink); font-variant-numeric: tabular-nums; }
    .fg-status-sub { font-size: 0.875rem; line-height: 1.5; color: var(--ink-soft); }
    .fg-credit { display: flex; flex-wrap: wrap; align-items: baseline; gap: 0.4rem 0.8rem; margin-top: 1.25rem; padding-top: 1.1rem; border-top: 1px solid var(--ink-hairline); }
    .fg-credit-mark { font-variation-settings: "wght" 600; letter-spacing: 0.02em; color: var(--ink); }
    .fg-credit-note { font-size: 0.9375rem; color: var(--ink-soft); }
    @media (max-width: 600px) { .fg-plate { aspect-ratio: 4 / 5; } }"""


def _atlas_svg() -> str:
    """A decorative, abstract preview of the topic atlas (no labels, embargo-safe).

    Seeded so the output is deterministic across builds. Replaced by the live Topicpile
    embed once that service exists.
    """
    rng = random.Random(7)
    clusters = [(190, 150, "var(--tannin)"), (560, 135, "var(--moss)"),
                (320, 320, "var(--ochre)"), (620, 340, "var(--moss-deep)")]
    dots, links = [], []
    for cx, cy, color in clusters:
        for _ in range(rng.randint(9, 13)):
            x = round(cx + rng.uniform(-80, 80), 1)
            y = round(cy + rng.uniform(-64, 64), 1)
            r = round(rng.uniform(2.4, 5.4), 1)
            if rng.random() < 0.3:
                dots.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{color}" opacity="0.85"/>')
            else:
                dots.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="none" stroke="var(--ink)" stroke-width="1" opacity="0.3"/>')
            if rng.random() < 0.45:
                links.append(f'<line x1="{cx}" y1="{cy}" x2="{x}" y2="{y}" stroke="var(--ink)" stroke-width="0.75" opacity="0.09"/>')
    return ('<svg class="atlas-svg" viewBox="0 0 800 460" preserveAspectRatio="xMidYMid slice" aria-hidden="true">'
            + "".join(links) + "".join(dots) + "</svg>")


def render_field_guide() -> str:
    """The field guide: a Topicpile topic-atlas of the published series.

    Ships now as a palette-matched placeholder (abstract atlas + live count + a
    'Created with Topicpile' funnel). The live embed mounts in place of .fg-status
    once the Topicpile service exists. Only ever reflects published counts, so it
    stays embargo-safe. See scripts/potw/README and the field-guide memory.
    """
    queue = load_queue()
    specs = list(iter_specimens(queue))
    total = len(specs)
    revealed = sum(1 for number, spec, _c, _s in specs if _is_drafted(number, spec))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>The field guide: Protein of the Week, Phyla Technologies</title>
  <link rel="icon" type="image/svg+xml" href="favicon.svg">
  <meta name="description" content="The Protein of the Week field guide: an explorable topic atlas of the series, where every published protein finds its place among the others.">
  <meta name="view-transition" content="same-origin">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wdth,wght@12..96,75..100,300..800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="styles.css">
  <style>
    .masthead {{ border-bottom: 1px solid var(--ink-hairline); background: var(--parchment); }}
    .masthead-inner {{ display: flex; align-items: baseline; justify-content: space-between; gap: 1.5rem; padding-block: 1.25rem; flex-wrap: wrap; }}
    .masthead .column-name {{ font-size: 0.75rem; font-variation-settings: "wdth" 100, "wght" 600; letter-spacing: 0.22em; text-transform: uppercase; color: var(--tannin); }}
{FIELD_GUIDE_CSS}
{SUBSCRIBE_CSS}
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
      <a class="column-name" href="potw.html" style="text-decoration: none;">Protein of the Week</a>
    </div>
  </header>

  <main id="main">
    <section class="field-guide">
      <div class="wrap">
        <div class="section-head">
          <span class="label">&sect; &nbsp; The field guide</span>
          <h2 class="headline">The series as a map.</h2>
          <p class="body">Every published protein takes its place in a living atlas: not a list but a map, where specimens drift into clusters by the techniques they share, the organisms they came from, and the problems they solved. It fills in one point a week.</p>
        </div>
        <!-- The live Topicpile atlas mounts here once that service exists; it replaces .fg-status and the placeholder .atlas-svg, and must map published issues only (embargo). -->
        <div class="fg-plate">
          {_atlas_svg()}
          <div class="fg-status">
            <div class="fg-status-card">
              <span class="label">Being drawn</span>
              <span class="fg-status-line">{revealed} of {total} specimens mapped</span>
              <span class="fg-status-sub">The interactive atlas opens once enough of the collection is on the page. New points appear as each week is revealed.</span>
            </div>
          </div>
        </div>
        <div class="fg-credit">
          <span class="fg-credit-mark">Created with Topicpile</span>
          <span class="fg-credit-note">Topicpile turns any research library into a map like this one.</span>
          <!-- TODO: point to the Topicpile product URL once the service is live. -->
          <a class="link-arrow" href="https://fullspec.dev" target="_blank" rel="noopener noreferrer">Explore Topicpile <span class="arrow">&rarr;</span></a>
        </div>
      </div>
    </section>

{SUBSCRIBE_HTML}
  </main>

  <footer class="site-footer">
    <div class="wrap footer-inner">
      <div class="footer-etymology">
        <em>Phyla</em>, plural of <em>phylum</em>. Kingdom, phylum, class, order, family, genus, species: the Linnaean ladder for naming the living world. Every model we ship is, underneath, a way of sorting it.
      </div>
      <div class="footer-meta">&copy; 2026 Phyla Technologies</div>
      <div class="footer-links">
        <a href="index.html">Main site</a>
        <a href="potw.html">Latest issue</a>
        <a href="potw-catalogue.html">The catalogue</a>
      </div>
    </div>
  </footer>
</body>
</html>
"""


def render_field_guide_file() -> None:
    FIELD_GUIDE.write_text(render_field_guide())
    print(f"Wrote {FIELD_GUIDE.relative_to(SITE_ROOT)}", file=sys.stderr)


def _tl_item(m: dict, ref_count: int) -> str:
    """One timeline row, optionally with an open-licensed portrait/photo scattered beside it."""
    img = (m.get("image") or "").strip()
    photo, has = "", ""
    if img:
        has = " has-photo"
        alt = esc(m.get("image_alt") or m.get("title", ""))
        credit = esc(m.get("image_credit", ""))
        href = esc(m.get("image_href", ""))
        cap = ""
        if credit:
            inner = f'<a href="{href}" target="_blank" rel="noopener noreferrer">{credit}</a>' if href else credit
            cap = f"<figcaption>{inner}</figcaption>"
        photo = (
            f'<figure class="tl-photo"><img src="{esc(img)}" alt="{alt}" loading="lazy" '
            f'width="112" height="140">{cap}</figure>'
        )
    return (
        f'          <li class="tl-item{has}">\n'
        f'            <span class="tl-year">{esc(m["year"])}</span>\n'
        f'            <span class="tl-body"><span class="tl-text"><span class="tl-title">{esc(m["title"])}</span>'
        f'<span class="tl-detail">{_cite(m["detail"], ref_count)}</span></span>{photo}</span>\n'
        f'          </li>'
    )


def render_page(issue: dict, issues: list[dict]) -> str:
    n = issue["number"]
    ref_count = len(issue.get("references") or [])
    facts = "\n".join(
        f'            <div class="fact"><dd class="value">{esc(f["value"])}</dd>'
        f'<dt class="label">{esc(f["label"])}</dt></div>'
        for f in issue["facts"]
    )
    movements = []
    for i, m in enumerate(issue["movements"], start=1):
        paras = "\n".join(f"            <p>{_cite(p, ref_count)}</p>" for p in m["paragraphs"])
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
    timeline = "\n".join(_tl_item(m, ref_count) for m in issue["timeline"])
    archive_rows = render_archive(issues, n)
    org = esc(_organism(issue["binomial"]))
    band = _collection_band(issue)
    reveal_modal = _reveal_modal(n, issue)
    structure_section = _structure_section(issue)
    references_section = _references_section(issue)
    structure_script = STRUCTURE_SCRIPT if (issue.get("pdb_id") or "").strip() else ""

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
{SUBSCRIBE_CSS}
{REVEAL_CSS}
{STRUCTURE_CSS}
{REFERENCES_CSS}
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
          <div class="pullquote"><p>{_cite(issue["pull_quote"], ref_count)}</p></div>
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

{structure_section}
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

{references_section}
    <section id="archive">
      <div class="wrap">
        <div class="section-head">
          <span class="label">&sect; &nbsp; The archive</span>
          <h2 class="headline">Every protein, every week.</h2>
          <p><a class="link-arrow" href="potw-catalogue.html">Browse the full catalogue <span class="arrow">&rarr;</span></a></p>
        </div>
        <div class="archive-list">
          {ARCHIVE_START}
{archive_rows}
          {ARCHIVE_END}
        </div>
      </div>
    </section>

{SUBSCRIBE_HTML}
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

{reveal_modal}
{TIMELINE_SCRIPT}
{REVEAL_SCRIPT}
{structure_script}
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
    ap.add_argument("--catalogue", action="store_true", help="Render the full-series catalogue page (potw-catalogue.html).")
    ap.add_argument("--preview", action="store_true", help="With the catalogue, also write an editorial preview that reveals every name (potw-catalogue-preview.html, gitignored).")
    ap.add_argument("--field-guide", action="store_true", help="Render the field-guide page (potw-field-guide.html), the Topicpile atlas placeholder.")
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

    want_catalogue = args.all or args.catalogue or args.preview
    want_field_guide = args.all or args.field_guide
    want_pages = want_catalogue or want_field_guide

    # Which issues to render this run.
    if args.all:
        targets = [d for d in all_issues if d["number"] != 1]
    elif args.issue:
        p = Path(args.issue)
        if not p.exists():
            p = ISSUES_DIR / args.issue
        targets = [json.loads(p.read_text())]
    elif args.announcement or want_pages:
        targets = []  # announcement-, catalogue-, or field-guide-only run
    else:
        print("Pass an issue filename, --announcement <id>, --catalogue, --field-guide, or --all.", file=sys.stderr)
        return 1

    if not all_issues and not ann_targets and not want_pages:
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

    if want_catalogue:
        render_catalogue_file(preview=False)
    if args.preview:
        render_catalogue_file(preview=True)
    if want_field_guide:
        render_field_guide_file()
    return 0


def _canonical_number(all_issues: list[dict], args) -> int:
    # The canonical page currently shows GFP (No. 1) unless --set-latest promoted another.
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
