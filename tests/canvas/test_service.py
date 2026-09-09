from __future__ import annotations

import copy
import json
import threading
from pathlib import Path

import pytest

from lfo.canvas.client import CanvasClient
from lfo.canvas.graph import CanvasError
from lfo.canvas.server import CanvasHTTPServer
from lfo.canvas.service import CanvasService
from lfo.canvas.settings import CanvasSettings

PROJECT = Path(__file__).resolve().parents[2]


@pytest.fixture
def service(tmp_path):
    settings = CanvasSettings(PROJECT, tmp_path / "state", tmp_path / "media", 0)
    instance = CanvasService(settings, start_worker=False)
    yield instance
    instance.close()


def image_graph(prompt="雨后的小巷"):
    return {
        "nodes": [
            {
                "id": "image-one",
                "type": "image",
                "position": {"x": 0, "y": 0},
                "data": {
                    "prompt": prompt,
                    "provider": "codex-imagegen",
                    "model": "image_gen",
                    "mode": "create",
                },
            }
        ],
        "edges": [],
        "viewport": {"x": 0, "y": 0, "zoom": 1},
        "selection": ["image-one"],
    }


def test_reusing_workspace_media_does_not_copy_or_delete_source(service):
    media = service.settings.media_root / "projects" / "story" / "clip.mp4"
    media.parent.mkdir(parents=True)
    media.write_bytes(b"existing story video")
    imported = service.media.import_file(str(media))
    assert imported["path"] == str(media.resolve())
    assert imported["kind"] == "video"
    assert not (service.settings.media_root / "assets" / "uploads").exists()
    graph = image_graph()
    graph["nodes"].append(
        {
            "id": "source-video",
            "type": "asset",
            "position": {"x": 300, "y": 0},
            "data": {"asset": imported},
        }
    )
    canvas = service.store.create_canvas("故事素材", graph)
    graph["nodes"].pop()
    service.store.save_canvas(canvas["id"], canvas["version"], graph)
    assert media.read_bytes() == b"existing story video"


def test_confirm_uses_saved_version_and_is_idempotent(service):
    canvas = service.store.create_canvas("测试", image_graph())
    first = service.confirm(canvas["id"], "image-one", canvas["version"], "request-a")
    assert first["status"] == "pending_agent"
    changed = copy.deepcopy(canvas["graph"])
    changed["nodes"][0]["data"]["prompt"] = "清晨的山谷"
    saved = service.store.save_canvas(canvas["id"], canvas["version"], changed)
    retried = service.confirm(canvas["id"], "image-one", canvas["version"], "request-a")
    assert retried["id"] == first["id"]
    assert retried["snapshot"]["prompt"] == "雨后的小巷"
    assert service.runs(canvas["id"])[0]["matches_current"] is False
    with pytest.raises(CanvasError, match="新修改"):
        service.confirm(canvas["id"], "image-one", canvas["version"], "request-b")
    assert saved["version"] > canvas["version"]


def test_claim_uses_fixed_media_and_cannot_be_claimed_twice(service):
    media = service.settings.media_root / "frame.png"
    media.parent.mkdir(parents=True)
    media.write_bytes(b"original-media")
    graph = image_graph()
    graph["nodes"].append(
        {
            "id": "reference",
            "type": "asset",
            "position": {"x": 10, "y": 10},
            "data": {"asset": {"path": str(media), "kind": "image"}},
        }
    )
    graph["edges"].append(
        {
            "id": "ref-edge",
            "source": "reference",
            "target": "image-one",
            "sourceHandle": "output",
            "targetHandle": "reference_image",
        }
    )
    canvas = service.store.create_canvas("参考", graph)
    run = service.confirm(canvas["id"], "image-one", canvas["version"], "fixed-media")
    media.write_bytes(b"changed-source")
    assert service.runs(canvas["id"])[0]["matches_current"] is False
    claimed = service.claim_agent(run["id"], ["image_gen"])
    actual = claimed["execution_snapshot"]["inputs"]["reference_images"][0]["path"]
    assert Path(actual).read_bytes() == b"original-media"
    with pytest.raises(CanvasError):
        service.claim_agent(run["id"], ["image_gen"])
    assert "owner_token" not in service.runs()[0]


def test_agent_result_is_copied_and_old_result_survives_edit(service, tmp_path):
    canvas = service.store.create_canvas("成品", image_graph())
    run = service.confirm(canvas["id"], "image-one", canvas["version"], "result-a")
    claim = service.claim_agent(run["id"], ["image_gen"])
    result = tmp_path / "host-image.png"
    result.write_bytes(b"returned-image")
    with pytest.raises(CanvasError):
        service.complete_agent(run["id"], "wrong", outputs=[{"path": str(result), "kind": "image"}])
    completed = service.complete_agent(
        run["id"], claim["owner_token"], outputs=[{"path": str(result), "kind": "image"}]
    )
    target = Path(completed["outputs"][0]["path"])
    assert target.is_relative_to(service.settings.media_root)
    assert target.read_bytes() == b"returned-image"
    moved = copy.deepcopy(canvas["graph"])
    moved["nodes"][0]["position"]["x"] = 240
    saved = service.store.save_canvas(canvas["id"], canvas["version"], moved)
    assert service.runs(canvas["id"])[0]["matches_current"] is True
    moved["nodes"][0]["data"]["prompt"] = "下一版"
    service.store.save_canvas(canvas["id"], saved["version"], moved)
    assert service.runs(canvas["id"])[0]["matches_current"] is False
    assert target.exists()


def test_missing_skill_does_not_break_saved_canvas(service):
    graph = image_graph()
    graph["nodes"][0]["data"]["provider"] = "removed-provider"
    canvas = service.store.create_canvas("可移除", graph)
    assert service.store.get_canvas(canvas["id"])["graph"] == graph
    with pytest.raises(ValueError, match="移除"):
        service.confirm(canvas["id"], "image-one", canvas["version"], "missing-provider")
    assert service.store.list_runs() == []


def test_unsupported_pixel_budget_is_not_silently_discarded(service):
    graph = image_graph()
    graph["nodes"][0]["data"]["megapixels"] = 0.4
    canvas = service.store.create_canvas("参数", graph)
    with pytest.raises(ValueError, match="不支持参数 megapixels"):
        service.confirm(canvas["id"], "image-one", canvas["version"], "invalid-param")


def test_embedded_image_asset_is_used_without_a_fake_run(service):
    media = service.settings.media_root / "anchor.png"
    media.parent.mkdir(parents=True)
    media.write_bytes(b"embedded-anchor")
    graph = image_graph()
    graph["nodes"].append(
        {
            "id": "upstream",
            "type": "image",
            "position": {"x": 0, "y": 0},
            "data": {
                "prompt": "已经导入的锚点",
                "mode": "create",
                "asset": {"path": str(media), "kind": "image", "name": "anchor.png"},
            },
        }
    )
    graph["edges"].append(
        {
            "id": "asset-edge",
            "source": "upstream",
            "target": "image-one",
            "sourceHandle": "output",
            "targetHandle": "reference_image",
        }
    )
    canvas = service.store.create_canvas("嵌入成品", graph)
    run = service.confirm(canvas["id"], "image-one", canvas["version"], "embedded-asset")
    assert run["snapshot"]["inputs"]["reference_images"][0]["path"] == str(media.resolve())
    claimed = service.claim_agent(run["id"], ["image_gen"])
    frozen = claimed["execution_snapshot"]["inputs"]["reference_images"][0]
    assert Path(frozen["path"]).read_bytes() == b"embedded-anchor"
    assert service.store.list_runs(canvas["id"])[0]["node_id"] == "image-one"


def test_provider_options_cannot_hide_common_parameters(service):
    graph = image_graph()
    graph["nodes"][0]["data"]["options"] = {"codex-imagegen": {"aspect_ratio": "1:1"}}
    canvas = service.store.create_canvas("参数来源", graph)
    with pytest.raises(CanvasError, match="专属参数不能覆盖"):
        service.confirm(canvas["id"], "image-one", canvas["version"], "hidden-param")


@pytest.fixture
def http_service(service):
    server = CanvasHTTPServer(("127.0.0.1", 0), service)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = CanvasClient(service.settings, f"http://127.0.0.1:{server.server_address[1]}")
    yield client
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def test_dialogue_edit_and_browser_read_share_configuration(http_service):
    canvas = http_service.request(
        "POST", "/api/canvases", {"name": "对话建图", "graph": image_graph()}
    )
    edited = http_service.edit(
        canvas["id"],
        canvas["version"],
        [
            {
                "op": "update_node",
                "node_id": "image-one",
                "data": {"prompt": "用户刚修改的中文提示词"},
            }
        ],
    )
    read = http_service.request("GET", f"/api/canvases/{canvas['id']}")
    assert read == edited
    run = http_service.request(
        "POST",
        f"/api/canvases/{canvas['id']}/runs",
        {"node_id": "image-one", "version": edited["version"], "request_id": "dialogue"},
    )
    assert run["snapshot"]["prompt"] == "用户刚修改的中文提示词"
    assert run["status"] == "pending_agent"


def test_media_range_and_foreign_origin(http_service, service):
    from urllib.error import HTTPError
    from urllib.parse import quote
    from urllib.request import Request, urlopen

    media = service.settings.media_root / "preview.mp4"
    media.parent.mkdir(parents=True)
    media.write_bytes(b"0123456789")
    url = http_service.url + "/api/media?path=" + quote(str(media))
    with urlopen(Request(url, headers={"Range": "bytes=3-6"})) as response:
        assert response.status == 206
        assert response.headers["Content-Range"] == "bytes 3-6/10"
        assert response.read() == b"3456"
    with pytest.raises(HTTPError) as denied:
        urlopen(
            Request(
                http_service.url + "/api/canvases",
                data=b"{}",
                headers={"Origin": "https://foreign.example", "Content-Type": "application/json"},
            )
        )
    assert denied.value.code == 403
    assert service.store.list_canvases() == []


def test_script_execution_translates_only_after_confirm(tmp_path):
    root = tmp_path / "project"
    skill = root / ".agents" / "skills" / "test-executor"
    skill.mkdir(parents=True)
    (skill / "capability.json").write_text(
        json.dumps(
            {
                "id": "test",
                "execution": "script",
                "node_types": ["image"],
                "entrypoint": "execute.py",
                "models": [],
                "modes": [],
                "fields": [],
            }
        ),
        encoding="utf-8",
    )
    (skill / "execute.py").write_text(
        "import argparse,json,pathlib\np=argparse.ArgumentParser();p.add_argument('--input');p.add_argument('--output-dir');a=p.parse_args()\n"
        "s=json.loads(pathlib.Path(a.input).read_text(encoding='utf-8'));o=pathlib.Path(a.output_dir)/'result.png';o.write_bytes(s['prompt'].encode())\n"
        "print(json.dumps({'provider_task_id':'one-submit'}),flush=True)\n"
        "print(json.dumps({'outputs':[{'path':str(o),'kind':'image'}],'provider_task_id':'one-submit'}))\n",
        encoding="utf-8",
    )
    service = CanvasService(
        CanvasSettings(root, tmp_path / "state", tmp_path / "media"), start_worker=False
    )
    try:
        graph = image_graph("固定输入")
        graph["nodes"][0]["data"]["provider"] = "test"
        canvas = service.store.create_canvas("执行", graph)
        assert not service.settings.media_root.exists()
        run = service.confirm(canvas["id"], "image-one", canvas["version"], "one")
        assert run["status"] == "queued"
        service._execute(service.store.claim_run(run["id"]))
        result = service.store.get_run(run["id"])
        assert result["status"] == "succeeded"
        assert result["provider_task_id"] == "one-submit"
        assert Path(result["outputs"][0]["path"]).read_text(encoding="utf-8") == "固定输入"
        assert not list((service.settings.data_dir / "temporary").glob("*/input.json"))
    finally:
        service.close()
