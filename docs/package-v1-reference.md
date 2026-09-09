# Video Execution Package v1（单 Panel）

角色、Panel ready、实际末态/音频验收和授权复用遵守[项目共享生产规则](ai-system-prompt.md)；本文只定义 package CLI 的公共字段和边界。

`lfo.video-execution.v1` 是创作 Skill 与 LFO 之间的唯一公共边界。Skill 决定故事、镜头、视觉资产、H3 提示词和用户审批；LFO 只执行已确认的一个 Panel/Clip。

当前版本是 breaking redesign：新执行不兼容旧 `shots[]`、旧 Panel-only 入口、旧 lock/retry/recovery 语义，也不提供迁移层。

## 顶层字段

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `schema` | 是 | 必须为 `lfo.video-execution.v1`。 |
| `package_id` | 是 | 当前 Panel 执行包标识；不同 Panel 必须不同，zero-to-story 缺省使用 `<project_id>-<panel_id>`。 |
| `revision` | 是 | 正整数；执行内容变化后由创作侧生成新 revision。 |
| `project` | 是 | 至少包含稳定的 `project_id` 和展示标题。 |
| `assets` | 否 | 当前 Panel 实际需要的本地素材；缺省为空数组。 |
| `clips` | 是 | 生成包必须只有一个非 passthrough Clip；最终 assembly package 包含一个或多个 Clip，且必须全部为 `video.passthrough`。 |
| `output` | 否 | 当前 Panel 和最终组装的输出策略；缺省使用 Runtime 默认值。 |
| `approval` | 否 | 上游用户确认信息；执行时另以 package 完整文件字节 SHA-256（exact file SHA-256）作为锁。 |
| `timeline` | 否 | 单 Clip 的时间线元数据。 |
| `extensions` | 否 | 命名空间扩展；当前唯一会改变执行路径的内置扩展是可选 `upscale`。 |

LFO 在 `validate` 阶段拒绝空包和包含多个生成 Clip 的包。一个章节/成片的多个 Panel 由调用方按顺序分别准备和执行；只有全部 Panel 已 `ACCEPT` 后，才允许用一份含一个或多个 Clip、且全为 `video.passthrough` 的 package 做最终组装。

## AssetSpec

```json
{
  "asset_key": "character.hero",
  "media_type": "image",
  "source": {
    "uri": "assets/hero.png",
    "sha256": "optional-source-sha256"
  },
  "provenance": {
    "source_type": "external_skill",
    "producer": "zero-to-story",
    "operation": "image.generate"
  },
  "review": { "required": true }
}
```

`source.uri` 必须是相对 package 的本地路径。LFO 在执行前读取并校验素材，可将其导入 CAS；不得修改源文件。`asset_key` 只在当前 package 内使用，不是 LFO 内部 ID。`source.sha256` 可选；需要把素材内容本身纳入批准边界时应填写它，Runtime 会在导入时核对实际内容。

## ClipSpec

```json
{
  "clip_id": "P001",
  "sequence": 1,
  "duration_ms": 10000,
  "generation": {
    "operation": "video.image_to_video",
    "prompt": "已确认的 H3 最终提示词",
    "requirements": {
      "aspect_ratio": "9:16",
      "megapixels": 0.4,
      "sampler_profile": "vdn_turbo",
      "steps": 8,
      "fps": 24
    },
    "references": [
      {
        "reference_id": "first-frame",
        "asset_key": "character.hero",
        "semantic_usage": "continuity.start",
        "binding": {
          "placement": "first",
          "slot": "first_frame"
        }
      }
    ]
  },
  "audio": {},
  "subtitles": {},
  "dependencies": [],
  "source_context": {
    "creative_unit": "panel",
    "panel": "P001"
  }
}
```

`generation.prompt` 必须逐字来自已确认的 H3 输出；LFO 不补写、不改写、不生成提示词。operation 由创作侧先锁定，LFO 只校验 operation 与引用是否匹配，不静默换模式。上例中的 `video.image_to_video` 因此必须提供且只提供一个 `first_frame` 引用。

当前支持的 operation 由后端 Manifest 声明，常用值包括：

- `video.text_to_video`：无视觉首帧锁；
- `video.image_to_video`：使用一张真实 `first_frame`；
- `video.first_last_frame`：使用真实 `first_frame` 与 `last_frame`；
- `video.reference_to_video`：使用一个或多个明确 fixed typed slot 的普通参考；单张可变网格分镜板也可以作为一个引用；
- `video.virtual_presenter`：仅在对应 Manifest 存在且当前 Panel 明确需要时使用；
- `video.passthrough`：仅用于已接受视频的确定性组装输入。

Reference 的 `binding.slot` 必须与最终 H3 `<Picture N>`、`<Video N>`、`<Audio N>` 标签一致。R2V 使用 `placement: "fixed"` 和明确槽位；若已批准计划把整张分镜板列为模型引用，它作为一张图片只占一个槽位，板内格子不拆分。未列为模型引用的分镜板仍只是 planning 资产，且分镜板的存在不会自动选择 R2V。

### 采样模式与动态步数

所有创作调用方通过 `generation.requirements.sampler_profile` 与 `steps` 成对声明采样选择；LFO 不负责向用户提问，也不从一个步数推断是否启用加速。

| sampler_profile | steps | 执行路径 |
| --- | --- | --- |
| `vdn_turbo` | 必须为整数 `8` | VDN Turbo 的独立工作流，euler / simple；只支持标准 H3 operation |
| `native` | 整数且 ≥ 8，例如 8、16、20、24 | 不接入 VDN / SigmaShift 的原生工作流，res_multistep / simple；支持标准 H3 与 virtual_presenter |

只提供其中一个字段、未知模式、非整数步数、小于 8，或 `vdn_turbo` 搭配非 8 步，均在提交前拒绝。显式选择的模式不会因环境缺失而自动换成另一模式；原生图不依赖 VDN 插件及 bundle。模式选择与 `operation` 正交：切换 native 不改变首尾帧或 typed reference 约定。

为保持已有包的执行语义，成对省略时，标准 H3 仍采用原来的 VDN Turbo 8 步，virtual_presenter 仍为原生 20 步。纯 passthrough 不做采样，不应声明这两个字段。旧包默认值不是新项目的用户授权。

在创作流程中，像素预算、模式和步数在首个视频包前让用户选择一次，再持久化到项目规格；zero-to-story 使用蓝图顶层 `user_constraints`，逐 Panel 继承到公共 requirements。适配器拒绝与项目采样选择冲突的 Panel 覆盖，用户明确变更后才能更新项目规格并重新形成包。LFO 使用包中的值完成工作流选择、步数绑定及执行结果记录，不接受执行时临时覆盖。更改任一字段会改变包 hash，受影响包需新 revision 和精确批准。具体 VDN 开关含义见 [H3 采样模式说明](h3-vdn8.md)。

### 可选 SeedVR2 放大

需要在当前生成 Clip 通过 H3 后再做一次放大时，只显式写入：

```json
{
  "extensions": {
    "upscale": {
      "enabled": true,
      "scale_multiplier": 2.0,
      "seed": 12345
    }
  }
}
```

`seed` 可省略。LFO 对这个已声明的 SeedVR2 workflow 只提交一次，并直接使用工作流原生的自适应时域分块；不支持公开 `segment_seconds`，也不会因 OOM 自动改参数后重投。ComfyUI 输出根目录是可选的：若未配置，LFO 通过同一 ComfyUI 服务的 `/view` 元数据下载结果。纯 `video.passthrough` assembly 不允许开启放大，否则它就不再是无模型调用的确定性组装。

所有契约对象都拒绝未知字段，避免把拼写错误静默当成无效配置；只有 `metadata`、`source_context` 和尚未被 LFO 识别的命名空间扩展内容保留为开放映射。已识别的 `extensions.upscale` 字段同样严格校验。

## 批准与 package hash 锁

人工确认与技术哈希锁是两层：调用方可依据用户明确授予的项目内修订包持续授权，在完成新包、validate 及范围核对后直接绑定当前 hash，无需用户逐次回复。授权范围与原话保存在创作侧现有项目记录，不能把笼统“继续”当成持续授权；也不能扩大范围、略过校验或将模型自批伪装成用户逐包审阅。后文“用户确认”在这种情况下指已覆盖本次修订的明确授权，运行时仍只接收精确 hash，不新增免校验开关。

运行 `validate` 后，LFO 在成功结果中返回完整 `execution-package.json` 的完整文件字节 SHA-256（`package_sha256`）。用户确认该值后将它传给 `execute --approved-sha256`。执行开始前 LFO 重新计算并比对：

- 一致：继续当前 Panel 的执行；
- 不一致：立即停止，要求重新确认并生成新的 revision。

package 文件中的素材引用或声明 hash、提示词、时长、operation、字幕/音频或 output 字段变化都会改变 hash。仅替换 `source.uri` 指向文件的内容不会改变 package 文件本身；若该素材必须随批准一起锁定，应填写 `source.sha256`，Runtime 会在导入时拒绝内容不匹配。当前不使用独立 `lfo.production_lock.v1` 文件、不允许 prompt revision，也不维护审批状态机或恢复日志。

## 执行与结果

调用方按以下顺序执行：

```text
validate → execute（一次同步 H3；显式开启时再一次 SeedVR2）→ 最小 QC → ACCEPT/REJECT
```

`execute` 只处理当前 Clip，调用配置的官方 ComfyUI/comfy-cli 并等待结果。它返回生成视频或错误；执行单元必须查看实际视频，记录实际末态和实际音频证据，再作一次 `ACCEPT`/`REJECT` 判断。证据不足时先做一次本地复核，仍不清楚就停止；不能用元数据、轨道存在或不确定的 ASR 代替证据。只有 `ACCEPT` 后才按下游需要从实际视频提取真实尾帧。公开协议不包含自动重试或失败候选；调用方不读取或维护恢复记录，底层运行记录不改变这一交接边界。

Canvas 和 package CLI 的 Comfy 提交共用项目的机器范围提交占用和持久回执；package 运行时不能绕过这个低层占用直接并发提交。诊断入口见[CLI 指南](cli-guide.md)和 `python -m lfo.comfy.admission`。

`plan` 可用于诊断，但不参与批准，也不是必经步骤。最终 assembly package 同样需要 `validate` 和完整文件字节 SHA-256 批准；其中一个或多个 Clip 必须全部是 `video.passthrough`，只执行确定性媒体组装，不调用生成模型。即使项目只有一个 Panel，也使用单 Clip passthrough assembly 应用最终配音、字幕和输出策略。

## 产物布局

```text
workspace/projects/<project_id>/
├── panel-P001.execution-package.json
├── panel-P002.execution-package.json
├── assembly.execution-package.json
├── outputs/<run_id>/clips/<clip_id>/
└── final/<output.directory>/
```

所有 Panel 包和 assembly 包必须直接位于项目根目录，不能各自放在子目录；包内相对 `source.uri` 才能直接引用同一项目 `outputs/<run_id>/...` 下的已接受视频或真实尾帧。文件名可以不同于示例，但必须唯一，命令按实际路径传入。

### 通用 assembly 最小示例

下面的 assembly 不依赖 presenter 专用适配器，适用于 zero-to-story、短剧或其他创作侧。前提是两个视频都已经 `ACCEPT`，且这些文件与 package 位于同一项目根目录：

```json
{
  "schema": "lfo.video-execution.v1",
  "package_id": "story-assembly",
  "revision": 1,
  "project": {"project_id": "story", "title": "两 Panel 故事", "locale": "zh-CN"},
  "assets": [
    {
      "asset_key": "accepted.P001",
      "media_type": "video",
      "source": {"uri": "outputs/run-p001/clips/P001/mixed.mp4"},
      "provenance": {"source_type": "accepted_clip", "producer": "caller", "operation": "video.accepted"}
    },
    {
      "asset_key": "accepted.P002",
      "media_type": "video",
      "source": {"uri": "outputs/run-p002/clips/P002/mixed.mp4"},
      "provenance": {"source_type": "accepted_clip", "producer": "caller", "operation": "video.accepted"}
    },
    {
      "asset_key": "dialogue.P001",
      "media_type": "audio",
      "source": {"uri": "assets/audio/p001.wav"},
      "provenance": {"source_type": "user_upload", "producer": "caller", "operation": "audio.import"}
    },
    {
      "asset_key": "dialogue.P002",
      "media_type": "audio",
      "source": {"uri": "assets/audio/p002.wav"},
      "provenance": {"source_type": "user_upload", "producer": "caller", "operation": "audio.import"}
    },
    {
      "asset_key": "captions.P001",
      "media_type": "subtitle",
      "source": {"uri": "assets/subtitles/p001.srt"},
      "provenance": {"source_type": "user_upload", "producer": "caller", "operation": "subtitle.import"}
    },
    {
      "asset_key": "captions.P002",
      "media_type": "subtitle",
      "source": {"uri": "assets/subtitles/p002.srt"},
      "provenance": {"source_type": "user_upload", "producer": "caller", "operation": "subtitle.import"}
    }
  ],
  "clips": [
    {
      "clip_id": "P001",
      "sequence": 1,
      "duration_ms": 8000,
      "generation": {
        "operation": "video.passthrough",
        "prompt": "Pass through accepted P001",
        "references": [{"reference_id": "video-P001", "asset_key": "accepted.P001", "semantic_usage": "accepted.clip", "binding": {"required": true}}]
      },
      "audio": {"native_audio": "mute", "tracks": [{"asset_key": "dialogue.P001", "role": "dialogue"}]},
      "subtitles": {"asset_key": "captions.P001"}
    },
    {
      "clip_id": "P002",
      "sequence": 2,
      "duration_ms": 7000,
      "generation": {
        "operation": "video.passthrough",
        "prompt": "Pass through accepted P002",
        "references": [{"reference_id": "video-P002", "asset_key": "accepted.P002", "semantic_usage": "accepted.clip", "binding": {"required": true}}]
      },
      "audio": {"native_audio": "mute", "tracks": [{"asset_key": "dialogue.P002", "role": "dialogue"}]},
      "subtitles": {"asset_key": "captions.P002"}
    }
  ],
  "timeline": {"segments": [{"clip_id": "P001"}, {"clip_id": "P002"}]},
  "output": {"width": 1080, "height": 1920, "fps": 24, "sample_rate": 48000, "subtitles_mode": "both", "directory": "story-assembly"}
}
```

`outputs/...`、音频和 SRT 的 URI 都相对 `assembly.execution-package.json`；不要改成上一个 Panel 子目录下的 `../../` 路径。音频轨道和字幕字段按 assembly 的每个时间段迁移：保留 H3 原声用 `native_audio: "preserve"`，替换原声就用 `"mute"` 并显式绑定对应音频；外部整片口播不能无条件重复挂到每个 Panel，应按 Panel 时间段拆分，或把它作为单 Clip assembly 的唯一音轨。字幕可用该 Clip 的内联 `cues` 或 `asset_key` 指向对应 SRT；只有用户需要时才把 `output.subtitles_mode` 设为 `sidecar`/`burnin`/`both`，否则设为 `none`。所有 Panel `ACCEPT` 后才创建本包，再按 `validate` → 用户批准其返回 hash → `execute --approved-sha256 <hash>` 执行一次。

ComfyUI 自己的输出目录只是提供方缓存。LFO 将当前 Panel 的视频写入项目输出目录；调用方在 `ACCEPT` 后按下游需要提取并登记真实尾帧。所有 Panel `ACCEPT` 后，由调用方执行一次最终 `cut` assembly 并写入 `final/<output.directory>/`。

机器可读 schema 位于 [`src/lfo/contracts/schemas/video-execution-v1.schema.json`](../src/lfo/contracts/schemas/video-execution-v1.schema.json)。
