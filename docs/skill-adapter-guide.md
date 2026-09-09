# Creative Skill 适配器指南

共同的角色、Panel ready、实际验收、音频证据和授权规则见[项目共享生产规则](ai-system-prompt.md)。本指南只描述旧 package CLI 的适配边界。

Creative Skill 负责创作，LFO 负责执行。适配器的职责是把一个已经确认的 Panel 转成一个只含一个 Clip 的 `lfo.video-execution.v1` package；适配器不得调用 ComfyUI、操作 LFO 数据库或拼接内部节点 ID。

## 交付顺序

1. 完成故事、角色/场景资产、Panel 和 H3 提示词的创作审批。
2. 固定当前 Panel 所需的本地素材，保留原始路径和必要 hash。
3. 创建素材条目和一个 `ClipSpec`。
4. 让 operation、真实首帧/尾帧和引用槽位与已批准的 H3 标签一致。
5. 写出当前 Panel 的 package，确保 `clips` 恰好一个元素。所有 Panel package 和最终 assembly package 都直接放在同一个 `workspace/projects/<project_id>/` 项目根目录，用唯一文件名（例如 `panel-P001.execution-package.json`、`assembly.execution-package.json`），不要放入 Panel 子目录，否则前一 Run 的 `outputs/<run_id>/...` 无法用包内相对 URI 稳定引用。
6. 运行 `validate`，由其返回完整 package 文件的精确文件字节 `package_sha256`。
7. 核对用户明确的项目授权：持续授权覆盖当前修订时直接绑定当前 hash，否则取得该 hash 的确认；随后启动当前 Panel 的隔离执行单元。`plan` 只在需要时诊断。

适配器不为历史 `shots[]`、旧 Panel CLI 或旧 lock/retry/recovery 语义提供转换层。需要重做时重新生成当前 Panel 的 package；不自动改写或重试。

## 最小示例

```python
from lfo.contracts import VideoPackageBuilder

builder = VideoPackageBuilder(
    package_id="episode-001-p001",
    title="Episode 001 / P001",
    project_id="episode-001",
)
builder.add_asset(
    asset_key="hero.identity",
    media_type="image",
    uri="assets/hero.png",
    producer="my-creative-skill",
    operation="image.generate",
)
builder.add_clip(
    clip_id="P001",
    sequence=1,
    duration_ms=5000,
    operation="video.image_to_video",
    prompt="已确认的 H3 最终提示词",
    references=[{
        "reference_id": "hero-first-frame",
        "asset_key": "hero.identity",
        "semantic_usage": "subject.identity",
        "binding": {
            "required": True,
            "placement": "first",
            "slot": "first_frame",
        },
    }],
)
builder.write("panel-P001.execution-package.json")
```

`generation.prompt` 必须逐字来自用户确认的 H3 输出；适配器不能在 package 阶段补写提示词、负向词或创作说明。I2V 只绑定真实 `first_frame`，FL2V 绑定真实 `first_frame` 与 `last_frame`，R2V 只使用明确的 fixed typed slot；整张分镜板若被批准为模型引用，只占一个图片槽位，板内格子不拆分，否则只作为 planning 资产。

## 执行交接

交给 LFO 的输入保持最小；尾帧提取目标只属于调用方执行单元，不是 LFO CLI 参数：

```text
panel_id
package_path
approved_package_sha256
machine_id（有已保存机器配置时）
tail_frame_output_path（仅下游需要时；调用方的 ffmpeg 提取目标，不传给 LFO）
```

LFO 只处理当前 Panel，回传生成视频或错误。执行单元查看实际输出，记录实际末态和实际音频证据，再决定一次 `ACCEPT`/`REJECT`；证据不足时先复核，仍不清楚就停止。仅在 `ACCEPT` 后按需提取真实尾帧，再写入下一包的相对素材 URI；失败即停。单次执行不读取完整故事历史，不改变 package，也不并行启动下一个 Panel。

## 适配器测试

只验证当前契约和主流程：JSON/schema、完整文件字节 hash、相对素材路径、operation/引用匹配、生成包单 Clip 约束、passthrough 组装约束和 package 往返。真实尾帧由调用方在 `ACCEPT` 后按需提取，不把它伪装成 Runtime 自动状态。不要为公开协议中的自动重试、失败候选、复杂恢复或旧格式兼容添加测试。
