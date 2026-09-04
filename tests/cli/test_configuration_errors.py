from __future__ import annotations

import json

from lfo.cli.main import main


def test_unknown_machine_profile_returns_structured_cli_error(capsys):
    code = main(["--json", "validate", "unused-package.json", "--machine-id", "missing"])
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert code != 0
    assert result["ok"] is False
    assert "missing" in result["error"]["message"]
    assert "Traceback" not in captured.err
