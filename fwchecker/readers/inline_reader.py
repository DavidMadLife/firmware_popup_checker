from .popup_reader import find_windows_by_title_contains, read_version_hybrid

def find_inline_windows_by_title(title_contains: str):
    # INLINE chỉ cần tìm theo title (BurnAP_Merge)
    return find_windows_by_title_contains(title_contains, max_scan=120)

def read_inline_version(win, pattern):
    return read_version_hybrid(win, pattern)