import threading
import time
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox

from .config import (
    AUTO_INTERVAL_MS,
    ASSET_WRONG_SOUND_REL,
    ASSET_OK_SOUND_REL,
    UNLOCK_PASSWORDS,
    FW_POPUP_PATTERN,
    FW_INLINE_PATTERN,
)
from .models import CheckResult
from .db import DbLogger
from .resources import resource_path
from .sound import play_mp3

from .readers.popup_reader import (
    find_windows_by_title_contains,
    find_windows_by_content_contains,
    read_version_hybrid,
    window_contains_confirm_key,
)
from .readers.inline_reader import (
    find_inline_windows_by_title,
    read_inline_version,
)

WRONG_SOUND = resource_path(ASSET_WRONG_SOUND_REL)
OK_SOUND = resource_path(ASSET_OK_SOUND_REL)

# ====== Colors ======
CLR_BG_DEFAULT = "#E5E7EB"
CLR_BORDER_DEFAULT = "#9CA3AF"

CLR_OK_BG = "#22C55E"
CLR_OK_BORDER = "#16A34A"

CLR_NG_BG = "#EF4444"
CLR_NG_BORDER = "#DC2626"

CLR_WARN_BG = "#F59E0B"
CLR_WARN_BORDER = "#D97706"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Firmware Version Check (POPUP/INLINE + SQL + SOUND)")
        self.geometry("1120x640")

        self.auto_running = False
        self.handled = set()
        self.last_inline_version = None
        self.db = DbLogger()
        self.db_failed_once = False

        self.version_locked = True

        self._build_ui()
        self._render_status(None)

    # ===================== VERSION LOCK =====================
    def _apply_version_lock(self):
        if not hasattr(self, "input_entry"):
            return
        if self.version_locked:
            self.input_entry.state(["disabled"])
        else:
            self.input_entry.state(["!disabled"])

    def unlock_version(self):
        if self.auto_running:
            messagebox.showwarning("Locked", "Stop AUTO first to change version.")
            return
        pw = (self.pw_var.get() or "").strip()

        if pw not in UNLOCK_PASSWORDS:
            messagebox.showerror("Permission denied", "Wrong password.")
            self.version_locked = True
            self._apply_version_lock()
            return

        self.version_locked = False
        self._apply_version_lock()
        self.pw_var.set("")
        self.input_entry.focus_set()

    def lock_version(self):
        self.version_locked = True
        self._apply_version_lock()
        if hasattr(self, "pw_entry"):
            self.pw_entry.focus_set()

    # ===================== UI =====================
    def _build_ui(self):
        left = ttk.Frame(self, padding=12)
        left.pack(side=tk.LEFT, fill=tk.Y)

        style = ttk.Style(self)
        style.configure("Popup.TLabel", font=("Segoe UI", 12, "bold"))
        style.configure("ResultText.TLabel", font=("Segoe UI", 20, "bold"))

        # PASSWORD
        ttk.Label(left, text="Password (unlock version)").pack(anchor="w")
        self.pw_var = tk.StringVar()
        self.pw_entry = ttk.Entry(left, textvariable=self.pw_var, width=30, show="*")
        self.pw_entry.pack(anchor="w", pady=(0, 8))
        self.pw_entry.bind("<Return>", lambda e: self.unlock_version())

        ttk.Button(left, text="Unlock Version", command=self.unlock_version)\
            .pack(anchor="w", fill=tk.X, pady=(0, 10))

        # INPUT VERSION
        ttk.Label(left, text="Input Version").pack(anchor="w")
        self.input_var = tk.StringVar(value="24071721")
        self.input_entry = ttk.Entry(left, textvariable=self.input_var, width=30)
        self.input_entry.pack(anchor="w", pady=(0, 10))
        self.input_entry.bind("<Return>", lambda e: self.lock_version())
        self._apply_version_lock()

        # ===== TYPE (NEW) =====
        ttk.Label(left, text="Type").pack(anchor="w")
        self.mode_var = tk.StringVar(value="POPUP")
        self.mode_cb = ttk.Combobox(
            left,
            textvariable=self.mode_var,
            values=["POPUP", "INLINE"],
            state="readonly",
            width=28
        )
        self.mode_cb.pack(anchor="w", pady=(0, 10))

        # ===== INLINE window title (NEW) =====
        ttk.Label(left, text="INLINE: App title contains").pack(anchor="w")
        self.inline_title_var = tk.StringVar(value="BurnAP_Merge")
        ttk.Entry(left, textvariable=self.inline_title_var, width=30).pack(anchor="w", pady=(0, 10))

        # ===== POPUP: Title / Content =====
        ttk.Label(left, text="POPUP: Title contains (optional)").pack(anchor="w")
        self.title_key_var = tk.StringVar(value="AitUVCExtTest")
        ttk.Entry(left, textvariable=self.title_key_var, width=30).pack(anchor="w", pady=(0, 10))

        ttk.Label(left, text="POPUP: Content contains (optional)").pack(anchor="w")
        self.content_key_var = tk.StringVar(value="Firmware Version")
        ttk.Entry(left, textvariable=self.content_key_var, width=30).pack(anchor="w", pady=(0, 10))

        ttk.Button(left, text="Check once", command=self.check_once)\
            .pack(anchor="w", fill=tk.X, pady=(0, 8))

        self.auto_btn = ttk.Button(left, text="AUTO: OFF", command=self.toggle_auto)
        self.auto_btn.pack(anchor="w", fill=tk.X, pady=(0, 8))

        ttk.Separator(left).pack(fill=tk.X, pady=10)

        # DETECTED VERSION box
        ttk.Label(left, text="Detected Version:").pack(anchor="w")
        self.popup_box = tk.Frame(left, bg=CLR_BG_DEFAULT, highlightthickness=2, highlightbackground=CLR_BORDER_DEFAULT)
        self.popup_box.pack(anchor="w", fill=tk.X, pady=(4, 10))

        self.popup_lbl = tk.Label(self.popup_box, text="-", font=("Segoe UI", 12, "bold"),
                                  fg="black", bg=self.popup_box["bg"], anchor="center")
        self.popup_lbl.pack(fill=tk.X, padx=10, pady=8)

        # RESULT box
        ttk.Label(left, text="Result:").pack(anchor="w")
        self.result_box = tk.Frame(left, bg=CLR_BG_DEFAULT, highlightthickness=2, highlightbackground=CLR_BORDER_DEFAULT)
        self.result_box.pack(anchor="w", fill=tk.X, pady=(10, 15), ipady=40)

        self.result_lbl = tk.Label(self.result_box, text="-", font=("Segoe UI", 60, "bold"),
                                   fg="black", bg=self.result_box["bg"], anchor="center")
        self.result_lbl.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(left, text=f"AUTO polling: {AUTO_INTERVAL_MS}ms").pack(anchor="w", pady=(6, 0))

        # RIGHT TABLE
        right = ttk.Frame(self, padding=12)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        cols = ("no", "type", "input", "detected", "result", "message", "time")
        self.tree = ttk.Treeview(right, columns=cols, show="headings", height=22)

        for c, h in zip(cols, ("No", "Type", "Input", "Detected", "Result", "Message", "Time")):
            self.tree.heading(c, text=h)

        self.tree.column("no", width=50, anchor="center")
        self.tree.column("type", width=80, anchor="center")
        self.tree.column("input", width=140, anchor="w")
        self.tree.column("detected", width=140, anchor="w")
        self.tree.column("result", width=110, anchor="center")
        self.tree.column("message", width=420, anchor="w")
        self.tree.column("time", width=210, anchor="w")

        self.tree.pack(fill=tk.BOTH, expand=True)
        self.history = []

    def _set_box_color(self, box: tk.Frame, label: tk.Label, bg: str, border: str, fg: str):
        box.config(bg=bg, highlightbackground=border)
        label.config(bg=bg, fg=fg)

    def _render_status(self, res: CheckResult | None):
        if not res:
            self.popup_lbl.config(text="-")
            self.result_lbl.config(text="-")
            self._set_box_color(self.popup_box, self.popup_lbl, CLR_BG_DEFAULT, CLR_BORDER_DEFAULT, "black")
            self._set_box_color(self.result_box, self.result_lbl, CLR_BG_DEFAULT, CLR_BORDER_DEFAULT, "black")
            return

        self.popup_lbl.config(text=res.popup_version or "")
        self.result_lbl.config(text=res.result)

        self._set_box_color(self.popup_box, self.popup_lbl, CLR_BG_DEFAULT, CLR_BORDER_DEFAULT, "black")

        if res.result == "OK":
            self._set_box_color(self.result_box, self.result_lbl, CLR_OK_BG, CLR_OK_BORDER, "white")
        elif res.result == "NG":
            self._set_box_color(self.result_box, self.result_lbl, CLR_NG_BG, CLR_NG_BORDER, "white")
        elif res.result == "ERROR":
            self._set_box_color(self.result_box, self.result_lbl, CLR_WARN_BG, CLR_WARN_BORDER, "black")
        else:
            self._set_box_color(self.result_box, self.result_lbl, CLR_BG_DEFAULT, CLR_BORDER_DEFAULT, "black")

    def _add_history_row(self, mode: str, res: CheckResult):
        self.history.insert(0, res)
        no = len(self.history)
        self.tree.insert("", 0, values=(no, mode, res.input_version, res.popup_version or "", res.result, res.message, res.ts))

    def _save_db_safe(self, res: CheckResult):
        try:
            self.db.insert_history(res)
        except Exception as e:
            if not self.db_failed_once:
                self.db_failed_once = True
                self.after(0, lambda: messagebox.showwarning("DB Warning", f"DB insert failed:\n{e}"))

    # ===================== PICK WINDOWS =====================
    def _pick_popup_candidates(self):
        title_key = (self.title_key_var.get() or "").strip()
        content_key = (self.content_key_var.get() or "").strip()

        if title_key:
            return find_windows_by_title_contains(title_key)  # SAFE (fast title)
        if content_key:
            return find_windows_by_content_contains(content_key, max_scan=80)
        return []

    def _pick_inline_candidates(self):
        key = (self.inline_title_var.get() or "").strip()
        if not key:
            return []
        return find_inline_windows_by_title(key)

    # ===================== CHECK CORE =====================
    def _do_check_once_core(self) -> tuple[str, CheckResult]:
        mode = (self.mode_var.get() or "POPUP").strip().upper()
        input_ver = (self.input_var.get() or "").strip()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

        if not input_ver:
            return mode, CheckResult(input_ver, None, "ERROR", "Input version is empty.", ts)

        if mode == "INLINE":
            wins = self._pick_inline_candidates()
            if not wins:
                key = (self.inline_title_var.get() or "").strip()
                return mode, CheckResult(input_ver, None, "NOT_FOUND", f"Inline window not found (title contains='{key}').", ts)

            win = wins[-1]
            ver = read_inline_version(win, FW_INLINE_PATTERN)
            if not ver:
                return mode, CheckResult(input_ver, None, "NOT_FOUND", "Inline window found but cannot read FW Version.", ts)

        else:
            title_key = (self.title_key_var.get() or "").strip()
            content_key = (self.content_key_var.get() or "").strip()

            wins = self._pick_popup_candidates()
            if not wins:
                if title_key:
                    return mode, CheckResult(input_ver, None, "NOT_FOUND", f"Target not found (title contains='{title_key}').", ts)
                if content_key:
                    return mode, CheckResult(input_ver, None, "NOT_FOUND", f"Target not found (content contains='{content_key}').", ts)
                return mode, CheckResult(input_ver, None, "ERROR", "Please fill POPUP Title or Content.", ts)

            win = wins[-1]
            if title_key and content_key and not window_contains_confirm_key(win, content_key):
                return mode, CheckResult(input_ver, None, "SKIP", f"Title matched but popup missing content '{content_key}' (skip).", ts)

            # chống spam popup trong AUTO
            if self.auto_running:
                try:
                    h = win.handle
                    if h in self.handled:
                        return mode, CheckResult(input_ver, None, "SKIP", "Popup already handled.", ts)
                    self.handled.add(h)
                except Exception:
                    pass

            ver = read_version_hybrid(win, FW_POPUP_PATTERN)
            if not ver:
                return mode, CheckResult(input_ver, None, "NOT_FOUND", "Popup found but cannot read firmware version.", ts)

        if ver.lower() == input_ver.lower():
            return mode, CheckResult(input_ver, ver, "OK", "Version matched.", ts)

        return mode, CheckResult(input_ver, ver, "NG", f"Version mismatch. Detected={ver}, Input={input_ver}", ts)

    # ===================== UI ACTIONS =====================
    def check_once(self):
        self.lock_version()

        def worker():
            try:
                mode, res = self._do_check_once_core()
                self.after(0, lambda: self._on_result(mode, res, show_popup=True))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _on_result(self, mode: str, res: CheckResult, show_popup: bool):
        self._render_status(res)
        self._add_history_row(mode, res)
        threading.Thread(target=self._save_db_safe, args=(res,), daemon=True).start()

        if res.result == "OK":
            play_mp3(OK_SOUND)
        elif res.result in ("NG", "ERROR"):
            play_mp3(WRONG_SOUND)

        if show_popup:
            if res.result == "OK":
                messagebox.showinfo("OK", res.message)
            elif res.result == "NG":
                messagebox.showerror("NG", res.message)
            elif res.result == "ERROR":
                messagebox.showerror("ERROR", res.message)
            else:
                messagebox.showwarning(res.result, res.message)

    def toggle_auto(self):
        self.auto_running = not self.auto_running
        self.auto_btn.config(text=("AUTO: ON" if self.auto_running else "AUTO: OFF"))

        if self.auto_running:
            self.lock_version()
            self.handled.clear()

            # chạy AUTO nền -> không block Tkinter
            threading.Thread(target=self._auto_worker, daemon=True).start()

    def _auto_worker(self):
        interval_ms = max(50, int(AUTO_INTERVAL_MS))
        while self.auto_running:
            try:
                mode, res = self._do_check_once_core()
                # AUTO: chỉ log khi có kết quả quan trọng
                if res.result in ("OK", "NG", "ERROR"):
                    self.after(0, lambda m=mode, r=res: self._on_result(m, r, show_popup=False))

            except Exception as e:
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
                mode = (self.mode_var.get() or "POPUP").strip().upper()
                res = CheckResult(self.input_var.get() or "", None, "ERROR", str(e), ts)
                self.after(0, lambda m=mode, r=res: self._on_result(m, r, show_popup=False))

            time.sleep(interval_ms / 1000.0)


def run_app():
    app = App()
    app.mainloop()