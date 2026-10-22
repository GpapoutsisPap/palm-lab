# 17. Colour palettes

Date: 2026-10-22

## Status

Accepted.

## Context

People asked for more personality than light and dark: an orange "sunset"
look, a green "neon" one. Custom CSS (ADR-0012) can already do this, but only
for someone who writes CSS. A palette has to work in both themes, keep every
text readable, leave the puzzle pieces recognisable (their colour says what
kind of action each one is), and still let custom CSS win.

## Decision

- **A palette is a set of colour variables, nothing else.** Each one sets the
  same variables the theme does (`--mica`, `--card`, `--accent` and the rest),
  once for light and once for dark, in app.css. Choosing one sets
  `<html data-palette="sunset">`. Layout, fonts and the puzzle pieces'
  colours are never touched.
- **Windows is the default palette,** and the only one that uses the Windows
  accent colour. The others bring their own accent, so they look the same on
  every PC.
- **Each palette is a scene, not a tinted grey.** A first version mixed a
  little of each hue into the Windows greys; side by side they looked alike,
  differing mostly in the accent. Now each palette picks its own surfaces
  (Sunset's peach, or dusk purple in dark; Neon's mint, or near-black green), its
  own text colours to match, and a colour for page titles. Three extras give
  each one a character the accent alone can't: a gradient behind the sidebar
  (`--mica` fading to `--backdrop-end`, starting as `--mica` so it runs on
  from the title bar without a seam), a soft `--glow` in the page's top
  corner, and, for Neon only, a faint grid (`--pattern`). Windows has none of
  them. For each palette and theme a few colours were chosen by hand and
  the rest (hover states, borders, controls) mixed from them.
- **Checked by numbers, not by eye.** A test reads app.css and checks every
  palette in both themes against WCAG contrast, on every surface the text
  can land on, including the gradient's end and the glow: body text at least
  7:1, secondary text, titles and accent-coloured text at least 4.5:1, text
  on accent buttons at least 4.5:1, faint hints at least 3:1 (as faint as
  the Windows default), and the accent against cards and the page at least
  3:1 (WCAG's minimum for controls such as switches). Another test checks no
  two palettes share a background, accent or title colour.
- **Zero specificity, as before.** Palette blocks sit inside `:where(...)`,
  so a plain `:root { --accent: ... }` in custom CSS still wins in every
  palette and theme.
- **Each swatch previews itself.** The selectors match any element with
  `data-palette`, not only `<html>`, so a swatch button with
  `data-palette="neon"` shows Neon's colours whatever palette the window is
  in, with no colours repeated in JavaScript.
- **The window frame follows.** Python keeps each palette's window background
  (palettes.py), used before the page loads and for the title bar; a test
  checks it matches the CSS.

## Consequences

Seven palettes, each in light and dark, is fourteen sets of colours to keep
readable. The contrast test makes a careless change fail CI rather than ship.

A new palette means a block in app.css for each theme, an entry in
palettes.py, and nothing else; the Settings picker lists whatever Python
sends.

Custom CSS written for the default palette may look odd on a tinted one,
since it can set some backgrounds and not others. Setting the palette back to
Windows is the fix.
