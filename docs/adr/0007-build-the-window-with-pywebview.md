# 7. Build the window with pywebview and a plain web page

Date: 2026-09-28

## Status

Accepted

## Context

Until now palm-lab was driven from the command line and a bare OpenCV preview.
Most people will never open a terminal, so the app needs a real window where
they can bind gestures to actions by dragging blocks, start and stop tracking,
see what the camera sees, and change settings.

The window has to be packaged by PyInstaller (see ADR-0006), look at home on
Windows 10 and 11, and stay maintainable by one developer whose code is Python.

The options considered:

- Tkinter ships with Python, but looks dated and drag and drop between custom
  widgets is awkward to build.
- PySide6 (Qt) is powerful and native, but adds well over 100 MB to a build
  that is already 295 MB, and is a large framework to learn on the side.
- Electron or Tauri with Python as a background process means two runtimes,
  two packaging steps and an IPC protocol to maintain.
- A local web server opened in the user's browser is not an app window, and
  can collide with other programs over its port.
- pywebview opens a native window around the WebView2 browser engine that
  Windows 10 and 11 already have, shows a web page in it, and lets that page
  call methods on a Python object.

## Decision

The window is built with pywebview, using its EdgeChromium (WebView2) backend.

The page is plain HTML, CSS and JavaScript in `src/palm_lab/ui/static`, with no
framework and no build step. `load_page` inlines the stylesheet and script into
one page before it is shown, so running from source and running from a
PyInstaller build load it the same way.

Python exposes one class, `palm_lab.ui.api.Api`. Every method takes and returns
plain JSON-like data and never raises: failures come back as
`{"ok": false, "error": "..."}` so the page can always show a message. The
contract is: `get_state`, `save_bindings`, `test_binding`, `save_settings`,
`list_cameras`, `start`, `stop`, `status` and `preview`.

Tracking runs on a background thread inside `TrackingEngine`. The page polls
`status` every 300 ms and `preview` about every 70 ms (a JPEG as a data URL)
rather than Python pushing into the page, so the tracking thread never touches
the window.

Bindings save automatically half a second after the last edit. Python stays the
only validator: when it rejects a save with "Binding N, action M: ...", the
page puts the message on that gesture and outlines that block.

## Consequences

The window adds little to the build, because WebView2 comes with Windows. Very
old Windows 10 installs without it would need Microsoft's Evergreen WebView2
runtime.

The page can be tested without Python: a fake `window.pywebview.api` runs it in
Chromium. That harness is a development tool and is not part of CI yet. The
unit tests guard the joins instead: the page assembles, every element the
script looks up exists, and the files stay ASCII.

JavaScript is not type-checked the way the Python code is. Keeping the page to
one small script with no dependencies limits how much can go wrong there.

Polling costs a little CPU while the window is open. This is negligible next to
hand tracking itself, and polling stops mattering once the window can be
closed to a tray icon.

HTML drag and drop does not work with touch screens, so every drag has a click
alternative: clicking a block in the tray adds it, arrow buttons reorder, and a
remove button deletes.
