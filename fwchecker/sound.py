import os
import subprocess

def play_mp3(path: str, min_ms: int = 1500):
    """
    Play mp3 via PowerShell MediaPlayer (ổn định cho cả OK/NG).
    - Convert path -> file:/// URI
    - Giữ process sống đủ lâu để nghe thấy
    """
    if not path:
        return

    p = os.path.abspath(path)
    if not os.path.exists(p):
        return

    # MediaPlayer cần URI dạng file:///
    uri = "file:///" + p.replace("\\", "/")
    uri = uri.replace("'", "''")

    cmd = [
        "powershell",
        "-NoProfile",
        "-WindowStyle", "Hidden",
        "-Command",
        (
            "Add-Type -AssemblyName PresentationCore; "
            "$player = New-Object System.Windows.Media.MediaPlayer; "
            f"$player.Open([Uri]'{uri}'); "
            "$player.Volume = 1.0; "
            "$player.Play(); "
            f"Start-Sleep -Milliseconds {min_ms};"
        )
    ]

    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
