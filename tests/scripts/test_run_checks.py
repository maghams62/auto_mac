from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from scripts import run_checks


def test_run_checks_uses_repo_root(monkeypatch):
    captured = {}

    def fake_run(cmd, cwd=None, text=False):  # type: ignore[override]
        captured["cmd"] = cmd
        captured["cwd"] = cwd

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(run_checks, "CHECK_COMMANDS", {"dummy": ["echo", "ok"]})
    monkeypatch.setattr(run_checks, "subprocess", SimpleNamespace(run=fake_run))

    rc = run_checks.run_check("dummy")

    assert rc == 0
    assert Path(captured["cwd"]).resolve() == run_checks.REPO_ROOT.resolve()

