"""The pop-up card by the clock, drawn as a tiny native window.

Why not a second pywebview window? pywebview's show() always activates the
window, its first show hands keyboard focus to WebView2, and it can't keep a
window off the taskbar. A card that steals focus would break whatever the
gesture just did (typing, a game). So this is a plain Win32 window, made
with ctypes and drawn with GDI:

- WS_EX_NOACTIVATE + SW_SHOWNOACTIVATE: it never takes focus.
- WS_EX_TOOLWINDOW: no taskbar button, not in Alt+Tab.
- WS_EX_TOPMOST: above other windows.
- WS_EX_LAYERED + WS_EX_TRANSPARENT: semi-opaque, and clicks pass through.

It runs its own thread and message loop; show() can be called from any
thread and just posts the card to that thread. Layout maths and the busy
check's rules are plain functions, so they're tested on every platform.
"""

import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from palm_lab.run_popup import PopupMessage

# Card geometry in device-independent pixels (scaled by the monitor's DPI).
MARGIN = 12  # from the edges of the work area, i.e. just above the taskbar
PADDING = 14
ICON = 20
GAP = 12
MIN_WIDTH = 240
MAX_WIDTH = 420
HEIGHT = 60
RADIUS = 8
TITLE_SIZE = 14
DETAIL_SIZE = 12
ALPHA = 245  # nearly opaque, like Windows' own flyouts
FADE_STEPS = 8
FADE_STEP_MS = 16

# SHQueryUserNotificationState answers (shellapi.h).
QUNS_NOT_PRESENT = 1
QUNS_BUSY = 2
QUNS_RUNNING_D3D_FULL_SCREEN = 3
QUNS_PRESENTATION_MODE = 4
QUNS_ACCEPTS_NOTIFICATIONS = 5
QUNS_QUIET_TIME = 6
QUNS_APP = 7


@dataclass(frozen=True)
class Colours:
    background: str
    title: str
    detail: str
    success: str
    failure: str


LIGHT = Colours("#F9F9F9", "#1A1A1A", "#5C5C5C", "#0F7B0F", "#C42B1C")
DARK = Colours("#2B2B2B", "#FFFFFF", "#C5C5C5", "#6CCB5F", "#FF99A4")


def scaled(value: int, dpi: int) -> int:
    return round(value * dpi / 96)


def card_width(text_width: int, dpi: int) -> int:
    """Wide enough for the longer line of text, within sensible limits."""
    natural = text_width + scaled(PADDING * 2 + ICON + GAP, dpi)
    return max(scaled(MIN_WIDTH, dpi), min(natural, scaled(MAX_WIDTH, dpi)))


def card_position(
    work_area: tuple[int, int, int, int], size: tuple[int, int], dpi: int
) -> tuple[int, int]:
    """Bottom-right of the work area (the screen minus the taskbar), by the clock."""
    _, _, right, bottom = work_area
    width, height = size
    margin = scaled(MARGIN, dpi)
    return right - width - margin, bottom - height - margin


def busy(state: int | None) -> bool:
    """Whether Windows says now is a bad time for a pop-up.

    Only "accepts notifications" (and the quiet hour after a new user's first
    sign-in, which is about Windows' own tips) count as free. If the check
    itself fails, assume free: a pop-up is better than silence.
    """
    return state is not None and state not in (QUNS_ACCEPTS_NOTIFICATIONS, QUNS_QUIET_TIME)


def notification_state() -> int | None:
    """Ask Windows whether the user is busy (full screen, presenting, Do Not Disturb)."""
    if sys.platform != "win32":
        return None
    import ctypes

    state = ctypes.c_int(0)
    try:
        result = ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(state))
    except (AttributeError, OSError):
        return None
    return int(state.value) if result == 0 else None


def colorref(hex_colour: str) -> int:
    red, green, blue = (int(hex_colour[i : i + 2], 16) for i in (1, 3, 5))
    return (blue << 16) | (green << 8) | red


class _Card(Protocol):
    def post_show(self) -> None: ...

    def post_close(self) -> None: ...

    def loop(self) -> None: ...


TakePending = Callable[[], tuple[PopupMessage | None, bool]]

# The native card window: set below on Windows, None elsewhere.
_card_factory: Callable[[TakePending], _Card] | None = None


class Overlay:
    """The card window. start() once; then show() from any thread."""

    def __init__(self, dark: Callable[[], bool]) -> None:
        self._dark = dark
        self._lock = threading.Lock()
        self._pending: PopupMessage | None = None
        self._ready = threading.Event()
        self._window: _Card | None = None

    @property
    def available(self) -> bool:
        return self._window is not None

    def start(self) -> None:
        """Create the window on its own thread. Does nothing off Windows."""
        if sys.platform != "win32":
            return
        threading.Thread(target=self._run, name="palm-lab-popup", daemon=True).start()
        self._ready.wait(timeout=3.0)

    def show(self, message: PopupMessage) -> None:
        window = self._window
        if window is None:
            return
        with self._lock:
            self._pending = message
        window.post_show()

    def take_pending(self) -> tuple[PopupMessage | None, bool]:
        with self._lock:
            message, self._pending = self._pending, None
        return message, self._dark()

    def stop(self) -> None:
        if self._window is not None:
            self._window.post_close()

    def _run(self) -> None:
        if _card_factory is None:
            self._ready.set()
            return
        try:
            window = _card_factory(self.take_pending)
        except OSError:
            self._ready.set()
            return
        self._window = window
        self._ready.set()
        window.loop()


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    LRESULT = wintypes.LPARAM
    WNDPROC = ctypes.WINFUNCTYPE(
        LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
    )

    class WNDCLASSEXW(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.UINT),
            ("style", wintypes.UINT),
            ("lpfnWndProc", WNDPROC),
            ("cbClsExtra", ctypes.c_int),
            ("cbWndExtra", ctypes.c_int),
            ("hInstance", wintypes.HINSTANCE),
            ("hIcon", wintypes.HICON),
            ("hCursor", wintypes.HICON),
            ("hbrBackground", wintypes.HBRUSH),
            ("lpszMenuName", wintypes.LPCWSTR),
            ("lpszClassName", wintypes.LPCWSTR),
            ("hIconSm", wintypes.HICON),
        ]

    class PAINTSTRUCT(ctypes.Structure):
        _fields_ = [
            ("hdc", wintypes.HDC),
            ("fErase", wintypes.BOOL),
            ("rcPaint", wintypes.RECT),
            ("fRestore", wintypes.BOOL),
            ("fIncUpdate", wintypes.BOOL),
            ("rgbReserved", ctypes.c_byte * 32),
        ]

    def _signature(func: object, argtypes: list[object], restype: object) -> None:
        func.argtypes = argtypes  # type: ignore[attr-defined]
        func.restype = restype  # type: ignore[attr-defined]

    _signature(
        user32.DefWindowProcW,
        [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM],
        LRESULT,
    )
    _signature(user32.RegisterClassExW, [ctypes.POINTER(WNDCLASSEXW)], wintypes.ATOM)
    _signature(
        user32.CreateWindowExW,
        [
            wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
        ],
        wintypes.HWND,
    )  # fmt: skip
    _signature(kernel32.GetModuleHandleW, [wintypes.LPCWSTR], wintypes.HMODULE)
    if hasattr(user32, "GetDpiForWindow"):  # Windows 10 1607 and later
        _signature(user32.GetDpiForWindow, [wintypes.HWND], wintypes.UINT)
    _signature(
        user32.PostMessageW,
        [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM],
        wintypes.BOOL,
    )
    _signature(
        user32.GetMessageW,
        [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT],
        wintypes.BOOL,
    )
    _signature(user32.TranslateMessage, [ctypes.POINTER(wintypes.MSG)], wintypes.BOOL)
    _signature(user32.DispatchMessageW, [ctypes.POINTER(wintypes.MSG)], LRESULT)
    _signature(user32.PostQuitMessage, [ctypes.c_int], None)
    _signature(user32.DestroyWindow, [wintypes.HWND], wintypes.BOOL)
    _signature(user32.ShowWindow, [wintypes.HWND, ctypes.c_int], wintypes.BOOL)
    _signature(
        user32.SetWindowPos,
        [
            wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
            ctypes.c_int, ctypes.c_int, wintypes.UINT,
        ],
        wintypes.BOOL,
    )  # fmt: skip
    _signature(
        user32.SetLayeredWindowAttributes,
        [wintypes.HWND, wintypes.COLORREF, wintypes.BYTE, wintypes.DWORD],
        wintypes.BOOL,
    )
    _signature(
        user32.SetTimer,
        [wintypes.HWND, ctypes.c_size_t, wintypes.UINT, wintypes.LPVOID],
        ctypes.c_size_t,
    )
    _signature(user32.KillTimer, [wintypes.HWND, ctypes.c_size_t], wintypes.BOOL)
    _signature(
        user32.InvalidateRect, [wintypes.HWND, wintypes.LPRECT, wintypes.BOOL], wintypes.BOOL
    )
    _signature(user32.BeginPaint, [wintypes.HWND, ctypes.POINTER(PAINTSTRUCT)], wintypes.HDC)
    _signature(user32.EndPaint, [wintypes.HWND, ctypes.POINTER(PAINTSTRUCT)], wintypes.BOOL)
    _signature(user32.GetDC, [wintypes.HWND], wintypes.HDC)
    _signature(user32.ReleaseDC, [wintypes.HWND, wintypes.HDC], ctypes.c_int)
    _signature(
        user32.SystemParametersInfoW,
        [wintypes.UINT, wintypes.UINT, wintypes.LPVOID, wintypes.UINT],
        wintypes.BOOL,
    )
    _signature(user32.SetWindowRgn, [wintypes.HWND, wintypes.HRGN, wintypes.BOOL], ctypes.c_int)
    _signature(
        user32.FillRect,
        [wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.HBRUSH],
        ctypes.c_int,
    )
    _signature(
        user32.DrawTextW,
        [
            wintypes.HDC,
            wintypes.LPCWSTR,
            ctypes.c_int,
            ctypes.POINTER(wintypes.RECT),
            wintypes.UINT,
        ],
        ctypes.c_int,
    )
    _signature(
        gdi32.CreateRoundRectRgn,
        [ctypes.c_int] * 6,
        wintypes.HRGN,
    )
    _signature(gdi32.CreateSolidBrush, [wintypes.COLORREF], wintypes.HBRUSH)
    _signature(gdi32.CreatePen, [ctypes.c_int, ctypes.c_int, wintypes.COLORREF], wintypes.HPEN)
    _signature(gdi32.DeleteObject, [wintypes.HGDIOBJ], wintypes.BOOL)
    _signature(gdi32.SelectObject, [wintypes.HDC, wintypes.HGDIOBJ], wintypes.HGDIOBJ)
    _signature(gdi32.SetTextColor, [wintypes.HDC, wintypes.COLORREF], wintypes.COLORREF)
    _signature(gdi32.SetBkMode, [wintypes.HDC, ctypes.c_int], ctypes.c_int)
    _signature(
        gdi32.Ellipse,
        [wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int],
        wintypes.BOOL,
    )
    _signature(
        gdi32.MoveToEx,
        [wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.POINTER(wintypes.POINT)],
        wintypes.BOOL,
    )
    _signature(gdi32.LineTo, [wintypes.HDC, ctypes.c_int, ctypes.c_int], wintypes.BOOL)
    _signature(
        gdi32.GetTextExtentPoint32W,
        [wintypes.HDC, wintypes.LPCWSTR, ctypes.c_int, ctypes.POINTER(wintypes.SIZE)],
        wintypes.BOOL,
    )
    _signature(
        gdi32.CreateFontW,
        [ctypes.c_int] * 5 + [wintypes.DWORD] * 8 + [wintypes.LPCWSTR],
        wintypes.HFONT,
    )

    WS_POPUP = 0x80000000
    WS_EX_TOPMOST = 0x00000008
    WS_EX_TRANSPARENT = 0x00000020
    WS_EX_TOOLWINDOW = 0x00000080
    WS_EX_LAYERED = 0x00080000
    WS_EX_NOACTIVATE = 0x08000000
    SW_HIDE = 0
    SW_SHOWNOACTIVATE = 4
    HWND_TOPMOST = -1
    SWP_NOACTIVATE = 0x0010
    SWP_SHOWWINDOW = 0x0040
    WM_DESTROY = 0x0002
    WM_PAINT = 0x000F
    WM_TIMER = 0x0113
    WM_APP_SHOW = 0x8001
    WM_APP_CLOSE = 0x8002
    LWA_ALPHA = 0x2
    SPI_GETWORKAREA = 0x0030
    SPI_GETCLIENTAREAANIMATION = 0x1042
    TRANSPARENT_BK = 1
    DT_LEFT_SINGLE = 0x0020 | 0x0800 | 0x8000  # single line, no & prefixes, ellipsis
    FW_NORMAL = 400
    FW_SEMIBOLD = 600
    CLEARTYPE_QUALITY = 5
    PS_SOLID = 0
    # Never activated, no taskbar button, on top, see-through to clicks.
    CARD_STYLE = (
        WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_LAYERED | WS_EX_TRANSPARENT
    )
    TIMER_HIDE = 1
    TIMER_FADE = 2

    class _CardWindow:
        """The native window itself. Every method runs on the card's own thread."""

        def __init__(self, take: TakePending) -> None:
            self._take = take
            self._message: PopupMessage | None = None
            self._colours = LIGHT
            self._alpha = 0
            self._fading_in = True
            self._width = 0
            self._proc = WNDPROC(self._wndproc)  # kept alive: Windows calls it
            instance = kernel32.GetModuleHandleW(None)
            wc = WNDCLASSEXW()
            wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
            wc.lpfnWndProc = self._proc
            wc.hInstance = instance
            wc.lpszClassName = "palm-lab-popup"
            if not user32.RegisterClassExW(ctypes.byref(wc)):
                raise ctypes.WinError(ctypes.get_last_error())
            hwnd = user32.CreateWindowExW(
                CARD_STYLE,
                "palm-lab-popup", "palm-lab", WS_POPUP,
                0, 0, 1, 1, None, None, instance, None,
            )  # fmt: skip
            if not hwnd:
                raise ctypes.WinError(ctypes.get_last_error())
            self._hwnd = hwnd

        # Called from other threads -------------------------------------------

        def post_show(self) -> None:
            user32.PostMessageW(self._hwnd, WM_APP_SHOW, 0, 0)

        def post_close(self) -> None:
            user32.PostMessageW(self._hwnd, WM_APP_CLOSE, 0, 0)

        # The card's own thread ------------------------------------------------

        def loop(self) -> None:
            msg = wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))

        def _wndproc(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
            try:
                if msg == WM_APP_SHOW:
                    self._show()
                    return 0
                if msg == WM_TIMER:
                    self._tick(int(wparam))
                    return 0
                if msg == WM_PAINT:
                    self._paint()
                    return 0
                if msg == WM_APP_CLOSE:
                    user32.DestroyWindow(hwnd)
                    return 0
                if msg == WM_DESTROY:
                    user32.PostQuitMessage(0)
                    return 0
            except Exception:  # noqa: BLE001 - a broken card must not crash palm-lab
                return 0
            return int(user32.DefWindowProcW(hwnd, msg, wparam, lparam))

        def _dpi(self) -> int:
            try:
                return int(user32.GetDpiForWindow(self._hwnd)) or 96
            except AttributeError:  # Windows before 10 1607
                return 96

        def _animations_on(self) -> bool:
            enabled = wintypes.BOOL(True)
            user32.SystemParametersInfoW(SPI_GETCLIENTAREAANIMATION, 0, ctypes.byref(enabled), 0)
            return bool(enabled.value)

        def _font(self, size: int, weight: int, dpi: int) -> int:
            return int(
                gdi32.CreateFontW(
                    -scaled(size, dpi), 0, 0, 0, weight, 0, 0, 0, 1, 0, 0,
                    CLEARTYPE_QUALITY, 0, "Segoe UI",
                )
            )  # fmt: skip

        def _text_width(self, text: str, font: int) -> int:
            dc = user32.GetDC(self._hwnd)
            old = gdi32.SelectObject(dc, font)
            size = wintypes.SIZE()
            gdi32.GetTextExtentPoint32W(dc, text, len(text), ctypes.byref(size))
            gdi32.SelectObject(dc, old)
            user32.ReleaseDC(self._hwnd, dc)
            return int(size.cx)

        def _show(self) -> None:
            message, dark = self._take()
            if message is None:
                return
            self._message = message
            self._colours = DARK if dark else LIGHT
            dpi = self._dpi()
            title_font = self._font(TITLE_SIZE, FW_SEMIBOLD, dpi)
            detail_font = self._font(DETAIL_SIZE, FW_NORMAL, dpi)
            widest = max(
                self._text_width(message.title, title_font),
                self._text_width(message.detail_line, detail_font),
            )
            gdi32.DeleteObject(title_font)
            gdi32.DeleteObject(detail_font)
            width, height = card_width(widest, dpi), scaled(HEIGHT, dpi)
            self._width = width
            area = wintypes.RECT()
            user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(area), 0)
            x, y = card_position(
                (area.left, area.top, area.right, area.bottom), (width, height), dpi
            )
            radius = scaled(RADIUS, dpi) * 2
            user32.SetWindowRgn(
                self._hwnd,
                gdi32.CreateRoundRectRgn(0, 0, width + 1, height + 1, radius, radius),
                True,
            )
            if self._alpha == 0:
                # A layered window isn't drawn until it has an opacity: start
                # from fully see-through, then fade in.
                user32.SetLayeredWindowAttributes(self._hwnd, 0, 0, LWA_ALPHA)
            user32.SetWindowPos(
                self._hwnd, HWND_TOPMOST, x, y, width, height, SWP_NOACTIVATE | SWP_SHOWWINDOW
            )
            user32.InvalidateRect(self._hwnd, None, True)
            user32.KillTimer(self._hwnd, TIMER_HIDE)
            user32.SetTimer(self._hwnd, TIMER_HIDE, int(message.seconds * 1000), None)
            self._fade(towards_visible=True)

        def _fade(self, towards_visible: bool) -> None:
            self._fading_in = towards_visible
            if not self._animations_on():
                self._alpha = ALPHA if towards_visible else 0
                self._apply_alpha()
                return
            user32.SetTimer(self._hwnd, TIMER_FADE, FADE_STEP_MS, None)

        def _apply_alpha(self) -> None:
            user32.SetLayeredWindowAttributes(self._hwnd, 0, self._alpha, LWA_ALPHA)
            if self._alpha == 0:
                user32.ShowWindow(self._hwnd, SW_HIDE)
            else:
                user32.ShowWindow(self._hwnd, SW_SHOWNOACTIVATE)

        def _tick(self, timer: int) -> None:
            if timer == TIMER_HIDE:
                user32.KillTimer(self._hwnd, TIMER_HIDE)
                self._fade(towards_visible=False)
                return
            step = ALPHA // FADE_STEPS + 1
            if self._fading_in:
                self._alpha = min(ALPHA, self._alpha + step)
                done = self._alpha >= ALPHA
            else:
                self._alpha = max(0, self._alpha - step)
                done = self._alpha <= 0
            self._apply_alpha()
            if done:
                user32.KillTimer(self._hwnd, TIMER_FADE)

        def _paint(self) -> None:
            ps = PAINTSTRUCT()
            dc = user32.BeginPaint(self._hwnd, ctypes.byref(ps))
            try:
                message = self._message
                if message is not None:
                    self._draw(dc, message)
            finally:
                user32.EndPaint(self._hwnd, ctypes.byref(ps))

        def _draw(self, dc: int, message: PopupMessage) -> None:
            c = self._colours
            dpi = self._dpi()
            box = wintypes.RECT()
            box.right, box.bottom = 10_000, 10_000
            background = gdi32.CreateSolidBrush(colorref(c.background))
            user32.FillRect(dc, ctypes.byref(box), background)
            gdi32.DeleteObject(background)

            # The icon: a filled circle, with a tick for success or "!" for a failure.
            colour = colorref(c.failure if message.failed else c.success)
            pad, icon = scaled(PADDING, dpi), scaled(ICON, dpi)
            top = (scaled(HEIGHT, dpi) - icon) // 2
            brush = gdi32.CreateSolidBrush(colour)
            no_pen = gdi32.CreatePen(PS_SOLID, 1, colour)
            old_brush, old_pen = gdi32.SelectObject(dc, brush), gdi32.SelectObject(dc, no_pen)
            gdi32.Ellipse(dc, pad, top, pad + icon, top + icon)
            mark = gdi32.CreatePen(PS_SOLID, max(2, scaled(2, dpi)), colorref(c.background))
            gdi32.SelectObject(dc, mark)
            u = icon / 20  # the mark is drawn on a 20 x 20 grid
            if message.failed:
                gdi32.MoveToEx(dc, pad + round(10 * u), top + round(5 * u), None)
                gdi32.LineTo(dc, pad + round(10 * u), top + round(11 * u))
                gdi32.MoveToEx(dc, pad + round(10 * u), top + round(14 * u), None)
                gdi32.LineTo(dc, pad + round(10 * u), top + round(15 * u))
            else:
                gdi32.MoveToEx(dc, pad + round(5 * u), top + round(10 * u), None)
                gdi32.LineTo(dc, pad + round(8.5 * u), top + round(13.5 * u))
                gdi32.LineTo(dc, pad + round(15 * u), top + round(6.5 * u))
            gdi32.SelectObject(dc, old_brush)
            gdi32.SelectObject(dc, old_pen)
            for handle in (brush, no_pen, mark):
                gdi32.DeleteObject(handle)

            # Two lines of text, right of the icon.
            gdi32.SetBkMode(dc, TRANSPARENT_BK)
            left = pad + icon + scaled(GAP, dpi)
            right = self._width - pad
            middle = scaled(HEIGHT, dpi) // 2
            for text, size, weight, colour_hex, top_y, bottom_y in (
                (message.title, TITLE_SIZE, FW_SEMIBOLD, c.title, middle - scaled(20, dpi), middle),
                (message.detail_line, DETAIL_SIZE, FW_NORMAL, c.detail, middle + scaled(1, dpi),
                 middle + scaled(19, dpi)),
            ):  # fmt: skip
                font = self._font(size, weight, dpi)
                old_font = gdi32.SelectObject(dc, font)
                gdi32.SetTextColor(dc, colorref(colour_hex))
                line = wintypes.RECT(left, top_y, right, bottom_y)
                user32.DrawTextW(dc, text, -1, ctypes.byref(line), DT_LEFT_SINGLE)
                gdi32.SelectObject(dc, old_font)
                gdi32.DeleteObject(font)

    _card_factory = _CardWindow
