import os
import sys

def base_dir() -> str:
    """
    Dev:
      base = folder chứa app.py
    PyInstaller --onefile:
      sys._MEIPASS = thư mục temp extract (bạn thấy MEIxxxx)
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    # app.py nằm ở root project => base dir là folder của app.py
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # fwchecker/.. => project root

def resource_path(relative: str) -> str:
    return os.path.join(base_dir(), relative)
