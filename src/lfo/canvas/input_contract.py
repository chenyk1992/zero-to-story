"""Declarative input validation shared by Canvas and provider adapters."""

from __future__ import annotations

import math
from typing import Any


def validate_input_contract(snapshot: dict[str, Any], capability: dict[str, Any]) -> None:
    """Validate fields and mode constraints without executing provider code or I/O."""
    parameters = snapshot["parameters"]
    for field in capability.get("fields", []):
        value = parameters.get(field["key"])
        label = field["label"]
        if value is None or value == "":
            if field.get("required"):
                raise ValueError(f"请填写{label}")
            continue
        if field["type"] == "number":
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{label}需要有效数值")
            if "min" in field and value < field["min"]:
                raise ValueError(f"{label}不能小于 {field['min']}")
            if "max" in field and value > field["max"]:
                raise ValueError(f"{label}不能大于 {field['max']}")
            if field.get("integer") and int(value) != value:
                raise ValueError(f"{label}需要整数")
        choices = field.get("values")
        if field["type"] == "select":
            choices = [option["value"] for option in field.get("options", [])]
        if choices is not None and value not in choices:
            raise ValueError(f"{label}只支持：{', '.join(map(str, choices))}")
        if field["type"] == "boolean" and not isinstance(value, bool):
            raise ValueError(f"{label}需要开关值")
        if field.get("modes") and snapshot["mode"] not in field["modes"]:
            raise ValueError(f"{label}仅适用于 {', '.join(field['modes'])}")
    allowed = {field["key"] for field in capability.get("fields", [])}
    for key, value in parameters.items():
        if key not in allowed and value is not None and value != "":
            raise ValueError(f"所选方式不支持参数 {key}，请调整后确认")
    for rule in capability.get("parameter_rules", []):
        if all(parameters.get(key) == value for key, value in rule["when"].items()):
            for key, value in rule["require"].items():
                if parameters.get(key) != value:
                    raise ValueError(rule["message"])

    rules = capability.get("input_rules", {}).get(snapshot["mode"])
    if rules is None:
        return
    labels = {
        "first_frame": "首帧", "last_frame": "尾帧",
        "reference_images": "参考图片", "reference_videos": "参考视频",
        "reference_audios": "参考音频",
    }
    counts = {}
    for key, value in snapshot.get("inputs", {}).items():
        counts[key] = len(value) if isinstance(value, list) else int(value is not None)
        if counts[key] and key not in rules.get("allowed", []):
            raise ValueError(f"{snapshot['mode']} 不接受{labels.get(key, key)}，请调整输入连线")
    for key in rules.get("required", []):
        if counts.get(key, 0) != 1:
            raise ValueError(f"{labels.get(key, key)}为 {counts.get(key, 0)}，{snapshot['mode']} 需要 1 个")
    any_of = rules.get("any_of", [])
    for key, maximum in rules.get("max_counts", {}).items():
        if counts.get(key, 0) > maximum:
            raise ValueError(f"{labels.get(key, key)}最多支持 {maximum} 项")
    if any_of and not any(counts.get(key, 0) for key in any_of):
        raise ValueError(f"{snapshot['mode']} 至少需要一项参考素材")
