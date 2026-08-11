import logging
from logging.handlers import RotatingFileHandler


class PythonLogger:
    def __init__(self, name, path, enable_console=True):
        self.logger = logging.getLogger(name)

        self.logger.propagate = False

        if self.logger.handlers:
            return

        self.logger.setLevel(logging.DEBUG)

        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | "
            "%(pathname)s:%(funcName)s:%(lineno)d\n"
            "   %(message)s"
        )

        if enable_console:
            console = logging.StreamHandler()
            console.setFormatter(formatter)
            self.logger.addHandler(console)

        file = RotatingFileHandler(
            path, maxBytes=1024 * 1024, backupCount=3, encoding="utf-8"
        )

        file.setFormatter(formatter)
        self.logger.addHandler(file)

    def debug(self, message, *args, **kwargs):
        # stacklevel=2 giúp nhảy qua 1 lớp bọc này để lấy vị trí gọi thực tế
        self.logger.debug(message, *args, stacklevel=2, **kwargs)

    def info(self, message, *args, **kwargs):
        self.logger.info(message, *args, stacklevel=2, **kwargs)

    def warning(self, message, *args, **kwargs):
        self.logger.warning(message, *args, stacklevel=2, **kwargs)

    def error(self, message, *args, **kwargs):
        self.logger.error(message, *args, stacklevel=2, **kwargs)
