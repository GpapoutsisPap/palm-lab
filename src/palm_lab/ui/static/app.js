/* palm-lab window logic.
 *
 * Talks to Python through window.pywebview.api (see palm_lab/ui/api.py).
 * A Windows 11 style shell with three pages: Gestures, Activity and Settings.
 * Each gesture is an expander holding a script of jigsaw-piece actions.
 * All user-facing text lives in TEXT so the window can be translated later.
 *
 * Interface icons are Fluent UI System Icons, Copyright (c) 2020 Microsoft
 * Corporation, used under the MIT licence (see THIRD_PARTY_NOTICES.md).
 */
"use strict";

const TEXT = {
  switchOff: "Off",
  switchOn: "On",
  starting: "Starting\u2026",
  stopping: "Stopping\u2026",
  trackingDesc: "Watch the camera and run your shortcuts.",
  trackingDescOn: (camera) => `Watching camera ${camera}. Hold a gesture to run it.`,
  navStatus: {
    stopped: "Tracking is off",
    starting: "Starting\u2026",
    stopping: "Stopping\u2026",
    running: "Tracking",
    error: "Camera problem",
  },
  when: "When I show",
  nameLabel: "Name",
  namePlaceholder: "Name this shortcut",
  nameAria: (gesture) => `Name for the ${gesture} shortcut`,
  notSet: "Not set up yet",
  actionCount: (n) => `${n} action${n === 1 ? "" : "s"}`,
  more: (n) => `+${n}`,
  needsTarget: "needs a target",
  stackLabel: (gesture) => `Actions for ${gesture}`,
  dropHere: "Drag an action here",
  palette: "Actions",
  addTo: (action) => `${action}: click to add, or drag into place`,
  test: "Test",
  testing: "Testing\u2026",
  testRan: (name) => `Ran \u201C${name}\u201D`,
  moveUp: "Move up",
  moveDown: "Move down",
  remove: "Remove",
  target: (label) => `${label}: target`,
  saving: "Saving\u2026",
  saved: "All changes saved",
  incomplete: "Fill in the highlighted actions to save",
  saveFailed: "Not saved",
  loadFailed: "Couldn\u2019t load your shortcuts: ",
  movedTo: (label) => `Moved to ${label}`,
  noHands: "No hand in view",
  handInView: "Hand in view",
  fps: (fps) => `${Math.round(fps)} fps`,
  nothingYet: "Nothing yet",
  running: "Running\u2026",
  unbound: "Nothing is set up for this gesture yet.",
  camera: (i) => `Camera ${i}`,
  cameraWorks: (i) => `Camera ${i} (working)`,
  cameraHelp: "The webcam or phone camera palm-lab watches.",
  scanning: "Looking for cameras\u2026",
  scanFound: (n) => (n === 0
    ? "No working camera found. Is DroidCam or your webcam connected?"
    : `Found ${n} working camera${n === 1 ? "" : "s"}.`),
  seconds: (s) => `${Number(s).toFixed(1)} s`,
  cssSaving: "Saving\u2026",
  cssSaved: "Saved",
  cssBlocked: "Custom CSS is off for this run, because palm-lab was started with --no-custom-css. You can still edit it here.",
  cssOff: "Custom CSS is off. Turn it back on in Settings > Appearance.",
  version: (v) => `Version ${v} \u00B7 Open source under the MIT licence.`,
  dismiss: "Dismiss",
  wizardStarting: "Starting camera\u2026",
  wizardHold: (attempt) => (attempt === 1
    ? "Hold your gesture steady\u2026"
    : "Now hold the same shape again to confirm\u2026"),
  wizardRelease: "Relax your hand, then make the same shape again",
  wizardMismatch: "That didn\u2019t match \u2014 let\u2019s try both holds again",
  wizardDone: "Got it!",
  wizardTakenStage: "You already have this gesture",
  wizardTaken: (label) => `That shape is already your \u201C${label}\u201D gesture. `
    + "Try a different combination of fingers.",
  wizardNameRequired: "Give this gesture a name before saving.",
  removeGesture: "Remove gesture",
  gestureAdded: (name) => `Added \u201C${name}\u201D`,
  gestureRemoved: (name) => `Removed \u201C${name}\u201D`,
};

// Finger states are [thumb, index, middle, ring, pinky]; they drive the glyphs.
const GESTURES = {
  peace: { label: "Peace sign", fingers: [0, 1, 1, 0, 0] },
  fist: { label: "Fist", fingers: [0, 0, 0, 0, 0] },
  open_palm: { label: "Open palm", fingers: [1, 1, 1, 1, 1] },
  thumbs_up: { label: "Thumbs up", fingers: [1, 0, 0, 0, 0] },
};

const ACTIONS = {
  launch: { label: "Open app", icon: "app", placeholder: "Steam, Spotify, notepad\u2026", list: "known-apps", input: "text" },
  open_url: { label: "Open website", icon: "globe", placeholder: "https://youtube.com", list: null, input: "url" },
  hotkey: { label: "Press keys", icon: "keyboard", placeholder: "media_play_pause or ctrl+alt+t", list: "hotkey-presets", input: "text" },
};

const HOTKEY_LABELS = {
  media_play_pause: "Play / pause",
  media_next: "Next track",
  media_previous: "Previous track",
  volume_up: "Volume up",
  volume_down: "Volume down",
  volume_mute: "Mute",
  "win+d": "Show desktop",
  "alt+tab": "Switch window",
  "ctrl+alt+t": "Ctrl + Alt + T",
};

// MediaPipe's 21 hand landmarks, joined into a skeleton.
const HAND_BONES = [
  [0, 1], [1, 2], [2, 3], [3, 4], [0, 5], [5, 6], [6, 7], [7, 8], [5, 9], [9, 10], [10, 11],
  [11, 12], [9, 13], [13, 14], [14, 15], [15, 16], [13, 17], [17, 18], [18, 19], [19, 20], [0, 17],
];
const FINGERTIPS = new Set([4, 8, 12, 16, 20]);

/* Fluent UI System Icons: [viewBox size, path data]. */
const ICONS = {
  nav_gestures: [20, ["M15.85 1.14a.5.5 0 0 0-.7 0 .5.5 0 0 0 0 .72 6.6 6.6 0 0 1 1.86 5.56.5.5 0 0 0 .42.58.5.5 0 0 0 .56-.42 7.6 7.6 0 0 0-2.14-6.44M4.63 3.04a1.6 1.6 0 0 1 3.04-.63 1.6 1.6 0 0 1 2.59.7l.08.27a1.6 1.6 0 0 1 2.55.73l1.07 3.23.58 1.7a8.5 8.5 0 0 1 .38 3.9l-.27 2a2.5 2.5 0 0 1-1.51 1.96l-2.16.9c-.97.4-2.07.15-2.8-.55-3.12-2.99-5.88-3.97-6.65-4.2-.35-.11-.66-.52-.47-.98.15-.35.51-.97 1.28-1.32.6-.26 1.36-.33 2.35-.06L2.77 5.1a1.6 1.6 0 0 1 1.02-2.03q.43-.13.84-.04m2.15 3.64.55 1.68a.5.5 0 1 1-.95.31l-.57-1.72-.95-2.52a.6.6 0 0 0-.76-.4.6.6 0 0 0-.38.76l2.25 6.55a.5.5 0 0 1-.67.62c-1.33-.57-2.11-.49-2.55-.3q-.44.23-.62.53a19 19 0 0 1 6.74 4.33c.47.46 1.15.6 1.72.36l2.16-.9c.5-.2.84-.66.9-1.18l.28-1.99a7.5 7.5 0 0 0-.34-3.44l-.58-1.7v-.01l-1.07-3.24a.6.6 0 0 0-1.16.3l.85 2.62a.5.5 0 0 1-.95.31L9.85 5.1l-.04-.13-.5-1.56a.6.6 0 0 0-1.15.38l.6 1.85.03.11.53 1.6a.5.5 0 1 1-.95.3L6.79 2.92a.6.6 0 0 0-1.13.38l1.1 3.33zm7.46-3.61a.5.5 0 0 1 .69.17l.3.5c.5.83.76 1.78.77 2.75a.5.5 0 1 1-1 .01c0-.79-.22-1.57-.63-2.25l-.3-.5a.5.5 0 0 1 .17-.68"]],
  nav_activity: [20, ["M10 4a6 6 0 1 1-5.98 5.54.5.5 0 1 0-1-.08L3 10a7 7 0 1 0 2-4.9V3.5a.5.5 0 0 0-1 0v3c0 .28.22.5.5.5h3a.5.5 0 0 0 0-1H5.53c1.1-1.23 2.7-2 4.47-2m0 2.5a.5.5 0 0 0-1 0v4c0 .28.22.5.5.5h3a.5.5 0 0 0 0-1H10z"]],
  nav_settings: [20, ["M1.91 7.38A8.5 8.5 0 0 1 3.7 4.3a.5.5 0 0 1 .54-.13l1.92.68a1 1 0 0 0 1.32-.76l.36-2a.5.5 0 0 1 .4-.4 9 9 0 0 1 3.55 0q.32.08.38.4l.37 2a1 1 0 0 0 1.32.76l1.92-.68a.5.5 0 0 1 .54.13 8.5 8.5 0 0 1 1.78 3.08q.08.31-.15.54l-1.56 1.32a1 1 0 0 0 0 1.52l1.56 1.32a.5.5 0 0 1 .15.54 8.5 8.5 0 0 1-1.78 3.08.5.5 0 0 1-.54.13l-1.92-.68a1 1 0 0 0-1.32.76l-.37 2a.5.5 0 0 1-.38.4 8.5 8.5 0 0 1-3.56 0 .5.5 0 0 1-.39-.4l-.36-2a1 1 0 0 0-1.32-.76l-1.92.68a.5.5 0 0 1-.54-.13 8.5 8.5 0 0 1-1.78-3.08.5.5 0 0 1 .15-.54l1.56-1.32a1 1 0 0 0 0-1.52L2.06 7.92a.5.5 0 0 1-.15-.54m1.06 0 1.3 1.1a2 2 0 0 1 0 3.04l-1.3 1.1q.45 1.19 1.25 2.16l1.6-.58a2 2 0 0 1 2.63 1.53l.3 1.67a8 8 0 0 0 2.5 0l.3-1.67a2 2 0 0 1 2.64-1.53l1.6.58a8 8 0 0 0 1.24-2.16l-1.3-1.1a2 2 0 0 1 0-3.04l1.3-1.1a8 8 0 0 0-1.25-2.16l-1.6.58a2 2 0 0 1-2.63-1.53l-.3-1.67a8 8 0 0 0-2.5 0l-.3 1.67A2 2 0 0 1 5.81 5.8l-1.6-.58a8 8 0 0 0-1.24 2.16M7.5 10a2.5 2.5 0 1 1 5 0 2.5 2.5 0 0 1-5 0m1 0a1.5 1.5 0 1 0 3 0 1.5 1.5 0 0 0-3 0"]],
  video: [20, ["M5 4a3 3 0 0 0-3 3v6a3 3 0 0 0 3 3h5a3 3 0 0 0 3-3v-.32l3.04 2.1c.83.57 1.96-.03 1.96-1.03v-7.5c0-1-1.13-1.6-1.96-1.03L13 7.32V7a3 3 0 0 0-3-3zm8 4.54 3.6-2.5c.17-.1.4.01.4.21v7.5c0 .2-.23.32-.4.2L13 11.46zM3 7c0-1.1.9-2 2-2h5a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"]],
  camera: [20, ["M10 6a4 4 0 1 0 0 8 4 4 0 0 0 0-8m-3 4a3 3 0 1 1 6 0 3 3 0 0 1-6 0m1.12-8a1.5 1.5 0 0 0-1.34.83L6.2 4H4.5A2.5 2.5 0 0 0 2 6.5v8A2.5 2.5 0 0 0 4.5 17h11a2.5 2.5 0 0 0 2.5-2.5v-8A2.5 2.5 0 0 0 15.5 4h-1.69l-.58-1.17A1.5 1.5 0 0 0 11.89 2zm-.44 1.28A.5.5 0 0 1 8.12 3h3.77q.3 0 .45.28l.72 1.44a.5.5 0 0 0 .45.28h2c.82 0 1.5.67 1.5 1.5v8c0 .83-.68 1.5-1.5 1.5h-11A1.5 1.5 0 0 1 3 14.5v-8C3 5.67 3.67 5 4.5 5h2a.5.5 0 0 0 .44-.28z"]],
  timer: [20, ["M7.5 2a.5.5 0 0 0 0 1h4a.5.5 0 0 0 0-1zm7.66 1.93a.5.5 0 1 0-.71.7l1.41 1.42a.5.5 0 1 0 .71-.7zM9.5 6a.5.5 0 0 0-.5.5v5a.5.5 0 0 0 1 0v-5a.5.5 0 0 0-.5-.5m0 12a7 7 0 1 0 0-14 7 7 0 0 0 0 14m0-1a6 6 0 1 1 0-12 6 6 0 0 1 0 12"]],
  cooldown: [20, ["M16.5 6.67a.5.5 0 0 1 .3.1l.08.07.01.02A5 5 0 0 1 13.22 15L13 15H6.7l1.65 1.65c.18.17.2.44.06.63l-.06.07a.5.5 0 0 1-.63.06l-.07-.06-2.5-2.5a.5.5 0 0 1-.06-.63l.06-.07 2.5-2.5a.5.5 0 0 1 .76.63l-.06.07L6.72 14h.14L7 14h6a4 4 0 0 0 3.11-6.52.5.5 0 0 1 .39-.81m-4.85-4.02a.5.5 0 0 1 .63-.06l.07.06 2.5 2.5.06.07a.5.5 0 0 1 0 .56l-.06.07-2.5 2.5-.07.06a.5.5 0 0 1-.56 0l-.07-.06-.06-.07a.5.5 0 0 1 0-.56l.06-.07L13.28 6h-.14L13 6H7a4 4 0 0 0-3.1 6.52q.1.14.1.31a.5.5 0 0 1-.9.3A4.99 4.99 0 0 1 6.77 5h6.52l-1.65-1.65-.06-.07a.5.5 0 0 1 .06-.63"]],
  speaker: [20, ["M12 3a1 1 0 0 0-1.68-.73l-3.88 3.6A.5.5 0 0 1 6.1 6H3.5C2.67 6 2 6.67 2 7.5v5c0 .83.67 1.5 1.5 1.5h2.6a.5.5 0 0 1 .34.13l3.88 3.6a1 1 0 0 0 1.68-.74zM7.12 6.6 11 3v14l-3.88-3.6A1.5 1.5 0 0 0 6.1 13H3.5a.5.5 0 0 1-.5-.5v-5c0-.28.22-.5.5-.5h2.6c.38 0 .75-.14 1.02-.4m8.14-1.97a.5.5 0 0 1 .7.04 8 8 0 0 1 0 10.66.5.5 0 0 1-.74-.66 7 7 0 0 0 0-9.34.5.5 0 0 1 .04-.7m-1.18 8.3a.5.5 0 0 1-.18-.68 4.5 4.5 0 0 0 0-4.5.5.5 0 1 1 .86-.5 5.5 5.5 0 0 1 0 5.5.5.5 0 0 1-.68.18"]],
  desktop: [20, ["M4 2a2 2 0 0 0-2 2v9c0 1.1.9 2 2 2h3v2H5.5a.5.5 0 0 0 0 1h9a.5.5 0 0 0 0-1H13v-2h3a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2zm8 13v2H8v-2zM3 4a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z"]],
  start: [20, ["M2 3.5C2 2.67 2.67 2 3.5 2h1C5.33 2 6 2.67 6 3.5v1C6 5.33 5.33 6 4.5 6h-1A1.5 1.5 0 0 1 2 4.5zM3.5 3a.5.5 0 0 0-.5.5v1c0 .28.22.5.5.5h1a.5.5 0 0 0 .5-.5v-1a.5.5 0 0 0-.5-.5zM2 9.5C2 8.67 2.67 8 3.5 8h1C5.33 8 6 8.67 6 9.5v1c0 .83-.67 1.5-1.5 1.5h-1A1.5 1.5 0 0 1 2 10.5zM3.5 9a.5.5 0 0 0-.5.5v1c0 .28.22.5.5.5h1a.5.5 0 0 0 .5-.5v-1a.5.5 0 0 0-.5-.5zM2 15.5c0-.83.67-1.5 1.5-1.5h1c.83 0 1.5.67 1.5 1.5v1c0 .83-.67 1.5-1.5 1.5h-1A1.5 1.5 0 0 1 2 16.5zm1.5-.5a.5.5 0 0 0-.5.5v1c0 .28.22.5.5.5h1a.5.5 0 0 0 .5-.5v-1a.5.5 0 0 0-.5-.5zM8 4.5c0-.28.22-.5.5-.5h9a.5.5 0 0 1 0 1h-9a.5.5 0 0 1-.5-.5m0 6c0-.28.22-.5.5-.5h9a.5.5 0 0 1 0 1h-9a.5.5 0 0 1-.5-.5m0 6c0-.28.22-.5.5-.5h9a.5.5 0 0 1 0 1h-9a.5.5 0 0 1-.5-.5"]],
  power: [20, ["M10.5 2.5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0zM13.74 4a.5.5 0 1 0-.5.87 6.5 6.5 0 1 1-6.49 0 .5.5 0 1 0-.5-.87 7.5 7.5 0 1 0 7.5 0"]],
  window: [20, ["M6 3a3 3 0 0 0-3 3v8a3 3 0 0 0 3 3h8a3 3 0 0 0 3-3V6a3 3 0 0 0-3-3zM4 6c0-1.1.9-2 2-2h8a2 2 0 0 1 2 2zm0 1h12v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z"]],
  paint: [20, ["M5.5 2a.5.5 0 0 0-.5.5V11c0 1.1.9 2 2 2h1v3a2 2 0 1 0 4 0v-3h1a2 2 0 0 0 2-2V2.5a.5.5 0 0 0-.5-.5zm.5 8h8v1a1 1 0 0 1-1 1h-1.5a.5.5 0 0 0-.5.5V16a1 1 0 1 1-2 0v-3.5a.5.5 0 0 0-.5-.5H7a1 1 0 0 1-1-1zm8-1H6V3h4v1.5a.5.5 0 0 0 1 0V3h1v2.5a.5.5 0 0 0 1 0V3h1z"]],
  theme: [20, ["M10 3a7 7 0 1 1 0 14zm0-1a8 8 0 1 0 0 16 8 8 0 0 0 0-16"]],
  code: [20, ["M12.64 1.02a.5.5 0 0 1 .34.62l-5 17a.5.5 0 0 1-.96-.28l5-17a.5.5 0 0 1 .62-.34M5.13 5.17a.5.5 0 0 1 .74.66L2.17 10l3.7 4.17a.5.5 0 0 1-.74.66l-4-4.5a.5.5 0 0 1 0-.66zm9.04-.04a.5.5 0 0 1 .7.04l4 4.5a.5.5 0 0 1 0 .66l-4 4.5a.5.5 0 0 1-.74-.66l3.7-4.17-3.7-4.17a.5.5 0 0 1 .04-.7"]],
  folder: [20, ["M3 5.5v6.6l1.5-2.6A3 3 0 0 1 7.1 8H15v-.5c0-.83-.67-1.5-1.5-1.5h-4a.5.5 0 0 1-.35-.15l-1.71-1.7A.5.5 0 0 0 7.09 4H4.5C3.67 4 3 4.67 3 5.5m1.28 10.48.22.02h9.4a2 2 0 0 0 1.73-1l2.17-3.75A1.5 1.5 0 0 0 16.5 9H7.1a2 2 0 0 0-1.73 1L3.2 13.75a1.5 1.5 0 0 0 1.08 2.23M2 14.46V5.5A2.5 2.5 0 0 1 4.5 3h2.59c.4 0 .78.16 1.06.44L9.7 5h3.79A2.5 2.5 0 0 1 16 7.5V8h.5a2.5 2.5 0 0 1 2.16 3.75L16.5 15.5a3 3 0 0 1-2.6 1.5H4.5a2.5 2.5 0 0 1-1.62-.6A2.5 2.5 0 0 1 2 14.46"]],
  open: [16, ["M4.5 3C3.67 3 3 3.67 3 4.5v7c0 .83.67 1.5 1.5 1.5h7c.83 0 1.5-.67 1.5-1.5V9.27a.5.5 0 0 1 1 0v2.23a2.5 2.5 0 0 1-2.5 2.5h-7A2.5 2.5 0 0 1 2 11.5v-7A2.5 2.5 0 0 1 4.5 2h2.23a.5.5 0 0 1 0 1zm4.27-.5c0-.28.22-.5.5-.5h4.23c.28 0 .5.22.5.5v4.23a.5.5 0 0 1-1 0V3.71L9.62 7.08a.5.5 0 1 1-.7-.7L12.29 3H9.27a.5.5 0 0 1-.5-.5"]],
  chevron: [16, ["M3.15 5.65c.2-.2.5-.2.7 0L8 9.79l4.15-4.14a.5.5 0 0 1 .7.7l-4.5 4.5a.5.5 0 0 1-.7 0l-4.5-4.5a.5.5 0 0 1 0-.7"]],
  close: [16, ["m2.59 2.72.06-.07a.5.5 0 0 1 .63-.06l.07.06L8 7.29l4.65-4.64a.5.5 0 0 1 .7.7L8.71 8l4.64 4.65c.18.17.2.44.06.63l-.06.07a.5.5 0 0 1-.63.06l-.07-.06L8 8.71l-4.65 4.64a.5.5 0 0 1-.7-.7L7.29 8 2.65 3.35a.5.5 0 0 1-.06-.63l.06-.07z"]],
  grip: [16, ["M6 5a1 1 0 1 0 0-2 1 1 0 0 0 0 2m0 4a1 1 0 1 0 0-2 1 1 0 0 0 0 2m1 3a1 1 0 1 1-2 0 1 1 0 0 1 2 0m3-7a1 1 0 1 0 0-2 1 1 0 0 0 0 2m1 3a1 1 0 1 1-2 0 1 1 0 0 1 2 0m-1 5a1 1 0 1 0 0-2 1 1 0 0 0 0 2"]],
  up: [16, ["M7.5 13.5a.5.5 0 0 0 1 0V3.8l3.63 4.03a.5.5 0 0 0 .74-.66l-4.5-5a.5.5 0 0 0-.74 0l-4.5 5a.5.5 0 0 0 .74.66L7.5 3.8z"]],
  down: [16, ["M8.5 2.5a.5.5 0 1 0-1 0v9.7L3.87 8.17a.5.5 0 1 0-.74.66l4.5 5a.5.5 0 0 0 .74 0l4.5-5a.5.5 0 0 0-.74-.66L8.5 12.2z"]],
  bolt: [16, ["M4.91 1.71A1 1 0 0 1 5.87 1h4.4a1 1 0 0 1 .94 1.35L10.22 5h2.03c.63 0 .98.73.59 1.22l-6.6 8.3c-.86 1.07-2.57.18-2.19-1.13L5.33 9H3.75a.75.75 0 0 1-.72-.96zm5.37.29h-4.4l-1.8 6H6a.5.5 0 0 1 .48.64l-1.47 5.03a.2.2 0 0 0 .01.17q.03.08.12.12t.16.03.15-.1L11.73 6H9.5a.5.5 0 0 1-.47-.68z"]],
  refresh: [16, ["M3 8a5 5 0 0 1 9-3h-2a.5.5 0 0 0 0 1h3a.5.5 0 0 0 .5-.5v-3a.5.5 0 0 0-1 0v1.53A5.99 5.99 0 0 0 2 8a6 6 0 0 0 11.98.54.5.5 0 0 0-1-.08A5 5 0 0 1 3 8"]],
  check: [16, ["M13.86 3.66a.5.5 0 0 1-.02.7l-7.93 7.48a.6.6 0 0 1-.84-.02L2.4 9.1a.5.5 0 0 1 .72-.7l2.4 2.44 7.65-7.2a.5.5 0 0 1 .7.02"]],
  info: [16, ["M8 1a7 7 0 1 1 0 14A7 7 0 0 1 8 1m0 5.25a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5m.5 1.25a.5.5 0 0 0-1 0v3a.5.5 0 0 0 1 0z"]],
  warning: [16, ["M5.82 2.28a2.5 2.5 0 0 1 4.36 0l4.5 8A2.5 2.5 0 0 1 12.5 14h-9a2.5 2.5 0 0 1-2.18-3.72zM8 9.5A.75.75 0 1 0 8 11a.75.75 0 0 0 0-1.5M8 5a.5.5 0 0 0-.5.5V8a.5.5 0 0 0 1 0V5.5A.5.5 0 0 0 8 5"]],
  error: [16, ["M8 1a7 7 0 1 1 0 14A7 7 0 0 1 8 1m0 9a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5m0-5.5a.5.5 0 0 0-.5.5v3.59a.5.5 0 0 0 1-.09V4.91A.5.5 0 0 0 8 4.5"]],
  success: [16, ["M1 8a7 7 0 1 1 14 0A7 7 0 0 1 1 8m9.85-1.15a.5.5 0 0 0-.7-.7l-2.9 2.9-1.4-1.4a.5.5 0 1 0-.7.7L6.9 10.1c.2.2.5.2.7 0z"]],
  puzzle: [16, ["M7 3a2 2 0 0 1 4 0h1.5c.83 0 1.5.67 1.5 1.5V7h-1a1 1 0 0 0 0 2h1v2.5c0 .83-.67 1.5-1.5 1.5H11a2 2 0 0 1-4 0H5.5A1.5 1.5 0 0 1 4 11.5V10a2 2 0 0 1 0-4V4.5C4 3.67 4.67 3 5.5 3zm2-1a1 1 0 0 0-1 1v1H5.5a.5.5 0 0 0-.5.5V7H4a1 1 0 0 0 0 2h1v2.5c0 .28.22.5.5.5H8v1a1 1 0 0 0 2 0v-1h2.5a.5.5 0 0 0 .5-.5V10a2 2 0 0 1 0-4V4.5a.5.5 0 0 0-.5-.5H10V3a1 1 0 0 0-1-1"]],
  app: [16, ["M4.5 2A2.5 2.5 0 0 0 2 4.5v7A2.5 2.5 0 0 0 4.5 14h7a2.5 2.5 0 0 0 2.5-2.5v-7A2.5 2.5 0 0 0 11.5 2zM13 5H3v-.5C3 3.67 3.67 3 4.5 3h7c.83 0 1.5.67 1.5 1.5zM3 6h10v5.5c0 .83-.67 1.5-1.5 1.5h-7A1.5 1.5 0 0 1 3 11.5z"]],
  globe: [16, ["M8 14A6 6 0 1 0 8 2a6 6 0 0 0 0 12M8 3c.37 0 .88.36 1.31 1.32q.14.3.26.68H6.43q.12-.37.26-.68C7.12 3.36 7.63 3 8 3m-2.22.9q-.23.5-.4 1.1H4a5 5 0 0 1 2.04-1.6q-.14.24-.26.5M5.16 6a12 12 0 0 0 0 4H3.42a5 5 0 0 1 0-4zm.22 5a8 8 0 0 0 .66 1.6A5 5 0 0 1 4 11zm1.05 0h3.14a6 6 0 0 1-.26.68C8.88 12.64 8.37 13 8 13s-.88-.36-1.31-1.32a6 6 0 0 1-.26-.68m3.4-1H6.17a11 11 0 0 1 0-4h3.64a11 11 0 0 1 0 4m.79 1H12a5 5 0 0 1-2.04 1.6q.15-.24.26-.5.23-.5.4-1.1m1.96-1h-1.74a12 12 0 0 0 0-4h1.74a5 5 0 0 1 0 4M9.96 3.4c.81.35 1.52.9 2.04 1.6h-1.38a8 8 0 0 0-.66-1.6"]],
  keyboard: [16, ["M3 10.5c0-.28.22-.5.5-.5h9a.5.5 0 0 1 0 1h-9a.5.5 0 0 1-.5-.5M3.25 7a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5M10 6.25a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 0M6.25 7a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5M13 6.25a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 0M5.25 9a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5M9 8.25a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 0m2.25.75a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5M1 4.75C1 3.78 1.78 3 2.75 3h10.5c.97 0 1.75.78 1.75 1.75v6.5c0 .97-.78 1.75-1.75 1.75H2.75C1.78 13 1 12.22 1 11.25zM2.75 4a.75.75 0 0 0-.75.75v6.5c0 .41.34.75.75.75h10.5c.41 0 .75-.34.75-.75v-6.5a.75.75 0 0 0-.75-.75z"]],
  add: [16, ["M8 2c.28 0 .5.22.5.5v5h5a.5.5 0 0 1 0 1h-5v5a.5.5 0 0 1-1 0v-5h-5a.5.5 0 0 1 0-1h5v-5c0-.28.22-.5.5-.5"]],
};

const SAVE_DELAY_MS = 500;
const STATUS_INTERVAL_MS = 300;
const PREVIEW_INTERVAL_MS = 70;
const ACTIVITY_LIMIT = 50;
const TOAST_LIMIT = 3;
const SPLASH_FALLBACK_MS = 2600;
const EASE_OUT = "cubic-bezier(0.23, 1, 0.32, 1)";
const EASE_IN_OUT = "cubic-bezier(0.77, 0, 0.175, 1)";
const STACK_GAP = 2;               // px between stacked pieces, as in app.css
const SNAP_SOUND_DELAY = 0.14;     // s: lands with the overshoot in snapIn()
const ARROW_SOUND_DELAY = 0.17;    // s: lands as a reordered piece settles
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
const darkTheme = window.matchMedia("(prefers-color-scheme: dark)");

const app = {
  data: null,          // state from Python
  rows: [],            // [{gesture, name, stepDelay, actions: [{id, type, target}]}]
  open: null,          // gesture whose row is expanded
  page: "gestures",
  status: null,
  startError: null,    // why the last start failed, shown in the tracking card
  seen: null,
  drag: null,          // {kind: "new", type} or {kind: "move", gesture, id, type}
  saveTimer: null,
  saveRequest: 0,
  lastEvent: null,     // {at, finished} of the newest fired gesture
  unread: 0,
  previewing: false,
  hasFrame: false,
  busy: false,
  nextId: 1,
  shortcutsLoaded: false,
  css: {                 // the user's custom CSS
    style: null,         // the <style> element it is applied through
    text: "",
    allowed: true,       // false when started with --no-custom-css
    saveTimer: null,
    saveRequest: 0,
  },
  wizard: {              // state for the "Add gesture" wizard, while it's open
    open: false,
    polling: false,
    hasFrame: false,
    fingers: null,        // the finished capture's finger tuple, once stage is "done"
    wasRunning: false,    // whether tracking was already on before the wizard started it
  },
};

const $ = (id) => document.getElementById(id);
const api = () => window.pywebview.api;
const sleep = (ms) => new Promise((resolve) => { setTimeout(resolve, ms); });

/* Building blocks ----------------------------------------------------------- */

function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === undefined || value === null) continue;
    if (key === "class") node.className = value;
    else if (key === "dataset") Object.assign(node.dataset, value);
    else if (key === "html") node.innerHTML = value; // only ever trusted SVG built in this file
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else if (key in node) node[key] = value;
    else node.setAttribute(key, value);
  }
  for (const child of [].concat(children)) {
    if (child !== null && child !== undefined && child !== false) node.append(child);
  }
  return node;
}

function icon(name, extraClass = "") {
  if (name === "spinner") {
    return `<svg class="icon spin ${extraClass}" viewBox="0 0 16 16" aria-hidden="true" focusable="false">`
      + '<circle cx="8" cy="8" r="6.25" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-dasharray="26 40"/></svg>';
  }
  const [size, paths] = ICONS[name];
  return `<svg class="icon ${extraClass}" viewBox="0 0 ${size} ${size}" aria-hidden="true" focusable="false">`
    + paths.map((d) => `<path d="${d}"/>`).join("") + "</svg>";
}

function iconEl(name, className = "") {
  return el("span", { class: className, "aria-hidden": "true", html: icon(name) });
}

/* A gesture glyph drawn from its five finger states: the outline of the union
   of simple shapes (see .glyph in app.css), so new gestures get one too. */
function glyph(fingers) {
  const [thumb, ...rest] = fingers;
  const w = 2.1;
  const r = (v) => Math.round(v * 100) / 100;
  const shapes = [];
  const details = [];
  if (thumb && rest.every((up) => !up)) {
    shapes.push('<rect x="12.5" y="7" width="8" height="19" rx="4" transform="rotate(-14 16.5 26)"/>');
    shapes.push('<rect x="11" y="21" width="20" height="20" rx="6"/>');
    for (const [y, x2] of [[21, 36], [26.3, 37], [31.6, 36.5], [36.9, 34.5]]) {
      shapes.push(`<rect x="22" y="${y}" width="${x2 - 22}" height="${r(5.3 - w)}" rx="${r((5.3 - w) / 2)}"/>`);
    }
    shapes.push('<rect x="13" y="38" width="12" height="8" rx="2"/>');
  } else {
    const cx = [15.2, 21.4, 27.6, 33.8];
    const top = [9, 5.5, 7.5, 12];
    const width = r(6.2 - w);
    const vee = !thumb && rest[0] && rest[1] && !rest[2] && !rest[3];
    rest.forEach((up, i) => {
      const y = up ? top[i] : 17.5;
      const angle = up ? (vee ? [-10, 9][i] : [-5, -1.5, 1.5, 5][i]) : 0;
      shapes.push(`<rect x="${r(cx[i] - width / 2)}" y="${y}" width="${width}" height="${r(28 - y)}" rx="${width / 2}" transform="rotate(${angle} ${cx[i]} 28)"/>`);
    });
    if (thumb) shapes.push('<rect x="-2.6" y="-14" width="5.2" height="14" rx="2.6" transform="translate(14 34) rotate(-42)"/>');
    shapes.push('<rect x="12" y="22" width="25" height="19" rx="7.5"/>');
    shapes.push('<rect x="17" y="36" width="15" height="10" rx="2"/>');
    if (!thumb) details.push('<path d="M12.6 31.5c3.2-2.4 8.4-3.2 13.2-2"/>');
  }
  const body = shapes.join("");
  return `<svg class="glyph" viewBox="0 0 48 48" aria-hidden="true" focusable="false"><g class="glyph-ink">${body}</g>`
    + `<g class="glyph-fill">${body}</g><g class="glyph-detail">${details.join("")}</g></svg>`;
}

/* The app icon, with its own ids so several copies can share a page. */
function appIcon(id) {
  return `<svg viewBox="0 0 48 48" aria-hidden="true" focusable="false"><defs>`
    + `<linearGradient id="${id}-tile" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#6E6BFF"/><stop offset="1" stop-color="#4338CA"/></linearGradient>`
    + `<clipPath id="${id}-clip"><rect x="2" y="2" width="44" height="44" rx="11"/></clipPath></defs>`
    + `<rect x="2" y="2" width="44" height="44" rx="11" fill="url(#${id}-tile)"/>`
    + `<g clip-path="url(#${id}-clip)" fill="#fff"><g transform="translate(0.8 1) rotate(-6 25 40)">`
    + '<rect x="13.80" y="12.5" width="5.2" height="18.5" rx="2.6" transform="rotate(-7 16.4 31)"/>'
    + '<rect x="19.70" y="8.5" width="5.2" height="22.5" rx="2.6" transform="rotate(-2.5 22.3 31)"/>'
    + '<rect x="25.60" y="10" width="5.2" height="21" rx="2.6" transform="rotate(2 28.2 31)"/>'
    + '<rect x="31.40" y="14.5" width="5.2" height="16.5" rx="2.6" transform="rotate(6.5 34 31)"/>'
    + '<rect x="-2.7" y="-11.5" width="5.4" height="13" rx="2.7" transform="translate(15.6 34.5) rotate(-46)"/>'
    + '<path d="M17.4 25H33a4 4 0 0 1 4 4v2.5c0 5-1.4 9.5-3.5 12.5V54H17V44c-2.2-3.2-3.6-7.2-3.6-12.5V29a4 4 0 0 1 4-4z"/>'
    + "</g></g></svg>";
}

function gestureInfo(id) {
  return GESTURES[id] || { label: String(id).replace(/_/g, " "), fingers: [1, 1, 1, 1, 1] };
}

/* A gesture recorded through the wizard: its name doubles as its id and its
   label, and .custom marks it so the editor offers to remove it. */
function registerCustomGestures(customGestures) {
  for (const gesture of customGestures) {
    GESTURES[gesture.name] = { label: gesture.name, fingers: gesture.fingers, custom: true };
  }
}

function shortTarget(action) {
  const target = action.target.trim();
  if (!target) return TEXT.needsTarget;
  if (action.type === "open_url") {
    try {
      return new URL(target).hostname.replace(/^www\./, "") || target;
    } catch (err) {
      return target;
    }
  }
  if (action.type === "hotkey") return HOTKEY_LABELS[target.toLowerCase()] || target;
  const base = target.split(/[\\/]/).pop();
  return base.replace(/\.(exe|lnk|url)$/i, "") || target;
}

function clock(seconds) {
  return new Date(seconds * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

/* Motion helpers -------------------------------------------------------------- */

function enter(node, delay = 0) {
  const frames = reducedMotion.matches
    ? [{ opacity: 0 }, { opacity: 1 }]
    : [{ opacity: 0, transform: "scale(0.96)" }, { opacity: 1, transform: "none" }];
  node.animate(frames, { duration: 200, delay, easing: EASE_OUT, fill: "backwards" });
}

/* A piece dropping into its socket: a short fall, a tiny overshoot, then still. */
function snapIn(node) {
  const frames = reducedMotion.matches
    ? [{ opacity: 0 }, { opacity: 1 }]
    : [
      { opacity: 0, transform: "translateY(-10px)", easing: EASE_OUT },
      { opacity: 1, transform: "translateY(1.5px)", offset: 0.7, easing: "ease-out" },
      { opacity: 1, transform: "none" },
    ];
  node.animate(frames, { duration: 200 });
}

/* A piece coming off: it lifts away and fades. */
function unsnap(node) {
  const frames = reducedMotion.matches
    ? [{ opacity: 1 }, { opacity: 0 }]
    : [{ opacity: 1, transform: "none" }, { opacity: 0, transform: "translate(8px, -4px) rotate(2deg)" }];
  return node.animate(frames, { duration: 150, easing: EASE_OUT, fill: "forwards" }).finished.catch(() => {});
}

/* A one-off ring pulse on a gesture: when it runs, is tested, or gets a piece. */
function pulse(node, color) {
  if (!node) return;
  node.style.setProperty("--pulse", color);
  const frames = reducedMotion.matches
    ? [{ opacity: 1 }, { opacity: 0 }]
    : [{ opacity: 1, transform: "scale(1)" }, { opacity: 0, transform: "scale(1.012)" }];
  node.animate(frames, { duration: 600, easing: EASE_OUT, pseudoElement: "::before" });
}

/* Sound ------------------------------------------------------------------------ */

/* Small clicks made with the Web Audio API, so no sound files ship with the app.
   Each one is a burst of filtered noise (the click) over a short falling tone
   (the body), which reads as plastic pieces meeting. */
const sound = {
  ctx: null,
  out: null,
  noise: null,

  enabled() {
    return !app.data || app.data.settings.sounds !== false;
  },

  context() {
    if (!this.ctx) {
      const Context = window.AudioContext || window.webkitAudioContext;
      if (!Context) return null;
      this.ctx = new Context();
      this.out = this.ctx.createGain();
      this.out.gain.value = 0.55;
      this.out.connect(this.ctx.destination);
      const length = Math.round(this.ctx.sampleRate * 0.05);
      this.noise = this.ctx.createBuffer(1, length, this.ctx.sampleRate);
      const samples = this.noise.getChannelData(0);
      for (let i = 0; i < length; i += 1) samples[i] = Math.random() * 2 - 1;
    }
    if (this.ctx.state === "suspended") this.ctx.resume();
    return this.ctx;
  },

  play(name, { delay = 0, force = false } = {}) {
    if (!force && !this.enabled()) return;
    try {
      const ctx = this.context();
      if (ctx) SOUNDS[name](ctx, this.out, this.noise, ctx.currentTime + delay);
    } catch (err) {
      /* sound is a nicety; it must never break editing */
    }
  },
};

function click(ctx, out, noise, t, { tone, body = 0, level, length = 0.03 }) {
  const gain = ctx.createGain();
  gain.gain.value = level;
  gain.connect(out);

  const burst = ctx.createBufferSource();
  burst.buffer = noise;
  const band = ctx.createBiquadFilter();
  band.type = "bandpass";
  band.frequency.value = tone;
  band.Q.value = 1.3;
  const burstEnvelope = ctx.createGain();
  burstEnvelope.gain.setValueAtTime(0, t);
  burstEnvelope.gain.linearRampToValueAtTime(1, t + 0.001);
  burstEnvelope.gain.exponentialRampToValueAtTime(0.001, t + length);
  burst.connect(band).connect(burstEnvelope).connect(gain);
  burst.start(t);
  burst.stop(t + length + 0.01);

  if (!body) return;
  const osc = ctx.createOscillator();
  osc.type = "sine";
  osc.frequency.setValueAtTime(body, t);
  osc.frequency.exponentialRampToValueAtTime(body * 0.55, t + 0.05);
  const bodyEnvelope = ctx.createGain();
  bodyEnvelope.gain.setValueAtTime(0, t);
  bodyEnvelope.gain.linearRampToValueAtTime(0.6, t + 0.002);
  bodyEnvelope.gain.exponentialRampToValueAtTime(0.001, t + 0.07);
  osc.connect(bodyEnvelope).connect(gain);
  osc.start(t);
  osc.stop(t + 0.08);
}

const SOUNDS = {
  // Two quick clicks: the knob pushing into its socket, then seating.
  snap: (ctx, out, noise, t) => {
    click(ctx, out, noise, t, { tone: 4200, body: 1100, level: 0.22 });
    click(ctx, out, noise, t + 0.032, { tone: 2500, body: 560, level: 0.42 });
  },
  // One light tick when a piece is picked up.
  lift: (ctx, out, noise, t) => click(ctx, out, noise, t, { tone: 4800, level: 0.26, length: 0.02 }),
  // A click and a short rising blip when a piece is taken off.
  remove: (ctx, out, noise, t) => {
    click(ctx, out, noise, t, { tone: 3200, level: 0.2, length: 0.022 });
    const osc = ctx.createOscillator();
    osc.type = "sine";
    osc.frequency.setValueAtTime(420, t);
    osc.frequency.exponentialRampToValueAtTime(900, t + 0.07);
    const envelope = ctx.createGain();
    envelope.gain.setValueAtTime(0, t);
    envelope.gain.linearRampToValueAtTime(0.16, t + 0.005);
    envelope.gain.exponentialRampToValueAtTime(0.001, t + 0.09);
    osc.connect(envelope).connect(out);
    osc.start(t);
    osc.stop(t + 0.1);
  },
};

/* Collapsibles -------------------------------------------------------------------- */

function setCollapse(collapse, open) {
  collapse.classList.toggle("is-open", open);
  collapse.inert = !open;
}

/* Launch splash ------------------------------------------------------------------- */

const splashDone = new Promise((resolve) => {
  const splash = $("splash");
  if (!splash) {
    resolve();
    return;
  }
  let finished = false;
  const finish = () => {
    if (finished) return;
    finished = true;
    splash.remove();
    resolve();
  };
  splash.addEventListener("animationend", (event) => {
    if (event.target === splash) finish();
  });
  const skip = () => splash.classList.add("is-skipped");
  splash.addEventListener("click", skip);
  window.addEventListener("keydown", skip, { once: true });
  setTimeout(finish, SPLASH_FALLBACK_MS);
});

/* Theme and accent ----------------------------------------------------------------- */

/* Windows' accent palette, lightest first: Light3, Light2, Light1, Accent,
   Dark1, Dark2, Dark3. Light theme fills with Dark1, dark theme with Light2. */
function applyAccent(palette) {
  if (!Array.isArray(palette) || palette.length < 7) return;
  const [light3, light2, , , dark1, dark2] = palette;
  const root = document.documentElement.style;
  root.setProperty("--sys-accent-dark1", dark1);
  root.setProperty("--sys-accent-dark2", dark2);
  root.setProperty("--sys-accent-light2", light2);
  root.setProperty("--sys-accent-light3", light3);
}

/* Theme ---------------------------------------------------------------------------------

   The page is light unless <html data-theme="dark">. Python writes the
   starting theme before the page loads; from then on it follows the Theme
   setting, and Windows' own mode while that setting is "system". */

function themeSetting() {
  return (app.data && app.data.settings.theme) || "system";
}

function applyTheme(setting = themeSetting()) {
  const dark = setting === "dark" || (setting === "system" && darkTheme.matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
}

/* Navigation ------------------------------------------------------------------------ */

function showPage(name) {
  if (app.page === name) return;
  app.page = name;
  for (const button of document.querySelectorAll(".nav-item")) {
    if (button.dataset.page === name) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  }
  for (const page of document.querySelectorAll(".page")) {
    const shown = page.dataset.page === name;
    page.hidden = !shown;
    if (shown) {
      const frames = reducedMotion.matches
        ? [{ opacity: 0 }, { opacity: 1 }]
        : [{ opacity: 0, transform: "translateY(8px)" }, { opacity: 1, transform: "none" }];
      page.animate(frames, { duration: 200, easing: EASE_OUT });
    }
  }
  $("content").scrollTop = 0;
  moveIndicator();
  if (name === "activity") {
    app.unread = 0;
    updateBadge();
  }
  if (name === "settings") loadShortcuts();
}

function moveIndicator() {
  const current = document.querySelector('.nav-item[aria-current="page"]');
  if (!current) return;
  const top = current.offsetTop + (current.offsetHeight - 16) / 2;
  $("nav-indicator").style.transform = `translateY(${top}px)`;
}

/* Startup ------------------------------------------------------------------------- */

function paintStaticIcons() {
  for (const node of document.querySelectorAll("[data-icon]")) node.innerHTML = icon(node.dataset.icon);
  $("about-icon").innerHTML = appIcon("about-icon");
  $("activity-empty-glyph").innerHTML = glyph(GESTURES.open_palm.fingers);
  $("seen-glyph").innerHTML = glyph(GESTURES.open_palm.fingers);
}

async function init() {
  let data;
  try {
    data = await api().get_state();
  } catch (err) {
    await splashDone;
    showProblems([TEXT.loadFailed + err]);
    return;
  }
  app.data = data;
  applyAccent(data.accent);
  applyTheme();
  loadCustomCss(data.custom_css);
  registerCustomGestures(data.custom_gestures);
  const gestureIds = [...data.gestures, ...data.custom_gestures.map((g) => g.name)];
  app.rows = gestureIds.map((gesture) => rowFromBinding(gesture, data.bindings.find((b) => b.gesture === gesture)));

  fillDatalists();
  renderSettings();
  showProblems(data.problems);
  $("welcome").hidden = data.bindings.length > 0;

  await splashDone;
  renderRows(true);
  $("tracking-switch").disabled = false;
  applyStatus(data.status);
  setInterval(pollStatus, STATUS_INTERVAL_MS);
}

function rowFromBinding(gesture, binding) {
  const label = gestureInfo(gesture).label;
  if (!binding) return { gesture, name: "", stepDelay: null, actions: [] };
  return {
    gesture,
    // A blank name is saved as the gesture's label; show it as blank again.
    name: binding.name === label ? "" : binding.name,
    stepDelay: binding.step_delay_seconds,
    actions: binding.action.map((a) => newAction(a.type, a.target)),
  };
}

function newAction(type, target = "") {
  const action = { id: app.nextId, type, target };
  app.nextId += 1;
  return action;
}

function fillDatalists() {
  $("known-apps").replaceChildren(...app.data.known_apps.map((name) => el("option", { value: name })));
  $("hotkey-presets").replaceChildren(
    ...app.data.hotkey_presets.map((key) => el("option", { value: key, label: HOTKEY_LABELS[key] || key })),
  );
}

function showProblems(problems) {
  $("problems").hidden = problems.length === 0;
  $("problems-text").textContent = problems.join(" ");
}

/* Gesture rows ---------------------------------------------------------------------- */

const rowOf = (gesture) => app.rows.find((row) => row.gesture === gesture);
const rowNode = (gesture) => document.querySelector(`.gesture[data-gesture="${gesture}"]`);

function renderRows(animate) {
  const list = $("gesture-list");
  list.replaceChildren(...app.rows.map((row, index) => {
    const node = renderRow(row);
    if (animate) {
      node.classList.add("is-entering");
      node.style.setProperty("--i", index);
      node.addEventListener("animationend", () => node.classList.remove("is-entering"), { once: true });
    }
    return node;
  }));
  list.setAttribute("aria-busy", "false");
}

function renderRow(row) {
  const info = gestureInfo(row.gesture);
  const open = app.open === row.gesture;
  const headId = `g-${row.gesture}-head`;
  const bodyId = `g-${row.gesture}-body`;

  const head = el("button", {
    class: "gesture-head", type: "button", id: headId,
    "aria-expanded": String(open), "aria-controls": bodyId,
    onclick: () => setOpen(app.open === row.gesture ? null : row.gesture),
  }, [
    el("span", { class: "gesture-glyph", html: glyph(info.fingers) }),
    el("span", { class: "gesture-titles" }, [
      el("span", { class: "gesture-label", textContent: info.label }),
      el("span", { class: "gesture-sub" }),
    ]),
    el("span", { class: "gesture-summary", "aria-hidden": "true" }),
    iconEl("warning", "gesture-flag"),
    iconEl("chevron", "chevron"),
  ]);

  const body = el("div", { class: "collapse gesture-body", id: bodyId, role: "region", "aria-labelledby": headId }, [
    el("div", { class: "collapse-inner" }, [renderEditor(row)]),
  ]);
  setCollapse(body, open);

  const node = el("li", {
    class: "card gesture" + (open ? " is-open" : ""),
    dataset: { gesture: row.gesture },
    ondragover: (event) => rowDragOver(event, row, node),
    ondragleave: (event) => rowDragLeave(event, node),
    ondrop: (event) => rowDrop(event, row, node),
  }, [head, body]);
  if (app.seen === row.gesture) node.classList.add("is-seen");
  updateHead(row, node);
  return node;
}

function updateHead(row, node = rowNode(row.gesture)) {
  if (!node) return;
  const count = row.actions.length;
  const name = row.name.trim();
  let sub = TEXT.notSet;
  if (count) sub = name ? `${name} \u00B7 ${TEXT.actionCount(count)}` : TEXT.actionCount(count);
  node.querySelector(".gesture-sub").textContent = sub;

  const chips = row.actions.slice(0, 3).map((action) => el("span", {
    class: "chip" + (action.target.trim() ? "" : " is-empty"),
    dataset: { type: action.type, id: action.id },
  }, [
    el("span", { class: "chip-icon", html: icon(ACTIONS[action.type].icon) }),
    el("span", { class: "chip-text", textContent: shortTarget(action) }),
  ]));
  if (count > 3) chips.push(el("span", { class: "chip chip-more", textContent: TEXT.more(count - 3) }));
  node.querySelector(".gesture-summary").replaceChildren(...chips);
  node.classList.toggle("has-warning", row.actions.some((a) => !a.target.trim()));
}

function renderEditor(row) {
  const info = gestureInfo(row.gesture);
  const testButton = el("button", {
    class: "btn test-button", type: "button", disabled: row.actions.length === 0,
    onclick: () => testRow(row, testButton),
  }, [el("span", { class: "btn-icon-slot", html: icon("bolt") }), el("span", { class: "test-label", textContent: TEXT.test })]);

  const bar = el("div", { class: "editor-bar" }, [
    el("label", { class: "name-field" }, [
      el("span", { textContent: TEXT.nameLabel }),
      el("input", {
        class: "textbox name-input", type: "text", value: row.name, maxLength: 60, spellcheck: false,
        placeholder: TEXT.namePlaceholder, "aria-label": TEXT.nameAria(info.label),
        oninput: (event) => { row.name = event.target.value; updateHead(row); scheduleSave(); },
      }),
    ]),
    el("span", { class: "spacer" }),
    info.custom ? el("button", {
      class: "btn btn-subtle", type: "button",
      onclick: () => removeCustomGesture(row),
    }, [el("span", { class: "btn-icon-slot", html: icon("close") }), el("span", { textContent: TEXT.removeGesture })]) : null,
    testButton,
  ]);

  const palette = el("div", { class: "palette" }, [
    el("p", { class: "palette-title" }, [iconEl("puzzle"), TEXT.palette]),
    ...app.data.action_types.map((type) => el("button", {
      class: "palette-piece piece has-socket", type: "button", draggable: true, dataset: { type },
      title: TEXT.addTo(ACTIONS[type].label),
      onclick: () => insertAction(row, row.actions.length, type),
      ondragstart: (event) => startDrag(event, { kind: "new", type }),
      ondragend: endDrag,
    }, [iconEl(ACTIONS[type].icon), el("span", { textContent: ACTIONS[type].label })])),
  ]);

  const hat = el("div", { class: "hat piece" }, [
    el("span", { textContent: TEXT.when }),
    el("span", { class: "hat-gesture" }, [el("span", { html: glyph(info.fingers) }), info.label]),
  ]);

  const stack = el("ol", { class: "stack", "aria-label": TEXT.stackLabel(info.label) },
    row.actions.length
      ? row.actions.map((action, index) => renderBlock(row, action, index))
      : [el("li", { class: "stack-empty" }, [iconEl("add"), TEXT.dropHere])]);

  return el("div", { class: "editor" }, [
    bar,
    el("div", { class: "canvas" }, [palette, el("div", { class: "script" }, [hat, stack])]),
    el("div", { class: "infobar is-error row-error", role: "alert", hidden: true }),
  ]);
}

function renderBlock(row, action, index) {
  const info = ACTIONS[action.type];
  const last = row.actions.length - 1;
  const input = el("input", {
    class: "block-input", type: info.input, value: action.target, placeholder: info.placeholder,
    spellcheck: false, autocomplete: "off", "aria-label": TEXT.target(info.label),
    oninput: (event) => {
      action.target = event.target.value;
      block.classList.toggle("is-incomplete", !action.target.trim());
      block.classList.remove("is-invalid");
      updateHead(row);
      scheduleSave();
    },
  });
  if (info.list) input.setAttribute("list", info.list);

  const tool = (name, label, disabled, onclick, extra = "") => el("button", {
    class: `tool ${extra}`, type: "button", title: label, "aria-label": label, disabled,
    dataset: { tool: name }, html: icon(name), onclick,
  });

  const block = el("li", {
    class: "block piece has-socket" + (action.target.trim() ? "" : " is-incomplete"),
    dataset: { type: action.type, id: action.id },
    // Only drag from the piece itself, so text in the input can still be selected.
    onpointerdown: (event) => { block.draggable = !event.target.closest("input, button"); },
    ondragstart: (event) => startDrag(event, { kind: "move", gesture: row.gesture, id: action.id, type: action.type }, block),
    ondragend: endDrag,
  }, [
    iconEl("grip", "block-grip"),
    iconEl(info.icon, "block-icon"),
    el("span", { class: "block-label", textContent: info.label }),
    input,
    el("span", { class: "block-tools" }, [
      tool("up", TEXT.moveUp, index === 0, () => moveAction(row.gesture, action.id, row.gesture, index - 1, { focusPart: "up" }), "tool-move"),
      tool("down", TEXT.moveDown, index === last, () => moveAction(row.gesture, action.id, row.gesture, index + 2, { focusPart: "down" }), "tool-move"),
      tool("close", TEXT.remove, false, () => removeAction(row, action.id)),
    ]),
  ]);
  return block;
}

/* Re-draw one row's editor, animating what moved, snapped in, or needs focus. */
function refreshRow(row, { snapId = null, focus = null, flip = false } = {}) {
  const node = rowNode(row.gesture);
  if (!node) return;
  const isOpen = app.open === row.gesture;
  const before = new Map();
  if (flip && isOpen) {
    node.querySelectorAll(".block[data-id]").forEach((b) => before.set(b.dataset.id, b.getBoundingClientRect().top));
  }

  node.querySelector(".gesture-body .collapse-inner").replaceChildren(renderEditor(row));
  updateHead(row, node);

  if (before.size && !reducedMotion.matches) {
    node.querySelectorAll(".block[data-id]").forEach((b) => {
      const top = before.get(b.dataset.id);
      if (top === undefined || b.dataset.id === String(snapId)) return;
      const dy = top - b.getBoundingClientRect().top;
      if (Math.abs(dy) > 1) b.animate([{ transform: `translateY(${dy}px)` }, { transform: "none" }], { duration: 220, easing: EASE_IN_OUT });
    });
  }
  if (snapId !== null) {
    if (isOpen) {
      const block = node.querySelector(`.block[data-id="${snapId}"]`);
      if (block) snapIn(block);
    } else {
      const chip = node.querySelector(`.chip[data-id="${snapId}"]`);
      if (chip) enter(chip);
    }
  }
  if (focus) focusInRow(node, focus);
}

function focusInRow(node, { id, part = "input" }) {
  const block = node.querySelector(`.block[data-id="${id}"]`);
  if (!block) {
    node.querySelector(".palette-piece")?.focus();
    return;
  }
  const input = block.querySelector(".block-input");
  if (part === "input") {
    input.focus();
    return;
  }
  // After moving to the top or bottom the arrow just used disappears: use the other one.
  const opposite = part === "up" ? "down" : "up";
  const target = [part, opposite]
    .map((name) => block.querySelector(`[data-tool="${name}"]`))
    .find((button) => button && !button.disabled) || input;
  target.focus({ preventScroll: true });
}

function setOpen(gesture) {
  const previous = app.open;
  if (previous === gesture) return;
  app.open = gesture;
  if (previous) pruneEmptyActions(rowOf(previous));

  for (const node of document.querySelectorAll(".gesture[data-gesture]")) {
    const open = node.dataset.gesture === gesture;
    node.classList.toggle("is-open", open);
    node.querySelector(".gesture-head").setAttribute("aria-expanded", String(open));
    setCollapse(node.querySelector(".gesture-body"), open);
  }
  if (gesture) {
    const node = rowNode(gesture);
    setTimeout(() => node.scrollIntoView({ block: "nearest", behavior: reducedMotion.matches ? "auto" : "smooth" }), 270);
  }
}

/* An empty piece left behind in a closed gesture would block saving: drop it. */
function pruneEmptyActions(row) {
  const kept = row.actions.filter((action) => action.target.trim());
  if (kept.length === row.actions.length) return;
  row.actions = kept;
  refreshRow(row);
  scheduleSave();
}

/* Editing --------------------------------------------------------------------------------- */

function insertAction(row, index, type) {
  const action = newAction(type);
  row.actions.splice(index, 0, action);
  refreshRow(row, { snapId: action.id, focus: { id: action.id }, flip: true });
  sound.play("snap", { delay: SNAP_SOUND_DELAY });
  clearRowErrors();
  scheduleSave();
}

/* toIndex is a position in the target list before the piece is taken out.
   Arrow buttons pass focusPart; drags do not, and their piece snaps in. */
function moveAction(fromGesture, id, toGesture, toIndex, { focusPart = null } = {}) {
  const from = rowOf(fromGesture);
  const to = rowOf(toGesture);
  const fromIndex = from.actions.findIndex((action) => action.id === id);
  if (fromIndex < 0) return;
  if (from === to && (toIndex === fromIndex || toIndex === fromIndex + 1)) return;
  const [action] = from.actions.splice(fromIndex, 1);
  let index = toIndex;
  if (from === to && fromIndex < index) index -= 1;
  to.actions.splice(index, 0, action);

  if (from === to) {
    refreshRow(to, focusPart
      ? { flip: true, focus: { id, part: focusPart } }
      : { flip: true, snapId: id });
    sound.play("snap", { delay: focusPart ? ARROW_SOUND_DELAY : SNAP_SOUND_DELAY });
  } else {
    refreshRow(from, { flip: true });
    refreshRow(to, { snapId: action.id });
    sound.play("snap", { delay: SNAP_SOUND_DELAY });
    if (app.open !== to.gesture) {
      pulse(rowNode(to.gesture), "var(--accent)");
      toast(TEXT.movedTo(gestureInfo(to.gesture).label), "info");
    }
  }
  clearRowErrors();
  scheduleSave();
}

async function removeAction(row, id) {
  const node = rowNode(row.gesture);
  const block = node && node.querySelector(`.block[data-id="${id}"]`);
  sound.play("remove");
  if (block) {
    block.style.pointerEvents = "none";
    await unsnap(block);
  }
  const index = row.actions.findIndex((action) => action.id === id);
  if (index < 0) return;
  row.actions.splice(index, 1);
  const neighbour = row.actions[index] || row.actions[index - 1];
  refreshRow(row, { flip: true, focus: neighbour ? { id: neighbour.id } : { id: null } });
  clearRowErrors();
  scheduleSave();
}

/* Drag and drop ------------------------------------------------------------------------------ */

function startDrag(event, drag, source = null) {
  app.drag = drag;
  event.dataTransfer.effectAllowed = drag.kind === "new" ? "copy" : "move";
  event.dataTransfer.setData("text/plain", drag.kind === "new" ? drag.type : "move");
  document.body.classList.add("is-dragging-block");
  sound.play("lift");
  // Fade the original only after the browser has taken its drag picture.
  if (source) requestAnimationFrame(() => source.classList.add("is-dragging"));
}

function endDrag() {
  app.drag = null;
  document.body.classList.remove("is-dragging-block");
  clearDropHints();
  document.querySelectorAll(".block.is-dragging").forEach((node) => node.classList.remove("is-dragging"));
}

function clearDropHints(scope = document) {
  scope.querySelectorAll(".is-ghost").forEach((ghost) => ghost.remove());
  scope.querySelectorAll(".stack-empty").forEach((zone) => { zone.hidden = false; });
  scope.querySelectorAll(".is-drop-target").forEach((node) => node.classList.remove("is-drop-target"));
}

/* A faded piece shows where the dragged one will land. */
function showGhost(stack, index, type) {
  const blocks = [...stack.querySelectorAll(":scope > .block:not(.is-ghost)")];
  const before = blocks[index] || null;
  let ghost = stack.querySelector(":scope > .is-ghost");
  if (ghost && ghost.dataset.type !== type) {
    ghost.remove();
    ghost = null;
  }
  if (!ghost) {
    ghost = el("li", { class: "block piece has-socket is-ghost", "aria-hidden": "true", dataset: { type } });
    stack.insertBefore(ghost, before);
    ghost.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 120, easing: "ease-out" });
    return;
  }
  if (ghost.nextElementSibling !== before) stack.insertBefore(ghost, before);
}

/* Measured as if the ghost were not there, so showing it never moves the target. */
function dropIndex(stack, clientY) {
  const ghost = stack.querySelector(":scope > .is-ghost");
  const shift = ghost ? ghost.getBoundingClientRect().height + STACK_GAP : 0;
  let pastGhost = false;
  let index = 0;
  for (const child of stack.children) {
    if (child === ghost) {
      pastGhost = true;
      continue;
    }
    if (!child.classList.contains("block")) continue;
    const box = child.getBoundingClientRect();
    if (clientY < box.top + box.height / 2 - (pastGhost ? shift : 0)) return index;
    index += 1;
  }
  return index;
}

function rowDragOver(event, row, node) {
  const drag = app.drag;
  if (!drag) return;
  event.preventDefault();
  event.dataTransfer.dropEffect = drag.kind === "new" ? "copy" : "move";
  if (app.open !== row.gesture) {
    node.classList.add("is-drop-target");
    return;
  }
  const stack = node.querySelector(".stack");
  const empty = stack.querySelector(".stack-empty");
  if (empty) empty.hidden = true;
  const index = dropIndex(stack, event.clientY);
  if (drag.kind === "move" && drag.gesture === row.gesture) {
    const from = row.actions.findIndex((action) => action.id === drag.id);
    if (index === from || index === from + 1) {
      clearDropHints(stack);
      return;
    }
  }
  showGhost(stack, index, drag.type);
}

function rowDragLeave(event, node) {
  if (node.contains(event.relatedTarget)) return;
  clearDropHints(node);
  node.classList.remove("is-drop-target");
}

function rowDrop(event, row, node) {
  event.preventDefault();
  const drag = app.drag;
  const isOpen = app.open === row.gesture;
  const index = isOpen ? dropIndex(node.querySelector(".stack"), event.clientY) : row.actions.length;
  endDrag();
  if (!drag) return;
  if (drag.kind === "new") {
    // A new piece needs a target typed in, so open the gesture it landed on.
    if (!isOpen) setOpen(row.gesture);
    insertAction(row, index, drag.type);
  } else {
    moveAction(drag.gesture, drag.id, row.gesture, index);
  }
}

/* Saving ----------------------------------------------------------------------------------------- */

function setSaveState(state, message = "") {
  const node = $("save-state");
  node.dataset.state = state;
  if (state === "idle") {
    node.replaceChildren();
    return;
  }
  const name = { saving: "spinner", saved: "check", warn: "warning" }[state] || "error";
  node.replaceChildren(el("span", { html: icon(name) }), el("span", { textContent: message }));
}

function scheduleSave() {
  clearTimeout(app.saveTimer);
  app.saveTimer = setTimeout(saveNow, SAVE_DELAY_MS);
}

function clearRowErrors() {
  document.querySelectorAll(".gesture.has-error").forEach((node) => node.classList.remove("has-error"));
  document.querySelectorAll(".row-error").forEach((node) => { node.hidden = true; node.replaceChildren(); });
  document.querySelectorAll(".block.is-invalid").forEach((node) => node.classList.remove("is-invalid"));
}

function buildPayload() {
  const used = app.rows.filter((row) => row.actions.length > 0);
  const binding = used.map((row) => {
    const entry = {
      gesture: row.gesture,
      name: row.name.trim() || gestureInfo(row.gesture).label,
      action: row.actions.map((action) => ({ type: action.type, target: action.target.trim() })),
    };
    if (row.stepDelay !== null && row.stepDelay !== undefined) entry.step_delay_seconds = row.stepDelay;
    return entry;
  });
  return { used, payload: { binding } };
}

async function saveNow() {
  clearTimeout(app.saveTimer);
  clearRowErrors();
  if (app.rows.some((row) => row.actions.some((action) => !action.target.trim()))) {
    setSaveState("warn", TEXT.incomplete);
    return false;
  }
  const { used, payload } = buildPayload();
  app.saveRequest += 1;
  const request = app.saveRequest;
  setSaveState("saving", TEXT.saving);
  let result;
  try {
    result = await api().save_bindings(payload);
  } catch (err) {
    result = { ok: false, error: String(err) };
  }
  if (request !== app.saveRequest) return result.ok; // a newer save superseded this one
  if (result.ok) {
    setSaveState("saved", TEXT.saved);
    return true;
  }
  setSaveState("error", TEXT.saveFailed);
  if (!showBindingError(used, result.error)) toast(result.error, "error");
  return false;
}

/* Python reports "Binding N, action M: ..."; put the message on that gesture and piece. */
function showBindingError(used, message) {
  const match = /Binding (\d+)(?:, action (\d+))?/.exec(message);
  const row = match && used[Number(match[1]) - 1];
  if (!row) return false;
  if (app.open !== row.gesture) setOpen(row.gesture);
  const node = rowNode(row.gesture);
  node.classList.add("has-error");
  const box = node.querySelector(".row-error");
  box.replaceChildren(
    iconEl("error", "infobar-icon"),
    el("p", { class: "infobar-text", textContent: message.replace(/^Binding \d+(, action \d+)?: /, "") }),
  );
  box.hidden = false;
  if (match[2]) {
    const block = node.querySelectorAll(".stack .block")[Number(match[2]) - 1];
    if (block) block.classList.add("is-invalid");
  }
  return true;
}

async function testRow(row, button) {
  const label = button.querySelector(".test-label");
  const slot = button.querySelector(".btn-icon-slot");
  button.disabled = true;
  slot.innerHTML = icon("spinner");
  label.textContent = TEXT.testing;
  try {
    if (!(await saveNow())) return;
    const result = await api().test_binding(row.gesture);
    if (!result.results) {
      toast(result.error, "error");
      return;
    }
    const failures = result.results.filter((r) => !r.ok);
    if (failures.length) {
      toast(failures.map((r) => r.message).join(" "), "error");
    } else {
      pulse(rowNode(row.gesture), "var(--success)");
      toast(TEXT.testRan(row.name.trim() || gestureInfo(row.gesture).label));
    }
  } catch (err) {
    toast(String(err), "error");
  } finally {
    button.disabled = row.actions.length === 0;
    slot.innerHTML = icon("bolt");
    label.textContent = TEXT.test;
  }
}

/* Tracking ------------------------------------------------------------------------------------------ */

async function toggleTracking() {
  const toggle = $("tracking-switch");
  const wasRunning = Boolean(app.status && app.status.running);
  if (app.busy || !app.data) {
    toggle.checked = wasRunning;
    return;
  }
  app.busy = true;
  showTrackingState(wasRunning ? "stopping" : "starting");
  if (!wasRunning) {
    app.startError = null;
    app.hasFrame = false;
    showTrackingError(null);
    setLive("starting");
  }
  let result;
  try {
    result = wasRunning ? await api().stop() : await api().start();
  } catch (err) {
    result = { ok: false, error: String(err), status: app.status };
  }
  app.busy = false;
  if (!result.ok) app.startError = result.error;
  applyStatus(result.status || app.status);
}

async function pollStatus() {
  if (app.busy) return;
  try {
    applyStatus(await api().status());
  } catch (err) {
    /* the window is closing */
  }
}

function showTrackingState(state) {
  const running = state === "running";
  const toggle = $("tracking-switch");
  toggle.checked = running || state === "starting";
  toggle.disabled = state === "starting" || state === "stopping";
  $("tracking-label").textContent = {
    starting: TEXT.starting, stopping: TEXT.stopping, running: TEXT.switchOn,
  }[state] || TEXT.switchOff;
  $("tracking-desc").textContent = running && app.data
    ? TEXT.trackingDescOn(app.data.settings.camera_index)
    : TEXT.trackingDesc;
  $("tracking").dataset.state = state;
  $("nav-status").dataset.state = state;
  $("nav-status-text").textContent = TEXT.navStatus[state];
}

function showTrackingError(message) {
  $("tracking-error").hidden = !message;
  $("tracking-error-text").textContent = message || "";
}

function applyStatus(status) {
  if (!status) return;
  const previous = app.status;
  app.status = status;
  if (app.busy) return;

  const error = status.running ? null : status.error || app.startError;
  showTrackingState(status.running ? "running" : error ? "error" : "stopped");
  if (error) $("tracking-label").textContent = TEXT.switchOff;
  showTrackingError(error);
  $("scan-cameras").disabled = status.running;

  if (status.running) {
    setLive(app.hasFrame ? "on" : "starting");
  } else {
    app.hasFrame = false;
    setLive("off");
  }
  showSeen(status);

  if (status.error && previous && previous.running && !status.running) toast(status.error, "error");
  recordActivity(status.last_fired);
  if (status.running && !app.previewing) startPreview();
}

function setLive(state) {
  setCollapse($("live-wrap"), state !== "off");
  $("camera-frame").dataset.state = state;
  if (state === "off") $("bones").replaceChildren();
}

function showSeen(status) {
  const seen = status.running ? status.gesture : null;
  if (seen !== app.seen) {
    app.seen = seen;
    document.querySelectorAll(".gesture[data-gesture]").forEach((node) => {
      node.classList.toggle("is-seen", node.dataset.gesture === seen);
    });
    $("seen-glyph").hidden = !seen;
    if (seen) $("seen-glyph").innerHTML = glyph(gestureInfo(seen).fingers);
  }
  $("seen-text").textContent = seen ? gestureInfo(seen).label : status.hands ? TEXT.handInView : TEXT.noHands;
  $("fps").textContent = status.running ? TEXT.fps(status.fps) : "\u2013";
}

async function startPreview() {
  app.previewing = true;
  const img = $("preview-img");
  while (app.status && app.status.running) {
    let frame = null;
    try {
      frame = await api().preview();
    } catch (err) {
      break;
    }
    if (frame && app.status.running) {
      img.src = frame.image;
      drawHands(frame.hands);
      if (!app.hasFrame) {
        app.hasFrame = true;
        setLive("on");
      }
    }
    await sleep(PREVIEW_INTERVAL_MS);
  }
  app.previewing = false;
}

/* The skeleton over the preview: landmarks arrive as 0-1 fractions of the frame. */
function drawHandsInto(svg, hands) {
  const line = (a, b, cls = "") => `<line${cls ? ` class="${cls}"` : ""} x1="${a[0]}" y1="${a[1]}" x2="${b[0]}" y2="${b[1]}"/>`;
  svg.innerHTML = hands.map((hand) => HAND_BONES.map(([a, b]) => line(hand[a], hand[b])).join("")
    + hand.map((point, i) => line(point, point, FINGERTIPS.has(i) ? "joint tip" : "joint")).join("")).join("");
}

function drawHands(hands) {
  drawHandsInto($("bones"), hands);
}

/* Activity --------------------------------------------------------------------------------------------- */

function recordActivity(event) {
  if (!event) return;
  const previous = app.lastEvent;
  if (previous && previous.at === event.at && previous.finished === event.finished) return;
  const isNew = !previous || previous.at !== event.at;
  const justFinished = event.finished && (isNew || !previous.finished);
  app.lastEvent = { at: event.at, finished: event.finished };

  const list = $("activity");
  const id = `event-${String(event.at).replace(/\W/g, "-")}`;
  const item = renderEvent(event, id);
  const existing = document.getElementById(id);
  if (existing) {
    existing.replaceWith(item);
  } else {
    list.prepend(item);
    if (app.page === "activity") enter(item);
  }
  while (list.children.length > ACTIVITY_LIMIT) list.lastElementChild.remove();
  $("activity-empty").hidden = true;
  showLastRun(event);

  if (isNew) {
    if (app.page !== "activity") app.unread += 1;
    updateBadge();
    pulse(rowNode(event.gesture), "var(--accent)");
  }
  if (justFinished) {
    const failures = event.results.filter((r) => !r.ok);
    if (failures.length) {
      toast(`${event.name || gestureInfo(event.gesture).label}: ${failures.map((r) => r.message).join(" ")}`, "error");
    }
  }
}

function updateBadge() {
  const badge = $("activity-badge");
  badge.hidden = app.unread === 0;
  badge.textContent = String(app.unread);
}

function showLastRun(event) {
  const name = event.name || gestureInfo(event.gesture).label;
  const failed = event.finished && event.results.some((r) => !r.ok);
  const iconName = !event.finished ? "spinner" : failed ? "error" : "success";
  $("last-run").replaceChildren(
    el("span", { class: failed ? "run-fail" : "run-ok", html: icon(iconName) }),
    el("span", { textContent: `${name} \u00B7 ${clock(event.at)}` }),
  );
}

function renderEvent(event, id) {
  const info = gestureInfo(event.gesture);
  let results;
  if (!event.name) {
    results = [el("li", { textContent: TEXT.unbound })];
  } else if (!event.finished) {
    results = [el("li", {}, [el("span", { html: icon("spinner") }), TEXT.running])];
  } else {
    results = event.results.map((r) => el("li", { class: r.ok ? "ok" : "fail" }, [
      el("span", { html: icon(r.ok ? "success" : "error") }),
      el("span", { textContent: `${ACTIONS[r.type] ? ACTIONS[r.type].label : r.type}: ${r.ok ? r.target : r.message}` }),
    ]));
  }
  return el("li", { class: "card event", id }, [
    el("span", { html: glyph(info.fingers) }),
    el("div", { class: "event-body" }, [
      el("p", { class: "card-title", textContent: event.name || info.label }),
      el("p", { class: "card-desc", textContent: info.label }),
      el("ul", { class: "event-results" }, results),
    ]),
    el("span", { class: "event-time", textContent: clock(event.at) }),
  ]);
}

/* Settings ---------------------------------------------------------------------------------------------- */

function renderSettings() {
  const { settings, limits } = app.data;
  const select = $("camera-select");
  select.replaceChildren();
  for (let i = limits.camera_index[0]; i <= limits.camera_index[1]; i += 1) {
    select.append(el("option", { value: String(i), textContent: TEXT.camera(i) }));
  }
  select.value = String(settings.camera_index);

  for (const [key, id] of [["dwell_seconds", "dwell"], ["cooldown_seconds", "cooldown"]]) {
    const input = $(id);
    input.min = limits[key][0];
    input.max = limits[key][1];
    input.value = settings[key];
    showSliderValue(input);
  }
  setSwitch($("sounds"), settings.sounds !== false);
  $("close-action").value = settings.close_action || "ask";
  $("theme").value = settings.theme || "system";
  $("bindings-file").textContent = app.data.bindings_file;
  setSwitch($("custom-css-on"), settings.custom_css !== false);
  $("about-version").textContent = TEXT.version(app.data.version);
}

function showSliderValue(input) {
  const fraction = (input.value - input.min) / (input.max - input.min);
  input.style.setProperty("--fill", `${Math.round(fraction * 1000) / 10}%`);
  $(`${input.id}-value`).textContent = TEXT.seconds(input.value);
}

function setSwitch(input, on) {
  input.checked = on;
  const label = document.querySelector(`.toggle-label[data-for="${input.id}"]`);
  if (label) label.textContent = on ? TEXT.switchOn : TEXT.switchOff;
}

function showSettingsError(message) {
  $("settings-error").hidden = !message;
  $("settings-error-text").textContent = message || "";
}

/* Settings apply as soon as they change, as in Windows Settings. */
async function saveSettings() {
  const payload = {
    camera_index: Number($("camera-select").value),
    dwell_seconds: Number($("dwell").value),
    cooldown_seconds: Number($("cooldown").value),
    sounds: $("sounds").checked,
    close_action: $("close-action").value,
    theme: $("theme").value,
    custom_css: $("custom-css-on").checked,
  };
  let result;
  try {
    result = await api().save_settings(payload);
  } catch (err) {
    result = { ok: false, error: String(err) };
  }
  if (result.settings) app.data.settings = result.settings;
  showSettingsError(result.ok ? null : result.error);
  if (app.status && app.status.running) showTrackingState("running");
}

async function scanCameras() {
  const button = $("scan-cameras");
  const help = $("camera-help");
  button.disabled = true;
  button.classList.add("is-busy");
  help.textContent = TEXT.scanning;
  try {
    const result = await api().list_cameras();
    if (!result.ok) {
      help.textContent = result.error;
      return;
    }
    const working = new Set(result.cameras);
    for (const option of $("camera-select").options) {
      const index = Number(option.value);
      option.textContent = working.has(index) ? TEXT.cameraWorks(index) : TEXT.camera(index);
    }
    help.textContent = TEXT.scanFound(result.cameras.length);
  } catch (err) {
    help.textContent = String(err);
  } finally {
    button.classList.remove("is-busy");
    button.disabled = Boolean(app.status && app.status.running);
  }
}

const SHORTCUT_SWITCHES = ["shortcut-desktop", "shortcut-start", "shortcut-startup"];

async function loadShortcuts() {
  if (app.shortcutsLoaded || !app.data) return;
  app.shortcutsLoaded = true;
  try {
    showShortcuts(await api().shortcut_state());
  } catch (err) {
    showShortcuts({ supported: false });
  }
}

function showShortcuts(state) {
  for (const id of SHORTCUT_SWITCHES) {
    const input = $(id);
    setSwitch(input, Boolean(state[input.dataset.kind]));
    input.disabled = !state.supported;
  }
}

async function setShortcut(input) {
  const wanted = input.checked;
  input.disabled = true;
  let result;
  try {
    result = await api().set_shortcut(input.dataset.kind, wanted);
  } catch (err) {
    result = { ok: false, error: String(err), shortcuts: null };
  }
  if (result.shortcuts) showShortcuts(result.shortcuts);
  else setSwitch(input, !wanted);
  input.disabled = Boolean(result.shortcuts && !result.shortcuts.supported);
  showSettingsError(result.ok ? null : result.error);
}

/* Add-gesture wizard ---------------------------------------------------------------------------------------- */

const WIZARD_POLL_MS = PREVIEW_INTERVAL_MS;

function openWizard() {
  if (app.wizard.open) return;
  app.wizard.open = true;
  app.wizard.hasFrame = false;
  app.wizard.fingers = null;
  app.wizard.wasRunning = Boolean(app.status && app.status.running);

  showWizardError(null);
  $("wizard-capture").hidden = false;
  $("wizard-done").hidden = true;
  $("wizard-retry").hidden = true;
  $("wizard-save").hidden = true;
  $("wizard-save").disabled = false;
  $("wizard-name").value = "";
  $("wizard-name").classList.remove("is-invalid");
  $("wizard-frame").dataset.state = "starting";
  $("wizard-preview-img").src = "";
  $("wizard-bones").replaceChildren();
  $("wizard-stage-text").textContent = TEXT.wizardStarting;
  $("wizard-progress-fill").style.width = "0%";
  $("wizard").dataset.stage = "";

  const overlay = $("wizard-overlay");
  overlay.hidden = false;
  void overlay.offsetHeight; // commit the start state so the transition runs
  overlay.classList.add("is-in");

  beginWizardCapture();
}

async function beginWizardCapture() {
  let result;
  try {
    result = await api().start_gesture_capture();
  } catch (err) {
    showWizardError(String(err));
    return;
  }
  if (!result.ok) {
    showWizardError(result.error);
    return;
  }
  pollWizard();
}

async function pollWizard() {
  if (app.wizard.polling) return;
  app.wizard.polling = true;
  while (app.wizard.open) {
    let frame = null;
    let status = null;
    try {
      [frame, status] = await Promise.all([api().preview(), api().capture_status()]);
    } catch (err) {
      break;
    }
    if (!app.wizard.open) break;
    if (frame) {
      $("wizard-preview-img").src = frame.image;
      drawHandsInto($("wizard-bones"), frame.hands);
      if (!app.wizard.hasFrame) {
        app.wizard.hasFrame = true;
        $("wizard-frame").dataset.state = "on";
      }
    }
    if (status) {
      applyWizardStatus(status);
      if (status.stage === "done" || status.stage === "taken") break;
    }
    await sleep(WIZARD_POLL_MS);
  }
  app.wizard.polling = false;
}

function applyWizardStatus(status) {
  $("wizard").dataset.stage = status.stage;
  $("wizard-progress-fill").style.width = `${Math.round(status.progress * 100)}%`;
  $("wizard-stage-text").textContent = {
    hold: TEXT.wizardHold(status.attempt),
    release: TEXT.wizardRelease,
    mismatch: TEXT.wizardMismatch,
    done: TEXT.wizardDone,
    taken: TEXT.wizardTakenStage,
  }[status.stage] || "";

  if (status.stage === "done" && status.fingers) {
    app.wizard.fingers = status.fingers;
    showWizardDone(status.fingers);
  } else if (status.stage === "taken" && status.fingers) {
    showWizardTaken(status.fingers, status.matches);
  }
}

function showWizardDone(fingers) {
  $("wizard-capture").hidden = true;
  $("wizard-done").hidden = false;
  $("wizard-glyph").innerHTML = glyph(fingers);
  $("wizard-taken").hidden = true;
  $("wizard-name-field").hidden = false;
  $("wizard-retry").hidden = false;
  $("wizard-save").hidden = false;
  $("wizard-name").focus();
}

/* The first hold landed on a shape that already belongs to a gesture: say
   which one straight away, and offer another go instead of a name to save. */
function showWizardTaken(fingers, matches) {
  $("wizard-capture").hidden = true;
  $("wizard-done").hidden = false;
  $("wizard-glyph").innerHTML = glyph(fingers);
  $("wizard-taken").textContent = TEXT.wizardTaken(gestureInfo(matches).label);
  $("wizard-taken").hidden = false;
  $("wizard-name-field").hidden = true;
  $("wizard-save").hidden = true;
  $("wizard-retry").hidden = false;
  $("wizard-retry").focus();
}

/* Python only knows a builtin gesture by its internal id ("open_palm"), so a
   conflict message names it that way. Swap in the label shown everywhere
   else in the window, so "already used by 'open_palm'" reads as the same
   "Open palm" row the person can see in their list, not something unknown. */
function humanizeGestureError(message) {
  return message.replace(/'([\w]+)'/, (match, id) => {
    const info = GESTURES[id];
    return info ? `'${info.label}'` : match;
  });
}

function showWizardError(message) {
  $("wizard-error").hidden = !message;
  $("wizard-error-text").textContent = message ? humanizeGestureError(message) : "";
}

async function retryWizard() {
  showWizardError(null);
  $("wizard-done").hidden = true;
  $("wizard-capture").hidden = false;
  $("wizard-retry").hidden = true;
  $("wizard-save").hidden = true;
  $("wizard-frame").dataset.state = app.wizard.hasFrame ? "on" : "starting";
  $("wizard-progress-fill").style.width = "0%";
  $("wizard").dataset.stage = "";
  app.wizard.fingers = null;
  try {
    await api().cancel_gesture_capture();
  } catch (err) {
    /* the window is closing */
  }
  beginWizardCapture();
}

async function saveWizardGesture() {
  const nameInput = $("wizard-name");
  const name = nameInput.value.trim();
  if (!name) {
    showWizardError(TEXT.wizardNameRequired);
    nameInput.classList.add("is-invalid");
    nameInput.focus();
    return;
  }
  nameInput.classList.remove("is-invalid");
  const saveButton = $("wizard-save");
  saveButton.disabled = true;
  let result;
  try {
    result = await api().save_captured_gesture(name);
  } catch (err) {
    result = { ok: false, error: String(err) };
  }
  if (!result.ok) {
    showWizardError(result.error);
    saveButton.disabled = false;
    return;
  }
  registerCustomGestures([{ name, fingers: app.wizard.fingers }]);
  app.rows.push(rowFromBinding(name, null));
  renderRows(true);
  toast(TEXT.gestureAdded(name));
  closeWizard();
}

function closeWizard() {
  if (!app.wizard.open) return;
  app.wizard.open = false;
  const overlay = $("wizard-overlay");
  overlay.classList.remove("is-in");
  setTimeout(() => { overlay.hidden = true; }, 150);
  api().cancel_gesture_capture().catch(() => {});
  if (!app.wizard.wasRunning) api().stop().then((result) => applyStatus(result.status)).catch(() => {});
}

async function removeCustomGesture(row) {
  let result;
  try {
    result = await api().remove_custom_gesture(row.gesture);
  } catch (err) {
    result = { ok: false, error: String(err) };
  }
  if (!result.ok) {
    toast(result.error, "error");
    return;
  }
  delete GESTURES[row.gesture];
  const index = app.rows.findIndex((r) => r.gesture === row.gesture);
  if (index >= 0) app.rows.splice(index, 1);
  if (app.open === row.gesture) app.open = null;
  renderRows(true);
  toast(TEXT.gestureRemoved(row.gesture));
  await saveNow();
}

/* Custom CSS ----------------------------------------------------------------------------------------------

   Applied as the text of its own <style> element, placed after palm-lab's
   styles so it wins ties. Setting textContent (never innerHTML) means the text
   is only ever CSS, whatever it contains. */

const CSS_SAVE_DELAY_MS = 500;

function loadCustomCss(state) {
  const css = app.css;
  css.style = document.createElement("style");
  css.style.id = "custom-css";
  document.head.append(css.style);
  css.text = state.text || "";
  css.allowed = state.allowed !== false;
  $("custom-css-input").value = css.text;
  $("custom-css-file").textContent = state.file || "";
  $("custom-css-card").hidden = !state.file;
  const notice = state.error || (css.allowed ? "" : TEXT.cssBlocked);
  $("custom-css-notice").hidden = !notice;
  $("custom-css-notice-text").textContent = notice;
  applyCustomCss();
}

function customCssOn() {
  return app.css.allowed && Boolean(app.data) && app.data.settings.custom_css !== false;
}

function applyCustomCss() {
  if (app.css.style) app.css.style.textContent = customCssOn() ? app.css.text : "";
}

function setCssState(state, message = "") {
  const node = $("custom-css-state");
  node.dataset.state = state;
  node.textContent = message;
}

function editCustomCss(event) {
  app.css.text = event.target.value;
  applyCustomCss();
  clearTimeout(app.css.saveTimer);
  app.css.saveTimer = setTimeout(saveCustomCss, CSS_SAVE_DELAY_MS);
  setCssState("saving", TEXT.cssSaving);
}

async function saveCustomCss() {
  app.css.saveRequest += 1;
  const request = app.css.saveRequest;
  let result;
  try {
    result = await api().save_custom_css(app.css.text);
  } catch (err) {
    result = { ok: false, error: String(err) };
  }
  if (request !== app.css.saveRequest) return; // a newer save superseded this one
  if (result.ok) setCssState("saved", TEXT.cssSaved);
  else setCssState("error", result.error);
}

function toggleCssEditor() {
  const button = $("custom-css-edit");
  const open = button.getAttribute("aria-expanded") !== "true";
  button.setAttribute("aria-expanded", String(open));
  setCollapse($("custom-css-wrap"), open);
  if (open) setTimeout(() => $("custom-css-input").focus({ preventScroll: true }), 60);
}

async function setCustomCssOn(on) {
  setSwitch($("custom-css-on"), on);
  if (app.data) app.data.settings.custom_css = on;
  applyCustomCss();
  await saveSettings();
}

/* Closing -----------------------------------------------------------------------------------------------------

   Python calls askBeforeClosing() when the window is closed while "When I close
   the window" is "Ask me". Yes keeps palm-lab running in the background, No
   quits, and closing the question (Escape, or clicking beside it) keeps the
   window open. */

function askBeforeClosing() {
  const overlay = $("close-overlay");
  if (!overlay.hidden) return;
  $("close-remember").checked = false;
  overlay.hidden = false;
  void overlay.offsetHeight; // commit the start state so the transition runs
  overlay.classList.add("is-in");
  $("close-yes").focus();
}

function dismissCloseQuestion() {
  const overlay = $("close-overlay");
  if (overlay.hidden) return;
  overlay.classList.remove("is-in");
  setTimeout(() => { overlay.hidden = true; }, 150);
}

async function answerClose(choice) {
  const remember = $("close-remember").checked;
  dismissCloseQuestion();
  if (app.wizard.open) closeWizard();
  let result;
  try {
    result = await api().close_choice(choice, remember);
  } catch (err) {
    result = { ok: false, error: String(err) };
  }
  if (result.settings && app.data) {
    app.data.settings = result.settings;
    $("close-action").value = result.settings.close_action;
  }
  if (!result.ok) toast(result.error, "error");
}

/* Toasts --------------------------------------------------------------------------------------------------- */

function toast(message, kind = "success") {
  const box = $("toasts");
  while (box.children.length >= TOAST_LIMIT) box.firstElementChild.remove();
  const node = el("div", { class: `toast is-${kind}`, role: kind === "error" ? "alert" : "status" }, [
    iconEl(kind, "toast-icon"),
    el("p", { class: "toast-text", textContent: message }),
    el("button", {
      class: "btn btn-subtle btn-icon", type: "button", "aria-label": TEXT.dismiss, title: TEXT.dismiss,
      html: icon("close"), onclick: () => dismiss(),
    }),
  ]);
  box.append(node);
  void node.offsetHeight; // commit the start state so the transition runs
  node.classList.add("is-in");

  const life = kind === "error" ? 7000 : 3200;
  let timer = setTimeout(dismiss, life);
  node.addEventListener("mouseenter", () => clearTimeout(timer));
  node.addEventListener("mouseleave", () => { clearTimeout(timer); timer = setTimeout(dismiss, 1500); });

  function dismiss() {
    clearTimeout(timer);
    node.classList.remove("is-in");
    setTimeout(() => node.remove(), 200);
  }
}

/* Wiring -------------------------------------------------------------------------------------------------- */

function wireControls() {
  for (const button of document.querySelectorAll(".nav-item")) {
    button.addEventListener("click", () => showPage(button.dataset.page));
  }
  window.addEventListener("resize", moveIndicator);
  $("tracking-switch").addEventListener("change", toggleTracking);
  $("close-problems").addEventListener("click", () => { $("problems").hidden = true; });
  $("close-welcome").addEventListener("click", () => { $("welcome").hidden = true; });

  $("camera-select").addEventListener("change", saveSettings);
  $("scan-cameras").addEventListener("click", scanCameras);
  for (const id of ["dwell", "cooldown"]) {
    $(id).addEventListener("input", (event) => showSliderValue(event.target));
    $(id).addEventListener("change", saveSettings);
  }
  $("sounds").addEventListener("change", (event) => {
    setSwitch(event.target, event.target.checked);
    // Turning sounds on plays one, so people know what they are getting.
    if (event.target.checked) sound.play("snap", { force: true });
    saveSettings();
  });
  for (const id of SHORTCUT_SWITCHES) {
    $(id).addEventListener("change", (event) => {
      setSwitch(event.target, event.target.checked);
      setShortcut(event.target);
    });
  }
  $("open-folder").addEventListener("click", () => api().open_config_folder());
  $("open-project").addEventListener("click", () => api().open_project_page());

  $("add-gesture").addEventListener("click", openWizard);
  $("wizard-close").addEventListener("click", closeWizard);
  $("wizard-cancel").addEventListener("click", closeWizard);
  $("wizard-retry").addEventListener("click", retryWizard);
  $("wizard-save").addEventListener("click", saveWizardGesture);
  $("wizard-name").addEventListener("keydown", (event) => {
    if (event.key === "Enter") { event.preventDefault(); saveWizardGesture(); }
  });
  $("wizard-name").addEventListener("input", (event) => {
    event.target.classList.remove("is-invalid");
  });
  $("wizard-overlay").addEventListener("click", (event) => {
    if (event.target === event.currentTarget) closeWizard();
  });
  window.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    if (!$("close-overlay").hidden) dismissCloseQuestion();
    else if (app.wizard.open) closeWizard();
  });

  $("close-action").addEventListener("change", saveSettings);

  $("custom-css-on").addEventListener("change", (event) => setCustomCssOn(event.target.checked));
  $("custom-css-edit").addEventListener("click", toggleCssEditor);
  $("custom-css-input").addEventListener("input", editCustomCss);
  $("custom-css-docs").addEventListener("click", (event) => {
    event.preventDefault();
    api().open_project_page();
  });
  // The way back from CSS that hides everything: script keeps working when
  // CSS has hidden every button, so a key press can always turn it off.
  window.addEventListener("keydown", (event) => {
    if (!(event.ctrlKey && event.shiftKey && event.code === "KeyX")) return;
    event.preventDefault();
    if (!app.data || app.data.settings.custom_css === false) return;
    setCustomCssOn(false);
    toast(TEXT.cssOff, "info");
  });
  $("close-yes").addEventListener("click", () => answerClose("background"));
  $("close-no").addEventListener("click", () => answerClose("quit"));
  $("close-overlay").addEventListener("click", (event) => {
    if (event.target === event.currentTarget) dismissCloseQuestion();
  });

  // Waking the audio engine on the first click makes the first snap instant.
  window.addEventListener("pointerdown", () => { if (sound.enabled()) sound.context(); }, { once: true, capture: true });
  // The title bar is coloured by Python; tell it whenever the theme changes.
  darkTheme.addEventListener("change", () => {
    applyTheme();
    if (window.pywebview && window.pywebview.api) api().theme_changed();
  });
  $("theme").addEventListener("change", async () => {
    applyTheme($("theme").value);
    await saveSettings();
    api().theme_changed();
  });
}

// Without a theme from Python (a page opened on its own), start from Windows'.
if (!document.documentElement.dataset.theme) applyTheme("system");
paintStaticIcons();
setCollapse($("live-wrap"), false);
setCollapse($("custom-css-wrap"), false);
wireControls();
moveIndicator();

if (window.pywebview && window.pywebview.api) init();
else window.addEventListener("pywebviewready", init);
