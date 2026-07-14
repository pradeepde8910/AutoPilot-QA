"""
Application-wide constants for the AI Test Engineering Platform.
"""
from pathlib import Path

import os
from config.settings import settings

# Base Paths
PROJECT_ROOT = Path(__file__).parent.parent.resolve()

class DynamicPath:
    """A proxy class that dynamically resolves path relative to settings.OUTPUT_DIR."""
    def __init__(self, dir_name: str):
        self.dir_name = dir_name

    @property
    def _path(self) -> Path:
        if settings.OUTPUT_DIR:
            base = Path(settings.OUTPUT_DIR).resolve()
            if self.dir_name == "reports":
                d = base
            else:
                d = base / self.dir_name
        else:
            d = PROJECT_ROOT / self.dir_name
        d.mkdir(parents=True, exist_ok=True)
        return d

    def __truediv__(self, other):
        return self._path / other

    def __rtruediv__(self, other):
        return other / self._path

    def __str__(self):
        return str(self._path)

    def __repr__(self):
        return repr(self._path)

    def __fspath__(self):
        return os.fspath(self._path)

    def __getattr__(self, name):
        return getattr(self._path, name)

LOGS_DIR = DynamicPath("logs")
SCREENSHOTS_DIR = DynamicPath("screenshots")
REPORTS_DIR = DynamicPath("reports")
INPUT_DIR = DynamicPath("input")

# Status Constants
STATUS_PENDING = "PENDING"
STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
STATUS_PARTIAL = "PARTIAL"
STATUS_NOT_EXECUTED = "NOT_EXECUTED"

# Priority Levels
PRIORITY_HIGH = "High"
PRIORITY_MEDIUM = "Medium"
PRIORITY_LOW = "Low"
