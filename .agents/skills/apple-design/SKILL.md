---
name: apple-design
description: "Apple's visual language as an actionable spec: exact tokens, type ladder, spacing rhythm and the rules that make it recognisable. Trigger: designing or reviewing the WhisperKey landing page, or any request for an Apple-like, premium, minimal aesthetic."
metadata:
  source: https://github.com/VoltAgent/awesome-design-md (design-md/apple)
  version: "alpha"
---

## When to Use

Load this before writing or reviewing markup and CSS for `web/` — the WhisperKey
landing page — or whenever a request asks for the Apple aesthetic.

`DESIGN.md` in this folder is the spec. Read it; do not paraphrase it from
memory. It carries exact hex values, font sizes, letter-spacing, radii and
breakpoints, and the precision is the whole point: those numbers are what make
the language recognisable.

## The three rules that carry the look

**One accent, and only one.** Action Blue `#0066cc` is every interactive
signal — links, buttons, focus rings. A second accent colour breaks the
language immediately. On dark tiles the accent shifts to `#2997ff`; never use
that one on light surfaces.

**The section divider is the colour change.** Full-bleed tiles alternate light
and dark, edge to edge, no gap, no rounding, no border between them. Reaching
for a divider line or a card outline means the rhythm is not being carried by
the surfaces, which is where Apple puts it.

**Exactly one shadow exists**, `rgba(0,0,0,0.22) 3px 5px 30px`, and it belongs
under product imagery resting on a surface. Not on cards, not on buttons, not
on text. Depth comes from surface changes and backdrop blur.

## What this rules out

The spec's "Don't" list is the useful part, because most of it is exactly what
generic AI layouts reach for: decorative gradient backgrounds, drop shadows on
cards, a second accent colour, 16px body text, rounded full-bleed sections,
weight 500. The type ladder is 300 / 400 / 600 / 700 — 500 is deliberately
absent.

Body copy runs at **17px**, not 16px, with line-height 1.47. That single pixel
is a large part of the reading pace.

## Fonts

SF Pro is proprietary. `system-ui, -apple-system, BlinkMacSystemFont` resolves
to the real thing on Apple hardware; **Inter** is the closest substitute
elsewhere. When substituting, tighten letter-spacing by a further `-0.01em` on
display sizes and drop body line-height from 1.47 to 1.44 — Inter runs wider
and taller than SF Pro.

## Attribution

Spec from [VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md).
It is an analysis of publicly observable patterns, not an official Apple
resource, and the aesthetic is a reference — the product still has to be itself.
