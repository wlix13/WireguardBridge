"""Logging functions for WireGuard Bridge."""

import logging
import os
import sys


# ANSI color codes
class Colors:
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[0;34m"
    NC = "\033[0m"  # No Color


class Logger:
    """Logger with colored output."""

    def __init__(self, name: str = "wireguard-bridge"):
        self.level = os.environ.get("LOG_LEVEL", "INFO").upper()

        self.logger = logging.getLogger(name)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                f"{Colors.BLUE}[%(levelname)s]{Colors.NC} %(asctime)s %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(self.level)

    def debug(self, message: str) -> None:
        """Log debug message with blue color."""

        self.logger.debug(message)
        sys.stdout.flush()

    def info(self, message: str) -> None:
        """Log info message with blue color."""

        self.logger.info(message)
        sys.stdout.flush()

    def success(self, message: str) -> None:
        """Log success message with green color."""

        self.logger.info(f"{Colors.GREEN}SUCCESS:{Colors.NC} {message}")
        sys.stdout.flush()

    def warning(self, message: str) -> None:
        """Log warning message with yellow color."""

        self.logger.warning(message)
        sys.stderr.flush()

    def error(self, message: str) -> None:
        """Log error message with red color."""

        self.logger.error(message)
        sys.stderr.flush()


LOG = Logger()
