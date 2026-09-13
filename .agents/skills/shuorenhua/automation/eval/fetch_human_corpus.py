#!/usr/bin/env python3
"""从固定 MediaWiki revision 机械抽取 HUMAN 纯正文。"""

import argparse
import hashlib
import html
import json
import os
import re
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path


PROJECTS = {
    "wikinews": "https://zh.wikinews.org",
    "wikisource": "https://zh.wikisource.org",
}
EXCLUDED_SECTIONS = {
    "延伸閱讀",
    "延伸阅读",
    "消息來源",
    "消息来源",
    "參考資料",
    "参考资料",
    "相關新聞",
    "相关新闻",
    "外部連結",
    "外部链接",
    "註釋",
    "注释",
}
VISIBLE_TEXT_TEMPLATES = {"w", "big", "large"}


def _split_template_parts(body):
    """按模板顶层管道切分；链接显示文本里的 `|` 不算模板分隔符。"""
    parts = []
    current = []
    link_depth = 0
    index = 0
    while index < len(body):
        if body.startswith("[[", index):
            link_depth += 1
            current.append("[[")
            index += 2
            continue
        if body.startswith("]]", index):
            if link_depth == 0:
                raise ValueError("显示模板内有未配对的 ]] 链接标记")
            link_depth -= 1
            current.append("]]")
            index += 2
            continue
        if body[index] == "|" and link_depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(body[index])
        index += 1
    if link_depth:
        raise ValueError("显示模板内有未闭合的 [[ 链接标记")
    parts.append("".join(current).strip())
    return parts


def _template_positional_values(parts):
    """解析 MediaWiki 位置参数，兼容 `1=正文` 与普通位置参数混用。"""
    values = {}
    next_position = 1
    for part in parts:
        numbered = re.match(r"^([1-9]\d*)=(.*)$", part, flags=re.DOTALL)
        if numbered:
            values[int(numbered.group(1))] = numbered.group(2).strip()
            continue
        if re.match(r"^[^=]+=(.*)$", part, flags=re.DOTALL):
            continue
        while next_position in values:
            next_position += 1
        values[next_position] = part.strip()
        next_position += 1
    return values


def _replace_visible_templates(text):
    """保留少数纯显示模板的可见参数，删除其余 MediaWiki 模板。

    当前固定语料中 `w` 是词条链接，`big/large` 只是字号包装；它们的参数
    属于正文。日期、来源、采访标签等结构模板整段删除。先从最内层处理，
    使嵌套在结构模板里的显示文本最终仍随外层结构模板一起删除。
    """
    innermost = re.compile(r"\{\{([^{}]*)}}")

    def replacement(match):
        parts = _split_template_parts(match.group(1))
        name = parts[0].lower() if parts else ""
        values = _template_positional_values(parts[1:])
        if name not in VISIBLE_TEXT_TEMPLATES or not values:
            return ""
        if name == "w":
            return values.get(2, values.get(1, ""))
        return values.get(1, "")

    while innermost.search(text):
        text = innermost.sub(replacement, text)
    if "{{" in text or "}}" in text:
        raise ValueError("{{ 模板标记未闭合")
    return text


def _drop_excluded_sections(text):
    kept = []
    skipped_level = None
    heading_pattern = re.compile(r"^(={2,6})\s*(.*?)\s*\1\s*$")
    for line in text.splitlines():
        match = heading_pattern.match(line.strip())
        if match:
            level = len(match.group(1))
            title = re.sub(r"''+", "", match.group(2)).strip()
            if title in EXCLUDED_SECTIONS:
                skipped_level = level
                continue
            if skipped_level is not None and level <= skipped_level:
                skipped_level = None
        if skipped_level is None:
            kept.append(line)
    return "\n".join(kept)


def _remove_namespaced_links(text):
    removable = re.compile(r"^(?:File|Image|Category|文件|檔案|图像|分類|分类):", re.IGNORECASE)
    result = []
    index = 0
    while index < len(text):
        if not text.startswith("[[", index):
            result.append(text[index])
            index += 1
            continue
        cursor = index + 2
        depth = 1
        while cursor < len(text) and depth:
            if text.startswith("[[", cursor):
                depth += 1
                cursor += 2
            elif text.startswith("]]", cursor):
                depth -= 1
                cursor += 2
            else:
                cursor += 1
        if depth:
            result.append(text[index])
            index += 1
            continue
        content = text[index + 2 : cursor - 2].lstrip()
        if not removable.match(content):
            result.append(text[index:cursor])
        index = cursor
    return "".join(result)


def _replace_variant_markup(text):
    def replacement(match):
        content = match.group(1)
        variants = {}
        for part in content.split(";"):
            if ":" in part:
                key, value = part.split(":", 1)
                variants[key.strip().lower()] = value.strip()
        if variants:
            for key in ("zh-hans", "zh-cn", "zh-sg"):
                if key in variants:
                    return variants[key]
            return next(iter(variants.values()))
        return content

    return re.sub(r"-\{(.*?)}-", replacement, text, flags=re.DOTALL)


def extract_wikitext(wikitext):
    text = wikitext.replace("\r\n", "\n").replace("\r", "\n")
    text = _drop_excluded_sections(text)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = re.sub(r"<ref\b[^>]*/\s*>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<ref\b[^>]*>.*?</ref\s*>", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<gallery\b[^>]*>.*?</gallery\s*>", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"^\{\|.*?^\|\}\s*$", "", text, flags=re.MULTILINE | re.DOTALL)
    text = _replace_visible_templates(text)
    text = _remove_namespaced_links(text)
    link_pattern = re.compile(r"\[\[([^\[\]]+?)\]\]")

    def replace_link(match):
        parts = match.group(1).split("|")
        return parts[-1].strip()

    while link_pattern.search(text):
        text = link_pattern.sub(replace_link, text)
    text = re.sub(r"\[(?:https?|ftp)://\S+\s+([^\]]+)]", r"\1", text)
    text = re.sub(r"\[(?:https?|ftp)://[^\]]+]", "", text)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</?(?:poem|blockquote|div|span|small|center|section)\b[^>]*>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"^\s*__\w+__\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*(={2,6})\s*(.*?)\s*\1\s*$", r"\n\2\n", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[*#;:：]+\s*", "", text, flags=re.MULTILINE)
    text = _replace_variant_markup(text)
    text = text.replace("'''", "").replace("''", "")
    text = html.unescape(text).replace("\xa0", " ")
    lines = [re.sub(r"[ \t\f\v]+", " ", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if not re.fullmatch(r"[-─—]{3,}", line)]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def _get_json(base_url, params):
    url = f"{base_url}/w/api.php?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "shuorenhua-human-corpus/2.3.1 (fixed-revision extractor)"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def fetch_revision(project, oldid):
    base_url = PROJECTS[project]
    queried = _get_json(
        base_url,
        {
            "action": "query",
            "prop": "revisions",
            "revids": oldid,
            "rvprop": "ids|timestamp|content",
            "rvslots": "main",
            "format": "json",
            "formatversion": 2,
        },
    )
    pages = queried.get("query", {}).get("pages", [])
    revisions = pages[0].get("revisions", []) if len(pages) == 1 else []
    if len(revisions) != 1 or revisions[0].get("revid") != oldid:
        raise RuntimeError(f"固定 revision 返回不完整或编号不符: {oldid}")
    content = revisions[0].get("slots", {}).get("main", {}).get("content")
    if not isinstance(content, str):
        raise RuntimeError(f"固定 revision 缺少 main slot 正文: {oldid}")

    return {
        "title": pages[0].get("title", ""),
        "revid": oldid,
        "timestamp": revisions[0]["timestamp"],
        "text": extract_wikitext(content),
    }


def validate_expected_timestamp(revision, expected_timestamp):
    """防止同一条 manifest 命令在 revision 元数据漂移时静默覆盖正文。"""
    actual = revision.get("timestamp")
    if actual != expected_timestamp:
        raise ValueError(
            f"固定 revision 时间不符：期望 {expected_timestamp}，API 返回 {actual}"
        )


def validate_output_path(root, output):
    root = Path(root).resolve()
    output = Path(output)
    if (
        output.is_absolute()
        or output != Path("evals") / "human-corpus" / output.name
        or not re.fullmatch(r"HUMAN-\d{2,}\.txt", output.name)
    ):
        raise ValueError("--output 只能写入 evals/human-corpus/HUMAN-xx.txt")

    evals_dir = root / "evals"
    corpus_dir = evals_dir / "human-corpus"
    if evals_dir.is_symlink() or corpus_dir.is_symlink():
        raise ValueError("evals/human-corpus 及其父目录不能是 symlink")
    if not corpus_dir.is_dir():
        raise ValueError("evals/human-corpus 目录不存在")

    target = root / output
    if target.is_symlink():
        raise ValueError("HUMAN 输出目标不能是 symlink")
    if target.resolve().parent != corpus_dir.resolve():
        raise ValueError("--output 只能写入 evals/human-corpus/HUMAN-xx.txt")
    return target


def write_atomic(path, text):
    path = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as handle:
            handle.write(text)
            temporary = Path(handle.name)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", choices=sorted(PROJECTS), required=True)
    parser.add_argument("--oldid", type=int, required=True)
    parser.add_argument("--expected-timestamp", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.oldid <= 0:
        parser.error("--oldid 必须是正整数")
    root = Path(__file__).resolve().parents[2]
    try:
        output = validate_output_path(root, args.output)
    except ValueError as exc:
        parser.error(str(exc))
    revision = fetch_revision(args.project, args.oldid)
    try:
        validate_expected_timestamp(revision, args.expected_timestamp)
    except ValueError as exc:
        parser.error(str(exc))
    write_atomic(output, revision.pop("text"))
    body = output.read_bytes()
    revision.update(
        {
            "output": args.output.as_posix(),
            "bytes": len(body),
            "han": len(re.findall(r"[\u3400-\u9fff]", body.decode("utf-8"))),
            "sha256": hashlib.sha256(body).hexdigest(),
        }
    )
    print(json.dumps(revision, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
