# Polish round T1.1 · `03-el-mapa.html`

Decisions for the polish round asked in `odd/tasks/panel-operaciones.md` (T1.1, S6-S8, Log L7). Sources: a motion audit (remove-animations → improve-animations → animation-performance → animate, emil-design-eng) and a visual audit (better-interface and the better-* family, impeccable critique and craft-floor, unslop signs and tokens). Where the skills disagreed, the rule was: what makes the screen clearer for the operations person wins, and the user's explicit brief beats a skill default.

## Diagnosis

Authored structure, interchangeable skin. Keep: one tile per remito across the three moments, the answer as a sentence, amber never red, "Ver detalle técnico de R-…", the ring on tiles that need a fix, the fix table with hairlines. Fix: default system font, rounded cards with soft shadows (and cards inside cards), stock pastel trio, one word of the H1 painted orange, a kicker above a heading, nine font sizes, mixed icon strokes.

## World: "Remito"

The physical remito pad: carbon copies (original, duplicado, triplicado), stamp ink, a highlighter. Color strategy: Restrained. One saturated mass on the page, and it is what needs action.

## Typography

- Typeface: **Atkinson Hyperlegible Next** (Braille Institute, OFL). Reason: it was drawn so that similar characters never get confused (0/O, 1/l/I), which is exactly the risk with remito numbers (R-10000477) and tracking codes (AND4BD591C) read by non-technical staff. It has its own shapes at display sizes, it is not on any burned list (impeccable `new-work.md` flags Inter, DM Sans, Plus Jakarta, Instrument Sans, IBM Plex, Space Grotesk, Outfit and others; Geist and Roboto excluded by our own judgment).
- Fallback if it lacks tabular figures or weight 500, or is too wide for the tiles: Public Sans (USWDS, OFL).
- Embedded as a woff2 data URI, subset to Latin-1 plus « » ¿ ¡ … — – ’ “ ”, keeping `kern` and `tnum`; OFL notice in an HTML comment; respect any Reserved Font Name. Stack: `"Atkinson Hyperlegible Next", system-ui, sans-serif`. System mono only inside the technical detail (real code).
- This is a deliberate deviation from gentle-design's "system font stacks only": the file stays self-contained and works offline.
- Scale (5 steps, rem, unitless line-height):
  - 0.8125rem / 1.4: meta, remito in tile, table headers, legend, technical detail.
  - 0.9375rem / 1.5: secondary text, buttons, picked line, header meta, summaries.
  - 1.0625rem / 1.5: body, sub, table cells, `.what`.
  - 1.5rem / 1.25: section titles.
  - 3rem / 1.08 (2.25rem on narrow): the answer.
- Nothing under 13px. Weights 400 / 500 / 600; 600 only where it carries meaning without color (name in a tile that needs a fix, `.what`). Tracking 0 under 16px, -0.01em from 24px, -0.025em on the answer. `tabular-nums` on every count and code.

## Palette (OKLCH, every text pair ≥ 4.5:1, every boundary ≥ 3:1, measured)

```
--ground:    oklch(0.972 0.006 250)  page
--paper:     oklch(0.995 0.003 95)   the fix sheet (only elevated surface)
--sunken:    oklch(0.945 0.008 250)  technical detail background
--text:      oklch(0.21 0.02 255)    ink
--text-2:    oklch(0.45 0.02 255)
--hair:      oklch(0.21 0.02 255 / 0.12)
--accent:    oklch(0.38 0.10 258)    stamp ink: primary button, selection ring, focus
--ok-fill:   oklch(0.955 0.02 165)   20 of 23 tiles step back
--ok:        oklch(0.42 0.09 165)
--prev-fill: diagonal hatch of oklch(0.21 0.02 255 / 0.07) on transparent (carbon copy)
--prev:      var(--text-2)
--attn-fill: oklch(0.90 0.12 88)     highlighter / triplicado yellow
--attn-line: oklch(0.50 0.12 70)
--attn-ink:  oklch(0.28 0.06 70)     text on --attn-fill
```

- Light blue is gone: "Ya estaba" is the quietest state (hatch + retry icon).
- The H1 count ("3 de 23 envíos") stays in ink with a highlighter band behind it: `box-shadow: inset 0 -0.32em 0 var(--attn-fill)` with `box-decoration-break: clone`. Solid band, no gradient.
- States never rely on color: Cargado = check + low green; Ya estaba = retry icon + hatch; Falta un dato = blank-field icon + yellow fill + 2px ring + name in 600; every tile keeps its `aria-label`.
- Re-measure the dashed pending border and the mini-cell outlines: they must reach 3:1.

## Radii (tighter, utilitarian: a remito, a label, a warehouse slot)

`--r-xs: 2px` mini cells · `--r-sm: 4px` tiles, technical detail, picked line · `--r-md: 6px` buttons, skip link · `--r-lg: 10px` the fix sheet. Concentric rule (outer = inner + padding + border) applies if anything is ever nested.

## Fewer boxes

- `.map-wrap` card: removed. The map sits on the page; its title becomes a plain section heading with a hairline.
- Legend moves to the left column under the answer, as three rows with tabular counts (fills the empty band under the button).
- `.picked`: a flat text line under the map with a hairline above, no fill, same min-height.
- The fix table becomes the only elevated surface: a `--paper` sheet, radius 10, one hairline ring (no layered shadow), rows with hairlines. Lo accionable es el papel.
- The two earlier moments: no cards, no kicker. Plain section "Antes del resultado" with two flat columns split by a vertical hairline, each with its own heading ("Elegir el export", "Mientras carga").
- Selection ring gap must use `--ground` (no more `--surface` halo).
- Spacing on a 4px grid: 8 inside a group, 16-24 between groups; replace 10/6/14/18/3.2px values.
- Icons: stroke 1.5 next to 400-500 text, 1.75 next to 600. One family of drawn SVG.

## Motion (Emil's flow)

- **Remove** the tile hover `filter: brightness(0.98)` and `filter` from tile transitions (imperceptible, filter compositing on 23 tiles).
- **Curves:** `--ease-out: cubic-bezier(0.23, 1, 0.32, 1)` for every enter/exit/state change; plain `ease` for color hovers.
- **Replay cadence:** STEP 70ms, START 200ms, TAIL 250ms (about 2.1s). Linear rate: it is progress.
- **Headline swap:** sequenced with a 2px blur mask. Exit 120ms no delay; live counter enters 200ms with 60ms delay; final sentence enters 220ms with 80ms delay; offset 5px. Opacity-only under reduced motion.
- **Fix rows are discovered, not held:** each row appears when its tile resolves during the replay (opacity + 6px, 220ms ease-out), so the table fills as the map does. Hidden rows are `inert`.
- **Tile icon:** scale 0.25→1 + blur 4px→0, 240ms ease-out; pending exit 120ms. Tile reset faster than fill (120ms).
- **Selection ring:** box-shadow 140ms ease-out; tile press scale 0.97 like buttons.
- **Row flash:** `attn 900ms ease-out`, holding the color for the first 25%. If the row is already in view, flash immediately (no scrollend wait).
- **Keyboard-initiated scroll** (`e.detail === 0`) jumps instead of smooth-scrolling.
- **Settle ping (new, one-shot):** when a replay finishes on its own, the three amber tiles emit a single expanding ring (`::after`, opacity .55→0, scale 1→1.16, 500ms ease-out, delay 260ms + 60ms per tile). Never on load, never on restart, omitted under reduced motion.
- Cache the `[data-count]` nodes once.
- Keep: button hover color 150ms and press 0.97, picked fade 60/120ms, instant counters, disclosure `::details-content` animation, no `will-change`, nothing on load, nothing looping.

## Conflicts and how they were resolved

| Topic | Skills | Decision |
| --- | --- | --- |
| Typeface | gentle-design and impeccable Operate accept system stacks; better-typography says do not propose a typeface unless asked | The user asked (S8). Embedded OFL font with system fallback |
| Depth | better-ui: layered ring shadows; impeccable, unslop, better-layout: no nested cards, group with space | Delete boxes first; one hairline ring only on the surviving sheet |
| Radii | better-ui formula; unslop scale 12-16 for cards | Formula kept; scale tightened to 2/4/6/10 because large radii were the template look |
| Easing | better-ui `(0.2, 0, 0, 1)`; Emil `(0.23, 1, 0.32, 1)`; unslop `(0.22, 1, 0.36, 1)` | Emil's, as the user asked for his flow |
| Exit | better-ui: -12px + blur; Emil: exit like the enter, faster | Emil: in-place swaps, 5px, shorter exit |
| Blur | better-ui 4px; Emil 2px for crossfades | 4px on small icons, 2px on large text |
| Hover | better-ui allows ≤150ms; Emil: remove on high-frequency surfaces | Remove on tiles, keep on buttons |
| Weights | unslop 400/500; better-typography 600 headings | 600 only where it replaces color |
| Mono | unslop accepts it for data; impeccable calls it a costume | Only real code (technical detail) |
| Process | unslop: show the direction and wait | The user delegated judgment in L7; the canvas is the review |
