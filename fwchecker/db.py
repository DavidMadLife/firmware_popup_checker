import threading
from datetime import datetime

import pyodbc

from .config import (
    DEFAULT_SQL_SERVER, DEFAULT_SQL_DB, DEFAULT_SQL_USER, DEFAULT_SQL_PASS,
    ODBC_DRIVER_PRIMARY, ODBC_DRIVER_FALLBACK, TABLE_NAME
)
from .models import CheckResult

class DbLogger:
    def __init__(self):
        self.server = DEFAULT_SQL_SERVER
        self.database = DEFAULT_SQL_DB
        self.username = DEFAULT_SQL_USER
        self.password = DEFAULT_SQL_PASS

        self._conn = None
        self._lock = threading.Lock()
        self.driver = self._pick_driver()

        self.conn_str = (
            f"DRIVER={{{self.driver}}};"
            f"SERVER={self.server};"
            f"DATABASE={self.database};"
            f"UID={self.username};"
            f"PWD={self.password};"
            "Encrypt=Yes;"
            "TrustServerCertificate=Yes;"
            "Connection Timeout=5;"
        )

    def _pick_driver(self) -> str:
        drivers = [d.lower() for d in pyodbc.drivers()]
        if ODBC_DRIVER_PRIMARY.lower() in drivers:
            return ODBC_DRIVER_PRIMARY
        if ODBC_DRIVER_FALLBACK.lower() in drivers:
            return ODBC_DRIVER_FALLBACK
        return ODBC_DRIVER_PRIMARY

    def _get_conn(self):
        if self._conn is None:
            self._conn = pyodbc.connect(self.conn_str, autocommit=True)
        return self._conn

    def insert_history(self, res: CheckResult):
        sql = f"""
        INSERT INTO {TABLE_NAME} (InputVersion, PopupVersion, Result, Message, CreatedAt)
        VALUES (?, ?, ?, ?, ?)
        """
        created_at = datetime.strptime(res.ts, "%Y-%m-%d %H:%M:%S.%f")

        with self._lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(sql, res.input_version, res.popup_version, res.result, res.message, created_at)
