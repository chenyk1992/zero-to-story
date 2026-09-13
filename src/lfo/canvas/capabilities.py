"""Read removable project Skill descriptors without importing their code."""

from __future__ import annotations

import copy
import json
import os
import shutil
from pathlib import Path
from typing import Any

from lfo.canvas.input_contract import validate_input_contract


class CapabilityCatalog:
    def __init__(self, project_root: Path) -> None:
        self.skills_root = project_root / ".agents" / "skills"

    def entries(self, host_tools: list[str] | None = None) -> list[dict[str, Any]]:
        if host_tools is not None and (
            not isinstance(host_tools, list)
            or any(not isinstance(tool, str) or not tool.strip() for tool in host_tools)
        ):
            raise ValueError("host_tools 需要当前接手会话实际可调用的工具名称列表")
        tools = set(host_tools or [])
        paths = sorted(self.skills_root.glob("*/capability.json"))
        paths += sorted(self.skills_root.glob("*/references/capabilities/*.json"))
        entries: dict[str, dict[str, Any]] = {}
        for path in paths:
            try:
                item = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                    continue
                relative = path.relative_to(self.skills_root)
                skill_dir = self.skills_root / relative.parts[0]
                item["_skill_dir"] = str(skill_dir)
                item["skill"] = item.get("skill", skill_dir.name)
                item["installed"] = item.get("execution") in {"script", "agent"}
                item["available"] = item["installed"]
                if item.get("execution") == "agent":
                    required = item.get("requires_tools", [])
                    item["available"] = bool(required) and set(required).issubset(tools)
                    if not item["available"]:
                        item["reason"] = "需要接手会话核实工具：" + ", ".join(required)
                if item.get("execution") == "script":
                    entrypoint = (skill_dir / item.get("entrypoint", "")).resolve()
                    if (
                        not entrypoint.is_relative_to(skill_dir.resolve())
                        or not entrypoint.is_file()
                    ):
                        item.update(
                            installed=False, available=False, reason="执行 Skill 缺少有效入口"
                        )
                for executable in item.get("requires_executables", []):
                    override_name = {
                        "comfy": "LFO_COMFY_CLI",
                        "ffprobe": "LFO_FFPROBE",
                    }.get(executable)
                    candidate = (
                        os.environ.get(override_name, "") if override_name else ""
                    ) or executable
                    if not shutil.which(candidate):
                        item.update(
                            installed=False,
                            available=False,
                            reason=f"本机尚未发现 {candidate}",
                        )
                if item["id"] in entries:
                    entries[item["id"]].update(
                        installed=False,
                        available=False,
                        reason="存在重复的能力标识，请检查项目 Skill",
                    )
                else:
                    entries[item["id"]] = item
            except (OSError, ValueError, TypeError):
                continue
        return list(entries.values())

    def public(self, host_tools: list[str] | None = None) -> list[dict[str, Any]]:
        return [
            {k: v for k, v in entry.items() if not k.startswith("_")}
            for entry in self.entries(host_tools)
        ]

    def get(self, provider: str, host_tools: list[str] | None = None) -> dict[str, Any]:
        for entry in self.entries(host_tools):
            if entry["id"] == provider:
                return entry
        raise ValueError("所选生成 Skill 已移除或尚未接入，请重新选择生成方式")

    def validate(
        self,
        snapshot: dict[str, Any],
        host_tools: list[str] | None = None,
        *,
        for_claim: bool = False,
    ) -> dict[str, Any]:
        capability = self.get(snapshot["provider"], host_tools)
        # The browser may queue an explicitly selected agent provider. Only a
        # capable receiving session can claim it; no global host is assumed.
        usable = capability["available"] or (
            not for_claim and capability["installed"] and capability["execution"] == "agent"
        )
        if not usable:
            raise ValueError(capability.get("reason", "所选能力不可用"))
        if snapshot["node_type"] not in capability.get("node_types", []):
            raise ValueError("所选能力不支持这个组件类型")
        for key, choices_key in (("model", "models"), ("mode", "modes")):
            choices = capability.get(choices_key, [])
            if choices and snapshot.get(key) not in [choice["id"] for choice in choices]:
                raise ValueError(f"请在所选生成方式中选择有效的 {key}")
        validate_input_contract(snapshot, capability)
        return copy.deepcopy(capability)
