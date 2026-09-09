# H3 工作流约定

共同的角色、Panel ready、输入冻结和实际末态/音频验收规则见[项目共享生产规则](ai-system-prompt.md)。本文只描述 H3 registry 与绑定约定。

LFO 的 H3 工作流以 `src/lfo/registry/` 中的 JSON 为唯一配置来源。JSON
负责声明模型文件、VAE、提示词和引用输入、分辨率、帧数、采样器、调度器、
步数以及输出链路。Python 运行时不复制这些值，也不通过节点编号推断
工作流语义。

Python 运行时只做四件事：

1. 通过稳定的 `_meta.title` 绑定可变输入，例如
   `LFO.Prompt`、`LFO.Duration`、`LFO.Reference01` 和
   `LFO.MainGenerator`；节点编号和 ComfyUI 画布顺序不属于公共接口。
2. 在上传前读取 ComfyUI `/object_info`，检查所需节点、模型选择项及固定
   配置；输入绑定同时检查声明的槽位。预检应当说明缺少的模型或节点，不通过偷偷换模型、
   换采样器或删除引用来恢复。
3. 按 LFO 的单 Panel 契约串行提交一次并同步等待官方 ComfyUI/comfy-cli
   完成。Python 代码负责素材导入、输入绑定、超时和结果收集，不负责创作
   提示词或决定镜头语义。
4. 从本次 ComfyUI 结果中复制唯一明确的视频到 RunArtifactLayout，并记录
   `prepared_workflow_hash`、采样参数、`provider_elapsed_seconds`、
   `handler_elapsed_seconds`、媒体流和最小 QC 结果。生成失败或结果不唯一
   时停止当前 Panel，不自动换工作流重提。工作流技术成功不代表内容
   `ACCEPT`；执行单元必须依据实际视频记录实际末态和实际音频证据。

工作流的模型名、采样参数和输出节点必须留在 JSON；绑定代码依赖标题、
节点类型和公开输入名称。替换 registry JSON 后沿用现有的 workflow hash、manifest、
binding report 和静态/预检检查。不要在 Python 中增加隐藏的备用节点 ID、
环境变量模式或同一 JSON 的另一套采样参数。

当前 H3 视频工作流保持以下边界：VDN8 直接替换标准 FL2VA/R2V 的
registry JSON，并完整保留这些模板已有的 operation 映射、T2V/FL2V 映射和
视频/音频/混合引用绑定；LFO 继续使用同一套输入绑定。数字人口播
`video.virtual_presenter` 继续使用独立的原生 20 步工作流。质量验证采用
8 步，不能以 4 步作为生产默认。

工作流变更不改变 `VideoExecutionPackage` 公共字段。仍按现有的
`validate` → `execute --approved-sha256` 和 workflow hash 契约执行。

Canvas Comfy 与 package CLI 共用低层提交占用和持久提交回执；工作流绑定代码不能绕过该占用或自行并发提交。回执诊断由 `python -m lfo.comfy.admission` 提供，核实原任务只读取原始 Comfy `/history`，不重新提交。

## ComfyUI 工作流编码

- 同类节点有多个实例时，可变输入使用唯一的 `_meta.title`；声明的标题
  必须恰好匹配一个节点。采样器等结构性单例可以按 `class_type` 查找，并检查数量。
- 复用现有的 binding、上传、runner、materialize 和 result collector；新
  工作流不复制一套提交、下载或耗时统计逻辑。
- 标准 R2V 与数字人口播共享引用接线和上传流程；场景差异只放在对应的
  工作流和必要的输入限制中。引用位置由公共包的明确槽位决定。
- 输入参数及所有本地素材路径先检查，之后才上传；动态参考节点按本次实际
  使用的素材类型检查，预留但未使用的图片节点不应成为依赖。
- 通过 `/object_info` 检查 `class_type` 是否可用。业务绑定不硬编码
  ComfyUI 数字节点 ID，节点 ID 只属于当前 JSON 的内部连线。
- 预检先验证完整工作流结构、当前 hash 和严格绑定，再检查运行中的节点及
  模型；不根据历史快照或旧的通过记录跳过本次检查。
- 新工作流的最小变更是 registry JSON、对应的 capability/manifest 和一
  个针对绑定、预检或结果收集的测试；需要实际执行时再沿用现有单 Panel
  流程验证。
