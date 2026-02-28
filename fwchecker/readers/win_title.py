import ctypes
from ctypes import wintypes

_user32 = ctypes.WinDLL("user32", use_last_error=True)

_GetWindowTextLengthW = _user32.GetWindowTextLengthW
_GetWindowTextLengthW.argtypes = [wintypes.HWND]
_GetWindowTextLengthW.restype = ctypes.c_int

_GetWindowTextW = _user32.GetWindowTextW
_GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
_GetWindowTextW.restype = ctypes.c_int

_IsWindow = _user32.IsWindow
_IsWindow.argtypes = [wintypes.HWND]
_IsWindow.restype = wintypes.BOOL

def fast_window_title(hwnd: int) -> str:
    """Safe title getter (avoid SendMessage/WM_GETTEXT hang)."""
    try:
        if not hwnd or not _IsWindow(hwnd):
            return ""
        length = _GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)
        _GetWindowTextW(hwnd, buf, length + 1)
        return (buf.value or "").strip()
    except Exception:
        return ""