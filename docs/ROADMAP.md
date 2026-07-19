# Roadmap -- Protein of the Week: reveals, launch scheduling & hosting

Status: decision record + plan. Nothing here changes the current deploy; it captures how we
run the weekly reveals, how we set/shift the launch date, and how (and whether) to move off a
purely static host without painting ourselves into a vendor corner.

---

## 1. How the weekly reveal actually works today

A protein becomes public when its issue is **authored** -- an issue JSON is committed under
`scripts/potw/issues/` (or a specimen is marked `status: "published"`). The `anchor_date`
schedule (below) drives the *teaser* dates ("opens Mon 14 Sep") and the reveal modal, not the
reveal itself. The site is static and Cloudflare rebuilds on every push, so:

> **Author issue N → commit → Cloudflare rebuilds → week N is live.**

That means the weekly cadence is **already handled by commit-triggered rebuilds**. There is no
hosting gap for the common "write it the week it goes out" workflow, and **no dynamic host is
required** for it.

The only workflow that needs more is **authoring ahead** -- committing several future issues at
once but keeping each sealed until its Monday. Two ways to get that, cheapest first:

1. **Build-time date gate + weekly rebuild (recommended).** Teach the renderer to treat an issue
   as revealed only when *authored AND its reveal date has arrived*, then run a weekly
   GitHub Actions cron that re-renders and commits (mirroring the existing
   `refresh-impact-data.yml`). Each Monday the rebuild flips the next issue public. Free; static.
2. **Edge gate.** A Cloudflare Worker (we are already on Workers) decides at request time whether
   week N is visible. Instant, timezone-exact, still ~free -- but more moving parts.

> Embargo constraint either way: never ship an unrevealed protein's **name** to the browser.
> Client-side JS may advance dates/teasers, but names only enter the bundle when authored+built.
> (See the POTW embargo invariant.)

**Recommendation:** stay static on Cloudflare. Adopt #1 (date gate + weekly cron) when we want to
batch-author ahead. Reach for a real dynamic backend only when a feature actually needs one
(the Topicpile field-guide atlas, submissions/accounts) -- not for reveals.

---

## 2. Launch date & runway (implemented in this PR)

`anchor_date` in `scripts/potw/proteins.json` is the **single launch knob**: week 1's Monday.
Every reveal/teaser date is `anchor_date + 7×(week − 1)` days.

- **Shift the whole schedule permanently:**
  `python scripts/potw/render.py --set-anchor YYYY-MM-DD`
  Validates that the date is a Monday, rewrites `anchor_date` (minimal-diff), syncs the
  hand-authored week-1 issue's own date, and regenerates the catalogue, field guide,
  announcements, and archives.
- **Preview a shifted calendar for one build (no file change):**
  `POTW_ANCHOR=YYYY-MM-DD python scripts/potw/render.py --catalogue --preview`

**Runway:** the scheduled catalogue holds **96 specimens = 96 weeks (~1.8 years)**. From a
1 Jul 2026 anchor the last reveal lands ~May 2028; a different launch date shifts that window
whole. A further **24 specimens across 2 bench seasons** sit as unscheduled swap inventory. So
once launched, the series runs its full outlined catalogue with no content gap, and there is
slack to extend or substitute.

**When we pick a launch date:** run `--set-anchor <that Monday>`, commit, and merge. Until then
the anchor is a placeholder and the POTW section lives only on this PR (not on `main`), so
nothing is public yet.

---

## 3. Hosting cost comparison

At our traffic (a marketing site + a weekly blog), **static hosting is effectively free on every
provider**, and a dynamic layer is also ~free *if* it scales to zero. The trap is always-on VMs,
which put a monthly floor under a workload that is idle most of the time. Figures are ballpark;
verify at signup.

| Provider | Static | Dynamic option | Practical floor | Notes |
|---|---|---|---|---|
| **Cloudflare** (current) | Free, **unlimited** asset bandwidth | Workers (free 100k req/day; Paid $5/mo → 10M req) | **$0**, or $5/mo if we exceed free Workers | Already deployed; `wrangler.jsonc` is IaC-lite; scale-to-zero |
| **Render** | Free static sites | Web service from **$7/mo** (512 MB, always-on) | ~$7/mo per service | Simple; no scale-to-zero on the cheap tier; Postgres +$6/mo |
| **Fly.io** | (no static tier -- it runs VMs/containers) | Small always-on VM **<$2/mo**, pay-as-you-go | ~$2–10/mo | No free tier (trial only); great for containers/multi-region |
| **AWS** | S3 + CloudFront ≈ pennies (1 TB/mo CloudFront free tier) | CloudFront Functions / Lambda@Edge ≈ free at this scale | ~$0–1/mo | Most control + most complexity; easy to sprawl |
| **GCP** | Cloud Storage + CDN ≈ pennies (or Firebase Hosting free tier) | Cloud Run, **scale-to-zero** (2M req/mo free) | ~$0 idle | Cleanest container-to-serverless story |

**Verdict:** there is no cost reason to leave Cloudflare. If we add a backend, keep it
scale-to-zero (Cloudflare Workers/Containers, Cloud Run, or CloudFront Functions) rather than an
always-on Render/Fly VM.

Sources: [Cloudflare Workers/Pages pricing](https://developers.cloudflare.com/workers/platform/pricing/),
[Render pricing](https://render.com/pricing), [Fly.io pricing](https://fly.io/docs/about/pricing/).

---

## 4. Avoiding vendor lock-in (IaC)

We already have **IaC-lite**: `wrangler.jsonc` declares the Cloudflare deployment and the GitHub
Actions workflows describe CI/cron -- all in git, all reproducible. That is enough for a static
site; a full multi-cloud Terraform estate now would be overhead with no payoff.

The real portability lever is the **application boundary, not the IaC tool**:

- Content lives in **git** and builds via **`pixi run` tasks** -- portable to any host.
- **DNS at a registrar we control** (the domain is not locked to one host) so we can repoint in
  minutes.
- Any future backend ships as a **container (Dockerfile)** behind a thin, standard interface
  (HTTP; S3-compatible storage). A container runs unchanged on Cloudflare Containers, Cloud Run,
  Fly, Render, or ECS -- that is what actually prevents lock-in.

**IaC tool: OpenTofu** (decided). It is the open-source, Apache-2.0 fork of Terraform, so we avoid
HashiCorp's BSL licensing lock-in while keeping the whole Terraform provider ecosystem (Cloudflare,
AWS, GCP, Fly, and the DNS registrar). Plan when we adopt it: one small per-provider module, remote
state in an S3-compatible bucket (Cloudflare R2), imported from the Worker and DNS that already
exist. We bring it in alongside the *first real backend* (the Topicpile jobs, a database, queues),
not before: one tool, open license, no Pulumi/Terraform split to maintain.

---

## 5. Going private

The GitHub repo can be made **private today with no hosting change**. Cloudflare Workers Builds
deploys from private repos on the **free** plan (the Cloudflare GitHub app just needs read access),
so previews and production keep working. This is also the reason to stay on Cloudflare rather than
GitHub Pages: Pages only serves a private repo on a paid plan. Private is the right default anyway,
so unreleased Protein of the Week issues and future hiring PRs are not world-readable.

---

## 6. Recommended sequence

1. **Now:** stay on Cloudflare (free). Keep authoring issues week-by-week; commit → auto-deploy.
   Set the real launch date with `--set-anchor` once decided, then merge the POTW PR.
2. **When batch-authoring ahead:** add the build-time date gate + a weekly rebuild cron
   (copy of `refresh-impact-data.yml`) so future-dated issues reveal on their Monday automatically.
3. **When a backend is needed** (Topicpile atlas, accounts, submissions): build it as a container,
   deploy to a scale-to-zero runtime, and describe it with OpenTofu. The container + DNS-we-control
   boundary keeps any later migration a low-drama move.
