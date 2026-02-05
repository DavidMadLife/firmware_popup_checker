import os
import re

FW_PATTERN = re.compile(r"Firmware\s*Version\s*:\s*([0-9A-Za-z._\-]+)", re.IGNORECASE)
AUTO_INTERVAL_MS = 500

# SQL Server connection (ưu tiên ENV; fallback theo bạn cung cấp)
DEFAULT_SQL_SERVER = os.getenv("CMTM_SQL_SERVER", "192.168.91.225,1433")
DEFAULT_SQL_DB     = os.getenv("CMTM_SQL_DB", "IOM")
DEFAULT_SQL_USER   = os.getenv("CMTM_SQL_USER", "sa")
DEFAULT_SQL_PASS   = os.getenv("CMTM_SQL_PASS", "1")

ODBC_DRIVER_PRIMARY = "ODBC Driver 18 for SQL Server"
ODBC_DRIVER_FALLBACK = "ODBC Driver 17 for SQL Server"

TABLE_NAME = "dbo.FirmwareCheckHistory"

# Assets
ASSET_WRONG_SOUND_REL = os.path.join("assets", "Wrong.mp3")
ASSET_OK_SOUND_REL = os.path.join("assets", "Ok.mp3")
