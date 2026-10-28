"""Dịch vụ ghi nhật ký sử dụng thư viện logging chuẩn của Python."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from src.domain.ports import LoggerPort


class StandardLoggerService(LoggerPort):
    """Adapter triển khai LoggerPort ghi log ra file xoay vòng và màn hình console."""

    def __init__(
        self,
        log_file: Path | str,
        name: str = "agent_logger",
        enable_console: bool = True,
        level: int = logging.DEBUG,
    ):
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        self._logger = logging.getLogger(name)
        self._logger.setLevel(level)
        self._logger.propagate = False

        if not self._logger.handlers:
            formatter = logging.Formatter(
                "%(asctime)s - %(levelname)-8s - %(pathname)s:%(funcName)s:%(lineno)d %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )

            if enable_console:
                console_handler = logging.StreamHandler()
                console_handler.setFormatter(formatter)
                self._logger.addHandler(console_handler)

            file_handler = RotatingFileHandler(
                self.log_file,
                maxBytes=1024 * 1024,
                backupCount=3,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            self._logger.addHandler(file_handler)

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._logger.debug(msg, *args, **kwargs)

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._logger.error(msg, *args, **kwargs)

    def close(self) -> None:
        """Đóng tất cả các handlers để giải phóng file lock."""
        for handler in list(self._logger.handlers):
            handler.close()
            self._logger.removeHandler(handler)
