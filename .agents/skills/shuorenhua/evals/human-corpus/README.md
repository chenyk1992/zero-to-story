# HUMAN 长文对照语料

这里放人写中文长文的纯文本正文；元数据和授权依据统一登记在 `../human-corpus.jsonl`。这批语料只用于 residual 统计的假阳性对照，不进入 benchmark、盲测、rewrite 或 judge 分母，也不把“人写”当作绝对正确标签。

HUMAN 正文保留 manifest 里逐篇标明的权利条件，不因放进本仓库就统一改授为根目录的 MIT License。复制、fork 或单独复用正文时，不得拆掉 `human-corpus.jsonl` 里的来源、归属、许可链接和改动说明。

## 准入

- 收 8–12 篇，目标 12 篇；每篇至少 1,000 个汉字，且当前句子解析器能识别至少 12 句。
- v2.3.1 只收逐篇核验过的公开来源；公开可读不等于允许再分发。优先 Public Domain、CC0、CC BY、CC BY-SA，也可用留有证据的书面许可。
- active 条目必须明确 `ai_assisted=no`、填写可核验的 `ai_evidence`，并设 `deidentified=true`。后者表示已经做过隐私检查，必要身份线索已去除；未知、模型生成、模型改写稿不进统计。
- 不收付费墙、私域内容、授权不清或含可识别第三方隐私的正文。去标识只改身份线索，不改句式、数字和术语。
- 至少覆盖 3 个作者组；历史、现代文本各不少于 3 篇，翻译文本不超过 active cohort 的三分之一，不让单一时代、作者或翻译腔支配分布。`docs / public-writing / status` 的发布代表性只统计 `representation_role=direct`，`proxy` 可以进入 residual，但不能替直接场景顶数。

## JSONL 字段

每行一篇，字段固定：

```json
{"id":"HUMAN-01","path":"evals/human-corpus/HUMAN-01.txt","scene":"status","genre":"public-year-in-review","era":"modern","origin_language":"zh-original","representation_role":"proxy","author_group":"author-a","source_type":"open","source_url":"https://example.org/work?oldid=123","source_revision":"123","source_revision_at":"2021-01-30T20:09:33Z","source_title":"公开文章","source_author":"原作者；站点 contributors","license":"CC BY 4.0","license_url":"https://creativecommons.org/licenses/by/4.0/","license_evidence_url":"https://example.org/policy?oldid=456","modifications":"downloaded fixed-revision wikitext; preserved visible display-template text; removed structural templates and wiki markup; no prose rewrite","consent_evidence":"source page declares CC BY 4.0","written_at":"2020","fixed_revision_at":"2021-01-30","ai_assisted":"no","ai_evidence":"the fixed source revision existed before widespread generative-AI writing; no generative rewrite","deidentified":true,"added_on":"2026-08-20","sha256":"0000000000000000000000000000000000000000000000000000000000000000","withdrawn":false}
```

- `author_group` 用稳定匿名组名即可，不必公开实名。
- `era` 只取 `historical/modern`；`origin_language` 只取 `zh-original/translated-from-en`。它们用于拆开历史文体与翻译腔，不能从一组混合数字反推“人类写作”的总体分布。
- `representation_role` 只取 `direct/proxy`。只有语体和使用场景本身都直接匹配时才标 `direct`；公开回顾代内部周报、历史议论文代现代技术文档都必须标 `proxy`。
- `source_type` 仍保留 `owner/open` 两种通用格式，但 v2.3.1 cohort 的 active 条目必须全部为 `open`。公开来源必须填写可核对的 HTTP(S) `source_url`、作品名 `source_title` 和创作者 `source_author`；`author_group` 可匿名，但公开许可要求的归属不能匿掉。
- `license` 写可再分发依据：公开来源可用 `Public Domain`、`CC0`、`CC BY`、`CC BY-SA` 的受支持版本或 `written-permission`。Public Domain 和 CC 条目的 `license_url` 必须写对应 Creative Commons 官方 canonical URL；MediaWiki 条目的 `license_evidence_url` 指向同站带 `oldid` 的固定版权政策证据，作品版本本身由 `source_url + source_revision` 锁定。
- `modifications` 必须说明入库前是否改动；未改写 `none`，去标识、抽取正文、繁简转换或其他变更要如实写明。可见归属由 `source_title + source_author + source_url + license + license_url + modifications` 组成；CC BY-SA 正文及本仓库中的改编版本继续按同版本 CC BY-SA 分享，不适用根目录 MIT。
- owner 的 `consent_evidence` 固定写 `owner approved repository redistribution on YYYY-MM-DD`；Public Domain/CC 条目写 `source page declares <license>`；书面许可写 `written permission archived at <证据路径或链接> on YYYY-MM-DD`。脚本只核对这些元数据是否满足合同，归属内容和授权证据真实性仍由维护者人工确认。
- `ai_evidence` 记录 `ai_assisted=no` 的依据。历史作品可写明首次发表年份早于生成式 AI，且本仓库只作机械抽取/格式清理、没有生成式改写；无法证明作者内容来源的，不纳入。
- 公开来源必须同时记录 `source_revision`、API 返回的 UTC `source_revision_at` 和日期 `fixed_revision_at`。MediaWiki 作品 `source_url` 的 `oldid` 必须等于 `source_revision`，日期必须等于时间戳的 UTC 日期；`license_evidence_url` 则单独锁定已核验版权政策页的 revision，不要求与作品 revision 相同。这些字段证明本仓库拿到的是哪一版，不等于单凭 revision 完成作者身份或许可判断。
- active 正文只放 `evals/human-corpus/HUMAN-xx.txt`，文件名必须和 `id` 对应，不用 symlink 指向仓库其他文件。
- `sha256` 是正文 UTF-8 原始字节的哈希，用来防漂移和去重。
- 作者撤回时保留原 `id`，设 `withdrawn=true`，把 `consent_evidence` 改成 `withdrawn by author on YYYY-MM-DD`，可删除正文；撤回条目不进统计，编号不复用。

## 校验与统计

```bash
python3 automation/eval/hard_metrics.py --human-stats evals/human-corpus.jsonl
python3 automation/eval/hard_metrics.py --human-stats evals/human-corpus.jsonl --report-json
python3 automation/eval/hard_metrics.py --calibrate
```

格式、重复 ID/路径/哈希、授权字段、AI 辅助状态、长度和句数任一不合格都退出 2。输出按总体、场景和长度桶列句长 CV 与连词密度；样本数小于 8 的分组同时列原始值。分布不可分就记录负结论，不设阈值。

固定 MediaWiki revision 可用仓库内的零依赖抽取器重建；它读取固定 wikitext，去掉模板、导航、引用、媒体说明和 wiki 标记，不使用会随当前模板变化的渲染 HTML，也不做生成式改写：

```bash
python3 automation/eval/fetch_human_corpus.py \
  --project wikinews --oldid 195471 \
  --expected-timestamp 2021-01-30T20:09:33Z \
  --output evals/human-corpus/HUMAN-01.txt
```

## 代表性边界

当前 8 篇是一个分层 residual 对照切片：3 篇现代中文公开年度/报道回顾、2 篇现代英译中公开采访、3 篇历史中文原作。`status` 只表示“公开回顾文本的状态汇总功能”，不是内部团队周报；两篇 `public-writing` 是翻译稿；当前没有可公开再分发且能证明 AI 来源的真实团队聊天、内部周报和现代原创中文技术文档。

因此 6 篇 `proxy` 不进入场景代表性计数；当前 `direct` 只有 2 篇 `public-writing`，发布代表性门禁明确缺 `docs` 和 `status`。这批数据只能比较已列出的时代、场景和来源，不能宣称代表现代中文职场写作，更不能单独训练或设定“人味”阈值。缺口保持显式，后续只有拿到逐篇授权和 provenance 的真实样本才补，不用新闻、文学或翻译稿改标签顶数。
