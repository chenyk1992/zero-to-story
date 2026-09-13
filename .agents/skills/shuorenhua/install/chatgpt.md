# ChatGPT / 通用 LLM 安装

## mini / lite / full 怎么选

- `mini`：只加载 [`dist/shuorenhua-mini.md`](../dist/shuorenhua-mini.md)。适合 Custom Instructions、直接贴对话、较弱模型或只想先清明显模板感的场景。
- `lite`：只加载 `SKILL.md`。适合 API system prompt、临时项目和需要完整保真合同的改写。
- `full`：加载 `SKILL.md` + `references/`。适合 Custom GPT、Project、公开文本、技术文档和需要误杀防护的场景。

ChatGPT / 通用 LLM 临时使用可以从 mini 开始；只要涉及公开文本、技术边界、长文或反误杀，就用 lite 或 full。mini 是压缩子集，不替代完整规则。

## ChatGPT

### 方案一：Custom GPT（推荐）

`SKILL.md` 有 12,000+ 字符，超过 Custom Instructions 当前所有档位的上限。用 Custom GPT 可以加载完整规则，不用删减。

**直接使用：** [说人话 GPT](https://chatgpt.com/g/g-6a5829b1163481919e1e45851f6bc709-shuo-ren-hua)（需要 ChatGPT Plus / Pro）

如果你想自建一个，步骤如下：

1. 打开 [ChatGPT GPT Editor](https://chatgpt.com/gpts/editor)，新建一个 GPT
2. 名称填"说人话"，描述填"去 AI 味的中英文改写助手"
3. 将 [`install/chatgpt-gpt-instructions.md`](chatgpt-gpt-instructions.md) 中分隔线以下的内容粘贴到 Instructions
4. 上传 Knowledge Files：`SKILL.md` + `references/` 目录下所有 `.md` 文件（full 用法）
5. 保存，发布为 "Only me" 或 "Anyone with a link"

用的时候直接打开这个 GPT 对话就行。

### 方案二：Projects

如果你有 ChatGPT Plus / Pro，也可以用 Projects：

1. 新建一个 Project
2. 把 `SKILL.md` 和需要的 `references/` 文件上传到 Project Files；长期使用建议走 full，临时项目可以先只放 `SKILL.md`
3. Project Instructions 里写一句：`按照项目文件中 SKILL.md 的规则改写用户提供的文本。`

Projects 的文件没有严格字符限制，效果和 Custom GPT 类似。

### 方案三：直接贴对话（mini）

不想建 GPT 也不想建 Project，直接在对话开头贴 `dist/shuorenhua-mini.md` 的内容。适合偶尔用一次、上下文紧张或较弱模型。

如果需要完整保真合同，可以改贴 `SKILL.md`，这是 lite 用法。

### 方案四：Custom Instructions（mini）

把 `dist/shuorenhua-mini.md` 粘贴到 Settings > Personalization > Custom Instructions。按 [OpenAI 当前官方说明](https://help.openai.com/en/articles/8096356-custom-instructions-for-chatgpt)，Free / Go 上限是 1,500 字符，Plus / Pro / Enterprise / Business / Education 上限是 5,000 字符；约 1,000 字符的 mini 两边都放得下，完整 `SKILL.md` 两边都放不下。

## Claude（Web / Project）

1. 创建一个 Project
2. 将 `SKILL.md` 内容添加到 Project Instructions
3. 需要更稳的误杀防护时，再把相关 `references/` 文件加入 Project Knowledge

## API / System Prompt

```python
messages = [
    {"role": "system", "content": open("SKILL.md").read()},
    {"role": "user", "content": "改写以下文本：..."}
]
```

如果已有主 system prompt，把 `SKILL.md` 当成一个风格模块拼进去，不要整段覆盖。

## 使用提示

如果你想先判断"哪里像 AI"，不要直接改稿，在对话里说：

```text
先不要改写，只按 annotation mode 标出下面这段文字里的问题：...
```

适合这几类场景：

- 你想先看这段话该不该改
- 你要做审稿或 review，不想直接替作者重写
- 你怀疑有无源引用、语域混搭或工程师腔，但还不想动正文

处理无源引用时，可以指定模式：

```text
用说人话规则改写这段文本，无源引用按 audit-only 处理。
```

三种模式：`rewrite-safe`（默认用于 chat/public-writing，直接删无证据权威铺垫）、`audit-only`（默认用于 docs/status，只标缺来源）、`rewrite-with-placeholder`（保留结构但暴露缺来源）。不指定时按场景默认值走。

## 长文改写的三档 scope

长文（约 1000 字以上的 `public-writing`）改写时，可以指定三档 scope，和力度档位正交：

- `structural`：自由删句、并句、重排，去味最彻底，但长度不可控（实测同一篇可能 -18% 到 -39%）
- `bounded`（长文默认）：实句只做句内清理；整句空话不直接删，列成「建议删除（待确认）」清单交你拍板
- `in-place`：一句都不删，只做句内降调，适合“完全原样”的要求

在指令里直接说就行，例如：「用 bounded scope 改写，整句空话列出来给我确认、别直接删。」

## 什么时候需要补 `references/`

- AI 腔很重，普通去词表改写效果不够
- 中英文混合，需要精细场景判断
- 技术文案，担心误杀术语
- 需要处理结构问题，不只是删词

优先补：`structures.md` / `severity.md` / `operation-manual.md` / `boundary-cases.md`
