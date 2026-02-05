import os
import threading
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox

from .config import AUTO_INTERVAL_MS, ASSET_WRONG_SOUND_REL, ASSET_OK_SOUND_REL

from .models import CheckResult
from .db import DbLogger
from .resources import resource_path
from .sound import play_mp3
from .popup_reader import (
    find_windows_by_title_contains,
    find_windows_by_content_contains,
    read_firmware_version_hybrid,
    window_contains_confirm_key,
)

WRONG_SOUND = resource_path(ASSET_WRONG_SOUND_REL)
OK_SOUND = resource_path(ASSET_OK_SOUND_REL)

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Firmware Version Check (WIN32+UIA + SQL + SOUND)")
        self.geometry("1100x600")

        self.auto_running = False
        self.handled = set()

        self.db = DbLogger()
        self.db_failed_once = False

        self._build_ui()
        self._render_status(None)

    def _build_ui(self):
        left = ttk.Frame(self, padding=12)
        left.pack(side=tk.LEFT, fill=tk.Y)

        ttk.Label(left, text="Input Version").pack(anchor="w")
        self.input_var = tk.StringVar(value="24071721")
        ttk.Entry(left, textvariable=self.input_var, width=30).pack(anchor="w", pady=(0, 10))

        ttk.Label(left, text="Title contains (optional)").pack(anchor="w")
        self.title_key_var = tk.StringVar(value="AitUVCExtTest")
        ttk.Entry(left, textvariable=self.title_key_var, width=30).pack(anchor="w", pady=(0, 10))

        ttk.Label(left, text="Content contains (optional, used when title empty)").pack(anchor="w")
        self.content_key_var = tk.StringVar(value="Firmware Version")
        ttk.Entry(left, textvariable=self.content_key_var, width=30).pack(anchor="w", pady=(0, 10))

        ttk.Button(left, text="Check once", command=self.check_once).pack(anchor="w", fill=tk.X, pady=(0, 8))

        self.auto_btn = ttk.Button(left, text="AUTO: OFF", command=self.toggle_auto)
        self.auto_btn.pack(anchor="w", fill=tk.X, pady=(0, 8))

        ttk.Separator(left).pack(fill=tk.X, pady=10)

        ttk.Label(left, text="Popup Version:").pack(anchor="w")
        self.popup_lbl = ttk.Label(left, text="-", font=("Segoe UI", 11, "bold"))
        self.popup_lbl.pack(anchor="w", pady=(0, 8))

        ttk.Label(left, text="Result:").pack(anchor="w")
        self.result_lbl = ttk.Label(left, text="-", font=("Segoe UI", 11, "bold"))
        self.result_lbl.pack(anchor="w")

        ttk.Label(left, text=f"AUTO polling: {AUTO_INTERVAL_MS}ms").pack(anchor="w", pady=(10, 0))
        ttk.Label(left, text=f"Sound: {WRONG_SOUND}").pack(anchor="w", pady=(6, 0))

        right = ttk.Frame(self, padding=12)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        cols = ("no", "input", "popup", "result", "message", "time")
        self.tree = ttk.Treeview(right, columns=cols, show="headings", height=22)
        for c, h in zip(cols, ("No", "Input", "Popup", "Result", "Message", "Time")):
            self.tree.heading(c, text=h)

        self.tree.column("no", width=50, anchor="center")
        self.tree.column("input", width=140, anchor="w")
        self.tree.column("popup", width=140, anchor="w")
        self.tree.column("result", width=110, anchor="center")
        self.tree.column("message", width=520, anchor="w")
        self.tree.column("time", width=200, anchor="w")

        self.tree.pack(fill=tk.BOTH, expand=True)
        self.history = []

    def _render_status(self, res: CheckResult | None):
        if not res:
            self.popup_lbl.config(text="-")
            self.result_lbl.config(text="-")
            return
        self.popup_lbl.config(text=res.popup_version or "")
        self.result_lbl.config(text=res.result)

    def _add_history_row(self, res: CheckResult):
        self.history.insert(0, res)
        no = len(self.history)
        self.tree.insert("", 0, values=(no, res.input_version, res.popup_version or "", res.result, res.message, res.ts))

    def _save_db_safe(self, res: CheckResult):
        try:
            self.db.insert_history(res)
        except Exception as e:
            if not self.db_failed_once:
                self.db_failed_once = True
                print("DB insert failed:", e)
                self.after(0, lambda: messagebox.showwarning("DB Warning", f"DB insert failed:\n{e}"))

    def _pick_candidates(self):
        title_key = (self.title_key_var.get() or "").strip()
        content_key = (self.content_key_var.get() or "").strip()

        if title_key:
            return find_windows_by_title_contains(title_key)
        if content_key:
            return find_windows_by_content_contains(content_key, max_scan=80)
        return []

    def _do_check_once(self) -> CheckResult:
        input_ver = (self.input_var.get() or "").strip()
        title_key = (self.title_key_var.get() or "").strip()
        content_key = (self.content_key_var.get() or "").strip()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

        if not input_ver:
            return CheckResult(input_ver, None, "ERROR", "Input version is empty.", ts)

        wins = self._pick_candidates()
        if not wins:
            if title_key:
                return CheckResult(input_ver, None, "NOT_FOUND", f"Target not found (title contains='{title_key}').", ts)
            if content_key:
                return CheckResult(input_ver, None, "NOT_FOUND", f"Target not found (content contains='{content_key}').", ts)
            return CheckResult(input_ver, None, "ERROR", "Please fill Title contains or Content contains.", ts)

        win = wins[-1]

        # If title is used AND content_key exists -> confirm content to avoid false positives
        if title_key and content_key and not window_contains_confirm_key(win, content_key):
            return CheckResult(input_ver, None, "SKIP",
                               f"Title matched but popup missing content '{content_key}' (skip).", ts)

        popup_ver = read_firmware_version_hybrid(win)
        if not popup_ver:
            return CheckResult(input_ver, None, "NOT_FOUND",
                               "Popup found but cannot read firmware version (UIA/WIN32 text not available).", ts)

        if popup_ver.lower() == input_ver.lower():
            return CheckResult(input_ver, popup_ver, "OK", "Version matched.", ts)
        return CheckResult(input_ver, popup_ver, "NG",
                           f"Version mismatch. Popup={popup_ver}, Input={input_ver}", ts)

    def check_once(self):
        def worker():
            try:
                res = self._do_check_once()
                self.after(0, lambda: self._on_result(res, show_popup=True))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _on_result(self, res: CheckResult, show_popup: bool):
        self._render_status(res)
        self._add_history_row(res)

        

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
            self.handled.clear()
            self._auto_loop()

    def _auto_loop(self):
        if not self.auto_running:
            return

        input_ver = (self.input_var.get() or "").strip()
        title_key = (self.title_key_var.get() or "").strip()
        content_key = (self.content_key_var.get() or "").strip()

        wins = self._pick_candidates()
        for w in wins:
            try:
                handle = w.handle
            except Exception:
                continue

            if handle in self.handled:
                continue
            self.handled.add(handle)

            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

            if not input_ver:
                res = CheckResult(input_ver, None, "ERROR", "Input version is empty.", ts)
                self._on_result(res, show_popup=False)
                continue

            if title_key and content_key and not window_contains_confirm_key(w, content_key):
                res = CheckResult(input_ver, None, "SKIP",
                                  f"New popup title matched but missing content '{content_key}' (skip).", ts)
                self._on_result(res, show_popup=False)
                continue

            popup_ver = read_firmware_version_hybrid(w)
            if not popup_ver:
                res = CheckResult(input_ver, None, "NOT_FOUND", "Cannot read firmware version from target popup.", ts)
            elif popup_ver.lower() == input_ver.lower():
                res = CheckResult(input_ver, popup_ver, "OK", "Version matched.", ts)
            else:
                res = CheckResult(input_ver, popup_ver, "NG",
                                  f"Version mismatch. Popup={popup_ver}, Input={input_ver}", ts)

            self._on_result(res, show_popup=False)

        if len(self.handled) > 5000:
            self.handled.clear()

        self.after(AUTO_INTERVAL_MS, self._auto_loop)

def run_app():
    app = App()
    app.mainloop()
