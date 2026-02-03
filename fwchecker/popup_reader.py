from pywinauto import Desktop

from .config import FW_PATTERN

def _dedup_keep_order(texts: list[str]) -> list[str]:
    seen = set()
    out = []
    for x in texts:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out

def safe_texts_uia(win):
    texts = []

    def add(s):
        if not s:
            return
        s = str(s).strip()
        if s:
            texts.append(s)

    try: add(win.window_text())
    except Exception: pass

    try: add(win.element_info.name)
    except Exception: pass

    try:
        for d in win.descendants():
            try: add(d.window_text())
            except Exception: pass

            try: add(d.element_info.name)
            except Exception: pass

            try:
                lp = d.legacy_properties()
                add(lp.get("Name"))
                add(lp.get("Value"))
            except Exception:
                pass

            try: add(d.get_value())
            except Exception: pass
    except Exception:
        pass

    return _dedup_keep_order(texts)

def safe_texts_win32(win):
    texts = []

    def add(s):
        if not s:
            return
        s = str(s).strip()
        if s:
            texts.append(s)

    try: add(win.window_text())
    except Exception: pass

    try:
        for t in win.texts():
            add(t)
    except Exception:
        pass

    try:
        for ch in win.children():
            try: add(ch.window_text())
            except Exception: pass
    except Exception:
        pass

    return _dedup_keep_order(texts)

def find_windows_by_title_contains(title_key: str):
    title_key_l = (title_key or "").strip().lower()
    if not title_key_l:
        return []

    wins = Desktop(backend="win32").windows(visible_only=True)
    matched = []
    for w in wins:
        try:
            title = (w.window_text() or "").strip()
        except Exception:
            continue
        if title_key_l in title.lower():
            matched.append(w)
    return matched

def find_windows_by_content_contains(content_key: str, max_scan: int = 80):
    key = (content_key or "").strip().lower()
    if not key:
        return []

    wins = Desktop(backend="win32").windows(visible_only=True)
    matched = []

    count = 0
    for w in wins:
        count += 1
        if count > max_scan:
            break

        try:
            if key in "\n".join(safe_texts_win32(w)).lower():
                matched.append(w)
                continue
        except Exception:
            pass

        try:
            uia_win = Desktop(backend="uia").window(handle=w.handle)
            if key in "\n".join(safe_texts_uia(uia_win)).lower():
                matched.append(w)
        except Exception:
            pass

    return matched

def window_contains_confirm_key(win, key: str) -> bool:
    k = (key or "").strip().lower()
    if not k:
        return True

    try:
        if k in "\n".join(safe_texts_win32(win)).lower():
            return True
    except Exception:
        pass

    try:
        uia_win = Desktop(backend="uia").window(handle=win.handle)
        return k in "\n".join(safe_texts_uia(uia_win)).lower()
    except Exception:
        return False

def read_firmware_version_hybrid(win):
    # UIA
    try:
        uia_win = Desktop(backend="uia").window(handle=win.handle)
        joined = "\n".join(safe_texts_uia(uia_win))
        m = FW_PATTERN.search(joined)
        if m:
            return m.group(1).strip()
    except Exception:
        pass

    # WIN32
    try:
        joined = "\n".join(safe_texts_win32(win))
        m = FW_PATTERN.search(joined)
        if m:
            return m.group(1).strip()
    except Exception:
        pass

    # title fallback
    try:
        title = win.window_text() or ""
    except Exception:
        title = ""
    m = FW_PATTERN.search(title)
    return m.group(1).strip() if m else None
