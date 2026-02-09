import time
from pywinauto import Desktop

APP_TITLE_RE = r"AIT UVC Extension Unit Tool.*"

class DeviceWatcher:
    def __init__(self, poll_ms=300, min_len=3):
        self.poll_ms = poll_ms
        self.min_len = min_len
        self._last_connected = False

    def _get_app(self):
        app = Desktop(backend="uia").window(title_re=APP_TITLE_RE)
        app.wait("visible", timeout=10)
        return app

    def _pick_device_info_control(self, app):
        # Ưu tiên Edit (ô dài cạnh Select Device)
        edits = app.descendants(control_type="Edit")
        if not edits:
            edits = app.descendants(control_type="Text")

        best = None
        best_w = -1
        for c in edits:
            try:
                r = c.rectangle()
                if r.width() > best_w:
                    best_w = r.width()
                    best = c
            except Exception:
                pass
        return best

    def _read_text(self, ctrl):
        if not ctrl:
            return ""
        try:
            return (ctrl.window_text() or "").strip()
        except Exception:
            return ""

    def _click_fw_version(self, app):
        btn = app.child_window(title="FW Version", control_type="Button")
        if btn.exists() and btn.is_enabled():
            btn.click_input()

    def watch_once(self) -> bool:
        """
        return True nếu vừa detect cắm device (rising edge)
        """
        app = self._get_app()
        ctrl = self._pick_device_info_control(app)
        txt = self._read_text(ctrl)

        connected = len(txt) >= self.min_len
        rising_edge = (not self._last_connected) and connected

        if rising_edge:
            app.set_focus()
            self._click_fw_version(app)

        self._last_connected = connected
        return rising_edge

    def loop(self):
        while True:
            try:
                self.watch_once()
            except Exception as e:
                print("DeviceWatcher error:", e)
            time.sleep(self.poll_ms / 1000)
