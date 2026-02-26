import threading
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox

from .config import AUTO_INTERVAL_MS, ASSET_WRONG_SOUND_REL, ASSET_OK_SOUND_REL, UNLOCK_PASSWORDS
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

# ====== Colors ======
CLR_BG_DEFAULT = "#E5E7EB"  # gray
CLR_BORDER_DEFAULT = "#9CA3AF"

CLR_OK_BG = "#22C55E"       # green
CLR_OK_BORDER = "#16A34A"

CLR_NG_BG = "#EF4444"       # red
CLR_NG_BORDER = "#DC2626"

CLR_WARN_BG = "#F59E0B"     # amber
CLR_WARN_BORDER = "#D97706"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Firmware Version Check (WIN32+UIA + SQL + SOUND)")
        self.geometry("1100x600")

        self.auto_running = False
        self.handled = set()

        self.db = DbLogger()
        self.db_failed_once = False

        # ===== lock input version by default =====
        self.version_locked = True

        self._build_ui()
        self._render_status(None)

    # ===================== VERSION LOCK =====================
    def _apply_version_lock(self):
        """Lock/unlock the Input Version entry."""
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
        """Enter correct password => unlock input version."""
        pw = (self.pw_var.get() or "").strip()

        if pw not in UNLOCK_PASSWORDS:
            messagebox.showerror("Permission denied", "Wrong password.")
            self.version_locked = True
            self._apply_version_lock()
            return

        self.version_locked = False
        self._apply_version_lock()

        # clear password and focus version entry
        self.pw_var.set("")
        self.input_entry.focus_set()

    def lock_version(self):
        """Lock again (press Enter in version entry)."""
        self.version_locked = True
        self._apply_version_lock()
        if hasattr(self, "pw_entry"):
            self.pw_entry.focus_set()

    # ===================== UI =====================
    def _build_ui(self):
        # ===== Left panel =====
        left = ttk.Frame(self, padding=12)
        left.pack(side=tk.LEFT, fill=tk.Y)

        # Styles
        style = ttk.Style(self)
        style.configure("Popup.TLabel", font=("Segoe UI", 12, "bold"))
        style.configure("ResultText.TLabel", font=("Segoe UI", 20, "bold"))

        # ===== PASSWORD to unlock version =====
        ttk.Label(left, text="Password (unlock version)").pack(anchor="w")
        self.pw_var = tk.StringVar()
        self.pw_entry = ttk.Entry(left, textvariable=self.pw_var, width=30, show="*")
        self.pw_entry.pack(anchor="w", pady=(0, 8))

        # Enter ở password để unlock
        self.pw_entry.bind("<Return>", lambda e: self.unlock_version())

        ttk.Button(left, text="Unlock Version", command=self.unlock_version) \
            .pack(anchor="w", fill=tk.X, pady=(0, 10))

        # ===== INPUT VERSION (locked by default) =====
        ttk.Label(left, text="Input Version").pack(anchor="w")
        self.input_var = tk.StringVar(value="24071721")
        self.input_entry = ttk.Entry(left, textvariable=self.input_var, width=30)
        self.input_entry.pack(anchor="w", pady=(0, 10))

        # Enter trong Input Version để tự khóa lại
        self.input_entry.bind("<Return>", lambda e: self.lock_version())

        # Apply lock ngay khi mở app
        self._apply_version_lock()

        # ===== Title / Content =====
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

        # ===== Popup Version box =====
        ttk.Label(left, text="Popup Version:").pack(anchor="w")

        self.popup_box = tk.Frame(
            left,
            bg=CLR_BG_DEFAULT,
            highlightthickness=2,
            highlightbackground=CLR_BORDER_DEFAULT,
        )
        self.popup_box.pack(anchor="w", fill=tk.X, pady=(4, 10))

        self.popup_lbl = tk.Label(
            self.popup_box,
            text="-",
            font=("Segoe UI", 12, "bold"),
            fg="black",
            bg=self.popup_box["bg"],
            anchor="center",
        )
        self.popup_lbl.pack(fill=tk.X, padx=10, pady=8)

        # ===== Result box (BIG + colored) =====
        ttk.Label(left, text="Result:").pack(anchor="w")

        self.result_box = tk.Frame(
            left,
            bg=CLR_BG_DEFAULT,
            highlightthickness=2,
            highlightbackground=CLR_BORDER_DEFAULT,
        )
        # x3 size 느낌: ipady lớn + font lớn
        self.result_box.pack(anchor="w", fill=tk.X, pady=(10, 15), ipady=40)

        self.result_lbl = tk.Label(
            self.result_box,
            text="-",
            font=("Segoe UI", 60, "bold"),
            fg="black",
            bg=self.result_box["bg"],
            anchor="center",
        )
        self.result_lbl.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(left, text=f"AUTO polling: {AUTO_INTERVAL_MS}ms").pack(anchor="w", pady=(6, 0))
        ttk.Label(left, text=f"Sound OK: {OK_SOUND}").pack(anchor="w", pady=(6, 0))
        ttk.Label(left, text=f"Sound NG: {WRONG_SOUND}").pack(anchor="w", pady=(2, 0))

        # ===== Right panel =====
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

        # Popup box: giữ default
        self._set_box_color(self.popup_box, self.popup_lbl, CLR_BG_DEFAULT, CLR_BORDER_DEFAULT, "black")

        # Result box đổi màu
        if res.result == "OK":
            self._set_box_color(self.result_box, self.result_lbl, CLR_OK_BG, CLR_OK_BORDER, "white")
        elif res.result == "NG":
            self._set_box_color(self.result_box, self.result_lbl, CLR_NG_BG, CLR_NG_BORDER, "white")
        elif res.result == "ERROR":
            self._set_box_color(self.result_box, self.result_lbl, CLR_WARN_BG, CLR_WARN_BORDER, "black")
        else:
            self._set_box_color(self.result_box, self.result_lbl, CLR_BG_DEFAULT, CLR_BORDER_DEFAULT, "black")

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

        if title_key and content_key and not window_contains_confirm_key(win, content_key):
            return CheckResult(
                input_ver, None, "SKIP",
                f"Title matched but popup missing content '{content_key}' (skip).",
                ts
            )

        popup_ver = read_firmware_version_hybrid(win)
        if not popup_ver:
            return CheckResult(
                input_ver, None, "NOT_FOUND",
                "Popup found but cannot read firmware version (UIA/WIN32 text not available).",
                ts
            )

        if popup_ver.lower() == input_ver.lower():
            return CheckResult(input_ver, popup_ver, "OK", "Version matched.", ts)

        return CheckResult(
            input_ver, popup_ver, "NG",
            f"Version mismatch. Popup={popup_ver}, Input={input_ver}",
            ts
        )

    def check_once(self):
        self.lock_version()
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
            self.lock_version()
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
                res = CheckResult(
                    input_ver, None, "SKIP",
                    f"New popup title matched but missing content '{content_key}' (skip).",
                    ts
                )
                self._on_result(res, show_popup=False)
                continue

            popup_ver = read_firmware_version_hybrid(w)
            if not popup_ver:
                res = CheckResult(input_ver, None, "NOT_FOUND", "Cannot read firmware version from target popup.", ts)
            elif popup_ver.lower() == input_ver.lower():
                res = CheckResult(input_ver, popup_ver, "OK", "Version matched.", ts)
            else:
                res = CheckResult(
                    input_ver, popup_ver, "NG",
                    f"Version mismatch. Popup={popup_ver}, Input={input_ver}",
                    ts
                )

            self._on_result(res, show_popup=False)

        if len(self.handled) > 5000:
            self.handled.clear()

        self.after(AUTO_INTERVAL_MS, self._auto_loop)


def run_app():
    app = App()
    app.mainloop()