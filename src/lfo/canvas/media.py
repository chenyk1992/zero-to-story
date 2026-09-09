"""Local media imports, previews and immutable inputs for confirmed runs."""

from __future__ import annotations

import copy
import hashlib
import re
import shutil
import uuid
from pathlib import Path
from typing import Any

from lfo.canvas.settings import CanvasSettings

MEDIA_EXTENSIONS = {
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
    ".gif": "image",
    ".bmp": "image",
    ".mp4": "video",
    ".webm": "video",
    ".mov": "video",
    ".mkv": "video",
    ".wav": "audio",
    ".mp3": "audio",
    ".flac": "audio",
    ".m4a": "audio",
    ".aac": "audio",
    ".ogg": "audio",
}


def media_kind(path: Path) -> str:
    try:
        return MEDIA_EXTENSIONS[path.suffix.lower()]
    except KeyError as exc:
        raise ValueError("请选择图片、视频或音频文件") from exc


class CanvasMedia:
    def __init__(self, settings: CanvasSettings) -> None:
        self.settings = settings
        self._digests: dict[str, tuple[int, int, str]] = {}

    def resolve(self, value: str, *, external: bool = False) -> Path:
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = self.settings.project_root / path
        path = path.resolve()
        media_kind(path)
        if not external and not path.is_relative_to(self.settings.media_root):
            raise ValueError("请先导入工作区外的素材，再连接到画布")
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError("素材不存在或内容为空")
        return path

    def import_file(self, source: str) -> dict[str, str]:
        path = self.resolve(source, external=True)
        target = path
        if not path.is_relative_to(self.settings.media_root):
            target = self.upload_path(path.name)
            shutil.copyfile(path, target)
        asset = self.asset(target, path.name)
        with target.open("rb") as stream:
            asset["sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
        return asset

    def upload_path(self, name: str) -> Path:
        clean = re.sub(r"[^\w.\- ()\u4e00-\u9fff]", "_", Path(name).name)[-120:]
        media_kind(Path(clean))
        parent = self.settings.media_root / "assets" / "uploads"
        parent.mkdir(parents=True, exist_ok=True)
        return parent / f"{uuid.uuid4().hex[:10]}-{clean}"

    @staticmethod
    def asset(path: Path, name: str | None = None) -> dict[str, str]:
        return {"path": str(path.resolve()), "kind": media_kind(path), "name": name or path.name}

    def validate_input(self, value: dict[str, Any]) -> Path:
        """Resolve an input and verify any explicit production acceptance binding."""
        path = self.resolve(value["path"])
        if media_kind(path) != value["kind"]:
            raise ValueError("素材类型与输入端口不匹配")
        accepted_source = value.get("accepted_source")
        checks = [(path, value.get("accepted_sha256"))]
        if accepted_source:
            checks.append(
                (self.resolve(accepted_source["output_path"]), accepted_source["output_sha256"])
            )
        for source, digest in checks:
            if digest:
                with source.open("rb") as stream:
                    if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
                        raise ValueError("已采用素材或其来源发生变化，请重新核实")
        return path

    def freeze(self, snapshot: dict[str, Any], request_id: str) -> dict[str, Any]:
        frozen = copy.deepcopy(snapshot)
        folder = self.settings.data_dir / "inputs" / uuid.uuid5(uuid.NAMESPACE_URL, request_id).hex
        counter = 0

        def visit(value: Any) -> Any:
            nonlocal counter
            if isinstance(value, list):
                return [visit(item) for item in value]
            if isinstance(value, dict):
                if "path" in value and "kind" in value:
                    source = self.validate_input(value)
                    folder.mkdir(parents=True, exist_ok=True)
                    counter += 1
                    target = folder / f"input-{counter}{source.suffix.lower()}"
                    digest = hashlib.sha256()
                    before = source.stat()
                    with source.open("rb") as reader, target.open("wb") as writer:
                        for block in iter(lambda: reader.read(1024 * 1024), b""):
                            digest.update(block)
                            writer.write(block)
                    after = source.stat()
                    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                        raise ValueError("素材在确认期间发生了变化，请重新确认")
                    if (
                        value.get("accepted_sha256")
                        and digest.hexdigest() != value["accepted_sha256"]
                    ):
                        raise ValueError("已采用的上游媒体发生变化，请重新核实")
                    return {
                        **value,
                        "path": str(source),
                        "frozen_path": str(target),
                        "sha256": digest.hexdigest(),
                    }
                return {key: visit(item) for key, item in value.items()}
            return value

        frozen["inputs"] = visit(frozen.get("inputs", {}))
        return frozen

    def execution_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        def visit(value: Any) -> Any:
            if isinstance(value, list):
                return [visit(item) for item in value]
            if isinstance(value, dict):
                if "frozen_path" in value:
                    path = Path(value["frozen_path"]).resolve()
                    if not path.is_relative_to((self.settings.data_dir / "inputs").resolve()):
                        raise ValueError("运行输入路径无效")
                    with path.open("rb") as stream:
                        digest = hashlib.file_digest(stream, "sha256").hexdigest()
                    if digest != value["sha256"]:
                        raise ValueError("确认后的素材已改变，停止本次执行")
                    return {
                        k: v
                        for k, v in {**value, "path": str(path)}.items()
                        if k not in {"frozen_path", "sha256"}
                    }
                return {key: visit(item) for key, item in value.items()}
            return value

        return visit(snapshot)

    def inputs_unchanged(self, snapshot: dict[str, Any]) -> bool:
        """Notice edits to referenced media without rehashing every preview poll."""

        def visit(value: Any) -> bool:
            if isinstance(value, list):
                return all(visit(item) for item in value)
            if isinstance(value, dict):
                if "sha256" in value and "path" in value:
                    try:
                        if value.get("accepted_source"):
                            self.validate_input(value)
                        path = self.resolve(value["path"])
                        stat = path.stat()
                        key = str(path)
                        cached = self._digests.get(key)
                        if cached is None or cached[:2] != (stat.st_size, stat.st_mtime_ns):
                            with path.open("rb") as stream:
                                digest = hashlib.file_digest(stream, "sha256").hexdigest()
                            cached = (stat.st_size, stat.st_mtime_ns, digest)
                            if len(self._digests) >= 256:
                                self._digests.pop(next(iter(self._digests)))
                            self._digests[key] = cached
                        return cached[2] == value["sha256"]
                    except (OSError, ValueError):
                        return False
                return all(visit(item) for item in value.values())
            return True

        return visit(snapshot.get("inputs", {}))

    def collect_outputs(
        self, outputs: list[dict[str, Any]], canvas_id: str, run_id: str
    ) -> list[dict[str, Any]]:
        if not outputs:
            raise ValueError("执行没有返回可用媒体文件")
        destination = self.settings.output_dir(canvas_id, run_id).resolve()
        destination.mkdir(parents=True, exist_ok=True)
        result = []
        for index, output in enumerate(outputs, 1):
            source = self.resolve(output["path"], external=True)
            if output.get("kind") != media_kind(source):
                raise ValueError("输出媒体类型不符")
            if source.is_relative_to(destination):
                target = source
            else:
                target = (
                    destination / f"result-{index}-{uuid.uuid4().hex[:10]}{source.suffix.lower()}"
                )
                shutil.copyfile(source, target)
            asset: dict[str, Any] = self.asset(target, output.get("name"))
            if isinstance(output.get("metadata"), dict):
                asset["metadata"] = {
                    key: output["metadata"][key]
                    for key in ("duration_ms", "width", "height", "codec", "fps", "has_audio")
                    if key in output["metadata"]
                }
            result.append(asset)
        return result


def creative_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Compare creative configuration without layout or internal input-copy details."""

    def strip(value: Any) -> Any:
        if isinstance(value, list):
            return [strip(item) for item in value]
        if isinstance(value, dict):
            return {
                k: strip(v)
                for k, v in value.items()
                if k not in {"frozen_path", "sha256", "name", "source_run_id"}
            }
        return value

    return strip(snapshot)
