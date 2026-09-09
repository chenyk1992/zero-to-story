from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / ".agents/skills/canvas-workspace/scripts/import_workspace.py"
)
spec = importlib.util.spec_from_file_location("canvas_workspace_import", SCRIPT)
assert spec and spec.loader
importer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(importer)


def test_import_reads_documents_and_prompt_sources_and_registers_embedded_media_once(tmp_path):
    (tmp_path / "story.md").write_text("# 故事板\n回身取信", encoding="utf-8")
    (tmp_path / "prompt.txt").write_text("雨夜里的人物回头", encoding="utf-8")
    (tmp_path / "character.png").write_bytes(b"selected image")
    (tmp_path / "frame.png").write_bytes(b"derived frame")
    manifest = {
        "name": "一段故事",
        "graph": {
            "workspace": {"story": "故事", "chapter": "第六章"},
            "nodes": [
                {
                    "id": "story",
                    "type": "document",
                    "position": {"x": 0, "y": 0},
                    "data": {"source_path": "story.md"},
                },
                {
                    "id": "image",
                    "type": "image",
                    "position": {"x": 100, "y": 0},
                    "data": {
                        "prompt_source_path": "prompt.txt",
                        "mode": "create",
                        "history": [
                            {
                                "id": "v1",
                                "label": "第一版",
                                "asset": {"path": "character.png"},
                                "generation_snapshot": {"prompt": "旧版"},
                            }
                        ],
                        "derived_outputs": [
                            {
                                "id": "frame",
                                "label": "固定首帧",
                                "asset": {"path": "frame.png"},
                                "source_version": "v1",
                            }
                        ],
                    },
                },
            ],
            "edges": [],
        },
    }
    prepared = importer.prepare_workspace(manifest, tmp_path)
    assert prepared["graph"]["nodes"][0]["data"]["content"] == "# 故事板\n回身取信"
    image_data = prepared["graph"]["nodes"][1]["data"]
    assert image_data["prompt"] == "雨夜里的人物回头"
    assert image_data["history"][0]["asset"]["kind"] == "image"
    assert image_data["derived_outputs"][0]["asset"]["kind"] == "image"
    assert "content" not in manifest["graph"]["nodes"][0]["data"]

    calls = []

    class Client:
        def request(self, method, path, body):
            calls.append((method, path, body))
            if path == "/api/assets/import":
                source = Path(body["path"])
                return {"path": f"/media/{source.name}", "kind": "image", "name": source.name}
            assert path == "/api/canvases"
            return {"id": "new-story", **body}

    result = importer.import_workspace(Client(), prepared)
    assert [path for _, path, _ in calls] == [
        "/api/assets/import",
        "/api/assets/import",
        "/api/canvases",
    ]
    assert result["graph"]["workspace"]["chapter"] == "第六章"
    result_data = result["graph"]["nodes"][1]["data"]
    assert result_data["history"][0]["asset"]["path"] == "/media/character.png"
    assert result_data["derived_outputs"][0]["asset"]["path"] == "/media/frame.png"
    # The prepared graph is detached from the API payload mutation.
    assert prepared["graph"]["nodes"][1]["data"]["history"][0]["asset"]["path"] != "/media/character.png"


def test_missing_media_fails_before_import_and_prompt_source_is_text_only(tmp_path):
    (tmp_path / "prompt.txt").write_text("已审定片段", encoding="utf-8")
    manifest = {
        "name": "故事",
        "graph": {
            "nodes": [
                {
                    "id": "image",
                    "type": "image",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "prompt_source_path": "prompt.txt",
                        "mode": "create",
                    },
                },
                {
                    "id": "missing",
                    "type": "asset",
                    "position": {"x": 0, "y": 0},
                    "data": {"asset": {"path": "missing.png"}},
                },
            ],
            "edges": [],
        },
    }
    with pytest.raises(ValueError, match="所选文件不存在"):
        importer.prepare_workspace(manifest, tmp_path)

    manifest["graph"]["nodes"].pop()
    prepared = importer.prepare_workspace(manifest, tmp_path)
    assert prepared["graph"]["nodes"][0]["data"]["prompt"] == "已审定片段"


def test_image_source_path_is_not_read_as_prompt(tmp_path):
    (tmp_path / "binary.png").write_bytes(b"not utf8 prompt bytes \xff\xfe")
    manifest = {
        "name": "素材",
        "graph": {
            "nodes": [
                {
                    "id": "image",
                    "type": "image",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "source_path": "binary.png",
                        "prompt": "保留的提示词",
                        "mode": "create",
                    },
                }
            ],
            "edges": [],
        },
    }
    prepared = importer.prepare_workspace(manifest, tmp_path)
    data = prepared["graph"]["nodes"][0]["data"]
    assert data["prompt"] == "保留的提示词"
    assert "content" not in data
