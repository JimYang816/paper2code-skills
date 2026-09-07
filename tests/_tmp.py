"""Temporary-directory helper that avoids Python's read-only Windows mkdtemp mode."""

import os
from pathlib import Path
import shutil
import uuid


class TempDirectory:
    def __init__(self):
        base = Path(__file__).resolve().parents[1] / ".scratch" / "test-tmp"
        os.makedirs(base, exist_ok=True)
        self.name = str(base / uuid.uuid4().hex)
        os.mkdir(self.name)

    def __enter__(self):
        return self.name

    def __exit__(self, exc_type, exc, traceback):
        self.cleanup()

    def cleanup(self):
        shutil.rmtree(self.name, ignore_errors=True)
