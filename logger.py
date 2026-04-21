"""Dual-output logger: colored console + structured JSON file."""
import json
from datetime import datetime
from pathlib import Path


class Logger:
    """Logger with colored console output and JSONL file output."""

    COLORS = {
        "info": "\033[34m",
        "ok": "\033[32m",
        "warn": "\033[33m",
        "error": "\033[31m",
        "reset": "\033[0m",
    }

    LEVEL_LABELS = {
        "info": "INFO",
        "ok": "OK",
        "warn": "WARN",
        "error": "ERROR",
    }

    def __init__(self, module_name: str, jsonl_path: str = None):
        self.module_name = module_name
        self.jsonl_path = Path(jsonl_path) if jsonl_path else None
        if self.jsonl_path:
            self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
            self._file = open(self.jsonl_path, "a", encoding="utf-8")
        else:
            self._file = None

    def _format_console(self, level: str, msg: str, **kwargs) -> str:
        label = self.LEVEL_LABELS.get(level, level).upper()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"{ts} [{label:<5}] {self.module_name:<12} {msg}"

    def _write_json(self, level: str, msg: str, **kwargs):
        if not self._file:
            return
        entry = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "level": level,
            "module": self.module_name,
            "msg": msg,
        }
        entry.update(kwargs)
        self._file.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._file.flush()

    def _log(self, level: str, msg: str, **kwargs):
        console_msg = self._format_console(level, msg, **kwargs)
        print(f"{self.COLORS.get(level, '')}{console_msg}{self.COLORS['reset']}", flush=True)
        self._write_json(level, msg, **kwargs)

    def info(self, msg: str, **kwargs):
        self._log("info", msg, **kwargs)

    def ok(self, msg: str, **kwargs):
        self._log("ok", msg, **kwargs)

    def warn(self, msg: str, **kwargs):
        self._log("warn", msg, **kwargs)

    def error(self, msg: str, **kwargs):
        self._log("error", msg, **kwargs)

    def close(self):
        if self._file:
            self._file.close()
            self._file = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


def get_logger(module_name: str, jsonl_path: str = None) -> Logger:
    """Get a logger instance."""
    return Logger(module_name, jsonl_path)
