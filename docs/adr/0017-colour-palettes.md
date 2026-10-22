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
- **Backgrounds are tinted greys, not colours.** Each surface is the neutral
  Windows grey mixed with a little of the palette's hue (3 to 16%), so cards
  still stand out from the window and long sessions don't tire the eyes. The
  accent carries the personality.
- **Checked by numbers, not by eye.** A test reads app.css and checks every
  palette in both themes against WCAG contrast: body text at least 7:1,
  secondary text and accent-coloured text at least 4.5:1, text on accent
  buttons at least 4.5:1, and the accent against a card at least 3:1 (WCAG's
  minimum for controls such as switches).
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
