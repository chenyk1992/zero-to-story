---
name: mimo-video-understanding
description: Use when analyzing, describing, or extracting information from video files using MiMo V2.5 multimodal model. Supports video URL and Base64 input, configurable fps and resolution.
---

# MiMo Video Understanding

使用小米 MiMo V2.5 模型解析和理解视频内容。支持视频描述、内容分析、动作识别等场景。

脚本目录：`$SKILLS_PATH/mimo-video-understanding/scripts/`

默认接口：`https://api.xiaomimimo.com/v1/chat/completions`

## 模型选择

仅支持 `mimo-v2.5` 和 `mimo-v2-omni` 模型。

## 环境依赖

| 环境变量       | 说明                               | 必需 |
| -------------- | ---------------------------------- | ---- |
| `MIMO_API_KEY` | MiMo API 密钥，通过 Bearer 传入    | 是   |
| `MIMO_VIDEO_BASE_URL` | 可选 API base URL 或完整 `/chat/completions` URL | 否 |

| 依赖      | 说明                     | 必需 |
| --------- | ------------------------ | ---- |
| `python3` | 运行脚本                 | 是   |

## 视频限制

- **格式：** MP4、MOV、AVI、WMV
- **大小：** URL 方式 ≤ 300 MB，Base64 方式 ≤ 50 MB
- **数量：** 支持多视频，受上下文长度限制

## 参数说明

| 参数               | 类型    | 默认值    | 说明                                    |
| ------------------ | ------- | --------- | --------------------------------------- |
| `--video`          | string  | 必填      | 视频文件路径或 URL                      |
| `--prompt`         | string  | 必填      | 分析提示词                              |
| `--fps`            | float   | 2.0       | 每秒抽帧数，范围 [0.1, 10]             |
| `--media-resolution` | string | "default" | 分辨率档次："default" 或 "max"         |
| `--max-tokens`     | int     | 1024      | 最大输出 token 数                       |
| `--model`          | string  | "mimo-v2.5" | 模型名称：`mimo-v2.5` 或 `mimo-v2-omni` |
| `--base-url`       | string  | 无        | 覆盖默认 API base URL 或完整接口 URL    |
| `--output`         | string  | 无        | 输出文件路径（可选）                    |

### fps 参数

- 数值越高 → 抽帧越密集 → 动作/时序感知越精细 → Token 消耗越多
- 数值越低 → 抽帧越稀疏 → 处理速度越快 → Token 消耗越少

### media_resolution 参数

- `default`：平衡识别效果与处理效率
- `max`：最高分辨率，提升小物体、细节纹理识别能力

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

### 高精度分析

```bash
python3 $SKILLS_PATH/mimo-video-understanding/scripts/mimo_video.py \
  --video "/path/to/video.mp4" \
  --prompt "请详细分析视频中人物的动作和表情" \
  --fps 5 \
  --media-resolution max
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

可通过降低 fps 或使用 default 分辨率来减少 Token 消耗。

## 常见问题

### 是否支持本地文件？

支持。脚本会自动检测本地文件并转换为 Base64 编码传入。

### 支持哪些视频格式？

MP4、MOV、AVI、WMV。由于视频文件格式变种较多，建议先测试验证。

### 如何减少 Token 消耗？

- 降低 fps 值（如 0.5 或 1）
- 使用 `media_resolution=default`
- 缩短视频时长
