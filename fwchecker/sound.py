import os
import subprocess

def play_mp3(path: str):
    """
    Play mp3 via PowerShell MediaPlayer và đợi phát xong (không bị cắt).
    Không cần pip dependency.
    """
    if not path or not os.path.exists(path):
        return

    ps_path = path.replace("'", "''")

    # PowerShell script: lấy Duration của file -> sleep đúng duration
    ps_script = rf"""
    Add-Type -AssemblyName presentationCore
    $file = '{ps_path}'
    $p = New-Object system.windows.media.mediaplayer
    $p.Open([uri]$file)
    $p.Play()

    # Lấy duration bằng Shell.Application (COM)
    $sh = New-Object -ComObject Shell.Application
    $folder = $sh.Namespace((Split-Path $file))
    $item = $folder.ParseName((Split-Path $file -Leaf))

    # Duration thường trả về dạng "mm:ss" hoặc "hh:mm:ss"
    $durText = $folder.GetDetailsOf($item, 27)

    function ToSeconds($t) {{
        if ([string]::IsNullOrWhiteSpace($t)) {{ return 2 }}
        $parts = $t.Split(':')
        if ($parts.Length -eq 2) {{
            return ([int]$parts[0]*60 + [int]$parts[1])
        }}
        if ($parts.Length -eq 3) {{
            return ([int]$parts[0]*3600 + [int]$parts[1]*60 + [int]$parts[2])
        }}
        return 2
    }}

    $sec = ToSeconds $durText
    Start-Sleep -Milliseconds (($sec * 1000) + 200)
    """

    cmd = [
        "powershell",
        "-NoProfile",
        "-WindowStyle", "Hidden",
        "-ExecutionPolicy", "Bypass",
        "-Command", ps_script
    ]

    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass