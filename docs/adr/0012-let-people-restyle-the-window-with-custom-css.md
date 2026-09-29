# 12. Let people restyle the window with custom CSS

Date: 2026-09-29

## Status

Accepted.

## Context

The window is plain HTML and CSS (ADR-0007), so a stylesheet can change
anything about how it looks. Apps such as Jellyfin let people paste their own
CSS in settings, which gives tinkerers themes without forking the app. It
also lets someone break the window badly enough to lose the setting that
would undo it.

## Decision

- **Where it lives.** `custom.css` in palm-lab's config folder, edited in
  Settings > Appearance > Custom CSS or in any editor. A `custom_css` setting
  turns it on and off without losing the text. Files over 256 KB are refused.
- **Live, then saved.** The editor applies the CSS as you type and saves it
  half a second after you stop, like every other setting.
- **Only ever CSS.** The page puts it into its own `<style>` element with
  `textContent`, after palm-lab's styles so it wins ties. It is never pasted
  into the page's HTML (not even by Python when building the page), so a
  shared file containing `</style><script>` cannot run anything.
- **Easy to override.** palm-lab's colour variables are declared inside
  `:where(:root)` and `:where(:root[data-theme="dark"])`, which carry no
  specificity. A plain `:root { --accent: ... }` therefore wins in both
  themes; without this, the dark theme's more specific selector silently beat
  it.
- **Three ways back.** CSS can hide every control, but not stop JavaScript,
  so Ctrl+Shift+X always turns custom CSS off. `palm-lab ui --no-custom-css`
  starts without it (the text still loads into the editor, to be fixed), and
  the file can simply be deleted.

## Consequences

Anyone can theme palm-lab, and themes are shareable as one file. The README
lists the variables most themes need.

Class names and the page structure become something people's CSS depends on.
Renaming them can break someone's theme; the colour variables are the stable
part to point people at.

CSS can still load images or fonts from the internet through `url()`, which a
shared theme could use to see that it was opened. That is the same trust as
installing any theme, and nothing about the user is sent with it.
