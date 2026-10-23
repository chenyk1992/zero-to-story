from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from urllib.error import HTTPError

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / ".agents/skills/ai-creator-radar/scripts"
spec = importlib.util.spec_from_file_location("creator_xhs", SCRIPTS / "xhs.py")
assert spec and spec.loader
xhs = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(SCRIPTS))
try:
    spec.loader.exec_module(xhs)
finally:
    sys.path.pop(0)

NOTE = "6ad76021000000002701e41c"


def runtime(tmp_path: Path, base_url: str = "http://127.0.0.1:18060") -> Path:
    (tmp_path / "state").mkdir()
    (tmp_path / "state/token.txt").write_text("LOCAL-SECRET", encoding="utf-8")
    (tmp_path / "runtime.json").write_text(json.dumps({"base_url": base_url, "version": "v2.5.5",
                                                     "token_file": "state/token.txt"}), encoding="utf-8")
    return tmp_path


def test_transport_limits_host_and_operations(tmp_path: Path) -> None:
    folder = runtime(tmp_path)
    client = xhs.Client(folder)
    with pytest.raises(ValueError, match="only login"):
        client.call("publish", {"title": "not-authorized"})
    config = json.loads((folder / "runtime.json").read_text())
    config["base_url"] = "https://example.com"
    (folder / "runtime.json").write_text(json.dumps(config))
    with pytest.raises(ValueError, match="loopback"):
        xhs.Client(folder)


def test_http_failure_is_not_retried_or_printed_with_credentials(tmp_path: Path) -> None:
    client = xhs.Client(runtime(tmp_path))
    requests = []

    class FailingOpener:
        def open(self, request, timeout):
            requests.append(request)
            raise HTTPError(request.full_url, 500, "upstream ACCESS-SECRET", {}, None)

    client.opener = FailingOpener()
    with pytest.raises(xhs.CollectionError) as raised:
        client.call("search", {"keyword": "AI"})
    assert len(requests) == 1
    assert "SECRET" not in str(raised.value)
    assert "500" in str(raised.value)
    assert requests[0].get_header("Authorization") == "Bearer LOCAL-SECRET"


def test_search_separates_private_access_and_metrics() -> None:
    feed = {"id": NOTE, "modelType": "note", "xsecToken": "PRIVATE-ACCESS", "noteCard": {
        "displayTitle": "AI test", "type": "video", "user": {"nickname": "Author", "userId": "PRIVATE-USER"},
        "interactInfo": {"likedCount": "1.3万", "collectedCount": "0", "commentCount": "1,234"}}}
    items, access = xhs.search_projection({"feeds": [feed, feed, {"modelType": "hot_query"}]}, limit=10)
    assert len(items) == 1 and access == {NOTE: "PRIVATE-ACCESS"}
    assert items[0]["metrics"] == {"likes": None, "saves": 0, "comments": 1234, "shares": None, "views": None}
    assert items[0]["published_at"] is None and items[0]["rank"] is None
    assert "PRIVATE" not in json.dumps(items)


def test_detail_comments_are_bounded_anonymous_and_not_full_coverage() -> None:
    data = {"data": {"note": {"noteId": NOTE, "title": "test", "desc": "description", "time": 12345,
                              "xsecToken": "PRIVATE-ACCESS", "user": {"userId": "PRIVATE-USER"},
                              "interactInfo": {"commentCount": "100"}},
                     "comments": {"hasMore": True, "list": [
                         {"id": "private-comment-id", "content": "@某用户 请看 https://example.com/?xsec_token=PRIVATE-ACCESS", "likeCount": "0",
                          "userInfo": {"userId": "PRIVATE-USER"}, "ipLocation": "PRIVATE-PLACE"},
                         {"id": "another", "content": "second"}]}}}
    result = xhs.detail_projection(data, NOTE, max_comments=1)
    assert result["saved_comments"] == 1 and result["returned_parent_comments"] == 2
    assert result["platform_has_more"] is True
    assert result["note"]["metrics"]["comments"] == 100
    assert result["note"]["published_at"] is None
    assert "PRIVATE" not in json.dumps(result)
    assert "某用户" not in result["comments"][0]["text"]
    assert result["comments"][0]["likes"] == 0
    with pytest.raises(xhs.CollectionError, match="MISMATCH"):
        xhs.detail_projection(data, "6ad76021000000002701e41d", max_comments=1)


def test_cli_stops_before_search_when_login_missing(tmp_path: Path, monkeypatch, capsys) -> None:
    folder = runtime(tmp_path)
    calls = []

    def call(self, operation, body=None):
        calls.append(operation)
        assert operation == "status"
        return {"is_logged_in": False}

    monkeypatch.setattr(xhs.Client, "call", call)
    store = tmp_path / "research"
    code = xhs.main(["--runtime", str(folder), "search", "--keyword", "AI", "--store", str(store)])
    assert code == 2 and calls == ["status"]
    assert "LOGIN_REQUIRED" in capsys.readouterr().err
    assert len(list((store / "diagnostics").glob("*.json"))) == 1
    assert not (store / "snapshots").exists()
