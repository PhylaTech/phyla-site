# Where Protein of the Week lives

**Decision: Option A, a path on the main site.** Protein of the Week is served
from this one repo at:

- **Canonical: `https://phylatech.com/potw`** (the file `potw.html`)
- Descriptive alias: `https://phylatech.com/protein-of-the-week` -> 301s to `/potw`
- Back issues: `https://phylatech.com/potw-<NNN>-<slug>`

No DNS changes, no second repository, one source of truth. This works because
GitHub Pages serves a file `potw.html` at the extensionless path `/potw` (verified
against the live site: `/impact` serves `impact.html`), so the short URL is the real
page, not a redirect.

## How it fits together

- `potw.html` is the current issue (the hand-authored GFP launch page today; the
  render pipeline overwrites it when a newer issue is promoted with `--set-latest`).
- `protein-of-the-week.html` is a tiny `noindex` redirect stub pointing at `/potw`,
  kept so the descriptive URL keeps working for anyone who has it.
- `scripts/potw/render.py` treats `potw.html` as canonical (`CANONICAL`) and links
  issue No. 1 to `/potw` in every archive list. Back issues render to
  `potw-<NNN>-<slug>.html` at the site root.
- The homepage links to it from the primary nav ("Protein of the Week").

Nothing here needs your access. It ships the moment PR #10 (and its base, the POTW
page PR) merge to `main`.

## If you ever want the subdomain instead (`potw.phylatech.com`)

Not required, and not done, because GitHub Pages serves exactly one custom domain
per repository and this repo's is `phylatech.com` (see `CNAME`). If you later want a
true subdomain, two paths, both needing access only you have:

1. **DNS redirect (simplest).** Add a `CNAME` DNS record for `potw.phylatech.com`,
   then a URL-forward rule at your DNS/CDN provider (Cloudflare, Porkbun, etc.)
   sending `potw.phylatech.com/*` to `https://phylatech.com/potw` (301). No second
   deployment; the path above stays the source of truth.
2. **A second GitHub Pages site.** Create a separate repo whose Pages output is the
   POTW files, add a `CNAME` file containing `potw.phylatech.com`, and set that
   custom domain in its Pages settings. Fully independent, but assets live in two
   places and must be kept in sync. Prefer option 1 unless you specifically want
   POTW deployed on its own.

Either way, tell me and I'll prepare whatever the repo side needs.
