# 11. Keep running in the notification area

Date: 2026-09-29

## Status

Accepted.

## Context

palm-lab is only useful while it runs, but until now closing the window quit
it, and nothing started it when Windows did. People who want their gestures
available all the time had to keep a window open. The project's goal from the
start included starting with the PC.

## Decision

### Closing can mean "keep running"

A `close_action` setting decides what closing the window does: `ask` (the
default), `background` or `quit`. Asking shows "Keep palm-lab running in the
background?" with Yes, No and "Don't show this again"; ticking it saves the
answer as the setting, which Settings > "When I close the window" can change
back. `palm_lab.ui.lifecycle.Lifecycle` makes this decision and carries it
out through callbacks, so it is tested without a window.

Only a person closing the window is asked or sent to the background. The
decision is hooked on the Windows Forms `FormClosing` event, not pywebview's
`closing` event, because only the former says why the window is closing
(`CloseReason`). When Windows shuts down or an installer closes palm-lab to
update it, it closes, so it can never hold up a shutdown.

While hidden, the engine keeps tracking but stops encoding preview pictures,
since nobody can see them.

### An icon in the notification area

A hidden app has to be findable, so palm-lab puts an icon by the clock, drawn
by [pystray](https://github.com/moses-palmer/pystray) on its own thread.
Clicking it opens the window; its menu toggles tracking and quits. If the icon
cannot be created, closing always quits, because a hidden palm-lab with no
icon could not be found or quit again.

pystray was chosen over writing `Shell_NotifyIcon` calls with ctypes (more
code to get right for no gain) and over pythonnet's `NotifyIcon` (tied to
pywebview's internals and its UI thread). It is LGPL-3.0, which suits an
open-source app; its licence texts ship in the build, and anyone can rebuild
palm-lab with a different pystray.

### One copy at a time

A second copy would fight the first over the camera. The first copy holds a
named mutex (`GpapoutsisPap.palm-lab`); a later launch finds it, signals a
named event, and exits, and the first copy shows its window. The installer's
`AppMutex` uses the same name, so setup notices palm-lab running before it
updates or uninstalls.

### Start with Windows

A Settings switch puts a shortcut in the user's Startup folder, made the same
way as the desktop and Start menu shortcuts (ADR-0009). It runs
`palm-lab ui --background`: the window is created hidden and tracking starts
straight away, with no notification. The uninstaller deletes that shortcut.

A Startup-folder shortcut was chosen over the registry's `Run` key because
the shortcut code already exists, and both appear under Task Manager's
Startup apps, where Windows lets people turn them off.

## Consequences

palm-lab can run all day, starting with Windows, which is what makes gesture
shortcuts dependable.

The camera stays on while palm-lab runs in the background with tracking on;
Windows shows its camera-in-use indicator the whole time.

The native close hook depends on pywebview's Windows Forms backend. Off
Windows, the window falls back to pywebview's `closing` event, without the
shutdown distinction.
