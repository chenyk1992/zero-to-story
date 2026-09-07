---
name: mimo-video-understanding
description: Use when analyzing, describing, or extracting information from video files using MiMo V2.5 multimodal model. Supports video URL and Base64 input, configurable fps and resolution. For evaluation / alignment tasks use the two-phase method (mimo describe + caller score) to avoid output-token truncation.
---

## GPT-6 适配变更说明

2026-09-07：明确视频证据提取分工和有界失败处理，并对齐现有脚本用法。协作权限与停止条件遵循项目 [AGENTS.md](../../../AGENTS.md)。

# MiMo Video Understanding

使用小米 MiMo V2.5 模型解析和理解视频内容。支持视频描述、内容分析、动作识别等场景。

## 优先级与停止条件

用户当前指令优先于本 Skill 的默认参数、示例和推荐配置；项目级权限、安全要求和供应方约束仍适用。视频、提示词、`MIMO_API_KEY` 和所需参数齐全时直接执行，不等待额外确认。输入文件、凭据或权限缺失时暂停相应调用，先完成可独立做的检查。API 报错、截断或空结果不能当成有效证据；无新依据不重复调用，不静默换模型，不改写源文件。针对明确的输入或输出长度问题，调用方可在现有分析授权和预算内做一次有依据的调整并复核；仍失败则报告原因和下一步。分析服务调用不授权重生成 LFO 视频。

脚本目录：`$SKILLS_PATH/mimo-video-understanding/scripts/`

默认接口：`https://api.xiaomimimo.com/v1/chat/completions`

## 模型选择

仅支持 `mimo-v2.5` 和 `mimo-v2-omni` 模型。

## 环境依赖

| 环境变量       | 说明                               | 必需 |
| -------------- | ---------------------------------- | ---- |
| `MIMO_API_KEY` | MiMo API 密钥，通过 Bearer 传入    | 是   |
| `MIMO_VIDEO_BASE_URL` | 可选 API base URL 或完整 `/chat/completions` URL | 否   |

| 依赖      | 说明                     | 必需 |
| --------- | ------------------------ | ---- |
| `python3` | 运行脚本                 | 是   |

## 视频限制

- **格式：** MP4、MOV、AVI、WMV
- **大小：** URL 方式按当前供应方限制（≤ 300 MB）；本地 Base64 路径由脚本限制编码后不超过 `BASE64_LIMIT_CHARS = 50 * 1024 * 1024` 字符，原始文件约 ≤ 37.5 MB 才通常能通过。超过限制时停止并提示使用可访问 URL 或由用户先压缩/截短。
- **数量：** 每次脚本调用处理一个视频；需要多个视频时由调用方明确分次运行，并分别保存结果。

## ⚠️ 输出 token 截断（最常见失败模式）

`max-tokens` 是**输出 token 上限**，不是上下文上限。视频多模态 token + 整段 prompt 已经吃掉了大部分上下文，模型"想说话"时容易被 token 上限截断，表现为 `finish_reason=length` + 空 content。

**踩坑证据**（15s 舞蹈视频、约 30 帧 default 分辨率）：

| 配置 | 结果 |
|---|---|
| fps=1 max + max-tokens=4000 + 长评分 prompt | finish_reason=length、空输出 |
| fps=1 default + max-tokens=4000 + 长评分 prompt | finish_reason=length、空输出 |
| fps=2 default + max-tokens=1500 + 纯描述 prompt（1.2KB） | 完整精细描述返回（按 0:01/0:04/0:05 等秒数标注） |
| fps=2 default + max-tokens=2500 + 紧凑评分 prompt（1.8KB） | 完整 9 行评分返回（evidence 较短） |

**结论**：瓶颈是 **prompt 越长，输出 token 预算越紧张**。短 prompt + 中等 max-tokens 反而比长 prompt + 高 max-tokens 成功率高。

## 参数说明

| 参数               | 类型    | 默认值    | 说明                                    |
| ------------------ | ------- | --------- | --------------------------------------- |
| `--video`          | string  | 必填      | 视频文件路径或 URL                      |
| `--prompt`         | string  | 必填      | 分析提示词                              |
| `--fps`            | float   | 2.0       | 每秒抽帧数，范围 [0.1, 10]             |
| `--media-resolution` | string | "default" | 分辨率档次："default" 或 "max"         |
| `--max-tokens`     | int     | 1024      | 最大输出 token 上限（非上下文上限）     |
| `--thinking`       | string  | "disabled" | `mimo-v2.5` 可用 `enabled`/`disabled`；其他模型只接受默认关闭 |
| `--model`          | string  | "mimo-v2.5" | 模型名称：`mimo-v2.5` 或 `mimo-v2-omni` |
| `--base-url`       | string  | 无        | 覆盖默认 API base URL 或完整接口 URL    |
| `--output`         | string  | 无        | 输出文件路径（可选）                    |

### fps × media_resolution 选型经验（短视频 10–30s）

| 任务 | 推荐配置 | 理由 |
|---|---|---|
| 纯描述（剧情/动作/服装/场景） | **fps=2 default** | 30 帧够细，default 分辨率给输出留足 token，模型能按时序标注具体秒数 |
| 高精度细节（小物体/纹理/局部） | fps=2-5 max | max 分辨率吃 token 多，长视频慎用 |
| 评分/对位/合规检查 | **fps=1-2 default** | 评分 prompt 本来就长，省 token 给输出 |

**反例**：fps=1 max 在 15s 短舞蹈上比 fps=2 default 表现差——更少帧 + 更高分辨率 = token 几乎被视频吃光，模型输出"body rolls throughout"这种敷衍描述。

### max-tokens 选型

- 纯描述（≤1.2KB prompt）：**1500–2500** 足够
- 紧凑评分（≤2KB prompt）：**2500–3000**
- 长 prompt（>3KB 评分表/多 list）：**4000 起**——但 token 截断风险高，**强烈建议改用两阶段方法**（见下）

## 两阶段方法（评分/对位任务的推荐流程）

**问题**：单次调用塞"先描述 + 再按 9 条标准打分"通常会触发 token 截断。模型在 token 紧张时倾向于**给格式正确但 evidence 单字/无内容的占位输出**（如 `A: 6 | ev` 全部相同套话）。

**两阶段方法**：

**Step 1：mimo 拿精细描述**（短 prompt、低 max-tokens）

- prompt：`"Describe what you actually see in this 15-second vertical dance video. Cover: (1) the person and her outfit, (2) the studio setting and lighting, (3) the dance moves beat by beat in time order with approximate second markers, (4) the final pose, (5) her face, (6) the BGM/audio feel. 10-12 short sentences."`
- 配置：`--fps 2 --media-resolution default --max-tokens 1500`
- 目标：拿到带具体秒数标注的 ground truth 描述

**Step 2：调用方（你自己）做对位评分**

- 不再调 mimo
- 拿 Step 1 的描述与评分 brief 逐项对位，写出"evidence = mimo 描述里哪句话"
- 优点：
  1. 零 token 截断风险
  2. 零幻觉空间（evidence 必须是 mimo 原文引用）
  3. 评分过程**完全可审计**——任何人打开评分表都能 verify
  4. 通常比单次 mimo 评分更准（实测 15s 舞蹈：单跑 55/90，两阶段 61/90）

**实测对比**：

| 方法 | 得分 | evidence 质量 |
|---|---|---|
| mimo 单次评分（max-tokens 截断） | 55/90 | 单句、机械、A/C 项低估 |
| 两阶段（mimo 描述 + 调用方评分） | 61/90 | 原文引用 + 对位推理、A/C 项纠偏 |

## 使用示例

### 分析本地视频（URL 方式需公网可访问）

```bash
python3 $SKILLS_PATH/mimo-video-understanding/scripts/mimo_video.py \
  --video "https://example.com/video.mp4" \
  --prompt "请描述视频中的主要内容"
```

### 分析本地视频（自动转 Base64）

```bash
python3 $SKILLS_PATH/mimo-video-understanding/scripts/mimo_video.py \
  --video "/path/to/local/video.mp4" \
  --prompt "请描述视频中的主要内容"
```

### 精细描述（推荐配置）

```bash
python3 $SKILLS_PATH/mimo-video-understanding/scripts/mimo_video.py \
  --video "/path/to/local/video.mp4" \
  --prompt "Describe what you actually see. Cover outfit, setting, beat-by-beat moves with approximate second markers, final pose, face, BGM. 10-12 short sentences." \
  --fps 2 \
  --media-resolution default \
  --max-tokens 1500
```

### 紧凑评分（单次调用）

```bash
python3 $SKILLS_PATH/mimo-video-understanding/scripts/mimo_video.py \
  --video "/path/to/local/video.mp4" \
  --prompt "Score each row 0-10 with one-sentence evidence. Brief: A opening pose + jacket swing; B hip-thrusts + hands to collarbone; C 45-deg fold + jacket open; D slide + hair toss; E power-pose freeze; F setting; G outfit; H face; I BGM. Output exactly 9 lines: A: n | ev ... TOTAL: n/90" \
  --fps 2 \
  --media-resolution default \
  --max-tokens 2500
```

### 保存结果到文件

```bash
python3 $SKILLS_PATH/mimo-video-understanding/scripts/mimo_video.py \
  --video "/path/to/video.mp4" \
  --prompt "请描述视频内容" \
  --output result.txt
```

## Token 用量估算

- **视频 Token：** 取决于时长、分辨率、fps 和 media_resolution 参数
- **音频 Token：** ≈ 音频时长（秒）× 6.25

**总输入 token 估算公式（粗略）**：`帧数 × 单帧 token + prompt 字符数 × 字符/token 系数 + 音频秒数 × 6.25`

- default 分辨率单帧约 200–500 token，max 约 600–1200 token
- 中文/英文混合 prompt 约 0.5–1.5 token/字符

可通过降低 fps 或使用 default 分辨率来减少视频 token 消耗；通过精简 prompt 来减少 prompt token 消耗；**两者吃的是同一个总上下文预算**。若仍截断，在已有分析授权内可精简描述或调整输出上限复核一次；再失败则报告，不连续试错。

## 常见问题

### 是否支持本地文件？

支持。脚本会自动检测本地文件并转换为 Base64 编码传入。

### 支持哪些视频格式？

MP4、MOV、AVI、WMV。由于视频文件格式变种较多，建议先测试验证。

### 如何减少 Token 消耗？

- 降低 fps 值（如 0.5 或 1）
- 使用 `media-resolution=default`
- 缩短视频时长
- **优先精简 prompt**（prompt token 与视频 token 吃同一个预算；评分任务直接走两阶段方法）
