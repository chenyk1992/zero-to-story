#!/usr/bin/env python3
"""固定 MediaWiki revision 纯正文抽取的回归测试。"""

import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("fetch_human_corpus.py")
SPEC = importlib.util.spec_from_file_location("fetch_human_corpus", MODULE_PATH)
fetch_human_corpus = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fetch_human_corpus)


class WikitextExtractorTests(unittest.TestCase):
    def test_keeps_fixed_article_prose_and_removes_templates_and_source_tail(self):
        wikitext = """
        {{date|2020年10月26日}}
        <!-- 编者注 -->
        [[File:Queue.jpg|thumb|门外[[排隊]]買口罩]]
        '''第一段'''有[[w:测试|链接文字]]，还有{{nested|{{value}}}}模板。
        {{WNIQ|WSS}}：{{w|en:Jo Jorgensen|喬·喬根森}}支持{{big|保留正文}}、{{big|[[词条|链接显示文字]]}}和{{large|1=编号正文}}。

        == 进展 ==
        * 第一项
        * 第二项<ref>参考资料噪声</ref>

        第二段<br>换行内容。

        == 消息来源 ==
        * [https://example.org 模板表格噪声]
        [[Category:测试]]
        """

        text = fetch_human_corpus.extract_wikitext(wikitext)

        self.assertEqual(
            text,
            "第一段有链接文字，还有模板。\n喬·喬根森支持保留正文、链接显示文字和编号正文。\n\n进展\n第一项\n第二项\n\n第二段\n换行内容。\n",
        )
        self.assertNotIn("模板表格噪声", text)
        self.assertNotIn("参考资料噪声", text)
        self.assertNotIn("排隊", text)

    def test_collapses_inline_whitespace_without_joining_paragraphs(self):
        wikitext = "甲  乙 丙\n\n丁&nbsp;戊"

        self.assertEqual(fetch_human_corpus.extract_wikitext(wikitext), "甲 乙 丙\n\n丁 戊\n")


class OutputPathTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "evals" / "human-corpus").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_accepts_only_expected_corpus_filename(self):
        target = fetch_human_corpus.validate_output_path(
            self.root, Path("evals/human-corpus/HUMAN-09.txt")
        )

        self.assertEqual(
            target, self.root.resolve() / "evals" / "human-corpus" / "HUMAN-09.txt"
        )

    def test_unclosed_template_is_error(self):
        with self.assertRaisesRegex(ValueError, "未闭合"):
            fetch_human_corpus.extract_wikitext("正文。{{template\n后文不应静默丢失。")

    def test_rejects_absolute_path_and_traversal(self):
        for candidate in (Path("/tmp/HUMAN-09.txt"), Path("evals/human-corpus/../HUMAN-09.txt")):
            with self.subTest(candidate=candidate):
                with self.assertRaisesRegex(ValueError, "只能写入"):
                    fetch_human_corpus.validate_output_path(self.root, candidate)

    def test_rejects_symlink_directory_or_target(self):
        outside = self.root / "outside"
        outside.mkdir()
        corpus = self.root / "evals" / "human-corpus"
        corpus.rmdir()
        corpus.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "不能是 symlink"):
            fetch_human_corpus.validate_output_path(
                self.root, Path("evals/human-corpus/HUMAN-09.txt")
            )

        corpus.unlink()
        corpus.mkdir()
        target = corpus / "HUMAN-09.txt"
        target.symlink_to(outside / "body.txt")
        with self.assertRaisesRegex(ValueError, "不能是 symlink"):
            fetch_human_corpus.validate_output_path(
                self.root, Path("evals/human-corpus/HUMAN-09.txt")
            )


class RevisionIdentityTests(unittest.TestCase):
    def test_rejects_unexpected_revision_timestamp(self):
        revision = {"revid": 195471, "timestamp": "2021-01-30T20:09:33Z"}

        fetch_human_corpus.validate_expected_timestamp(
            revision, "2021-01-30T20:09:33Z"
        )
        with self.assertRaisesRegex(ValueError, "时间不符"):
            fetch_human_corpus.validate_expected_timestamp(
                revision, "2021-01-30T20:09:34Z"
            )

if __name__ == "__main__":
    unittest.main()
