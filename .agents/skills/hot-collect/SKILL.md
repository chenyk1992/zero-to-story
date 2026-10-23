---
name: hot-collect
description: 跨平台热点采集与快照。把抖音/B站/小红书/夸克热榜、B站作品级数据、YouTube 频道流与「近 7 天高播放新视频」拉成带时间戳的快照，并维护月度聚合与端点契约指纹；另提供 TikTok 视频级对标语料（5.6B 条公开视频元数据，月度分区）的同步与查询。当用户需要"现在的热点是什么""AI 圈今天在火什么""热点数据""跨平台热榜""趋势快照""选题数据从哪来""TikTok 上这个话题怎么样""海外对标"时使用。触发词：热点、热榜、趋势、抖音热榜、小红书热榜、B站排行榜、YouTube 热门、新视频、选题数据、快照、热度采集、TikTok、tiktok 对标、海外对标。
---

# hot-collect · 热点采集与快照层

**这个 skill 只记录，不判断。** 判断在 `topic-scout`。

## 它解决什么

判断"该做哪个选题"需要时间序列：今天什么在火、哪个词连续在榜、哪个词刚冒头、哪个词有热度但没人做。
单次查询给不出这些，**必须每天（或每小时）存快照**。

## 数据根目录（隔离，不进项目 workspace）

| 顺序 | 来源 |
|---|---|
| 1 | `--data-root` 参数 |
| 2 | 环境变量 `LFO_HOTSPOT_DATA` |
| 3 | `<用户数据>/zero-to-story/hotspot`（与 `canvas/`、`video/` 同级） |

默认落在应用数据目录，**和 zero-to-story 的媒体、产物完全隔离**，不会被项目构建或清理流程碰到。

```
<root>/
├── snapshots/YYYY-MM/HHMM.json   原始快照（按月分区，保留 12 个月）
├── aggregates/YYYY-MM.json        每个词的月度聚合（永久保留）
├── contracts/<source>__<ep>.json  每个端点的字段指纹（检测上游改字段）
└── corpora/tiktok/YYYY-MM.parquet  TikTok 对标语料（月度分区，不进快照）
```

## 用法

```bash
S=".agents/skills/hot-collect/scripts"

python "$S/daily.py"              # ★ 一条命令跑完整条链路（采集 → 打分 → 今日选题建议）
python "$S/doctor.py"              # ★ 环境体检：依赖/凭据/数据根/快照/语料/兄弟 skill/源连通性
python "$S/selftest.py"            # 离线自检（不联网、不碰真实数据）

python "$S/collect.py" --probe       # 只探活，不写盘
python "$S/collect.py" --collect     # 探活 → 拉取 → 落快照 → 更新契约指纹
python "$S/collect.py" --aggregate   # 从快照重建月度聚合
```

`daily.py` 会把**用户级环境变量补进当前进程**，所以新开的终端 / 定时任务不需要重启就能用；
它还会明确标出「本轮哪些信号是空的」，避免把空转的权重当成判断依据。

建议加一个每日定时任务（Windows 任务计划 / cron）：
`python "$S/daily.py" --include "<赛道词>"` 每天一次，建议 10:00 前后（避开平台榜单刷新高峰）。

## 依赖与环境

| 依赖 | 必需性 | 缺了会怎样 |
|---|---|---|
| Python ≥ 3.10 标准库 | **必需** | — |
| `pyarrow` + `pandas` | **可选**，只有 TikTok 对标语料面要 | 只有对标语料面不可用，主链路照跑；报错会直接告诉你装什么 |

```bash
python -m pip install pyarrow pandas   # 只有需要 TikTok 对标面时才装
```

**可移植性**：所有路径都靠 `--data-root` / `LFO_HOTSPOT_DATA` / `Path.home()` 解析，
**没有任何硬编码盘符**；把整个 `hot-collect/` 目录复制到另一台机器即可用。
搬运步骤见 [guides/hotspot-skill-porting.md](../../../guides/hotspot-skill-porting.md)。

## 退出码契约（与 topic-scout 一致）

| 码 | 含义 | 谁会用 |
|---|---|---|
| `0` | 成功 | 定时任务、CI |
| `1` | 跑了但结果不合格（契约漂移、闸门报红、回归未过） | 门禁 |
| `2` | 环境未就绪，**跑不起来**（缺依赖、缺凭据、数据根不可写） | 部署检查 |

## 故障排查

| 现象 | 原因 | 处理 |
|---|---|---|
| `[degraded] xxx: HTTP 429` | 60s 公共实例限频 | 正常，会自动退避重试；频繁出现就自部署 `vikiboss/60s` |
| `[degraded] youtube/rss: 空结果` | YouTube feed 端点本身在抖（实测成功率 40–50%） | 正常，adapter 已重试 4 次；**不影响** Data API 层 |
| `[contract CHANGED]` | 上游真改了字段 | 人工核对一次；确认无害后基线自动更新 |
| `[contract skip]` | 该端点本轮失败，**保留原基线** | 正常，不是告警 |
| `ModuleNotFoundError: pyarrow` | 可选依赖没装 | `pip install pyarrow pandas`，或不用 TikTok 对标面 |
| `未配置 YOUTUBE_API_KEY` | 凭据没配 | 见下「环境变量」 |

## 数据源与当前状态

| 源 | 覆盖 | 协议 | 凭据 | 状态（2026-10-23 实测） |
|---|---|---|---|---|
| `sixty` | 抖音热榜 / 小红书热榜 / 夸克 7x24 / AI 快讯 | MIT 开放 API | 无 | ✅ 4/4 端点（公共实例会 429） |
| `bilibili` | 作品级：全站榜 / 热门 / 分区榜，每条带完整 stat | 官方公开接口 | 无 | ✅ 3/3 端点（频繁调用会限流） |
| `youtube` | 频道 RSS（追踪频道最新视频） | 官方 RSS | 无 | ✅（**端点本身会抖，adapter 内置 4 次退避重试**） |
| `youtube` | 近 7 天高播放新视频（**带播放量/点赞数**） | 官方 Data API v3 | `YOUTUBE_API_KEY` | ✅ 已配置，50 条 / 次，101 units / 次 |

台账与合规状态见 [SOURCES.md](SOURCES.md)。

### 环境变量

| 变量 | 作用 | 未配置时 |
|---|---|---|
| `YOUTUBE_API_KEY` | YouTube Data API 凭据（用户级环境变量，不进仓库） | 该端点跳过并**明确报告**「未配置 YOUTUBE_API_KEY」，不静默 |
| `YOUTUBE_API_QUERY` | 这一层关注的赛道词（`\|` 分隔），默认 `AI\|LLM\|agent\|GPT\|Claude` | 用默认值 |
| `LFO_HOTSPOT_DATA` | 覆盖数据根目录 | 用默认应用数据目录 |

---

## 第二个采集面 · TikTok 对标语料（月度，**不是热点**）

TikTok **没有**免费、合规、实时的视频级 API（2026-10-23 逐条实测，六条路线全部证伪，
台账见 SOURCES.md）。能用的只有一份**免费公开的元数据语料**：
Hugging Face `datasocial/tiktok-5.6B-videos`（5.6B 条公开视频，148 个月度分区，
最新月 191MB，支持 HTTP range read）。

**它为什么单独一个面，而不是一个采集端点：**

| | 日常热点快照（`collect.py`） | TikTok 对标语料（`tiktok_bench.py`） |
|---|---|---|
| 更新 | 每小时/每天 | **月更** |
| 时效 | 实时 | **滞后约 20 天**（实测最新分区止于 2026-10-03） |
| 用途 | 算趋势（增速/爬升/跨平台） | 算对标（别人怎么写、多少播放量） |
| 落盘 | `snapshots/` + `contracts/` | `corpora/tiktok/`，**不进快照** |

> ⚠️ **不要把它接进快照流水线。** 月更 + 滞后的数据放进每日快照，会让
> `topic-scout` 把三周前的话题当成"正在火"——那是把过期数据伪装成趋势信号。
> 它只做对标，**永远不参与五信号打分**。

```bash
S=".agents/skills/hot-collect/scripts"

python "$S/tiktok_bench.py" sync --months 1        # 拉最新月度分区（191MB）
python "$S/tiktok_bench.py" stats                   # 语料体检：规模/覆盖时间/AI 两条轴
python "$S/tiktok_bench.py" search "vibe cod"       # ★ 主力：按关键词做对标查询
python "$S/tiktok_bench.py" hooks --query "claude code"  # 头部内容的开头写法 + 屏幕文字
python "$S/tiktok_bench.py" tags --query "chatgpt"       # 这个题在用什么标签
python "$S/tiktok_bench.py" top --topic-only --limit 20  # AI 话题播放量榜（严格口径）
```

**搜索会同时匹配 caption + 话题标签 + 屏幕文字**——实测一条 82.8 万播放的视频
caption 是 "Así se hace chat"（完全没提 AI），屏幕文字才是
"Cuando intentas engañar a ChatGPT"。只搜 caption 会漏掉关键对标。

**两条轴必须分开**（实测 2026-10 分区，2.5 天）：`is_ai_generated=1` 有 **84,804** 条
（用 AI 做的特效/短剧），**主题是 AI** 只有 **2,434** 条——差 35 倍。
TikTok 上「AI」流量的大头是「用 AI 做内容」，不是「讲 AI 工具」。

### ⚠️ 许可：这是 NC 数据，发布物里不许出现原文

数据集卡片原文（2026-10-23 实测抓取）：

> `license: cc-by-nc-4.0` … **"free for research and personal use. Commercial use,
> creator profiles and daily updates: datasocial.ai."**

**发布方把「商业使用」切走了**。本号是要变现的，所以按他们的定义就是 commercial use。
硬规则：

| 允许 | 禁止 |
|---|---|
| 读语料形成**自己的判断**，发布**自己的话** | ❌ 把 caption / 屏幕文字**原文**搬进发布的视频 |
| 用**聚合统计**（播放量分布、标签频次、结构模式） | ❌ 再分发数据集或它的任何子集 |
| 语料只留本地，不进 Git、不进快照 | ❌ 把语料做成生产采集链路 |

**用机制守住规则**——定稿前跑原文泄漏闸：

```bash
python "$S/tiktok_bench.py" check 你的稿子.md     # exit 0 = 干净, 1 = 有原文重合
```

它用「草稿词全语料召回 → 候选行精确片段比对」两段式查（覆盖 `search` 能返回的**任何**一行，
不是只查 AI 主题子集）。实测 3/3 用例符合预期：抄 caption → FAIL、抄屏幕文字 → FAIL、自己写 → PASS。

### 「TikTok 现在什么在火」走官方源

**TikTok 官方 Creative Center 的 hashtag 趋势榜在浏览器里免登录可读**：
`ads.tiktok.com/creative/creativeCenter/trends/hashtag?region=US&period=7`
给出 hashtag + posts + views + 趋势曲线 + 行业分类 + 地区 + 周期，DOM 可完整抽成文本。

| 项 | 实测 |
|---|---|
| 官方 API | ❌ `creative_radar_api` 即使在浏览器会话里也返 `{"code":40101,"msg":"no permission"}` → 数据是服务端渲染的，**没有可直连接口** |
| 免登录可见量 | 只有 **top 3**（「View more」跳 TikTok for Business 登录） |
| 能不能进 cron | ❌ 只能**按需用浏览器读**，不是脚本管线 |

→ **热点问题走这里**（许可干净），我随时可以按地区/周期/行业给你出表；
**对标语料问题走 NC 语料**（官方没有视频级公开数据），并用上面的闸守住。

过滤规则踩过的 5 个坑见 [references/tiktok_filter.md](references/tiktok_filter.md)。

## 输出格式

快照是 `records` 数组，每条统一形状：

```json
{"platform":"douyin","kind":"keyword","rank":1,"keyword":"...","title":null,
 "heat":1234567,"url":"...","category":null,"stat":{},"published":null,"extra":{}}
```

`kind=keyword` 是热词，`kind=video` 是作品（带 `stat.view/like/coin/favorite/comment`）。

## 维护纪律（这个 skill 的主要工作量在维护，不在写代码）

1. **端点级失败必须显式。** 一个源可能整体 probe 通过、但内部某个端点被限流。快照里 `sources.<name>.endpoints` 逐端点记 `ok/error`，采集时也会打印 `[degraded]`。**绝不静默降级。**
2. **契约指纹按端点算，不按源算。** 同一源的不同端点 schema 本来就不同，按源算会因为某个端点失败而误报。指纹变了会打印 `[contract CHANGED]`，需要人工核对上游是否改了字段。
3. **指纹取「所有条目的 key 并集」，不能只取第一条。** 只取 `items[0]` 在会轮换的列表上不稳定：B 站 `popular` 的 20 条里 `attribute_v3` 只出现在 19 条上，哪一条排第一就决定了指纹里有没有它 → **每次运行来回翻转、假 CHANGED**。并集只在上游真的增删字段时才变。
4. **端点失败不许覆盖指纹基线。** 抓空了就把契约写成空，等于毁掉基线，下次健康运行会报一个**假的 CHANGED**（真的变更反而被淹没）。失败时打印 `[contract skip]` 并保留原基线。
5. **同一源里的独立层不能互相否决。** YouTube 的 RSS 和 Data API 是两层，RSS 抖掉不能把带播放量的那层一起带走 —— 源级 `ok` 取「任一端点成功」。
6. **快照库只增不删。** 原始快照留 12 个月，月度聚合永久保留 —— 趋势信号全靠它。
7. **429 要退避重试**（已内置 3 次指数退避）。B 站请求之间有节流。**YouTube RSS 是另一种抖法**（同一 URL 同 UA 三秒内混出 200/404/500），要按 HTTP 错误码重试而不是只按 429。
8. **换源只改 adapter + SOURCES.md**，判定逻辑不动。
9. **对标语料不得混进快照流水线。** `corpora/` 里的东西（月更、滞后）永远不进 `snapshots/`，不进 `contracts/`，不参与五信号打分。

## 合规边界

- 只读公开榜单与公开数据；不写评论、不点赞、不关注、不发消息。
- 不做登录态下的批量抓取。
- **不要引入"禁止商业使用"协议的库代码**（如 `bilibili-API-collect` 是 CC-BY-NC）：只读文档借鉴思路，代码不进本链路。
- B 站历史榜单 `series/one` 需 wbi 签名（实测 -352），**不接进生产链路**。
- 平台协议与免费额度每月复核一次，结论写回 SOURCES.md。

## 已知限制

- **抖音视频级数据拿不到**（官方开放平台字段极少且限频，第三方全付费）。抖音层只到"热词"，作品级靠 B 站。
- **TikTok 实时视频级数据也拿不到**（比抖音更严，六条路线实测见 SOURCES.md）。只能拿到**月更滞后的对标语料**，做对标不做热点。
- **TikTok 语料许可 CC BY-NC 4.0（禁商用）**，且原始采集方式逆向 TikTok 私有移动 API、违反其 ToS 3.4 → 只做本地私有分析，**不进生产采集链路、不再分发原数据**。账号要变现的话，这条边界要自己把关。
- YouTube 官方 trending RSS 已下线、trending 列表不在 SSR 数据里 → 用 Data API 的"近 7 天高播放新视频"替代，**它比 trending 更贴题**（要的是"刚起"，不是"最大"）。
- 公共 API 实例有每日额度，生产建议自部署 `vikiboss/60s`。

## 配套

- 下游：`topic-scout`（打分与选题卡）
- 再下游：本机 `video-deconstruct-analyzer` → `short-drama-screenwriter` / `narration-writer` → `visual-design-creator`
- **TikTok 对标语料** → 给选题卡补「内容形式 + 开头 3 秒钩子」的证据（`tiktok_bench.py hooks`）
