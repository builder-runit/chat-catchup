"""Shared test setup: make the skill's scripts importable and give each test its own settings folder."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "skills" / "chat-catchup" / "scripts"
EXAMPLES = ROOT / "examples"
sys.path.insert(0, str(SCRIPTS))


class IsolatedHome(unittest.TestCase):
    """Points CHAT_CATCHUP_HOME at a throwaway folder so tests never touch real settings."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = Path(self._tmp.name) / "home"
        self._old = os.environ.get("CHAT_CATCHUP_HOME")
        os.environ["CHAT_CATCHUP_HOME"] = str(self.home)
        self.addCleanup(self._restore)

    def _restore(self):
        if self._old is None:
            os.environ.pop("CHAT_CATCHUP_HOME", None)
        else:
            os.environ["CHAT_CATCHUP_HOME"] = self._old
