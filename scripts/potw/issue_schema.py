"""Shared schema for a Protein of the Week issue.

The research/drafting harness (research.py) produces a DraftIssue via structured
outputs; the harness then stamps it with metadata (number, slug, dates, byline)
to make a full Issue. render.py turns an Issue JSON file into an HTML page.

Keeping the schema in one place means the writer model, the renderer, and any
future tooling all agree on the shape of an issue.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Fact(BaseModel):
    """One cell in the fact strip below the issue title."""

    value: str = Field(description="Short value, e.g. '1962' or 'A. victoria' or '11'.")
    label: str = Field(description="Small caps label, e.g. 'First isolated'.")


class Movement(BaseModel):
    """One section ('movement') of the article body."""

    kicker: str = Field(description="Short section label, e.g. 'The discovery'.")
    heading: str = Field(description="Sentence-case headline for the section.")
    paragraphs: list[str] = Field(description="One or more prose paragraphs. No em dashes.")


class Meanwhile(BaseModel):
    """One row in the 'meanwhile' contemporaneous-events timeline."""

    when: str = Field(description="Short time marker, e.g. 'Feb' or '1962'.")
    what: str = Field(description="One sentence on a contemporaneous world event.")


class Milestone(BaseModel):
    """One entry in the protein's own story timeline: a chronology across the years."""

    year: str = Field(description="Year or short range, e.g. '1962' or '1992-1994'. Years only; keep it terse.")
    title: str = Field(description="Short sentence-case headline for the event, no trailing period, e.g. 'Shimomura isolates GFP at Friday Harbor'.")
    detail: str = Field(description="One sentence of context for the event. No em dashes.")


class Reference(BaseModel):
    """One source in the references list, cited inline as [n] by its 1-based position."""

    title: str = Field(description="Article, paper, or page title.")
    source: str = Field(default="", description="Journal, publisher, or site, with year, e.g. 'Science, 1994' or 'NobelPrize.org'.")
    url: str = Field(default="", description="Stable link. Prefer a DOI (https://doi.org/...); otherwise a canonical URL.")


class DraftIssue(BaseModel):
    """The content fields the writer model produces (no metadata)."""

    protein: str = Field(description="Display name of the protein, e.g. 'Green Fluorescent Protein'.")
    binomial: str = Field(description="Source line, e.g. 'from Aequorea victoria, the crystal jelly'.")
    dek: str = Field(description="One-sentence standfirst under the title.")
    facts: list[Fact] = Field(description="Exactly four fact cells.")
    movements: list[Movement] = Field(description="Four or five article movements: discovery, the people, the techniques, where it went, and meanwhile.")
    pull_quote: str = Field(description="One memorable sentence used as a pull quote.")
    meanwhile_heading: str = Field(description="Heading for the meanwhile section, e.g. 'The world in 1962.'")
    meanwhile: list[Meanwhile] = Field(description="Three or four contemporaneous events from the discovery era.")
    timeline_heading: str = Field(description="Heading for the story-timeline section, e.g. 'From a jellyfish to a Nobel Prize.'")
    timeline: list[Milestone] = Field(description="Six to nine chronological milestones in the protein's own history, earliest first, from first observation to modern impact. May span many years or decades. Distinct from 'meanwhile': these are the protein's own notable events, not world events.")
    references: list[Reference] = Field(default_factory=list, description="Sources for the load-bearing claims, in citation order. Cite them inline in prose and timeline details with bracketed numbers like [1], [2], matching each reference's 1-based position in this list.")
    pdb_id: str = Field(default="", description="One representative RCSB PDB id for the protein's 3D structure, e.g. '1EMA'. Leave empty for a family or concept with no single canonical structure, or if unsure it is correct.")
    pdb_note: str = Field(default="", description="Short caption for the structure, e.g. 'The GFP beta-barrel (S65T mutant), solved by Ormo et al., 1996.' Empty when pdb_id is empty.")


class ThemeRef(BaseModel):
    """A collection (month) or season (quarter) an issue belongs to."""

    id: str = Field(default="", description="Calendar id, e.g. '2026-07' (month) or '2026-q3' (quarter); links to its kickoff page.")
    label: str = Field(description="Display name, e.g. 'Seeing' or 'The Instruments'.")
    blurb: str = Field(default="", description="One-line, reader-facing description of the grouping.")
    period: str = Field(default="", description="Calendar period, e.g. 'July 2026' (month) or 'Q3 2026' (quarter).")


class Issue(DraftIssue):
    """A full issue: draft content plus harness-assigned metadata."""

    number: int
    slug: str
    date_iso: str
    date_display: str
    byline: str = "Researched and written by the Phyla Protein Historian, a weekly dispatch on the molecules that quietly run the living world."
    # Editorial placement in the calendar. Optional: an off-queue (--protein) issue has none.
    collection: ThemeRef | None = None
    season: ThemeRef | None = None


class AnnouncementFeature(BaseModel):
    """One item listed in a kickoff: a protein (month) or a collection (season)."""

    name: str = Field(description="Protein or collection name.")
    note: str = Field(default="", description="One-line description.")
    href: str = Field(default="", description="Optional link to the issue page or child kickoff.")
    revealed: bool = Field(default=True, description="False = a sealed teaser: the page shows the schedule, not the name.")
    reveal: str = Field(default="", description="When it opens: an ISO date (a week) or a period label (a month), shown on sealed teasers.")


class DraftAnnouncement(BaseModel):
    """The copy an announcement writer produces (no metadata)."""

    heading: str = Field(description="Compelling, sentence-case headline for the kickoff.")
    dek: str = Field(description="One-sentence standfirst under the heading.")
    paragraphs: list[str] = Field(description="Two or three short paragraphs introducing the theme and why these belong together. No em dashes.")
    feature_notes: list[str] = Field(default_factory=list, description="One short note (<= 90 chars) per featured item, in the given order. No em dashes. Optional.")


class Announcement(DraftAnnouncement):
    """A month or season kickoff: draft copy plus calendar metadata."""

    kind: str  # "collection" (month) or "season" (quarter)
    period_id: str  # e.g. "2026-07" or "2026-q3"
    period: str  # e.g. "July 2026" or "Q3 2026"
    label: str  # e.g. "Seeing" or "The Instruments"
    blurb: str = ""
    axis: str = ""
    parent: ThemeRef | None = None  # the season a collection sits in
    features: list[AnnouncementFeature] = []
    date_iso: str = ""
    date_display: str = ""
