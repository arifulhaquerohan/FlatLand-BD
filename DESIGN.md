---
name: FlatLand BD
description: Verified flats and interior studios in Bangladesh — the Warm Blueprint design system.
colors:
  terracotta: "#a8541f"
  terracotta-decorative: "#d57b4c"
  terracotta-deep: "#9d481b"
  sand: "#f2b57b"
  clay-soft: "rgba(213, 123, 76, .12)"
  sage: "#2f6b57"
  sage-soft: "#e7f0eb"
  amber: "#a06a10"
  amber-soft: "#fbf0db"
  rose: "#ad3c32"
  rose-soft: "#fbe8e5"
  info: "#2b6383"
  info-soft: "#e5eff5"
  ink: "#1f2722"
  ink-2: "#38453d"
  muted: "#616f66"
  faint: "#94a09a"
  canvas: "#fbf9f6"
  canvas-2: "#f3efe9"
  surface: "#ffffff"
  surface-2: "#f7f4f0"
  surface-3: "#efe9e1"
  line: "#e4ddd3"
  line-strong: "#d3c8ba"
  ink-dark: "#14120f"
  cream: "#f6f1ea"
  dark-clay: "#e2884e"
  on-terracotta: "#ffffff"
typography:
  display:
    fontFamily: "Fraunces, 'Noto Sans Bengali', Georgia, serif"
    fontSize: "clamp(2.6rem, 6.4vw, 4.6rem)"
    fontWeight: 500
    lineHeight: 0.98
    letterSpacing: "-0.03em"
  headline:
    fontFamily: "Fraunces, 'Noto Sans Bengali', Georgia, serif"
    fontSize: "clamp(2.1rem, 4.4vw, 3.2rem)"
    fontWeight: 500
    lineHeight: 1.08
    letterSpacing: "-0.015em"
  title:
    fontFamily: "Fraunces, 'Noto Sans Bengali', Georgia, serif"
    fontSize: "clamp(1.7rem, 3.2vw, 2.4rem)"
    fontWeight: 500
    lineHeight: 1.08
  body:
    fontFamily: "Sora, 'Noto Sans Bengali', ui-sans-serif, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.55
  lead:
    fontFamily: "Sora, 'Noto Sans Bengali', ui-sans-serif, system-ui, sans-serif"
    fontSize: "clamp(1.03rem, 1.5vw, 1.2rem)"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "Sora, 'Noto Sans Bengali', ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.8rem"
    fontWeight: 600
    lineHeight: 1.4
  data:
    fontFamily: "Fraunces, Georgia, serif"
    fontWeight: 500
    fontFeature: "tabular-nums"
rounded:
  xs: "6px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "22px"
  pill: "999px"
spacing:
  1: "4px"
  2: "8px"
  3: "12px"
  4: "16px"
  5: "24px"
  6: "32px"
  7: "48px"
  8: "64px"
  9: "96px"
components:
  button-primary:
    backgroundColor: "{colors.terracotta}"
    textColor: "{colors.on-terracotta}"
    rounded: "{rounded.pill}"
    padding: "12px 22px"
    height: "46px"
  button-primary-hover:
    backgroundColor: "{colors.terracotta}"
    textColor: "{colors.on-terracotta}"
    rounded: "{rounded.pill}"
    padding: "12px 22px"
    height: "44px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.pill}"
    padding: "12px 22px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "12px 15px"
    height: "48px"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
---

# Design System: FlatLand BD

## Overview

**Creative North Star: The Warm Blueprint.** The system hangs on architecture heritage — blueprint linework, drafting grids, measured square footage, site-visit stamps — with warmth layered on top: terracotta, cream paper tones, and photography of real, sunlit rooms.

Voice: **honest craftsman**. Warm, direct, hand-finished; a person you trust, not a platform. Components are **tactile and confident** — rounded, clearly tappable, solid buttons, breathing cards.

**Anti-reference: never a classifieds site.** No rows of identical gray cards, no ad-clutter, no gray listing tables. Hierarchy, whitespace, and photography distinguish FlatLand BD from listing dumps.

Text is always light theme ("dark mode removed" is a product decision, not an omission). Bengali-first audience: font stacks carry Noto Sans Bengali; the ৳ glyph ships now, full Bengali UI is the planned direction — never foreclose it.

## Colors

- **Terracotta `{colors.terracotta}`** is the only text/solid-action accent: links, active nav, primary buttons, kickers-as-labels. It passes ≥4.5:1 on every light surface token — never darken/lighten ad hoc; compute before changing.
- `{colors.terracotta-decorative}` is for large display moments and decoration only (≥3:1 contexts) — never body text.
- Ink surfaces (`{colors.ink-dark}` bg, `{colors.cream}` text) invert tokens locally (`--clay-strong` becomes `{colors.dark-clay}`) — see `.section--ink` in core.css.
- Semantic pairs: sage = success, amber = pending, rose = danger, info = neutral notice; each has a `-soft` tint for backgrounds.
- Neutrals are warm paper: canvas → canvas-2 → surface-3; lines `{colors.line}`/`{colors.line-strong}`. Never pure gray.

## Typography

Fraunces (variable roman + italic) carries voice; Sora carries UI. Bengali fallback stacks on both.

- Display/headlines: Fraunces 500, tight leading (0.98–1.08), `text-wrap: balance`.
- The hero's italic accent line is **real Fraunces italic** — never let the italic axis drop from the font URL (synthetic oblique is a defect).
- Body/lead: Sora 400, 1.55/1.6 leading, measure ≤62ch, `text-wrap: pretty` on prose.
- Labels: Sora 600, 0.8rem sentence case (forms) or tracked caps (functional chips only — never above headings).
- Data (prices, stats, counters): Fraunces with `font-variant-numeric: tabular-nums`.
- Light-on-dark prose: +leading (1.66) and muted-token tints — compensate all three perceptual axes.

## Layout

- `.shell` caps content at **1180px** with 24px inline padding; `--shell-tight` 720px for reading.
- Sections: `clamp(56px, 8vw, 104px)` vertical rhythm; page background alternates canvas / canvas-2.
- Grids: listing cards `repeat(auto-fill, minmax(310px, 1fr))`; detail pages split 1.7fr/1fr in `.detail__grid` collapsing ≤1000px, with the price/CTA rail `position: sticky` ≥1001px; spec strips are a fixed 2×2 quadrant (always exactly 4 cells — never auto-fit, it orphans the 4th); forms pair fields in `.form-grid-2` (1fr 1fr → 1fr ≤560px).
- Mobile: fixed bottom dock ≤760px (body gets 64px + safe-area clearance), FABs above it, drawer nav behind the burger ≤1000px.
- **`html { overflow-x: clip }`** — never `overflow-x: hidden` on the root (iOS Safari touch-scroll killer).

## Elevation & Depth

**Soft ambient layering.** Three shadow tokens (`--shadow-1/2/3`) are layered, low-contrast, ambient — cards rest flat and lift on interaction (`hover-lift`, listing translateY(-6px)). Zero-offset colored halos are banned. The hero stacks real photography on floating cards (price card, inset second photo) — depth is compositional, not shadow-heavy. Focus is `{--ring}`: 3px terracotta ring.

## Shapes

Radii ramp xs 6 → xl 22px; **pills only for small controls** (buttons, chips, badges, FABs). Cards and panels: `{rounded.lg}`; hero imagery and large frames: `{rounded.xl}`. Borders are 1px `{colors.line}`; dashed borders signal dropzones and optional disclosures. No nested cards ever — disclosures inside the contact card are divider rows, not boxes.

## Components

- **Buttons**: pill, solid terracotta primary (min-height 46px, 54px large), ghost with `{colors.line-strong}` border, ink/soft/sage/danger variants; `.btn-arrow` slides its icon on hover. Touch floor 44px — scoped, so micro-controls keep their design size.
- **Cards**: `.listing` (media + body, hover lift + photo zoom + spec overlay), `.quote-card`, `.metric`, `.panel` (header/body/foot). Hover states always pair transform + shadow, never shadow alone.
- **Forms**: 48px inputs, terracotta focus ring, labels 600 sentence case, placeholders at `{colors.muted}`; optional fields collapse into `.form-extra` disclosure.
- **Trust chips**: glass badges over photos (`rgba(20,18,15,.58)` + blur) — the "Photographed on site" pattern.
- **Header**: sticky, blur backdrop, terracotta underline on active nav; mobile drawer + bottom dock (Home/Flats/Interior/Quote).
- **Motion**: one ease `cubic-bezier(.16,1,.3,1)`, durations .18/.34/.6s; reveal-on-scroll (blur-up, stagger); ticker marquee; hover micro-interactions. Everything respects `prefers-reduced-motion` with explicit alternatives.

## Do's and Don'ts

**Do**
- Compute contrast before touching color tokens (all text ≥4.5:1 on its real surface)
- Keep every interactive control ≥44px tall unless a scoped exception documents it
- Use bare `<dl>`/`dt`/`dd` patterns with explicit styles — never rely on browser-default margins
- Test 320px: the hero title floor (2.1rem) and price-card `max-width` exist for it
- Keep the hero accent's italic real (Fraunces ital axis in the font URL)

**Don't**
- **No kicker/eyebrow above any heading** — the heading speaks for itself (hard ban)
- **No nested cards** — disclosures inside cards are divider rows
- No `max-width: 100vw` on `.shell`, no `overflow-x: hidden` on `<html>`, no fake italic, no unbounded `will-change` at rest
- No fabricated listings, counts, testimonials, or stats — evidence comes from PRODUCT.md's confirmed facts
- No second accent family or display font; Fraunces + Sora are the whole voice

## Console (Operate surfaces)

The admin console (`.console`, `console.css`) is the **ink chrome** application of this system: rail and bulk bar sit on the ink ground (`#14120f`) with the blueprint hairline grid at low-opacity cream and `#e2884e` as the accent-on-ink; every working surface stays paper (canvas `#fbf9f6`, white panels, 1px `#e4ddd3` lines). KPIs render as one divided band (never floating tinted cards); moderation mix is a stacked bar; status pills carry sage/amber/rose. The command palette (⌘K), confirm dialog, and `console.js` `data-*` hooks are part of the surface contract — keep them when restructuring. Honest zeros are a feature: the console must read intentional with an empty database.
