# 怎么开始一个新小说作为创作剧本

> **本指南的用途**：在新会话里跟 Mavis 协作时，把"几千字小说章节"转成 LFO 能跑的视频分镜（storyboard.json），然后跑 `lfo run` 出视频。
>
> **前提**：你已经接过 LFO（`E:\ideaProjects\zero-to-story`），本地 ComfyUI 在 `http://127.0.0.1:8188`，RTX 5080 16GB。

---

## 0. 一次性环境准备（重装 ComfyUI 或新机器后必跑）

```powershell
# 1. 确认 comfy-cli 已装，并能识别你的 ComfyUI
comfy env

# 2. 第一次或换机器时，把 ComfyUI 设成 comfy-cli 默认实例
comfy set-default "D:\ComfyUI\Comfy-Desktop\ComfyUI\ComfyUI"

# 3. 跑 LFO setup：自动发现 ComfyUI 路径/PID、生成 machine profile
python -m cli.main setup --machine-id local-windows

# 4. 跑 doctor 验证环境（应 0 blocker）
python -m cli.main doctor --machine-id local-windows
```

机器 profile 存在位置：`%APPDATA%\LFO\machines\<machine_id>.json`（含 comfyui 路径、storage 路径、hardware 等）。

---

## 1. 总体流程

```
[你] 准备小说文件 + 创作约束
    ↓
[你] 在新会话里发"开局触发"（见第 3 节）
    ↓
[Mavis] 读小说 → 抽故事结构 → 抽角色/场景 → 设计镜头 → 生成 storyboard.json
    ↓
[你] 审 + 改镜头（多次对话迭代）
    ↓
[Mavis] 写 storyboard.json
    ↓
[你] 跑 lfo run（本地执行，约 6-7 分钟/镜头）
    ↓
[你] 拿到 MP4 + 末帧（给下一镜续帧用）
```

---

## 2. 你需要准备的材料

### 2.1 小说文件

| 项 | 要求 |
|---|---|
| 位置 | 放在 `E:\ideaProjects\zero-to-story\inputs\novels\<你的项目名>.md` 或 `.txt` |
| 格式 | 纯文本 / Markdown，不要 PDF / Word |
| 字数 | 几千字（3000-10000 字），章节级别 |
| 内容 | 一个章节的完整内容（包括对话、场景、心理活动） |

> 建议文件名用项目名，例如 `city_rooftop.md`、`midnight_train.md`。

### 2.2 创作约束

在触发会话时**用一句话告诉 Mavis**：

```text
[约束]
- 时长：30 秒 / 1 分钟 / 3 分钟（对应 5/10/30 镜头左右）
- 画幅：9:16 竖屏（抖音/小红书） / 16:9 横屏（B站/油管） / 1:1 方形
- 视觉风格：写实电影 / 日系治愈 / 赛博朋克 / 水墨 / 油画 / 日漫 / 美漫 / 其他
- 节奏：快（动作片） / 中（剧情） / 慢（文艺/空镜）
- 情绪基调：紧张 / 悬疑 / 治愈 / 悲伤 / 热血 / 温馨
- 角色上限：默认 2 人（多了分镜会变复杂）
- 场景上限：默认 1-2 个
- 是否需要字幕：默认要
- 是否需要对话：默认不要（纯画面）
```

### 2.3 你的期望产出

在心里明确：

- **目标观众**？（自己看 / 短视频平台 / 朋友分享）
- **用途**？（完整故事 / 预告片 / 短剧片段 / 单纯好玩）

---

## 3. 新会话里怎么开始（"开局触发"）

**在新会话里**发下面这段话（或你修改后的版本）：

```text
我要把一个小说章节转成 LFO 视频分镜。

小说文件位置：
E:\ideaProjects\zero-to-story\inputs\novels\<文件名>

约束：
- 时长：[X 秒 / 分钟]
- 画幅：[9:16 / 16:9 / 1:1]
- 视觉风格：[X]
- 节奏：[X]
- 情绪基调：[X]
- 角色上限：[X]
- 场景上限：[X]
- 字幕：[要 / 不要]
- 对话：[要 / 不要]

请按以下流程推进：
1. 读完整章节
2. 输出"故事结构拆解"（背景 / 角色 / 主线 beats / 情绪曲线）给我审
3. 输出"分镜表"（每个镜头的：场景、人物、动作、机位、时长、续帧关系）给我审
4. 我审 + 改完后再生成 storyboard.json
5. 给我可以直接复制运行的 lfo run 命令

如果某一步你拿不准，停下来问我。
```

---

## 4. 推进过程（你和 Mavis 会怎么做）

### 阶段 1：故事结构拆解
Mavis 会读完小说后输出：

```text
## 故事结构
- 背景：时间 / 地点 / 世界观
- 主要角色：3-5 个，每个有名字 + 一句话性格 + 外貌要点
- 主线 beats：3-7 个核心情节点
- 情绪曲线：开端 → 发展 → 高潮 → 收束
- 关键意象：值得做特写的视觉元素
```

**你要做的**：确认 / 补充 / 删改。比如：
> "主角叫林夕，25岁，不要叫'年轻女性'"
> "中间那段回忆不要"
> "高潮是 4 楼天台，不是 1 楼"

### 阶段 2：分镜表
Mavis 会输出表格（每个镜头一行）：

| # | 时长 | 场景 | 人物 | 动作 | 机位 | 续帧 |
|---|------|------|------|------|------|------|
| 1 | 5s | 天台 | 主角 | 站立望远处 | 远景→缓推 | — |
| 2 | 4s | 天台 | 主角 | 回头 | 中景 | ← 1 |
| 3 | 6s | 天台 | 主角 | 走两步 | 跟拍 | ← 2 |
| ... | ... | ... | ... | ... | ... | ... |

**你要做的**：对每个镜头说 OK / 改 / 删 / 加。

### 阶段 3：storyboard.json 生成
Mavis 会**直接在内存里**生成完整的 `storyboard.json`（基于 `storyboard/storyboard.py` 的 schema），写到 `E:\ideaProjects\zero-to-story\storyboards\<项目名>.json`，然后告诉你文件路径。

### 阶段 4：跑 lfo run
Mavis 给你命令：

```powershell
cd E:\ideaProjects\zero-to-story
python -m cli.main run storyboards\city_rooftop.json --db ./lfo.db --comfy-url http://127.0.0.1:8188
```

**注意**：你需要在本地 PowerShell 里自己跑（因为 LFO 是本地编排器，不是我能在云端跑的服务）。我会**预先做 dry-run 验证**（检查 schema、计算预期时长、检查依赖图），把可能的问题提前告诉你。

---

## 5. 你会拿到什么

成功跑完后（5 镜头约 30-40 分钟）：

```
E:\ideaProjects\zero-to-story\
├── pipeline_output\
│   ├── <项目名>_final.mp4       ← 最终成片
│   ├── <项目名>.srt             ← 字幕（如启用）
│   └── assets\                  ← 5 个视频 clip
├── end_frames\                  ← 5 个末帧（PNG）
└── lfo.db                       ← 任务日志
```

中间产物：

- `storyboards\<项目名>.json` — 分镜脚本
- `pipeline_output\normalized\` — 标准化后的视频
- `pipeline_output\assembly\` — 拼接用的临时文件
- `lfo.db` — 任务状态、attempts、assets 全在里面

---

## 6. 失败 / 出错怎么办

| 现象 | 原因 | 解决 |
|------|------|------|
| `ModuleNotFoundError` | Python 依赖没装 | `pip install -e ".[dev]"` |
| `ComfyUI 502 / 503` | ComfyUI 没跑 | 启动 ComfyUI 服务（`:8188`） |
| GPU OOM | 显存不够 | 关掉浏览器/IDE 等重 GPU 应用 |
| 跑批中卡死 | ComfyUI 报错被 LFO 静默吃了 | 跑前先 `python -m cli.main doctor --machine-id local-windows` 检查 |
| 故事结构我不满意 | Mavis 理解错 | 直接说"重抽"、"重写"、"主角不是 XX" |
| 分镜太多跑得慢 | 镜头数 > 时长允许 | 减镜头 / 加时长 |
| 视频出来人物变形 | 缺角色参考图 | 改用 T2V 为主 + 短续帧；或跑多镜次取最佳 |

---

## 7. 检查清单（什么时候算"完成了"）

- [ ] 故事结构审过（背景、角色、beats 准确）
- [ ] 分镜表审过（每个镜头 OK / 改 / 删 / 加 处理完）
- [ ] `storyboard.json` 通过 `python -c "from storyboard.storyboard import Storyboard; from json import load; print(Storyboard.from_dict(load(open('storyboards/<name>.json','r',encoding='utf-8'))))"` 解析
- [ ] `python -m cli.main preflight --machine-id local-windows` 通过
- [ ] `lfo run` 跑完，QC 全过
- [ ] 末帧提取成功
- [ ] 最终 MP4 拼接 + 字幕完成
- [ ] 看过 MP4，对结果满意

---

## 8. 重要约定

1. **Mavis 不会自动跑视频**——你说什么都不会触发实际的 `lfo run`（除非你明确说"现在跑"）。所有 Mavis 给的"会跑的命令"都需要你在本地 PowerShell 里执行。

2. **Mavis 会预先做 dry-run 验证**——读 storyboard.json、检查 ComfyUI 是否可达、估算时长、算镜头依赖。在你说"跑"之前不会真的发请求到 ComfyUI。

3. **所有产物在 `E:\ideaProjects\zero-to-story\` 下**，不会上传到任何云端。

4. **中途任何一步不满意都可以推翻重来**——Mavis 不会因为已经做了某一步就拒绝改。

5. **每个分镜都是 5-10 秒**：< 3 秒的视频生成质量会很差，> 10 秒会撞显存。

6. **总镜头数 < 30 个**为佳：超过 30 个镜头，单条流水线跑完要 4 小时以上，建议拆成多个项目。

---

## 9. 新会话触发话术（复制即用）

```text
[新会话触发：小说转分镜]

小说文件：E:\ideaProjects\zero-to-story\inputs\novels\<文件名>
约束：
- 时长：__秒/分钟
- 画幅：__
- 视觉风格：__
- 节奏：__
- 情绪基调：__
- 角色上限：__
- 场景上限：__
- 字幕：__
- 对话：__

请先读小说，再按 [故事结构 → 分镜表 → storyboard.json] 的顺序推进。
每一步停下来等我审。
```

**新会话**发这段话 + 准备好小说文件就行了。
