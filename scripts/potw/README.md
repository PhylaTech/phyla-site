# Protein of the Week: research + drafting harness

A small multi-agent pipeline that researches one protein and drafts a weekly
issue for [Protein of the Week](../../potw.html), in the site's
house voice.

## How it works

```
proteins.json ──▶ research.py ──▶ issues/<NNN>-<slug>.json ──▶ render.py ──▶ potw-<NNN>-<slug>.html
   (queue)          (subagents,        (structured issue)        (deterministic)   + archive refresh
                     web search)
```

`research.py` fans out **one research sub-agent per beat** of the story, each with
the web-search tool and blind to the others:

1. Discovery & history
2. The people & institutions
3. Techniques & mechanism
4. Applications & industries
5. Contemporaneous events ("meanwhile")

The five run in parallel. A sixth **writer sub-agent** then folds the dossiers into
a structured issue (via structured outputs, validated against
[`issue_schema.py`](issue_schema.py)) in the Naturalist's Press voice: no em
dashes, sentence-case headings, facts grounded in the dossiers.

`render.py` turns an issue JSON into an HTML page and refreshes the archive list
on every POTW page. It is deterministic (no API calls), so it is safe to run in
CI and easy to preview.

Each issue also carries **sources** and, where one exists, a **structure**:

- `references` is a numbered source list. The writer cites them inline in prose and
  timeline details with bracketed markers like `[1]`, which the renderer turns into
  superscript links to a "Sources" section at the foot of the article. Prefer DOI
  links, and verify them in the fact-check before shipping.
- `pdb_id` (plus a short `pdb_note`) embeds an interactive 3D view of the protein.
  The page lazy-loads [3Dmol.js](https://3dmol.org) only when the viewer scrolls into
  view, fetches the structure from the RCSB PDB, and styles it in the house palette;
  on any failure it falls back to a link. Leave `pdb_id` empty for families or
  concepts with no single canonical structure.

## The editorial calendar

`proteins.json` is a three-level calendar, not a flat list:

```
season (quarter)   ─▶   collection (month)   ─▶   specimen (week)
"The Instruments"       "Seeing"                  Green Fluorescent Protein
                                                  Firefly luciferase, ...
```

- **Week** is one protein (one issue). **Month** groups ~4 proteins under a shared
  connection; **quarter** groups three months under a broad domain. Each level carries a
  `label`, a reader-facing `blurb`, and an `axis` naming what ties the group together
  (family, function, provenance, impact, discovery, disease, or any non-obvious link).
- The **week number is position**: `research.py` flattens the calendar in order, so the
  Nth specimen is issue No. N. A specimen counts as done when its
  `issues/<NNN>-<slug>.json` exists (or it is marked `"status": "published"`);
  `research.py` drafts the first one that is not.
- The chosen specimen's month and season are passed to the writer as light editorial
  context and stamped onto the issue, so the rendered page shows a "this month / this
  season" band and the story may gently reflect its collection.

`research.py --list` prints the whole calendar with a mark beside each drafted issue.
Add, reorder, or retheme freely; numbering just follows position.

## Running it

Everything runs in the project's mamba environment (`environment.yml`):

```bash
mamba env create -f environment.yml          # first time
export ANTHROPIC_API_KEY=sk-ant-...          # or use an `ant auth login` profile

# Research + draft the next queued protein (or pass one explicitly)
mamba run -n phyla-site python scripts/potw/research.py
mamba run -n phyla-site python scripts/potw/research.py --protein "Insulin" --slug insulin
mamba run -n phyla-site python scripts/potw/research.py --list      # print the full calendar

# Render it and refresh the archive
mamba run -n phyla-site python scripts/potw/render.py 002-insulin.json
mamba run -n phyla-site python scripts/potw/render.py --all          # re-render issues 2+
```

Issue No. 1 (GFP) is the hand-authored launch page at `potw.html` (served at
`/potw`); `render.py` leaves it alone unless you pass `--set-latest`. Issues 2+ render to
`potw-<NNN>-<slug>.html` at the site root. Every render rewrites the archive list
between the `POTW:ARCHIVE` markers on all POTW pages.

## Monthly and quarterly announcements

At the start of each month and quarter, a short kickoff introduces the theme ("the
proteins this month are all ..."). `announce.py` drafts one with a single writer
sub-agent (no web search: it frames the proteins the weekly issues cover in depth, so
it stays high-level and invents nothing).

```bash
mamba run -n phyla-site python scripts/potw/announce.py --list           # calendar + what is drafted
mamba run -n phyla-site python scripts/potw/announce.py --period 2026-07  # a month (collection)
mamba run -n phyla-site python scripts/potw/announce.py --period 2026-q3  # a quarter (season)

# Render the kickoff page (and refresh the links on every POTW page)
mamba run -n phyla-site python scripts/potw/render.py --announcement 2026-07
```

Output is `announcements/<period-id>.json`, rendered to `potw-<period-id>.html` (e.g.
`potw-2026-07.html`, `potw-2026-q3.html`). Kickoff pages list the proteins (for a month)
or child collections (for a quarter); the issue pages' "this month / this season" band
and the grouped archive link to a kickoff once it is drafted. The launch month (Seeing)
and season (The Instruments) kickoffs are hand-authored, like the GFP issue itself;
`announce.py` drafts the rest. Override the model with `POTW_ANNOUNCE_MODEL`.

## Reveals and the subscribe form

Upcoming proteins are held back: `render.py` only *names* a protein whose issue has
shipped. Unrevealed items render as sealed teasers ("Opens in 5 days", counting down
client-side) that link to the subscribe CTA, so a kickoff never spoils the weeks ahead.
Because the site rebuilds weekly, each protein unlocks on its week automatically. (The
full queue does live in `proteins.json`, so anyone reading the *repo* can see it; hold
future entries out of the committed queue if you need true secrecy.)

The subscribe CTA on every POTW page posts `email` and a `cadence` (`weekly` /
`monthly` / `quarterly`) to the form's `action`. It ships with a placeholder endpoint:

- Point it at your email provider (Buttondown, ConvertKit, Mailchimp, Formspree, all
  accept a simple POST). Replace `https://example.com/REPLACE-WITH-YOUR-EMAIL-ENDPOINT`
  in `render.py`'s `SUBSCRIBE_HTML` and in `potw.html`.
- Map the `cadence` field to lists or tags on the provider side, or drop it.
- Social follow (LinkedIn, X) needs no setup.

Anthropic cannot create the account or endpoint; that step is yours.

## Models and cost

Defaults to `claude-opus-4-8` for both research and writing. Each issue is roughly
six model calls (five with web search, one synthesis), so cost is dominated by the
research beats. To trade some quality for cost, override per role:

```bash
export POTW_RESEARCH_MODEL=claude-sonnet-5   # cheaper research
export POTW_WRITER_MODEL=claude-opus-4-8     # keep the writer sharp
# or POTW_MODEL=claude-sonnet-5 for both
```

Model IDs must be exact (see the API docs). The harness uses adaptive thinking and
the `web_search_20260209` server tool, both of which require Opus 4.6+ / Sonnet 4.6+.

## Editorial oversight

This drafts; it does not publish. The weekly GitHub Action
(`.github/workflows/potw.yml`) runs the pipeline and opens a **pull request** with
the generated issue and rendered page for a human to review, edit, and merge.
Treat every generated issue as a first draft: check the facts against the sources
before it ships. The writer is instructed not to invent specifics, but it is not a
substitute for a fact-check.

## Files

| File | Role |
|---|---|
| `proteins.json` | The editorial calendar: seasons (quarters) to collections (months) to specimens (weeks). See above. |
| `issue_schema.py` | Pydantic schema shared by the writer and the renderer. |
| `research.py` | Multi-subagent research + structured drafting (needs the API). |
| `announce.py` | Drafts a month/quarter kickoff announcement (one sub-agent, needs the API). |
| `render.py` | Issue and announcement JSON to HTML + archive refresh (deterministic, no API). |
| `issues/*.json` | The source record for each issue. |
| `announcements/*.json` | The source record for each month/quarter kickoff. |
