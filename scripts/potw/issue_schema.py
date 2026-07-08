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


class Issue(DraftIssue):
    """A full issue: draft content plus harness-assigned metadata."""

    number: int
    slug: str
    date_iso: str
    date_display: str
    byline: str = "Researched and written by the Phyla Protein Historian, a weekly dispatch on the molecules that quietly run the living world."
