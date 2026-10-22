# 15. A run history, and a pop-up by the clock

Date: 2026-10-22

## Status

Accepted.

## Context

With palm-lab's window closed, nothing showed that a gesture had run, or
that it had failed. The window learned about runs by polling the engine's
single `last_fired` event, so a run could be missed between polls. Windows
also slows a hidden WebView's timers right down, so runs made while the
window was hidden often never reached Activity at all.

Research for this (reports/Palm lab run feedback and actions.md) found:

- Windows notifications for every run are the wrong tool. Each one lands in
  Notification Center, and Microsoft's own guidance warns that too many
  interruptions make people turn an app's notifications off. No comparable
  tool sends one per successful action.
- A second pywebview window makes a poor overlay. Its `show()` always
  activates the window, its first show gives focus to WebView2, and it can't
  keep the window off the taskbar.
- `SHQueryUserNotificationState` is Microsoft's documented way to ask whether
  the user is busy (full-screen game, presentation, Do Not Disturb).

## Decision

- **The engine keeps a short run history.** Each run is numbered and recorded
  when its gesture fires, then completed in place when its pieces finish. A
  version number changes on every change. The last 50 runs are kept.
- **The window catches up from that history**, not from `last_fired`. When
  the status shows a new version, the page fetches `activity()` and adds
  whatever it hasn't seen. Runs from the Run button are recorded too, marked
  as run from the window.
- **"Last ran" on each gesture row comes from those runs.** It's worded as
  GitHub's Primer design system recommends ("just now", "5 minutes ago",
  "yesterday", then a date), with the exact time on hover. Failures read
  "Failed 5 minutes ago" and turn the row's flag red.
- **A small card by the clock** (`run_popup.py` decides, `overlay.py` draws).
  It's a native Win32 window made with ctypes: tool window, topmost,
  layered, click-through and never activated, drawn with GDI, on its own
  thread. A success shows for 2.5 s and a failure for 7 s. A repeat updates
  the same card ("x2") instead of stacking. A run that partly failed says how
  many of its steps failed.
- **It stays quiet when it should.** It doesn't show while palm-lab's own
  window is in front, or for runs from the Run button. When Windows says the
  user is busy, a success is dropped and a failure goes to Windows'
  notifications instead, which Windows holds back until the user is free.
- **A setting**, "When a gesture runs": for every run, only for failures, or
  off.

## Consequences

Activity and "Last ran" no longer miss runs made while the window was hidden.
The card adds no dependency. Its drawing code can only be exercised on
Windows, so its layout maths and its decisions are kept in plain functions
with tests, and a Windows-only smoke test opens and closes the real window.
Still to check on real hardware: whether `SHQueryUserNotificationState` sees
Windows 11's manual Do Not Disturb toggle, and whether Narrator announces
anything from a never-activated window. It probably doesn't, which is one
reason failures also stay in Activity.
