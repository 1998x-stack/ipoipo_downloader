"""Dual-output logger: colored console + structured JSONL file.

This module provides a ``Logger`` class that writes log entries to two
destinations simultaneously:

1. **Console** — Color-coded text output (ANSI escape codes). Colors are
   automatically disabled when stdout is not a TTY (e.g., piped to a file).
2. **JSONL file** — One JSON object per line, append-only. Each entry includes
   a timestamp, log level, module name, message, and any extra keyword arguments.

Thread safety is ensured by a ``threading.Lock`` around all file writes, so
multiple threads can log concurrently without corrupting the JSONL file.

Usage::

    from logger import get_logger

    log = get_logger("my_module", jsonl_path="logs/events.jsonl")
    log.info("Starting stage 1")
    log.ok("Category found", category_id="85")
    log.warn("Rate limit approaching")
    log.error("Download failed", post_id="12345")
    log.close()

Or as a context manager::

    with get_logger("my_module", "logs/events.jsonl") as log:
        log.info("Inside context manager")
    # File is automatically closed on exit.
"""
import io
import json
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class Logger:
    """Logger with colored console output and JSONL file output.

    Each log call writes to both the console (with ANSI color codes) and an
    optional JSONL file. Console colors are suppressed when stdout is not a
    TTY, making log output clean when redirected to files or CI pipelines.

    File writes are protected by a threading lock so that concurrent log calls
    from multiple threads produce valid, non-interleaved JSONL lines.

    Attributes:
        COLORS: Mapping of level names to ANSI color escape sequences.
        LEVEL_LABELS: Mapping of level names to fixed-width display labels.
        module_name: Identifier printed in every log line.
        jsonl_path: Path to the JSONL log file (None if console-only).
        _is_tty: Whether stdout is a terminal (controls color output).
        _lock: Threading lock protecting concurrent file writes.
        _file: Open file handle for JSONL output (None if no path given).
    """

    COLORS: Dict[str, str] = {
        "info": "\033[34m",
        "ok": "\033[32m",
        "warn": "\033[33m",
        "error": "\033[31m",
        "reset": "\033[0m",
    }

    LEVEL_LABELS: Dict[str, str] = {
        "info": "INFO",
        "ok": "OK",
        "warn": "WARN",
        "error": "ERROR",
    }

    def __init__(self, module_name: str, jsonl_path: Optional[str] = None) -> None:
        """Initialize a Logger instance.

        Args:
            module_name: Name displayed in every log line (e.g., "main", "scraper").
            jsonl_path: Optional path to a JSONL file for persistent log storage.
                The parent directory is created automatically if it does not exist.
        """
        self.module_name: str = module_name
        self.jsonl_path: Optional[Path] = Path(jsonl_path) if jsonl_path else None
        self._is_tty: bool = sys.stdout.isatty()
        self._lock: threading.Lock = threading.Lock()
        self._file: Optional[io.TextIOWrapper] = None

        if self.jsonl_path is not None:
            # 确保日志目录存在，即使父目录尚未创建
            self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
            self._file = open(self.jsonl_path, "a", encoding="utf-8")

    def _format_console(self, level: str, msg: str, **kwargs: Any) -> str:
        """Format a log line for console display.

        Produces a fixed-width timestamped string suitable for terminal output.
        Extra keyword arguments are ignored in console output (they only appear
        in the JSONL file).

        Args:
            level: Log level name ("info", "ok", "warn", "error").
            msg: Human-readable log message.
            **kwargs: Additional context data (ignored for console output).

        Returns:
            Formatted console line, e.g. "2026-04-22 08:00:00 [INFO ] main  ...".
        """
        label: str = self.LEVEL_LABELS.get(level, level).upper()
        ts: str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"{ts} [{label:<5}] {self.module_name:<12} {msg}"

    def _write_json(self, level: str, msg: str, **kwargs: Any) -> None:
        """Append a structured JSON entry to the JSONL file.

        This method is thread-safe: all file writes are serialized through
        ``self._lock`` to prevent interleaved or corrupted lines.

        Args:
            level: Log level name.
            msg: Human-readable log message.
            **kwargs: Additional key-value pairs merged into the JSON object
                (e.g., ``post_id="12345"``, ``file_size=4096``).
        """
        if self._file is None:
            return
        with self._lock:
            entry: Dict[str, Any] = {
                "ts": datetime.now().isoformat(timespec="seconds"),
                "level": level,
                "module": self.module_name,
                "msg": msg,
            }
            entry.update(kwargs)
            self._file.write(json.dumps(entry, ensure_ascii=False) + "\n")
            self._file.flush()

    def _log(self, level: str, msg: str, **kwargs: Any) -> None:
        """Core logging dispatch: writes to console and JSONL file.

        Console output uses ANSI color codes when stdout is a TTY; otherwise
        colors are stripped for clean file/pipe output.

        Args:
            level: Log level name.
            msg: Human-readable log message.
            **kwargs: Extra context data passed through to the JSONL entry.
        """
        console_msg: str = self._format_console(level, msg, **kwargs)
        if self._is_tty:
            color_code: str = self.COLORS.get(level, "")
            reset_code: str = self.COLORS["reset"]
            print(f"{color_code}{console_msg}{reset_code}", flush=True)
        else:
            print(console_msg, flush=True)
        self._write_json(level, msg, **kwargs)

    def info(self, msg: str, **kwargs: Any) -> None:
        """Log an informational message (blue).

        Args:
            msg: Human-readable log message.
            **kwargs: Extra context data for the JSONL entry.
        """
        self._log("info", msg, **kwargs)

    def ok(self, msg: str, **kwargs: Any) -> None:
        """Log a success message (green).

        Args:
            msg: Human-readable log message.
            **kwargs: Extra context data for the JSONL entry.
        """
        self._log("ok", msg, **kwargs)

    def warn(self, msg: str, **kwargs: Any) -> None:
        """Log a warning message (yellow).

        Args:
            msg: Human-readable log message.
            **kwargs: Extra context data for the JSONL entry.
        """
        self._log("warn", msg, **kwargs)

    def error(self, msg: str, **kwargs: Any) -> None:
        """Log an error message (red).

        Args:
            msg: Human-readable log message.
            **kwargs: Extra context data for the JSONL entry.
        """
        self._log("error", msg, **kwargs)

    def close(self) -> None:
        """Close the JSONL file handle if open.

        Safe to call multiple times — subsequent calls are no-ops.
        """
        if self._file is not None:
            self._file.close()
            self._file = None

    def __enter__(self) -> "Logger":
        """Enter the context manager protocol.

        Returns:
            Self, so that ``with get_logger(...) as log:`` works.
        """
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> bool:
        """Exit the context manager, closing the JSONL file.

        Args:
            exc_type: Exception class if an exception was raised, else None.
            exc_val: Exception instance if an exception was raised, else None.
            exc_tb: Traceback if an exception was raised, else None.

        Returns:
            False — exceptions are not suppressed and will propagate.
        """
        self.close()
        return False


def get_logger(module_name: str, jsonl_path: Optional[str] = None) -> Logger:
    """Factory function to create and return a Logger instance.

    This is the preferred entry point for obtaining a logger, used throughout
    the codebase (e.g., ``log = get_logger("scraper")``).

    Args:
        module_name: Name displayed in every log line.
        jsonl_path: Optional path to a JSONL file. When omitted or None,
            the logger writes to the console only.

    Returns:
        A configured Logger instance ready for use.
    """
    return Logger(module_name, jsonl_path)
