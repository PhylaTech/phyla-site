# Phyla Technologies
Landing page and impact page for [phylatech.com](https://phylatech.com).

## Development

This repo uses [pixi](https://pixi.sh) to manage its Python toolchain and common tasks. Install pixi once, then run any task with `pixi run <task>` (the environment is created automatically on first run; `pixi task list` shows everything).

| Task | Command | What it does |
|------|---------|--------------|
| Fetch impact data | `pixi run fetch-impact` | Query OpenAlex and write `data/impact-data.json` |
| Serve locally | `pixi run serve` | Static preview at http://localhost:4173 |
| One SVG → PNG | `pixi run svg2png <file.svg> [-d dpi]` | Convert a single SVG (args pass through) |
| All brand SVGs → PNG | `pixi run assets-png` | Render the logos + favicon into `build/png/` |
| Clean | `pixi run clean` | Remove `build/` |

## Impact Page — Citation Data

The [Impact & Influence](https://phylatech.com/impact.html) page visualizes real citation data from [OpenAlex](https://openalex.org). The data pipeline fetches publications, citing works, institution coordinates, and disciplinary influence for each researcher.

### How it works

```
scripts/researchers.json    ← researcher config (ORCIDs + verified work IDs)
        ↓
scripts/fetch_impact_data.py  ← queries OpenAlex API
        ↓
data/impact-data.json       ← generated output consumed by impact.html
```

### Refreshing the data

```bash
pixi run fetch-impact
```

This re-queries OpenAlex for the latest citation counts, citing institutions, geographic reach, and discipline data. Takes ~5 minutes due to API pagination. No dependencies beyond Python 3 standard library.

### Automated daily refresh

A GitHub Actions workflow (`.github/workflows/refresh-impact-data.yml`) runs the data pipeline daily at ~6:07 AM UTC. If citation counts or new citing works have changed, it auto-commits the updated `data/impact-data.json`.

- **Schedule:** Daily cron
- **Manual trigger:** Go to Actions > "Refresh Impact Data" > Run workflow
- **No-op on no changes:** If the data hasn't changed, no commit is created

The impact page footer displays "Citation data updated [date]" based on the `generated_at` timestamp in the JSON, so visitors can see how fresh the data is.

### Adding a new researcher

1. Find their [ORCID](https://orcid.org) (e.g., `0000-0001-5084-9035`)

2. Find their OpenAlex work IDs. Search by ORCID on the [OpenAlex API](https://api.openalex.org/works?filter=author.orcid:0000-0001-5084-9035) and note the `id` field (e.g., `W2949629831`) for each real publication. This step is important because OpenAlex often conflates authors with common names — you need to verify which works actually belong to the researcher.

3. Add an entry to `scripts/researchers.json`:

```json
{
  "name": "New Researcher",
  "orcid": "0000-0000-0000-0000",
  "include_work_ids": [
    "W1234567890",
    "W0987654321"
  ]
}
```

4. Run the script and commit the updated data:

```bash
python3 scripts/fetch_impact_data.py
git add data/impact-data.json scripts/researchers.json
git commit -m "Add [name] to impact data"
```

The script deduplicates shared publications across researchers automatically (e.g., co-authored papers).

### Config options

Each researcher entry in `researchers.json` supports:

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Display name |
| `orcid` | Yes | ORCID identifier |
| `include_work_ids` | Recommended | Allowlist of OpenAlex work IDs. If set, only these works are fetched (bypasses conflation). |
| `exclude_work_ids` | Optional | Blocklist of work IDs to skip. Only used when `include_work_ids` is empty (ORCID-based fallback). |

Using `include_work_ids` is strongly recommended. OpenAlex profiles are frequently conflated for common names, and the allowlist ensures only verified publications are included.

---

## SVG to PNG Conversion

The `svg_to_png.py` script converts SVG files to PNG at a specified DPI.

### Dependencies

Requires Python 3 and the following:

```bash
# System library (macOS)
brew install cairo

# Python packages
pip install cairosvg pillow
```

### Usage

```bash
python3 svg_to_png.py input.svg              # 300 DPI (default)
python3 svg_to_png.py input.svg -d 150       # custom DPI
python3 svg_to_png.py input.svg -o out.png   # custom output path
```

