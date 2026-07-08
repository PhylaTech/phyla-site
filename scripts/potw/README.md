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
| `render.py` | Issue JSON to HTML + archive refresh (deterministic, no API). |
| `issues/*.json` | The source record for each issue. |
