# H3 工作流约定

共同的角色、Panel ready、输入冻结和实际末态/音频验收规则见[项目共享生产规则](ai-system-prompt.md)。本文只描述 Canvas `comfy-video-executor` 的 H3 模板、绑定、预检和结果边界。

## 模板来源

Canvas H3 模板只维护在项目 Skill 的 `.agents/skills/comfy-video-executor/templates/`：

- `h3_native_fl2va.json`
- `h3_native_r2v.json`
- `h3_standard_fl2va.json`
- `h3_standard_r2v.json`

模板声明模型、VAE、提示词和引用输入、分辨率、时长、采样器、调度器、步数及输出链路。adapter 不从其他运行时目录加载模板，也不根据旧运行记录选择工作流。模板中的示例值不是 Canvas 默认值；本次确认快照必须显式提供 capability 要求的字段。

## adapter 职责

Python adapter 只做以下工作：

1. 校验冻结 snapshot 的 provider、model、mode、提示词、公共参数和 Comfy 专属参数。
2. 按模式检查真实素材槽位，通过官方本地 Comfy MCP `upload_file` 上传本次固定输入。
3. 把已确认提示词逐字绑定到模板，把时长、画幅、像素预算、采样配置、步数、seed、FPS 和引用位置写入公开输入。
4. 在提交前通过 MCP `nodes` 和 `validate_workflow` 检查必需节点、枚举值和工作流。动态上传后的文件名不拿旧服务列表做预判。
5. 在 `VideoSubmissionGuard` 的机器级串行互斥内先写提交意图，调用一次 `run_workflow(wait=False)`；立即持久化返回的 `prompt_id`，以 `job` 查询原任务。进程丢失后的未知回执继续阻塞新任务。
6. 经 `fetch_outputs` 把本次唯一视频取回当前 Canvas run 输出目录，并做 ffprobe 媒体校验。

adapter 不写创意提示词、不决定镜头语义、不切换 provider、不创建第二套数据库，也不在失败后隐式重提。技术成功不代表内容 `ACCEPT`；故事媒体仍由执行单元查看实际文件，记录实际末态和实际音频证据。

## 模式和素材槽位

- `t2v`：不接受媒体输入。
- `i2v`：恰好一个 `first_frame` 图片。
- `fl2v`：恰好一个 `first_frame` 和一个 `last_frame` 图片。
- `r2v`：至少一个明确类型的图片、视频或音频引用；固定槽位来自画布连线，不从提示词猜测。

图片、视频和音频引用分别绑定到对应的 `LoadImage`、`LoadVideo` 或 `LoadAudio` 链。R2V 的引用顺序和类型必须保持冻结 snapshot 的原顺序。业务代码不依赖 ComfyUI 数字节点 ID；节点 ID 只属于模板内部连线。

## 采样模板

`sampler_profile=native` 使用 `h3_native_*` 模板，接受至少 8 步；`sampler_profile=vdn_turbo` 使用 `h3_standard_*` 模板，只接受 8 步。T2V/I2V 使用 FL2VA 模板族，R2V 使用 R2V 模板族。adapter 不通过打开或关闭某个 VDN 节点把一种 profile 冒充另一种。

VDN 默认把权重驻留与工作缓存交给插件的 `auto` 策略。快照可明确选择 `vdn_checkpoint`（已安装的完整 8 步 bundle 相对目录），并用 `vdn_branch_weights`、`vdn_retain_buffers` 覆盖内存策略；这些字段只适用于 VDN Turbo。`video_decode=tiled` 在所有模式和采样配置下只替换视频解码节点，保留音频与输出连线；未选择时仍完整解码。参数、新版节点要求与旧策略对照方法见[执行协议](../.agents/skills/comfy-video-executor/references/execution.md#vdn-execution-options)。

成功运行的 `execution-report.json` 保存在当前 run 输出目录，记录实际绑定配置与可测耗时，不改变媒体输出数量。provider 等待不能解释为纯采样时间，显存峰值和内部阶段时间没有实际来源时留空。

模板更新必须同时检查：

- capability 字段与 adapter 校验一致；
- snapshot 的每个可变值只有一个明确绑定位置；
- MCP `nodes` 和 `validate_workflow` 能识别所需节点和模型；
- 输出仍然唯一且是视频；
- 单次提交、未知状态和媒体校验测试仍通过。

静态测试不能代替真实 provider 集成；真实生成只在对应 Canvas run 已确认时执行。
