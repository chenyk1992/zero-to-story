"""Read-only adapter to the official local xiaohongshu-mcp service; no paid APIs."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

import radar

MAX_RESPONSE = 16 * 1024 * 1024
NOTE_ID = re.compile(r"[a-f0-9]{24}")
READ_OPERATIONS = {
    "status": ("GET", "/api/v1/login/status"),
    "login": ("GET", "/api/v1/login/qrcode"),
    "search": ("POST", "/api/v1/feeds/search"),
    "detail": ("POST", "/api/v1/feeds/detail"),
}


class CollectionError(Exception):
    """Safe diagnostic code; provider bodies and access tokens are not printed."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


class Client:
    def __init__(self, runtime: Path):
        self.root = runtime.resolve(strict=True)
        config = radar.parse_json((self.root / "runtime.json").read_bytes())
        parsed = urlsplit(config["base_url"])
        if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or not parsed.port
                or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment):
            raise ValueError("runtime must use a loopback-only local HTTP service")
        self.base_url = config["base_url"]
        self.version = config["version"]
        token_path = (self.root / config["token_file"]).resolve(strict=True)
        if not token_path.is_relative_to(self.root / "state"):
            raise ValueError("service token must remain in this installation's state directory")
        self.token = token_path.read_text(encoding="utf-8").strip()
        if not self.token:
            raise ValueError("local service authentication is missing")
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def call(self, operation: str, body: dict | None = None) -> dict:
        if operation not in READ_OPERATIONS:
            raise ValueError("only login, status, search and detail reads are exposed")
        method, path = READ_OPERATIONS[operation]
        request = Request(self.base_url + path, method=method,
                          data=json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None,
                          headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/json"})
        try:
            with self.opener.open(request, timeout=120) as response:
                raw = response.read(MAX_RESPONSE + 1)
        except HTTPError as error:
            raise CollectionError(f"LOCAL_HTTP_{error.code}; stopped, no retry") from None
        except (URLError, TimeoutError, OSError):
            raise CollectionError("LOCAL_CONNECTION_FAILED; stopped, no retry") from None
        if len(raw) > MAX_RESPONSE:
            raise CollectionError("RESPONSE_TOO_LARGE")
        try:
            result = radar.parse_json(raw)
        except (ValueError, UnicodeError):
            raise CollectionError("INVALID_SERVICE_JSON") from None
        if not isinstance(result, dict) or result.get("success") is not True or not isinstance(result.get("data"), dict):
            raise CollectionError("SERVICE_DID_NOT_RETURN_SUCCESS")
        return result["data"]

    def require_login(self) -> None:
        if self.call("status").get("is_logged_in") is not True:
            raise CollectionError("LOGIN_REQUIRED; scan and confirm before collection")


def exact_count(value) -> int | None:
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str) and re.fullmatch(r"(?:\d+|\d{1,3}(?:,\d{3})+)", value.strip()):
        return int(value.replace(",", ""))
    return None


def metrics(info: dict) -> dict:
    return {"likes": exact_count(info.get("likedCount")), "saves": exact_count(info.get("collectedCount")),
            "comments": exact_count(info.get("commentCount")), "shares": exact_count(info.get("sharedCount")), "views": None}


def write_new(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")


def search_projection(data: dict, *, limit: int) -> tuple[list[dict], dict]:
    if not isinstance(data.get("feeds"), list):
        raise CollectionError("SEARCH_SCHEMA_CHANGED")
    items, access = [], {}
    for feed in data["feeds"]:
        if feed.get("modelType") != "note":
            continue
        note_id = feed.get("id", "")
        if not NOTE_ID.fullmatch(note_id) or note_id in {item["id"] for item in items}:
            continue
        card = feed.get("noteCard") or {}
        user = card.get("user") or {}
        items.append({"id": note_id, "kind": "note", "title": card.get("displayTitle") or "[标题未返回]",
                      "url": "https://www.xiaohongshu.com/explore/" + note_id,
                      "author": user.get("nickname") or user.get("nickName"), "published_at": None,
                      "rank": None, "metrics": metrics(card.get("interactInfo") or {})})
        if isinstance(feed.get("xsecToken"), str) and feed["xsecToken"]:
            access[note_id] = feed["xsecToken"]
        if len(items) >= limit:
            break
    return items, access


def anonymous_text(value: str) -> str:
    value = re.sub(r"https?://\S+", "[链接已隐藏]", value)
    return re.sub(r"@[^\s：:，。！？,!?]{1,40}", "@用户", value)


def detail_projection(data: dict, note_id: str, *, max_comments: int) -> dict:
    detail = data.get("data")
    if not isinstance(detail, dict) or not isinstance(detail.get("note"), dict):
        raise CollectionError("DETAIL_SCHEMA_CHANGED")
    note = detail["note"]
    if note.get("noteId") != note_id:
        raise CollectionError("DETAIL_ID_MISMATCH")
    comment_data = detail.get("comments")
    comments_available = isinstance(comment_data, dict) and isinstance(comment_data.get("list"), list)
    comment_data = comment_data if comments_available else {}
    comments = []
    for comment in comment_data.get("list", []):
        if not isinstance(comment, dict) or not isinstance(comment.get("content"), str):
            continue
        comments.append({"anonymous_id": hashlib.sha256(str(comment.get("id", "")).encode()).hexdigest()[:16],
                         "text": anonymous_text(comment["content"]), "likes": exact_count(comment.get("likeCount")),
                         "platform_time_ms": comment.get("createTime"),
                         "reply_count_display": comment.get("subCommentCount")})
        if len(comments) >= max_comments:
            break
    info = note.get("interactInfo") or {}
    return {"schema_version": 1, "operation": "detail", "platform": "xiaohongshu", "id": note_id,
            "url": "https://www.xiaohongshu.com/explore/" + note_id, "observed_at": radar.iso(radar.utc_now()),
            "note": {"title": note.get("title"), "description": note.get("desc"), "type": note.get("type"),
                     "platform_time_ms": note.get("time"), "published_at": None,
                     "metrics": metrics(info), "metrics_display": {key: info.get(key) for key in
                         ("likedCount", "collectedCount", "commentCount", "sharedCount")}},
            "comments_status": "ok" if comments_available else "unavailable",
            "comments": comments, "platform_has_more": comment_data.get("hasMore"),
            "returned_parent_comments": len(comment_data.get("list", [])),
            "saved_comments": len(comments), "saved_limit": max_comments,
            "limitations": ["Only initially loaded parent comments; no scrolling or reply expansion requested",
                             "Comment user identities, locations and access tokens removed; mentions/links redacted",
                             "Counts may be rounded; no competitor view count inferred",
                             "Platform time field retained; first publication vs editing not independently verified"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True, help="installed version directory containing runtime.json")
    sub = parser.add_subparsers(dest="operation", required=True)
    sub.add_parser("status")
    sub.add_parser("login", help="create one QR image in private state; no credentials printed")
    search = sub.add_parser("search")
    search.add_argument("--keyword", required=True)
    search.add_argument("--sort", choices=["综合", "最新", "最多点赞", "最多评论", "最多收藏"], default="综合")
    search.add_argument("--period", choices=["不限", "一天内", "一周内", "半年内"], default="不限")
    search.add_argument("--note-type", choices=["不限", "视频", "图文"], default="不限")
    search.add_argument("--limit", type=int, choices=range(1, 41), default=10)
    search.add_argument("--store", type=Path, required=True)
    detail = sub.add_parser("detail")
    detail.add_argument("--search-id", required=True, help="search receipt returned by this adapter")
    detail.add_argument("--note-id", required=True)
    detail.add_argument("--max-comments", type=int, choices=range(1, 41), default=20)
    detail.add_argument("--store", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        client = Client(args.runtime)
        if args.operation == "status":
            data = client.call("status")
            print(json.dumps({"is_logged_in": data.get("is_logged_in"), "username": data.get("username")}, ensure_ascii=False))
            return 0 if data.get("is_logged_in") is True else 2
        if args.operation == "login":
            data = client.call("login")
            result = {"is_logged_in": data.get("is_logged_in"), "timeout": data.get("timeout")}
            if data.get("img"):
                target = client.root / "state" / ("login-qr-" + uuid.uuid4().hex[:12] + ".png")
                with target.open("xb") as handle:
                    handle.write(base64.b64decode(data["img"].split(",")[-1], validate=True))
                result["qr_path"] = str(target)
            print(json.dumps(result, ensure_ascii=False))
            return 0
        if args.operation == "detail" and (not re.fullmatch(r"[a-f0-9]{32}", args.search_id) or not NOTE_ID.fullmatch(args.note_id)):
            raise ValueError("invalid search receipt or note ID")
        client.require_login()
        if args.operation == "search":
            filters = {"sort_by": args.sort, "publish_time": args.period, "note_type": args.note_type}
            data = client.call("search", {"keyword": args.keyword, "filters": filters})
            items, access = search_projection(data, limit=args.limit)
            search_id = uuid.uuid4().hex
            # Access materials remain exclusively in the ignored service state, never research output.
            write_new(client.root / "state" / "search-access" / (search_id + ".json"),
                      {"access": access, "created_at": radar.iso(radar.utc_now()), "keyword": args.keyword})
            scope_key = json.dumps([args.keyword, filters, args.limit], ensure_ascii=False, sort_keys=True)
            snapshot = {"schema_version": 1, "source_id": "xhs-mcp-" + hashlib.sha256(scope_key.encode()).hexdigest()[:16],
                        "platform": "xiaohongshu", "method": "browser", "observed_at": radar.iso(radar.utc_now()),
                        "source_updated_at": None, "source_url": "https://www.xiaohongshu.com/search_result?keyword=" + quote(args.keyword),
                        "query": args.keyword, "sort": args.sort,
                        "sample_scope": f"xiaohongshu-mcp {client.version}; requested filters={filters}; first returned page, at most {args.limit}; UI not independently rechecked",
                        "status": "ok" if items else "empty", "items": items}
            if not items:
                snapshot["diagnostic"] = "No note cards returned; login/loading/layout or a truly empty result unresolved"
            projection = {"collector": "xiaohongshu-mcp", "version": client.version, "operation": "search",
                          "observed_at": snapshot["observed_at"], "query": args.keyword, "filters_requested": filters,
                          "upstream_returned_count": data.get("count"), "items": items,
                          "redactions": "Projection only: access tokens, user IDs, signed media URLs and login state omitted"}
            selected_ids = {item["id"] for item in items}
            projection["display_fields"] = {feed["id"]: {
                "note_type": (feed.get("noteCard") or {}).get("type"),
                "metrics_display": {key: ((feed.get("noteCard") or {}).get("interactInfo") or {}).get(key)
                                    for key in ("likedCount", "collectedCount", "commentCount", "sharedCount")}}
                for feed in data["feeds"] if feed.get("id") in selected_ids}
            path = radar.save_snapshot(args.store, snapshot, json.dumps(projection, ensure_ascii=False).encode())
            print(json.dumps({"search_id": search_id, "status": snapshot["status"], "count": len(items),
                              "detail_ready_count": len(access), "snapshot": str(path.resolve()),
                              "items": [{"id": item["id"], "title": item["title"], "metrics": item["metrics"]} for item in items]}, ensure_ascii=False, indent=2))
            return 0 if items else 2
        index = radar.parse_json((client.root / "state" / "search-access" / (args.search_id + ".json")).read_bytes())
        token = index["access"].get(args.note_id)
        if not token:
            raise CollectionError("NOTE_NOT_IN_SEARCH_RECEIPT; search again only with user authorization")
        data = client.call("detail", {"feed_id": args.note_id, "xsec_token": token, "load_all_comments": False,
                                     "comment_config": {"click_more_replies": False, "max_comment_items": args.max_comments}})
        projection = detail_projection(data, args.note_id, max_comments=args.max_comments)
        projection["collector"] = {"name": "xiaohongshu-mcp", "version": client.version}
        target = args.store / "details" / (args.note_id + "-" + uuid.uuid4().hex[:12] + ".json")
        write_new(target, projection)
        print(json.dumps({"status": "ok", "title": projection["note"]["title"], "comments_status": projection["comments_status"],
                          "saved_comments": projection["saved_comments"], "platform_has_more": projection["platform_has_more"],
                          "detail": str(target.resolve())}, ensure_ascii=False))
        return 0 if projection["comments_status"] == "ok" else 2
    except (CollectionError, ValueError, KeyError, TypeError, OSError) as error:
        # Do not print arbitrary provider text, file contents, request bodies or access tokens.
        safe = str(error) if isinstance(error, CollectionError) else type(error).__name__
        if getattr(args, "store", None):
            receipt = {"operation": args.operation, "status": "stopped", "observed_at": radar.iso(radar.utc_now()),
                       "diagnostic": safe, "retry_performed": False}
            try:
                write_new(args.store / "diagnostics" / (uuid.uuid4().hex + ".json"), receipt)
            except OSError:
                pass
        print(json.dumps({"status": "stopped", "diagnostic": safe}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
