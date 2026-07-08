#!/usr/bin/env python3
"""Protein of the Week: monthly and quarterly kickoff announcements.

Drafts the short "the proteins this month are all ___" (and the quarterly equivalent)
announcement for a period in the editorial calendar, in the house voice. One writer
sub-agent, no web search: it frames proteins that the weekly issues cover in depth, so
it stays high-level and invents no facts.

    mamba run -n phyla-site python scripts/potw/announce.py --list
    mamba run -n phyla-site python scripts/potw/announce.py --period 2026-07   # a month
    mamba run -n phyla-site python scripts/potw/announce.py --period 2026-q3   # a quarter

Output: scripts/potw/announcements/<period-id>.json (validated against Announcement).
Render it with: render.py --announcement <period-id>  (or render.py --all).

Requires ANTHROPIC_API_KEY. Model defaults to claude-opus-4-8; override with
POTW_ANNOUNCE_MODEL / POTW_WRITER_MODEL / POTW_MODEL.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).resolve().parent))
from issue_schema import Announcement, AnnouncementFeature, DraftAnnouncement, ThemeRef  # noqa: E402
import render  # href helpers  # noqa: E402
import research  # calendar walkers  # noqa: E402

HERE = Path(__file__).resolve().parent
ANNOUNCE_DIR = HERE / "announcements"

DEFAULT_MODEL = os.environ.get("POTW_MODEL", "claude-opus-4-8")
WRITER_MODEL = os.environ.get("POTW_ANNOUNCE_MODEL", os.environ.get("POTW_WRITER_MODEL", DEFAULT_MODEL))

ANNOUNCE_SYSTEM = (
    "You are the Phyla Protein Historian, writing the opening announcement for a themed "
    "run of the weekly Protein of the Week column. Voice: a contemporary natural-history "
    "press. Warm, precise, quietly confident.\n\n"
    "You introduce either a COLLECTION (one month, about four proteins) or a SEASON (one "
    "quarter, three monthly collections). You are setting the table, not telling the full "
    "stories: the weekly issues do the deep dives.\n\n"
    "Hard rules:\n"
    "- Never use em dashes. Use commas, colons, semicolons, periods, or parentheses.\n"
    "- Sentence-case headlines, not title case.\n"
    "- Name the theme and say why these belong together. Be specific and evocative, but do "
    "not assert detailed facts (exact dates, mechanisms, attributions) about individual "
    "proteins; that is the weekly issues' job. Invent nothing.\n"
    "- Keep it short: a heading, a one-sentence dek, and two or three tight paragraphs."
)


def _specimen_index(queue: dict) -> dict:
    """Map slug -> (week number, specimen dict) across the whole calendar."""
    idx = {}
    for number, spec, _coll, _seas in research.iter_specimens(queue):
        slug = spec.get("slug") or research.slugify(spec["protein"])
        idx[slug] = (number, spec)
    return idx


def locate(queue: dict, period_id: str):
    """Return (kind, group, season_ref) for a calendar id, or (None, None, None)."""
    for season in queue.get("seasons", []):
        if season.get("id") == period_id:
            return "season", season, None
        for coll in season.get("collections", []):
            if coll.get("id") == period_id:
                return "collection", coll, season
    return None, None, None


def _reveal_iso(number: int | None, anchor: str) -> str:
    if not number:
        return ""
    return (dt.date.fromisoformat(anchor) + dt.timedelta(days=7 * (number - 1))).isoformat()


def build_features(kind: str, group: dict, queue: dict) -> list[dict]:
    """The items a kickoff lists: proteins (for a month) or collections (for a season).

    Unrevealed items become sealed teasers: revealed=False plus a 'reveal' marker (an ISO
    week for a protein, a period label for a collection) so the page teases without naming.
    """
    anchor = queue.get("anchor_date", "2026-07-06")
    feats = []
    if kind == "collection":
        idx = _specimen_index(queue)
        for spec in group.get("specimens", []):
            slug = spec.get("slug") or research.slugify(spec["protein"])
            number, indexed = idx.get(slug, (None, None))
            revealed = number is not None and research._is_drafted(number, indexed or spec)
            feats.append({
                "name": spec["protein"],
                "href": render.issue_href(number, slug) if revealed else "",
                "revealed": revealed,
                "reveal": "" if revealed else _reveal_iso(number, anchor),
            })
    else:
        announced = render.announced_ids()
        first_num: dict[str, int] = {}
        for number, _spec, coll, _seas in research.iter_specimens(queue):
            cid = coll.get("id", "")
            if cid and cid not in first_num:
                first_num[cid] = number
        for coll in group.get("collections", []):
            cid = coll.get("id", "")
            revealed = bool(cid and cid in announced)
            feats.append({
                "name": coll["label"],
                "note": coll.get("blurb", ""),
                "href": render.announce_href(cid) if revealed else "",
                "revealed": revealed,
                "reveal": "" if revealed else coll.get("month", ""),
            })
    return feats


def draft(client: anthropic.Anthropic, kind: str, label: str, blurb: str, axis: str, lines: list[str], sealed_count: int = 0) -> DraftAnnouncement:
    what = "monthly collection" if kind == "collection" else "quarterly season"
    listing = "\n".join(f"- {x}" for x in lines)
    seal_note = ""
    if kind == "collection":
        seal_note = (
            f"\n\nThose are the proteins revealed so far. {sealed_count} more are still sealed and "
            "will be revealed one per week; do NOT name or guess them. Write about the theme, not a roll call."
        )
    user = (
        f"Write the opening announcement for the {what} titled '{label}'.\n"
        f"Its one-line theme: {blurb}\n"
        f"What connects them: {axis}.\n\n"
        + ("Revealed so far:\n" if kind == "collection"
           else "The monthly collections in this season, in order:\n")
        + listing
        + seal_note
        + "\n\nReturn a heading, a one-sentence dek, and two or three short paragraphs."
        + (f"\nAlso return feature_notes: one short note (at most 90 characters) for each of "
           f"the {len(lines)} revealed proteins above, in the same order." if kind == "collection" else "")
    )
    resp = client.messages.parse(
        model=WRITER_MODEL,
        max_tokens=2000,
        system=[{"type": "text", "text": ANNOUNCE_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": user}],
        output_format=DraftAnnouncement,
    )
    return resp.parsed_output


def main() -> int:
    ap = argparse.ArgumentParser(description="Draft a monthly or quarterly POTW kickoff announcement.")
    ap.add_argument("--period", help="Calendar id: a month (e.g. 2026-07) or a quarter (e.g. 2026-q3).")
    ap.add_argument("--list", action="store_true", help="List calendar periods and whether each is drafted.")
    args = ap.parse_args()

    queue = research.load_queue()

    if args.list:
        for season in queue.get("seasons", []):
            mark = "x" if (ANNOUNCE_DIR / f"{season['id']}.json").exists() else " "
            print(f"[{mark}] {season['id']:<8} season  {season['label']}")
            for coll in season.get("collections", []):
                m2 = "x" if (ANNOUNCE_DIR / f"{coll['id']}.json").exists() else " "
                print(f"    [{m2}] {coll['id']:<8} month   {coll['label']}")
        return 0

    if not args.period:
        print("Pass --period <id> or --list.", file=sys.stderr)
        return 1

    kind, group, season_ref = locate(queue, args.period)
    if not kind:
        print(f"Period not found in the calendar: {args.period}", file=sys.stderr)
        return 1

    label = group["label"]
    blurb = group.get("blurb", "")
    axis = group.get("axis", "")
    features = build_features(kind, group, queue)
    if kind == "collection":
        lines = [f["name"] for f in features if f.get("revealed")] or ["(none revealed yet)"]
        sealed_count = sum(1 for f in features if not f.get("revealed"))
    else:
        lines = [f'{f["name"]}: {f.get("note", "")}' for f in features]
        sealed_count = 0

    client = anthropic.Anthropic()
    print(f"Drafting {kind} kickoff: {label} ...", file=sys.stderr)
    drafted = draft(client, kind, label, blurb, axis, lines, sealed_count)

    notes = list(drafted.feature_notes) if kind == "collection" else []
    feats_out = []
    ni = 0
    for f in features:
        note = f.get("note", "")
        if kind == "collection":
            note = notes[ni] if (f.get("revealed") and ni < len(notes)) else ""
            if f.get("revealed"):
                ni += 1
        feats_out.append(AnnouncementFeature(
            name=f["name"], note=note, href=f.get("href", ""),
            revealed=f.get("revealed", True), reveal=f.get("reveal", ""),
        ))

    parent = None
    if kind == "collection" and season_ref:
        parent = ThemeRef(
            id=season_ref.get("id", ""),
            label=season_ref["label"],
            blurb=season_ref.get("blurb", ""),
            period=season_ref.get("quarter", ""),
        )
    period_display = group.get("month") if kind == "collection" else group.get("quarter")

    today = dt.date.today()
    ann = Announcement(
        **drafted.model_dump(),
        kind=kind,
        period_id=args.period,
        period=period_display or "",
        label=label,
        blurb=blurb,
        axis=axis,
        parent=parent,
        features=feats_out,
        date_iso=today.isoformat(),
        date_display=today.strftime("%-d %B %Y") if os.name != "nt" else today.strftime("%#d %B %Y"),
    )

    ANNOUNCE_DIR.mkdir(parents=True, exist_ok=True)
    out = ANNOUNCE_DIR / f"{args.period}.json"
    out.write_text(json.dumps(ann.model_dump(), indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {out.relative_to(HERE.parent.parent)}", file=sys.stderr)
    print(f"Render: mamba run -n phyla-site python scripts/potw/render.py --announcement {args.period}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
