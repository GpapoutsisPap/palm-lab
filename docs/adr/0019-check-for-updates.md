# 19. Check GitHub for updates, and only say so

Date: 2026-10-22

## Status

Accepted.

## Context

palm-lab is installed from a GitHub Release (ADR-0009), and each pushed tag
publishes one (ADR-0010). Running a newer installer over an older one already
upgrades in place, because the installer's AppId never changes and settings
live in their own folder. What was missing is any way for people, testers
especially, to find out that a newer version exists.

## Decision

- **Ask GitHub's API, once a day.** `GET /repos/GpapoutsisPap/palm-lab/releases/latest`,
  which already leaves out drafts and pre-releases. No server of our own to
  run, and GitHub's limit (60 unauthenticated requests an hour per address)
  is far above one a day. The first check waits 20 seconds after start so it
  never slows opening the window; a background thread then looks every hour
  whether a day has passed, so a PC left on for a week still hears.
- **Compare version numbers, not text.** "v0.10.0" is newer than "0.9.9".
  Tags that aren't plain X.Y.Z (a future "0.5.0-beta.1") are never offered.
- **Only say so; never install by itself.** A bar on the Gestures page, a line
  in Settings > About, and one notification by the clock per new version.
  "What's new" opens the release page and "Download" the installer, both in
  the browser. Closing the bar hides it until a newer version comes out.
  Installing for the person (a one-click update) can come later, built on
  this.
- **Trust nothing in the answer.** Links from GitHub (and from the saved
  updates.json) are only used if they point into this project's releases,
  because the window opens them.
- **Say what's sent, and allow turning it off.** One HTTPS request carrying
  palm-lab's version as the User-Agent. The README and the setting's own
  description say so; Settings > About > Check for updates is on by default
  and switches it off. This is also what code-signing programmes such as
  SignPath Foundation's ask of open-source apps.
- **Remember the answer** in updates.json beside the settings: when it last
  checked, the latest release and the dismissed version. A failed check
  (offline, rate limited) changes nothing and is simply tried again.

## Consequences

Testers learn about a release within a day of it being published. Every
release now matters to people who installed palm-lab, so the changelog
entry, which becomes the release notes, is what they read first.

The check depends on GitHub's API and on releases keeping the installer's
name (`palm-lab-setup-X.Y.Z.exe`); a release without one still shows "What's
new", just not "Download".
