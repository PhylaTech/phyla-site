#!/usr/bin/env python3
"""Protein of the Week: research + drafting harness.

Fans out one research sub-agent per "beat" of the story (discovery, the people,
the techniques, the applications, the contemporaneous events), each with the
web-search server tool, then hands all five dossiers to a writer sub-agent that
synthesizes them into a structured issue via structured outputs.

Output: scripts/potw/issues/<NNN>-<slug>.json (validated against Issue). Render
it to HTML with render.py.

Usage (inside the project mamba env):

    mamba run -n phyla-site python scripts/potw/research.py               # next queued protein
    mamba run -n phyla-site python scripts/potw/research.py --protein "Insulin" --slug insulin
    mamba run -n phyla-site python scripts/potw/research.py --list        # show the queue

Requires ANTHROPIC_API_KEY in the environment (or an `ant auth login` profile).
Model defaults to claude-opus-4-8; override with POTW_MODEL / POTW_RESEARCH_MODEL
/ POTW_WRITER_MODEL (see README for the cost tradeoff).
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).resolve().parent))
from issue_schema import DraftIssue, Issue, ThemeRef  # noqa: E402

HERE = Path(__file__).resolve().parent
ISSUES_DIR = HERE / "issues"
QUEUE_PATH = HERE / "proteins.json"

# Default to the most capable model. Override per-role for cost (see README).
DEFAULT_MODEL = os.environ.get("POTW_MODEL", "claude-opus-4-8")
RESEARCH_MODEL = os.environ.get("POTW_RESEARCH_MODEL", DEFAULT_MODEL)
WRITER_MODEL = os.environ.get("POTW_WRITER_MODEL", DEFAULT_MODEL)

WEB_SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search", "max_uses": 6}

# One research sub-agent per beat. Each is blind to the others.
BEATS = [
    {
        "key": "discovery",
        "title": "Discovery & history",
        "focus": "When, where, and how the protein was first found or characterized. The origin organism or source. The sequence of events from first observation to being understood as a distinct protein. Dates, places, and the people present at the discovery.",
    },
    {
        "key": "people",
        "title": "The people & institutions",
        "focus": "The scientists, labs, companies, and institutions behind the protein across its history: who cloned it, who engineered it, who commercialized it. Any Nobel Prizes or major recognition, with years. Human stories and turning points.",
    },
    {
        "key": "techniques",
        "title": "Techniques & mechanism",
        "focus": "How the protein works at a mechanistic level, and the laboratory techniques required to discover, isolate, produce, or use it (e.g. crystallography, cloning, fermentation, assays). What makes it structurally or chemically distinctive.",
    },
    {
        "key": "applications",
        "title": "Applications & industries",
        "focus": "Where the protein is used today: research uses, clinical or diagnostic uses, and the industries it underpins. Concrete examples of what it made possible that was impossible before. Its economic or scientific footprint.",
    },
    {
        "key": "meanwhile",
        "title": "Contemporaneous events",
        "focus": "Notable world events (science, politics, culture) happening in the same year or era as the protein's key discovery, to place the science in its historical moment. Give specific years and events.",
    },
]

RESEARCH_SYSTEM = (
    "You are the Phyla Protein Historian's research desk: a rigorous scientific "
    "historian assembling sourced facts about a single protein for a weekly column. "
    "Use the web_search tool to find accurate, verifiable details. Prefer primary and "
    "authoritative sources (peer-reviewed papers, Nobel records, university and museum "
    "histories) over blogs. Return a dense, factual dossier: names, dates, places, "
    "institutions, and numbers, each as a short bulletted claim. Flag anything uncertain "
    "or contested rather than guessing. Do not write prose for publication; this is raw "
    "material for a writer. Never use em dashes."
)

WRITER_SYSTEM = (
    "You are the Phyla Protein Historian, writing one issue of a weekly column for "
    "Phyla Technologies, a natural-products-rooted ML consultancy for biotech. Voice: "
    "a contemporary natural-history press. Rigorous, warm, quietly confident. You tell "
    "the story of one protein: its discovery, the people behind it, the techniques it "
    "took, where it ended up, and the world at the time.\n\n"
    "Hard rules:\n"
    "- Never use em dashes. Use commas, colons, semicolons, periods, or parentheses.\n"
    "- Sentence-case headlines, not title case.\n"
    "- Every claim must be grounded in the supplied dossiers. Do not invent facts, "
    "dates, names, or quotations. If the dossiers disagree or are silent, stay general "
    "rather than fabricating specifics.\n"
    "- Prefer concrete specifics (a person, a place, a year, a number) over adjectives.\n"
    "- Where the protein connects to natural products, pharmacognosy, or the living "
    "world, draw the thread; never force it.\n\n"
    "Structure: exactly four fact cells; four or five movements (cover discovery, the "
    "people, the techniques, and where it went, plus a final 'meanwhile' framing); one "
    "pull quote that earns its place; a meanwhile heading naming the era; three or four "
    "meanwhile events; and a story timeline of six to nine chronological milestones in the "
    "protein's own history (earliest first), each with a year, a short title, and one "
    "sentence of context, spanning as many years or decades as the story needs. The "
    "timeline is the protein's own arc (discovery, cloning, engineering, recognition, "
    "impact), drawn strictly from the dossiers, and is distinct from the meanwhile world "
    "events. Give it a heading that names the arc. Keep paragraphs tight."
)


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic()


def _text_of(message) -> str:
    return "\n".join(b.text for b in message.content if getattr(b, "type", None) == "text").strip()


def research_beat(client: anthropic.Anthropic, protein: str, hint: str, beat: dict) -> str:
    """Run one research sub-agent (web-search agentic loop) and return its dossier text."""
    user = (
        f"Protein: {protein}\n"
        f"{('Seed context: ' + hint) if hint else ''}\n\n"
        f"Research beat: {beat['title']}.\n{beat['focus']}\n\n"
        "Search the web as needed, then return the dossier of sourced facts for this beat only."
    )
    messages = [{"role": "user", "content": user}]
    system = [{"type": "text", "text": RESEARCH_SYSTEM, "cache_control": {"type": "ephemeral"}}]

    # Server-tool agentic loop: the API runs web searches server-side; on pause_turn we resume.
    for _ in range(8):
        resp = client.messages.create(
            model=RESEARCH_MODEL,
            max_tokens=6000,
            system=system,
            thinking={"type": "adaptive"},
            tools=[WEB_SEARCH_TOOL],
            messages=messages,
        )
        if resp.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": resp.content})
            continue
        return _text_of(resp)
    return _text_of(resp)


def synthesize(client: anthropic.Anthropic, protein: str, dossiers: dict[str, str], theme: str = "") -> DraftIssue:
    """Writer sub-agent: fold the dossiers into a structured issue."""
    dossier_block = "\n\n".join(
        f"=== {beat['title']} ===\n{dossiers.get(beat['key'], '(no material)')}" for beat in BEATS
    )
    user = (
        f"Write this week's Protein of the Week issue on: {protein}.\n\n"
        + (theme + "\n\n" if theme else "")
        + "Base every fact strictly on the research dossiers below. Do not add facts that "
        "are not supported by them.\n\n"
        f"{dossier_block}"
    )
    resp = client.messages.parse(
        model=WRITER_MODEL,
        max_tokens=8000,
        system=[{"type": "text", "text": WRITER_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": user}],
        output_format=DraftIssue,
    )
    return resp.parsed_output


def load_queue() -> dict:
    return json.loads(QUEUE_PATH.read_text())


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def iter_specimens(queue: dict):
    """Yield (number, specimen, collection, season) for every specimen in calendar order.

    The week number is the specimen's 1-based position in the flattened calendar.
    """
    number = 0
    for season in queue.get("seasons", []):
        for collection in season.get("collections", []):
            for specimen in collection.get("specimens", []):
                number += 1
                yield number, specimen, collection, season


def _issue_path(number: int, slug: str) -> Path:
    return ISSUES_DIR / f"{number:03d}-{slug}.json"


def _is_drafted(number: int, specimen: dict) -> bool:
    slug = specimen.get("slug") or slugify(specimen["protein"])
    return specimen.get("status") == "published" or _issue_path(number, slug).exists()


def next_specimen(queue: dict):
    """First specimen not yet drafted, with its collection and season; None if the calendar is done."""
    for number, specimen, collection, season in iter_specimens(queue):
        if not _is_drafted(number, specimen):
            return number, specimen, collection, season
    return None


def _next_off_queue_number() -> int:
    """Number for an off-calendar --protein run: one past the highest existing issue."""
    nums = []
    for p in ISSUES_DIR.glob("*.json"):
        m = re.match(r"(\d+)-", p.name)
        if m:
            nums.append(int(m.group(1)))
    return (max(nums) + 1) if nums else 1


def theme_context(collection: dict | None, season: dict | None) -> str:
    """A short editorial-context note for the writer; empty for off-calendar issues."""
    if not collection and not season:
        return ""
    parts = []
    if season:
        parts.append(f"the quarterly season '{season['label']}' ({season.get('blurb', '')})")
    if collection:
        parts.append(f"the monthly collection '{collection['label']}' ({collection.get('blurb', '')})")
    return (
        "Editorial context: this protein was chosen as part of a themed run, "
        + " within ".join(reversed(parts))
        + ". You may let this lightly shape emphasis or a passing aside, but do not force the "
        "connection and do not invent facts to fit it."
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Research and draft a Protein of the Week issue.")
    ap.add_argument("--protein", help="Protein display name (default: next in proteins.json).")
    ap.add_argument("--slug", help="URL slug (default: derived from the name or the queue).")
    ap.add_argument("--hint", default="", help="Optional seed context for the researchers.")
    ap.add_argument("--list", action="store_true", help="Print the upcoming queue and exit.")
    args = ap.parse_args()

    queue = load_queue()
    if args.list:
        current_season = None
        for number, specimen, collection, season in iter_specimens(queue):
            if season["label"] != current_season:
                current_season = season["label"]
                print(f"\n=== {season['quarter']}  {season['label']} ===")
            mark = "x" if _is_drafted(number, specimen) else " "
            print(f"  [{mark}] {number:>2}. {specimen['protein']}  ({collection['label']})")
        return 0

    collection = season = None
    if args.protein:
        protein = args.protein
        slug = args.slug or slugify(args.protein)
        hint = args.hint
        number = _next_off_queue_number()
    else:
        selected = next_specimen(queue)
        if not selected:
            print("The calendar is fully drafted. Add specimens to proteins.json or pass --protein.", file=sys.stderr)
            return 1
        number, specimen, coll, seas = selected
        protein = specimen["protein"]
        slug = args.slug or specimen.get("slug") or slugify(protein)
        hint = args.hint or specimen.get("hint", "")
        collection = {"id": coll.get("id", ""), "label": coll["label"], "blurb": coll.get("blurb", ""), "period": coll.get("month", "")}
        season = {"id": seas.get("id", ""), "label": seas["label"], "blurb": seas.get("blurb", ""), "period": seas.get("quarter", "")}

    today = dt.date.today()
    print(f"Researching No. {number:03d}: {protein} ...", file=sys.stderr)

    client = _client()

    # Fan out the research sub-agents in parallel.
    dossiers: dict[str, str] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(BEATS)) as pool:
        futures = {pool.submit(research_beat, client, protein, hint, b): b for b in BEATS}
        for fut in concurrent.futures.as_completed(futures):
            beat = futures[fut]
            try:
                dossiers[beat["key"]] = fut.result()
                print(f"  dossier ready: {beat['title']}", file=sys.stderr)
            except Exception as exc:  # keep going; the writer tolerates a missing beat
                dossiers[beat["key"]] = ""
                print(f"  beat failed ({beat['title']}): {exc}", file=sys.stderr)

    print("Synthesizing the issue ...", file=sys.stderr)
    draft = synthesize(client, protein, dossiers, theme_context(collection, season))

    issue = Issue(
        **draft.model_dump(),
        number=number,
        slug=slug,
        date_iso=today.isoformat(),
        date_display=today.strftime("%-d %B %Y") if os.name != "nt" else today.strftime("%#d %B %Y"),
        collection=ThemeRef(**collection) if collection else None,
        season=ThemeRef(**season) if season else None,
    )

    ISSUES_DIR.mkdir(parents=True, exist_ok=True)
    out = ISSUES_DIR / f"{number:03d}-{slug}.json"
    out.write_text(json.dumps(issue.model_dump(), indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {out.relative_to(HERE.parent.parent)}", file=sys.stderr)
    print(f"Next: mamba run -n phyla-site python scripts/potw/render.py {out.name}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
