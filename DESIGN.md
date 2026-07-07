<!-- SEED: re-run /impeccable document once there's code in the new direction to capture actual tokens and components. -->
---
name: Phyla Technologies
description: MLOps and data infrastructure for life sciences, in the lineage of natural-products science.
---

# Design System: Phyla Technologies

## 1. Overview

**Creative North Star: "The Naturalist's Press"**

Phyla's interface should feel like a contemporary natural-history monograph from a working press (Princeton Architectural Press, MIT Press classics, the Wellcome Collection catalogues, Phaidon's *Living Earth*) crossed with the working pages of a field-naturalist's notebook. Not a biotech AI startup, not a tech consultancy, not a wellness brand. A modern publication that knows it sits inside a centuries-old tradition of cataloguing the living world, and presents its work with the careful weight of that lineage.

The system is built from a small specimen palette (parchment, ink, and a few named earth roles) set in one warm humanist sans whose weight contrast does all the typographic work. There is no serif costume, no display italic, no glass surface. Surfaces are flat as paper. Motion is reserved for one considered moment per page; the rest of the interface holds still on the assumption that good evidence does not need to perform.

Above all, the system rejects the visual reflexes of the categories Phyla touches: AI-startup neon (which the previous version of this site leaned into), SaaS gradient hero, big-consultancy navy and grey, pre-professional academic homepage. Phyla's site lives in the gap between those, where a careful contemporary monograph would.

**Key Characteristics:**

- Specimen palette: parchment + ink + 2 to 3 named earth roles. No rainbow gradients, no neon accents, no glow.
- One warm humanist sans across the whole system, weight contrast doing all the work.
- Flat surfaces at rest. No glassmorphism, no decorative shadow, no backdrop-filter blur.
- Restrained motion baseline plus exactly one deliberate page-load or scroll moment.
- Earth-toned, taxonomic, careful: modern in execution, ancient in lineage.

## 2. Colors: The Specimen Palette

A small, named palette. Each color is a role, not a flourish. All values resolved during implementation; the names and roles are the commitment.

### Primary
- **Tannin** [hex / OKLCH to be resolved during implementation]: The committed earth color that anchors the brand. Used for primary type, primary buttons, and one named-rule moment per page. Imagine the deep brown of oak-gall ink or a herbarium specimen sheet aged in archival storage. Saturated enough to feel earthen, never muddy.

### Secondary
- **Moss** [to be resolved during implementation]: A muted green pulled from lichen, fern frond, or a working naturalist's vest. Carries state, tags, links, and the citation / impact data layer. Earth-saturated, never spring-bright.

### Tertiary (optional)
- **Ochre or rust** [to be resolved during implementation]: A third earth role used sparingly: a section break, a single accent on the Impact page, an emphasis moment. Only present if it earns its place. If it doesn't, drop it before shipping.

### Neutral
- **Parchment** [to be resolved during implementation]: The dominant page surface. A tinted cream, never `#fff`, never the glare-white of a SaaS landing. Should read as paper under warm natural light.
- **Ink** [to be resolved during implementation]: Body type and primary text. A near-black tinted toward the brand hue (chroma 0.005 to 0.01), never `#000`. The weight of a printed monograph, not the contrast of a terminal.
- **Pale parchment, mid parchment** [to be resolved during implementation]: A short tonal ladder above and below parchment for surface differentiation. Used for depth, not for shadow.

### Named Rules

**The Specimen Rule.** Every color earns a name and a job. If a swatch on the page can't be assigned to one of the named roles, it doesn't belong. No "blue-500", no rainbow gradients, no neon. Color drift kills the system.

**The Parchment-First Rule.** The dominant background is parchment. Not white, not slate, not glass. If a section needs to feel different, shift along the parchment tonal ladder. Don't reach for a new color.

**The Tannin Restraint Rule.** Tannin is the committed earth, but committed does not mean dominant. Cap tannin at roughly 30% of any visible surface; let parchment carry the rest. Tannin's gravity comes from contrast, not coverage.

## 3. Typography

**Display Font:** Single warm humanist sans (specific family to be chosen at implementation)
**Body Font:** Same family
**Label Font:** Same family at small caps or tracked uppercase; optionally a deliberately chosen mono for citation metadata, resolved at implementation

**Character:** One family carries the whole system. The humanist drawing (open apertures, a slightly calligraphic skeleton, real italics rather than slanted regulars) supplies the warmth that the absence of a serif might otherwise leave cold. Weight contrast does all the hierarchy work.

The pick must avoid the reflex-reject list: not Inter, not DM Sans, not Plus Jakarta, not Outfit, not Instrument Sans, not IBM Plex. Look further. Candidates to evaluate at implementation: Söhne, GT America, Klim Untitled Sans, Reckless Neue's sans companion, Freight Sans Pro, ABC Diatype, the warmer offerings from Pangram Pangram or Velvetyne. The right pick will read as bookish without being a serif.

### Hierarchy
- **Display** (weight 700 to 800, fluid `clamp()` to large sizes, line-height ~1.0 to 1.05, tight tracking): Hero headline only. One per page.
- **Headline** (weight 600, ~32 to 40px, line-height ~1.2): Section openers.
- **Title** (weight 500, ~20 to 24px, line-height ~1.3): Sub-section openings, card titles, team names.
- **Body** (weight 400, 16 to 17px, line-height ~1.55, max 65 to 75ch): Long-form prose. Cap line length on every viewport.
- **Label** (weight 500, ~12 to 13px, letter-spacing ~0.06 to 0.08em, optional small caps): Eyebrows, metadata, citation tags. Used in place of all-caps body.

### Named Rules

**The One-Family Rule.** The whole system runs on one family. If a moment seems to need a second family, the answer is almost always weight, size, or small caps, not a new typeface.

**The No-Italic-Display Rule.** Big italic display is the editorial-magazine reflex (Fraunces / Cormorant / Newsreader cover-italic). Phyla's display is upright. Italic is reserved for genuine italic content: Latin binomials (*Cinchona officinalis*), book titles, foreign words.

**The 75ch Rule.** Body copy never exceeds 75ch line length. Even in wide hero sections. The eye is the limit, not the viewport.

## 4. Elevation

The system is **flat by default**. Surfaces sit on the parchment. Depth is conveyed through tonal layering of parchment itself (mid-parchment over parchment, ink-on-parchment ladders, hairline ink rules) rather than through cast shadows.

Shadow is a state, not a default: a hover treatment, a focus ring, the exception that signals interactivity. Shadows are never decorative, never used to "lift a card", never used as a section divider. The card sits where it sits.

Backdrop-filter blur is forbidden as a default surface. It is permitted only as a sticky-header technique over a dense ink section, and even then must be subtle enough that the page does not read as glassy.

### Named Rules

**The Flat-By-Default Rule.** Surfaces are flat at rest. Depth is ladder, not shadow. Glassmorphism is forbidden as a default surface treatment.

**The State-Only Shadow Rule.** Shadows respond to a user action: hover, focus, drag. They never sit there at rest, and they never carry brand color (no glowing teal or violet halos). Shadow color is a darker tint of parchment, never an accent color.

## 5. Components

[Components section omitted in seed mode: no production components exist in the new direction yet. Re-run `/impeccable document` after the redesign lands to capture the real button, card, navigation, input, and any signature components, with a sidecar for the live panel.]

## 6. Do's and Don'ts

### Do:
- **Do** anchor every surface to the specimen palette: parchment (dominant background), ink (body), tannin (committed earth, ≤30% surface), moss as supporting earth, ochre only if it earns its place.
- **Do** tint every neutral toward the brand hue. No `#fff`, no `#000`. Parchment is tinted cream; ink is tinted near-black.
- **Do** use one warm humanist sans across the whole system. Weight, size, and small caps do all the hierarchy work.
- **Do** keep body line length at or below 75ch on every viewport.
- **Do** keep surfaces flat at rest. Ladder parchment for depth, never shadow.
- **Do** reserve motion for one deliberate page-load or scroll moment per route. The rest of the page holds still.
- **Do** italicize Latin binomials and book titles as genuine italic content.
- **Do** treat the Impact page (live OpenAlex citation data) as the proof-of-work moment. The data is the design's load-bearing element; the rest of the visual system should yield to it on that page.
- **Do** use ink hairlines (1px ink at low opacity) and parchment-ladder shifts as the primary section dividers.

### Don't:
- **Don't** ship the current AI-generated boilerplate aesthetic: dark slate background, teal-cyan-blue-violet rainbow gradients, glassmorphic cards with neon glow, animated mesh-gradient hero. Every one of those is the explicit wrong direction (PRODUCT.md anti-reference: *Crypto / Web3 / AI-startup neon*).
- **Don't** drift into the SaaS-landing reflex: gradient blob hero, logo wall, big-number stat row, identical card grids of icon + heading + 2 lines (PRODUCT.md anti-reference: *Generic SaaS landing*).
- **Don't** drift into corporate-consultancy aesthetics: navy and grey, stock photos of diverse teams pointing at laptops, "global solutions" copy (PRODUCT.md anti-reference: *Big-consultancy corporate*).
- **Don't** drift into academic / lab-homepage aesthetics: Times New Roman, sidebar publications list, 1998 university CSS (PRODUCT.md anti-reference: *Academic / lab homepage*). Rooted in tradition is not the same as looking unfunded.
- **Don't** slip into the within-lane traps the natural-products direction creates: Whole Foods / Aveda spa-aesthetic, Etsy hand-crafted folk, hipster apothecary cliché, wellness-brand sage-and-cream. Phyla is a working scientific press, not a wellness brand. If the layout could host a "Shop our serums" CTA, rework it.
- **Don't** use display serif italic as the headline voice. That is the editorial-magazine second-order reflex. The display is upright sans.
- **Don't** use `border-left` or `border-right` greater than 1px as a colored stripe on cards, list items, callouts, or alerts. Ever.
- **Don't** use `background-clip: text` on a gradient. (The current site does this on the hero "MLOps" word; remove it in the redesign.)
- **Don't** use glassmorphism (`backdrop-filter: blur` on default surfaces). The current site uses it on the header, the cards, and the tree-nav nodes; remove it.
- **Don't** reach for a modal as a first thought. Inline and progressive alternatives first.
- **Don't** use em dashes in copy. Commas, colons, semicolons, periods, parentheses do the work.
- **Don't** use icon + heading + 2-line-of-copy card grids as a feature listing. The previous site does this for services; the new layout finds a different shape (asymmetric, list-based, a single committed illustration, or a working specimen-card pattern that earns the form).
