import os
import subprocess

def play_mp3(path: str):
    """
    Play mp3 via PowerShell MediaPlayer.
    Không cần pip dependency => build exe ổn.
    """
    if not path or not os.path.exists(path):
        return

    ps_path = path.replace("'", "''")
    cmd = [
        "powershell",
        "-NoProfile",
        "-WindowStyle", "Hidden",
        "-Command",
        (
            "Add-Type -AssemblyName presentationCore; "
            "$p=New-Object system.windows.media.mediaplayer; "
            f"$p.Open([uri]'{ps_path}'); "
            "$p.Play(); "
            "Start-Sleep -Milliseconds 900;"
        )
    ]
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
