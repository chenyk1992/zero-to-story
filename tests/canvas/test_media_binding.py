from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from lfo.canvas.media import CanvasMedia
from lfo.canvas.settings import CanvasSettings


@pytest.mark.parametrize("changed", ["frame", "parent"])
def test_accepted_derived_input_checks_frame_and_actual_parent(tmp_path, changed):
    media = CanvasMedia(CanvasSettings(tmp_path, tmp_path / "state", tmp_path / "media"))
    media.settings.media_root.mkdir()
    frame = media.settings.media_root / "frame.png"
    parent = media.settings.media_root / "adopted.mp4"
    frame.write_bytes(b"actual frame")
    parent.write_bytes(b"actual adopted parent")
    asset = media.import_file(str(frame))
    assert asset["path"] == str(frame.resolve())
    value = {
        **asset,
        "accepted_sha256": asset["sha256"],
        "accepted_source": {
            "output_path": str(parent),
            "output_sha256": hashlib.sha256(parent.read_bytes()).hexdigest(),
        },
    }
    snapshot = {"inputs": {"first_frame": value}}
    frozen = media.freeze(snapshot, "request")
    assert media.inputs_unchanged(frozen)
    (frame if changed == "frame" else parent).write_bytes(b"replaced file")
    assert not media.inputs_unchanged(frozen)
    with pytest.raises(ValueError, match="发生变化"):
        media.validate_input(value)
    with pytest.raises(ValueError, match="发生变化"):
        media.freeze(snapshot, "next-request")
    # A confirmed request still executes its original frozen bytes.
    assert (
        media.execution_snapshot(frozen)["inputs"]["first_frame"]["path"]
        == frozen["inputs"]["first_frame"]["frozen_path"]
    )


def test_frozen_input_accepts_directory_identity_across_resolved_alias(tmp_path, monkeypatch):
    media = CanvasMedia(CanvasSettings(tmp_path, tmp_path / "state", tmp_path / "media"))
    media.settings.media_root.mkdir()
    frame = media.settings.media_root / "frame.png"
    frame.write_bytes(b"original frozen image")
    frozen = media.freeze({"inputs": {"first_frame": media.import_file(str(frame))}}, "request")
    input_root = media.settings.data_dir / "inputs"
    original_resolve = Path.resolve

    def resolve_alias(path, *args, **kwargs):
        if path == input_root:
            return tmp_path / "logical-alias" / "inputs"
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve_alias)
    effective = media.execution_snapshot(frozen)
    assert Path(effective["inputs"]["first_frame"]["path"]).read_bytes() == frame.read_bytes()

    outside = tmp_path / "outside" / "request" / "frame.png"
    outside.parent.mkdir(parents=True)
    outside.write_bytes(frame.read_bytes())
    frozen["inputs"]["first_frame"]["frozen_path"] = str(outside)
    with pytest.raises(ValueError, match="运行输入路径无效"):
        media.execution_snapshot(frozen)
