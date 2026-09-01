"""Shared test fixtures — applies to every test file in this directory."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def isolate_output_folder(tmp_path, monkeypatch):
    """Every runner writes through output_folder(name) -> Desktop/<name>.

    Without this, tests silently write real files onto the developer's
    actual Desktop (Compressed/, Locked PDF/, etc.) — confirmed the hard
    way: a real, non-fixture file (from actually running the app by hand)
    turned up in one of those folders and made a size assertion flaky
    depending on what else happened to be sitting there. Autouse and
    defined here (not per-file) so no test, in any file, can forget to
    opt in and accidentally touch the real filesystem outside tmp_path.
    """
    from toolboxcli.core import runners

    def fake_output_folder(name: str) -> Path:
        folder = tmp_path / name
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    monkeypatch.setattr(runners, "output_folder", fake_output_folder)
