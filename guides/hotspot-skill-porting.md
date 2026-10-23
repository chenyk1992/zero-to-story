# 热点链路迁移指南（hot-collect + topic-scout）

> 适用：把这两个 skill 搬到**另一台机器**、**另一个项目**、或另一个账号的热点选题工作流。
> 前提：读过 `guides/ai-system-prompt.md` 与两个 skill 各自的 `SKILL.md`。
> 最后实测：2026-10-23（Windows / Python 3.12）

---

## 0. 迁移前要知道的四件事

1. **零硬编码路径**。所有路径靠 `--data-root` > 环境变量 `LFO_HOTSPOT_DATA` > `Path.home()` 解析。
   复制目录就能跑，不需要改代码。
2. **零第三方依赖（主链路）**。`hot-collect` 的每日快照与 `topic-scout` 的打分只用标准库。
   `pyarrow` / `pandas` **只有 TikTok 对标语料面需要**，不装也能跑主链路。
3. **数据在用户目录，不在仓库里**。快照、语料、契约、回归集全部落在
   `<用户数据>/zero-to-story/hotspot/`，换项目不污染工作区，Git 零污染。
4. **每个脚本的退出码是契约**：`0` 成功 / `1` 判定不合格 / `2` 环境未就绪。定时任务与 CI 可以直接依赖它。

---

## 1. 搬文件

```
<新项目>/.agents/skills/
├── hot-collect/
│   ├── SKILL.md  meta.yaml  SOURCES.md
│   ├── agents/openai.yaml
│   ├── references/tiktok_filter.md
│   └── scripts/
│       ├── _common.py        # 共用：版本、数据根、退出码、依赖、用户级 env 补齐
│       ├── adapters.py       # 三个源的 adapter
│       ├── collect.py        # 采集面
│       ├── daily.py          # ★ 完整链路：采集 → 打分 → 今日建议
│       ├── tiktok_bench.py   # TikTok 对标语料面
│       ├── tiktok_filters.py # 严格过滤器
│       ├── doctor.py         # 环境自检
│       └── selftest.py       # 离线自检
└── topic-scout/
    ├── SKILL.md  meta.yaml
    ├── agents/openai.yaml
    ├── references/{signals.md, card_template.md}
    └── scripts/
        ├── _common.py  scout.py  regress.py  doctor.py  selftest.py
```

**两个 skill 必须同级放置**：`topic-scout` 会在同级目录找 `hot-collect`（为了 S5 供给缺口）。
找不到不会崩，只是 S5 降级为 0。

---

## 2. 装依赖（按需）

```bash
# 主链路：不需要装任何东西
python --version          # 需要 ≥ 3.10

# 只有要用 TikTok 对标语料面才装
python -m pip install pyarrow pandas
```

---

## 3. 配环境变量

| 变量 | 必需 | 作用 | 没有会怎样 |
|---|---|---|---|
| `LFO_HOTSPOT_DATA` | 否 | 指定数据根目录 | 用默认 `<用户数据>/zero-to-story/hotspot` |
| `YOUTUBE_API_KEY` | 否 | YouTube「近 7 天高播放新视频」层 | 该端点跳过并**明确报告**，不静默 |
| `YOUTUBE_API_QUERY` | 否 | 这一层关注的赛道词 | 用默认 `AI\|LLM\|agent\|GPT\|Claude` |

```powershell
# Windows（用户级，永久）
[Environment]::SetEnvironmentVariable('YOUTUBE_API_KEY','<key>','User')
[Environment]::SetEnvironmentVariable('LFO_HOTSPOT_DATA','D:\data\hotspot','User')
```

```bash
# macOS / Linux
export YOUTUBE_API_KEY='<key>'
export LFO_HOTSPOT_DATA="$HOME/data/hotspot"
```

> ⚠️ **新开的进程才会继承**。已经开着的终端 / IDE / 定时任务进程要重启才会拿到新值。
> 这是「明明配了 key 却说没配置」最常见的原因。

**YouTube key 怎么来**：Google Cloud 建项目 → 启用 **YouTube Data API v3** → 建 API key
（**API 限制只勾这一个 API**）→ 写进用户级环境变量。免费额度 10000 units/天，
本链路每次采集消耗约 101 units（search.list 100 + videos.list 1）。

---

## 4. 验装（两条命令，分钟内出结果）

```bash
S="<新项目>/.agents/skills/hot-collect/scripts"
T="<新项目>/.agents/skills/topic-scout/scripts"

python "$S/selftest.py"    # 离线自检：不联网、不碰真实数据
python "$S/doctor.py"      # 环境体检：依赖/凭据/数据根/快照/语料/兄弟 skill/源连通性
python "$T/selftest.py"
python "$T/doctor.py"
```

- `selftest.py` 全绿 → **代码在这台机器上是好的**（不需要网络、key、语料）
- `doctor.py` 无阻塞项 → **环境是就绪的**（它会直接给出每个不通过项的修复命令）

---

## 5. 第一次跑真实数据

```bash
python "$S/daily.py"                      # ★ 一条命令跑完整条链路
python "$S/collect.py" --probe             # 或者分步来
python "$S/collect.py" --collect
python "$T/scout.py" score --top 10 --include "AI,大模型,智能,Agent,编程,GPT,Claude"
```

**`daily.py` = 采集 → 打分 → 今日选题建议**，一条命令。它会自动把用户级环境变量补进
当前进程（新开的终端不必重启就能用 key），并在末尾标出「本轮哪些信号是空的」。

**至少要两份快照** S1/S3 才有意义（趋势信号靠差分）。建议加每日定时任务：

```powershell
# Windows 任务计划
python "$S/daily.py" --include "AI,大模型,智能,Agent,编程,GPT,Claude"   # 每天 10:00 前后
```

---

## 6. 换赛道 / 换平台

| 要改什么 | 改哪里 | 注意 |
|---|---|---|
| 赛道词 | `scout.py score --include "..."` + `YOUTUBE_API_QUERY` | 两处要一起改，否则 YouTube 层和打分层的赛道不一致 |
| 平台 | `scout.py score --platforms "..."` | 平台名 = 快照记录里的 `platform` 字段 |
| 数据根目录 | `LFO_HOTSPOT_DATA` 或 `--data-root` | 换目录 = 换一套全新的快照库，趋势信号从头开始 |
| 判定口径 | `scout.py` + `references/signals.md` | **必须**走回归门禁，见下 |

---

## 7. 改判定口径的流程（不可跳过）

```bash
R="<新项目>/.agents/skills/topic-scout/scripts/regress.py"

python "$R" --freeze                                    # 冻结当前快照库（满 30 份）
python "$R" --make-baseline --profile v2 --include "$INC" # 生成基线
# ...改代码...
python "$R" --compare --profile v3 --baseline <root>/regression/baseline-v2.json --include "$INC"
# exit != 0 → 不允许合并
```

配套要求：
- 改 `scoring_version`
- 改 `references/signals.md`（**它是口径的唯一权威**）
- 每个改动要有独立回退开关（如 `--candidate-sources`）
- ⚠️ **S5 不在自动回归覆盖内**（要打 B 站实时接口，不可复现）→ S5 的变更只能人工对比

---

## 8. 已知的环境相关坑

| 现象 | 原因 | 处理 |
|---|---|---|
| 配了 key 但仍报「未配置」 | 进程没重启 | 重开终端 / 重启定时任务进程 |
| `ModuleNotFoundError: pyarrow` | 可选依赖没装 | `pip install pyarrow pandas`，或不用对标面 |
| 快照 0 份 | 没跑过 collect | `collect.py --collect` |
| `S4 跨平台` 恒为 0 | 跨语言标题不会字面重合 | 已知限制，见 `references/signals.md` 的「已知缺口」 |
| 契约一直报 CHANGED | 指纹取样点漂移 | 已修（取全集并集）；若仍出现，先连采 4 次比 key 集合 |
| 60s 报 429 | 公共实例限频 | 正常退避；频繁出现就自部署 `vikiboss/60s` |

---

## 9. 迁移验收清单

- [ ] `selftest.py` 两个 skill 都全绿
- [ ] `doctor.py` 两个 skill 都无阻塞项
- [ ] `collect.py --probe` 三个源都通
- [ ] 跑出第一份快照，且 `snapshots/` 不在项目目录里
- [ ] `scout.py score` 能出候选（至少 2 份快照后 S1 才有值）
- [ ] 定时任务能独立跑（不依赖交互式登录态）
- [ ] Git 里没有快照、语料、回归集、任何 key

---

*本文件随 Git 分发，是长期生产规则的一部分。*
