# 8. Design the window around collapsible gesture rows

Date: 2026-09-28

## Status

Accepted

## Context

The first version of the window showed everything at once: a palette of
blocks, a grid of gesture cards, a trash can, the camera preview and the
activity list. It worked, but it looked cluttered and home-made. Two later
passes added motion, skeleton loaders and a puzzle theme, which helped, but the
result still mixed a toy-like look with a web-dashboard layout, and did not
feel like a Windows program.

palm-lab is a Windows utility. The closest professional product is Microsoft
PowerToys, whose Keyboard Manager also maps inputs to shortcuts. People judge a
utility by whether it looks like it belongs on their system.

## Decision

### Follow Windows 11's own design language

- The layout is Windows 11's navigation view: a sidebar with Gestures and
  Activity at the top and Settings at the bottom, and a content area with a
  slightly lighter surface and a rounded top-left corner.
- Settings use Windows 11 setting cards: an icon, a title, a one-line
  description and the control on the right. They apply as soon as they change;
  there is no Save button.
- Controls follow Fluent: 32px buttons, text boxes with an underline, toggle
  switches with On/Off labels, sliders with a filled track, 4px corners.
- Text uses the Windows type ramp (12 caption, 14 body, 20 subtitle,
  28 title) in Segoe UI Variable.
- The accent colour is the user's own, read from Windows' accent palette: the
  darker shade in the light theme and the lighter shade in the dark theme, as
  Windows does.
- Light and dark themes follow Windows. The title bar is coloured to match the
  page, so the window reads as one surface.
- Interface icons are Microsoft's Fluent System Icons (MIT licensed). The four
  gesture icons are drawn in the same line weight, generated from the five
  finger states the recogniser uses, so a new gesture gets an icon for free.
- Feedback uses Windows patterns: inline info bars next to what they are about,
  and small notifications in the corner for things that happen elsewhere.

### Show only what the task needs

- Each gesture is a collapsible card showing a summary of its actions. Only one
  is open at a time, and the editor exists only inside the open one.
- The live camera view appears inside the Gesture tracking card only while
  tracking is on. The hand skeleton is drawn by the page from the landmarks, in
  the accent colour, rather than baked into the camera image.
- The history of fired gestures has its own Activity page, with a count on the
  sidebar for anything new.
- "Get started" guidance appears only when nothing is set up yet.

### Keep one playful element: the puzzle editor

- Actions are jigsaw pieces: a round tab underneath and a matching socket on
  top. Stacked pieces sit 2px apart, so each tab sits in the next socket with a
  thin seam around it. The tab is a 16px circle centred 5px below the piece,
  which makes its neck narrower than its head, the shape people recognise as a
  jigsaw tab. It is all CSS, with no images.
- The gesture's summary is a small chain of pieces locked together sideways.
- While a piece is dragged over a script, a faded piece in its colour opens a
  slot where it will land. The slot is placed as if it were not there, so
  showing it never moves the target and cannot flicker.
- A piece falls into place with a small overshoot, and makes a soft click.
  Clicks are synthesised with the Web Audio API, so no sound files ship, and a
  "Snap sounds" switch turns them off (`sounds` in `settings.toml`).

### Motion

- Only `transform` and `opacity` animate, except collapsible areas, which
  animate their grid row from `0fr` to `1fr`.
- Interface motion stays under 300 ms with strong ease-out curves. Anything
  that updates many times a second (status, frame rate) does not animate.
- Hover effects apply only to real pointers. With "reduce motion" on in
  Windows, movement becomes short fades.
- At launch the app icon appears, its hand waves twice and the name fades in,
  in about 1.5 seconds. A click or key press skips it.

## Consequences

The window looks like it belongs on Windows 11, in both themes and with any
accent colour, and the playful part is confined to the one place where it
explains something: pieces that fit together are actions that run together.

Fluent is implemented by hand in CSS, not with Microsoft's WinUI controls, so
details such as the exact Mica material cannot be matched; the colours are the
documented Windows 11 values instead.

The splash adds about 1.5 seconds to each launch. It is skippable and
self-contained in the page, so it can be shortened or removed on its own.

Synthesised sounds cannot be tuned by ear from code, so their levels were
checked by rendering them offline; how they feel is best judged on real
speakers, and each is a few numbers in `SOUNDS` in `app.js`.
