# Phyla Technologies — Design Tokens

The resolved, portable reference for the Phyla site's design system, **"The Naturalist's Press."**
`DESIGN.md` holds the philosophy and rules; this file holds the actual implemented
values (the source of truth is the `:root` block in [`styles.css`](styles.css)).

OKLCH is authoritative; hex is an sRGB approximation for tools that need it.

> **The feel:** a contemporary natural-history monograph crossed with a field
> naturalist's notebook. Parchment and ink, a few named earth roles, one warm
> humanist sans, flat surfaces, restrained motion. Not AI-startup neon, not SaaS
> gradient, not corporate navy, not a wellness brand.

---

## Color: the Specimen palette

Every color is a role, not a flourish. If a swatch can't be named here, it doesn't belong.

| Token | Role | OKLCH | Hex |
|---|---|---|---|
| `--parchment` | Dominant page background (paper, never `#fff`) | `oklch(95.5% 0.012 80)` | `#f4efe7` |
| `--parchment-pale` | Raised surface, inputs, cards | `oklch(97.2% 0.008 80)` | `#f9f5f0` |
| `--parchment-mid` | Recessed band / section shift | `oklch(92% 0.014 78)` | `#eae4da` |
| `--parchment-deep` | Deepest paper tone | `oklch(88% 0.018 75)` | `#dfd6cb` |
| `--ink` | Body + primary text (near-black, warm-tinted, never `#000`) | `oklch(22% 0.02 70)` | `#211910` |
| `--ink-soft` | Secondary text, captions | `oklch(35% 0.025 70)` | `#43382c` |
| `--ink-hairline` | Hairline rules (ink @ 18%) | `oklch(35% 0.025 70 / 0.18)` | `#43382c` @ 18% |
| `--ink-hairline-strong` | Stronger hairline / borders (ink @ 32%) | `oklch(35% 0.025 70 / 0.32)` | `#43382c` @ 32% |
| `--tannin` | **Committed earth.** Primary accent: links, buttons, one rule per page | `oklch(42% 0.10 55)` | `#753b07` |
| `--tannin-deep` | Tannin hover / pressed | `oklch(32% 0.09 55)` | `#542300` |
| `--moss` | Supporting earth: state, tags, the data/impact layer | `oklch(50% 0.08 140)` | `#4a6e42` |
| `--moss-deep` | Moss, deeper | `oklch(38% 0.08 140)` | `#294c22` |
| `--ochre` | Sparing third accent: a section break, one emphasis | `oklch(62% 0.12 70)` | `#b47825` |
| `--focus` | Focus ring (equals tannin) | `oklch(42% 0.10 55)` | `#753b07` |

**Rules.** Parchment carries the page; cap **tannin at ~30%** of any surface (its
gravity is contrast, not coverage). For depth, shift along the parchment ladder,
never reach for a new color. Neutrals are tinted toward the brand hue, never pure.

---

## Copy-paste tokens

```css
:root {
  /* Specimen palette. OKLCH is source of truth; hex fallback in comments. */
  --parchment:            oklch(95.5% 0.012 80);   /* #f4efe7 */
  --parchment-pale:       oklch(97.2% 0.008 80);   /* #f9f5f0 */
  --parchment-mid:        oklch(92% 0.014 78);     /* #eae4da */
  --parchment-deep:       oklch(88% 0.018 75);     /* #dfd6cb */

  --ink:                  oklch(22% 0.02 70);      /* #211910 */
  --ink-soft:             oklch(35% 0.025 70);     /* #43382c */
  --ink-hairline:         oklch(35% 0.025 70 / 0.18);
  --ink-hairline-strong:  oklch(35% 0.025 70 / 0.32);

  --tannin:               oklch(42% 0.10 55);      /* #753b07 */
  --tannin-deep:          oklch(32% 0.09 55);      /* #542300 */
  --moss:                 oklch(50% 0.08 140);     /* #4a6e42 */
  --moss-deep:            oklch(38% 0.08 140);     /* #294c22 */
  --ochre:                oklch(62% 0.12 70);      /* #b47825 */
  --focus:                oklch(42% 0.10 55);      /* #753b07 */

  /* Type */
  --sans: 'Bricolage Grotesque', 'Source Sans 3', 'Helvetica Neue', system-ui, -apple-system, sans-serif;

  /* Measure (max line length) */
  --measure-narrow: 52ch;
  --measure:        65ch;
  --measure-wide:   75ch;

  --view-transition-duration: 280ms;
}
```

---

## Typography

**One family does everything:** [Bricolage Grotesque](https://fonts.google.com/specimen/Bricolage+Grotesque),
a warm humanist sans with real width and weight axes. Hierarchy comes from weight,
width, and size, never a second family. Body copy never exceeds **75ch**.

```html
<!-- Web font (variable: optical size, width, weight) -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wdth,wght@12..96,75..100,300..800&display=swap" rel="stylesheet">
```

| Role | Weight / width | Size | Line height | Tracking |
|---|---|---|---|---|
| **Display** (one per page) | 700 / wdth 95 | `clamp(2.75rem, 7vw, 5rem)` | 1.02 | -0.025em |
| **Headline** (section openers) | 600 / wdth 100 | `clamp(1.75rem, 3.2vw, 2.625rem)` | 1.15 | -0.018em |
| **Title** (cards, names) | 600 / wdth 100 | 1.0625rem | 1.35 | -0.005em |
| **Body** | 400 | 1.0625rem (large: 1.1875rem) | 1.6 | 0 |
| **Label** (eyebrows, metadata) | 600 | 0.75rem, UPPERCASE | 1.35 | 0.14em |
| **Latin** (binomials, titles) | 400 italic / wdth 95 | inherits | inherits | 0 |

- Display and headline `em` render in **tannin italic** for emphasis.
- Latin binomials (*Aequorea victoria*), book titles, and foreign words are the
  only genuine italic. **Display is always upright** (no serif-italic magazine cover).
- Base body sets `font-feature-settings: "ss01","ss02","kern"`.

---

## Layout, surface, motion

- **Radius: `0`.** Buttons, inputs, and cards are square. No `rounded-lg`.
- **Flat by default.** Depth is the parchment ladder + ink hairlines, not shadow.
  Shadow is a *state* (hover/focus/drag) in a darker parchment tint, never an accent
  glow. No `backdrop-filter` blur on default surfaces.
- **Dividers** are 1px ink hairlines (`--ink-hairline`) or a parchment-ladder shift.
- **Focus:** `outline: 2px solid var(--focus); outline-offset: 3px;`.
- **Motion:** reserved for one deliberate moment per route; everything else holds
  still. House easing is `cubic-bezier(0.16, 1, 0.3, 1)`. Always honor
  `prefers-reduced-motion: reduce`.
- **Loaders:** an organic, earth-toned family (colony ripple, spore ring,
  fiddlehead, aperture, seed drift) in tannin on parchment / ochre on ink.

### Signature controls

```css
/* Solid accent button */
.btn-primary {
  background: var(--tannin); color: var(--parchment-pale);
  padding: 0.85rem 1.6rem; border: 1px solid var(--tannin); border-radius: 0;
  font-variation-settings: "wdth" 100, "wght" 600; letter-spacing: 0.02em;
}
.btn-primary:hover { background: var(--tannin-deep); border-color: var(--tannin-deep); }

/* Underlined text link with a nudging arrow */
.link-arrow {
  color: var(--tannin); border-bottom: 1px solid var(--tannin);
  font-variation-settings: "wdth" 100, "wght" 600; text-decoration: none;
}
.link-arrow:hover { color: var(--tannin-deep); }
```

---

## Keep / avoid

**Keep:** parchment-dominant surfaces; tinted neutrals; one humanist sans; ≤75ch
body; flat surfaces with hairline rules; italic only for real italic content; one
motion moment per page; earth roles that each earn a name.

**Avoid:** `#fff` / `#000`; AI-startup neon, gradient heroes, glassmorphism, glow;
corporate navy-and-grey; academic Times New Roman; wellness-brand sage-and-cream;
colored `border-left`/`right` stripes >1px; `background-clip: text` gradients;
display serif italic; icon + heading + 2-line card grids; **em dashes** in copy.
