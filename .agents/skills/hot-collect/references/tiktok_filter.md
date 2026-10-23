# 过滤器规则与踩过的坑

> 版本：v1（2026-10-23）
> 实测分区：`2026-10.parquet`，1,734,031 行，覆盖 2026-10-01 ~ 2026-10-03（2.5 天）

这些坑**不会报错**，只会安静地返回垃圾。每一条都是先看到错误的 top-N，再去反查命中的那句话。

---

## 坑 1 · 多语言里的 "ai" 是常用词

越南语 / 葡萄牙语 / 法语 / 西班牙语 / 意大利语里，`ai` 是普通词：

| 原文 | 实际意思 | 误判来源 |
|---|---|---|
| `CHUYỆN XUI RỦI ĐÂU AI MUỐN BÀ ƠI` | 「姐，今天想说啥啊」 | 越南语 `ai`（要/想） |
| `ai que tristeza 😔` | 「多难过啊」 | 葡萄牙语 `ai`（是） |
| `Huyền Miko là ai` | 「Huyền Miko 是谁」 | 越南语 `là ai`（是谁） |
| `có ai chiều cổ hơn tôi không` | 「有人比我更老吗」 | 越南语 |

**规则**：裸 `ai` 不算证据。AI 词必须**带上名词或限定词**（`ai tool` / `ai model` / `chatgpt` / `claude code`）。
`BARE_AI_OK_LANGS` 列出了这些语言的名单，裸 `ai` 在这些语言里直接忽略。

**影响量级**：宽松 `\bai\b` 正则命中 16,314 行，其中播放量 TOP 全是越南剧集和葡萄牙梗。

---

## 坑 2 · 产品名撞普通英文词

产品名白名单会被日常词直接命中，而且**命中的都是百万播放的正经内容**，所以不查就会误判：

| 白名单词 | 被什么撞了 | 实测播放量 |
|---|---|---:|
| `copilot` | **副驾驶**（"his copilot" = 副机长） | 481K |
| `claude` | **Jean-Claude Van Damme**（演员） | 338K |
| `runway` | 机场跑道 | — |
| `sora` / `kimi` / `manus` / `devin` | 各自的人名 | — |
| `perplexity` | 形容词「困惑」 | — |

**规则**：
- 明确的产品形态（`Claude Code` / `GitHub Copilot` / `OpenAI Sora` / `Gemini 2.5`）→ 强信号
- 裸词 → **弱信号（+1）**，必须与另一个 AI 信号共现才算话题
- `claude` 额外加负向后视：`Jean-Claude` 不算

---

## 坑 3 · "gemini" 是星座

西班牙语星座视频说 `géminis`（双子座），比真的 Gemini 模型内容播放量还高。
→ 命中 `ZODIAC_CONTEXT`（horoscope / zodiac / 双子座 / 占星 …）时扣 2 分。

---

## 坑 4 · 「用 AI 做」≠「讲 AI」

这是**量级最大**的一条：

| 轴 | 2026-10 分区条数 |
|---|---:|
| `is_ai_generated = 1`（用 AI 做的：CapCut 特效、AI 短剧、AI 滤镜） | **84,804** |
| 主题是 AI（严格口径，在讲 AI） | **2,434** |

差 35 倍。`#ai` 标签在 TikTok 上的用法也是「用 AI 做的内容」——实测最高播放的带 `#ai` 视频是一条 286 万播放的 "AI story" 剧情片（标签 `fruitdrama aistory ai fruitstory brainrot`）。

**规则**：
- `#ai` / `aivideo` / `aigenerated` / `aistory` / `dreamina` / `capcut` → **特效轴**
- `#chatgpt` / `#claude` / `#techtok` / `#vibecoding` / `#aicoding` / `#ia`（西语 AI）→ **话题轴**
- caption 里的 `AI-generated` 后面**没跟内容名词** → 特效轴，不算话题
  （实测：一条 101 万播放的 C 罗视频只因为 caption 带 "AI-generated" 标签被误判）

---

## 坑 5 · 屏幕文字里才藏着真信号

一条 82.8 万播放的视频：

- caption：`Así se hace chat #betoquez #humor` —— 西班牙语，**完全没提 AI**
- 屏幕文字：`Cuando intentas engañar a ChatGPT` —— 真正的钩子

**规则**：搜索与判定**必须同时覆盖 caption + 话题标签 + 屏幕文字**。只搜 caption 会漏掉关键对标。

---

## 规则总表

| 规则 | 强度 | 说明 |
|---|---|---|
| 话题标签命中（`#chatgpt` `#ia` `#techtok` …） | +2 | 强 |
| 明确产品名（`chatgpt` `openai` `anthropic` …） | +2 | 强 |
| 限定形态产品名（`Claude Code` `GitHub Copilot` `Gemini 2.5`） | +2 | 强 |
| AI + 技术名词（`ai tool` `ai coding` `ai workflow`） | +2 | 强 |
| AI 生成 + 内容名词（`AI-generated image`） | +2 | 强 |
| 提示词/智能体类（`prompting` `vibe coding` `ai agent`） | +2 | 强 |
| 连接词 + AI 词紧邻（`built with ai` `coding using ai`） | +1 | 中 |
| 裸歧义产品名（`claude` `copilot` `runway`） | +1 | 弱，需共现 |
| 星座上下文 | −2 | 排除 |
| 裸 `ai`（在多语言常用词语言里） | 0 | 忽略 |

判定阈值：`score ≥ 2` 记为「主题是 AI」。

---

## 性能

对 173 万行做 `.apply(axis=1)` 要几分钟。做法是**两级**：

1. **向量化粗筛**（`PREFILTER`，故意宽松，只保证不漏）→ 候选集
2. **严格判定**只跑在候选集上（`itertuples` + `zip(index)`）

整轮 `stats` ≈ 35s（含 191MB parquet 读入 + 1.73M 行向量化筛）。
