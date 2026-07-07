# Serving Protein of the Week at potw.phylatech.com

Today, Protein of the Week lives on the main site:

- Canonical: `https://phylatech.com/protein-of-the-week`
- Short alias: `https://phylatech.com/potw` (a redirect, `potw.html`)

That works now, with no extra infrastructure. A **subdomain** (`potw.phylatech.com`)
needs a hosting change, because GitHub Pages serves exactly one custom domain per
repository, and this repo's is `phylatech.com` (see `CNAME`). Anthropic/Claude
cannot edit your DNS or GitHub settings, so the last step is yours. Two clean paths:

## Option A (recommended): DNS redirect to the path

Keep everything in this one repo and point the subdomain at the existing page.

1. **DNS**: add a `CNAME` record `potw.phylatech.com` at your DNS provider.
2. **Redirect**: most providers (Cloudflare, Netlify DNS, Porkbun, etc.) offer a
   "redirect / URL forward" rule. Forward `potw.phylatech.com/*` to
   `https://phylatech.com/protein-of-the-week` (301). On Cloudflare this is a
   single Redirect Rule; no second deployment.

Result: `potw.phylatech.com` lands on the current page. One repo, one source of
truth, nothing to keep in sync.

## Option B: a second GitHub Pages site

Serve the subdomain as its own Pages site if you want it fully independent.

1. Create a second repo (e.g. `phylatech/potw`) whose Pages output is the POTW
   pages (`protein-of-the-week.html` as its `index.html`, plus `styles.css`,
   `favicon.svg`, and the generated `potw-*.html`).
2. Add a `CNAME` file containing `potw.phylatech.com` to that repo.
3. In its **Settings → Pages**, set the custom domain to `potw.phylatech.com`;
   GitHub will prompt you to add the DNS `CNAME` record and will provision TLS.
4. Point the POTW harness (or a small publish step) at that repo.

This gives a true standalone site but means keeping assets in two places. Prefer
Option A unless you specifically want POTW deployed separately.

## What I can do vs what needs you

- Done in-repo: canonical page, `/potw` alias, the render pipeline, and this guide.
- Needs your access: the DNS record and (Option B) the second repo + Pages setting.

Tell me which option you want and I'll prepare whatever the repo side needs (the
redirect target is already live for Option A; for Option B I can assemble the
standalone site directory and its `CNAME`).
