"""Read a current Canvas draft and run the H3 prompt linter without mutation."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

from h3_prompt_lint import lint_snapshot

from lfo.canvas.client import CanvasClient
from lfo.canvas.graph import resolve_snapshot
from lfo.canvas.settings import CanvasSettings

_SCHEMA = "h3-prompt-lint.v1"
_BLUEPRINT_SCHEMA = "zero-to-story.creative-blueprint.v2"


def inspect_canvas(
    client: CanvasClient,
    canvas_id: str,
    node_id: str,
    expected_version: int,
    *,
    blueprint: Mapping[str, Any] | None = None,
    panel_id: str | None = None,
) -> dict[str, Any]:
    """Inspect one stable Canvas snapshot with GET requests only."""

    try:
        canvas_path = f"/api/canvases/{quote(canvas_id, safe='')}"
        runs_path = f"{canvas_path}/runs"
        first_canvas = _mapping_response(client.request("GET", canvas_path), "canvas")
        first_version = _version(first_canvas)
        if first_version != expected_version:
            return _unavailable(canvas_id, node_id, first_version, "画布版本已变化, 请重新读取后检查。")
        first_runs = _runs_response(client.request("GET", runs_path))
        readiness_path = "/api/readiness?" + urlencode({"canvas_id": canvas_id, "node_id": node_id})
        readiness = _mapping_response(client.request("GET", readiness_path), "readiness")
        if readiness.get("ready") is not True:
            reason = readiness.get("reason")
            return _unavailable(
                canvas_id,
                node_id,
                first_version,
                f"Canvas readiness 未通过: {reason}" if isinstance(reason, str) else "Canvas readiness 未通过。",
            )
        if readiness.get("version") not in {None, first_version}:
            return _unavailable(canvas_id, node_id, first_version, "readiness 对应的画布版本已变化。")
        first_snapshot = resolve_snapshot(first_canvas, node_id, first_runs)
        first_digest = _digest_json(first_snapshot)
        lint = lint_snapshot(first_snapshot, blueprint=blueprint, panel_id=panel_id)

        second_canvas = _mapping_response(client.request("GET", canvas_path), "canvas")
        second_version = _version(second_canvas)
        if second_version != first_version:
            return _unavailable(canvas_id, node_id, second_version, "检查期间画布版本发生变化。")
        second_runs = _runs_response(client.request("GET", runs_path))
        second_snapshot = resolve_snapshot(second_canvas, node_id, second_runs)
        if _digest_json(second_snapshot) != first_digest:
            return _unavailable(canvas_id, node_id, second_version, "检查期间有效输入发生变化。")
    except (KeyError, TypeError, ValueError) as exc:
        return _unavailable(canvas_id, node_id, None, f"无法读取当前 Canvas 输入: {exc}")

    findings = [asdict(finding) for finding in lint.findings]
    if any(finding["severity"] == "error" for finding in findings):
        status = "failed"
    elif findings or lint.unverified:
        status = "needs_review"
    else:
        status = "passed"
    return {
        "schema": _SCHEMA,
        "canvas_id": canvas_id,
        "node_id": node_id,
        "canvas_version": first_version,
        "input_digest": first_digest,
        "blueprint_digest": None,
        "status": status,
        "findings": findings,
        "checked": list(lint.checked),
        "unverified": list(lint.unverified),
    }


def main(argv: list[str] | None = None) -> int:
    """Run the read-only adapter and return an automation-safe exit status."""

    parser = _parser()
    args = parser.parse_args(argv)
    try:
        _validate_id(args.canvas_id, "canvas-id")
        _validate_id(args.node_id, "node-id")
        if args.expected_version < 0:
            raise ValueError("expected-version 必须是非负整数。")
        if bool(args.blueprint) != bool(args.panel_id):
            raise ValueError("--blueprint 与 --panel-id 必须同时提供。")
        project_root = args.project.resolve()
        blueprint, blueprint_digest = _read_blueprint(args.blueprint) if args.blueprint else (None, None)
        settings = CanvasSettings.resolve(project_root=project_root)
        client = CanvasClient(settings, url=args.url)
        health = _mapping_response(client.request("GET", "/api/health"), "health")
        if health.get("project_root") != str(project_root):
            raise ValueError("Canvas 服务所属项目与 --project 不一致。")
        result = inspect_canvas(
            client,
            args.canvas_id,
            args.node_id,
            args.expected_version,
            blueprint=blueprint,
            panel_id=args.panel_id,
        )
        result["blueprint_digest"] = blueprint_digest
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result = _unavailable(args.canvas_id, args.node_id, None, str(exc))

    _print_result(result, as_json=args.json)
    if result["status"] in {"passed", "needs_review"}:
        return 0
    if result["status"] == "failed":
        return 1
    return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="只读检查当前 Canvas 的 H3 提示词草稿。")
    parser.add_argument("--canvas-id", required=True)
    parser.add_argument("--node-id", required=True)
    parser.add_argument("--expected-version", required=True, type=int)
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--url")
    parser.add_argument("--blueprint", type=Path)
    parser.add_argument("--panel-id")
    parser.add_argument("--json", action="store_true")
    return parser


def _validate_id(value: str, name: str) -> None:
    if not value or value in {".", ".."} or ".." in value or "/" in value or "\\" in value:
        raise ValueError(f"{name} 不能为空且不得包含路径分隔符或路径穿越。")


def _read_blueprint(path: Path) -> tuple[Mapping[str, Any], str]:
    raw = path.read_bytes()
    parsed = json.loads(raw.decode("utf-8"), parse_constant=_reject_non_finite)
    if not isinstance(parsed, Mapping):
        raise ValueError("blueprint 必须是 JSON 对象。")
    if parsed.get("schema") != _BLUEPRINT_SCHEMA:
        raise ValueError(f"blueprint schema 必须是 {_BLUEPRINT_SCHEMA}。")
    return parsed, sha256(raw).hexdigest()


def _reject_non_finite(value: str) -> None:
    raise ValueError(f"JSON 不允许 {value}。")


def _mapping_response(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} 响应不是对象。")
    return value


def _runs_response(value: Any) -> list[Mapping[str, Any]]:
    response = _mapping_response(value, "runs")
    runs = response.get("runs")
    if not isinstance(runs, Sequence) or isinstance(runs, (str, bytes, bytearray)):
        raise ValueError("runs 响应缺少数组。")
    if not all(isinstance(run, Mapping) for run in runs):
        raise ValueError("runs 响应包含无效条目。")
    return list(runs)


def _version(canvas: Mapping[str, Any]) -> int:
    value = canvas.get("version")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("canvas 响应缺少有效版本号。")
    return value


def _digest_json(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _unavailable(
    canvas_id: str,
    node_id: str,
    version: int | None,
    reason: str,
) -> dict[str, Any]:
    return {
        "schema": _SCHEMA,
        "canvas_id": canvas_id,
        "node_id": node_id,
        "canvas_version": version,
        "input_digest": None,
        "blueprint_digest": None,
        "status": "unavailable",
        "findings": [],
        "checked": [],
        "unverified": [reason],
    }


def _print_result(result: Mapping[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return
    print(f"H3 prompt lint: {result['status']}")
    for finding in result["findings"]:
        line = f" line {finding['line']}" if finding.get("line") is not None else ""
        print(f"{finding['severity']} {finding['code']}{line}: {finding['message']}")
    for item in result["unverified"]:
        print(f"unverified: {item}")


if __name__ == "__main__":
    raise SystemExit(main())
