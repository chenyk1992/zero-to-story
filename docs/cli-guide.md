# LFO 单 Panel CLI 指南

当前 CLI 只服务于一个简单、同步的 Panel 执行链。每个生成 package 文件只包含一个待执行 Clip；最终组装包可包含一个或多个全 `video.passthrough` Clip。调用方将每个 Panel 作为独立的短生命周期执行单元，按顺序运行本页命令。LFO 不并行处理多个生成 Panel，也不在失败后自动重试；具体运行机制由宿主工具自行决定。

## 主流程

```powershell
python -m lfo.cli.main validate path/to/panel-P001.execution-package.json --machine-id local-windows
python -m lfo.cli.main execute path/to/panel-P001.execution-package.json --approved-sha256 <approved-sha256> --machine-id local-windows
```

1. `validate` 检查 JSON、素材路径、operation、引用槽位、时长和基本输出规格，不启动生成；成功结果中同时返回 `package_sha256`，供用户确认。
2. `execute` 再次计算完整 package 文件的完整文件字节 SHA-256（exact file SHA-256），与批准值比较；一致后导入素材，通过官方 `comfy run --wait --json` 同步执行工作流，等待完成并收集当前 Panel 视频。调用方随后做最小 QC、决定 `ACCEPT/REJECT`，并在 `ACCEPT` 后按下游需要提取真实末帧。

`plan` 仅是只读的可选诊断命令，用来显示当前 Panel 选择的后端/工作流、实际引用和产物位置；它直接解析源素材并校验声明 hash，不导入 CAS、不记录素材 revision、不提交 ComfyUI、不锁定 package，也不是 `execute` 的前置条件。

`--machine-id` 让 validate/plan/execute 使用同一份已保存机器配置，其中的 ComfyUI 地址、`comfy` 可执行文件和输出根目录会进入实际执行器；指定不存在的 profile 会立即报错。没有保存 profile 时可以省略该参数并使用默认本机配置。

`execute` 只返回当前 Panel 的生成结果或错误；`ACCEPT/REJECT`、真实尾帧登记和最终 assembly 由调用方按顺序完成。

## 批准 hash

批准前由创作侧保存完整 package 文件，运行 `validate` 并将其返回的 `package_sha256` 交给用户确认。执行参数、素材引用或声明 hash、提示词、时长、operation、字幕/音频设置或输出策略任何变化，都会改变这个完整文件字节 SHA-256（exact file SHA-256），必须重新 validate 和确认。若还要锁定素材内容，应在 package 内填写 `source.sha256`。hash 不一致时 LFO 直接停止，不修改 package，也不提交 ComfyUI。

当前不使用额外的 production-lock 文件、prompt revision、审批状态机或历史兼容层。批准 hash 是唯一执行锁。

## 结果与失败

`execute` 的最小结果为生成视频路径或错误；调用方的最小交接结果为：

```text
ACCEPT  <clip path>  [tail-frame path when downstream needs it]
REJECT  <reason>
ERROR   <reason>
```

QC 只确认输出可解码/播放、没有明显生成错误，以及连续镜头没有明显倒带、重复收尾或状态跳变。语义判断由创作侧/用户完成；LFO 不评分、不自动修复、不触发重试。

ComfyUI 失败、超时、输出缺失、hash 不匹配、素材不存在或 QC `REJECT` 都立即结束当前 Panel。等待超时时，LFO 只向当前 ComfyUI 发出一次尽力而为的中断请求以释放串行队列；这不是重试，也不会掩盖原始超时结果。主流程不包含 `retry`、`prompt-revision`、`review` 或自动恢复；若底层保留 `status`、`cancel`、`export` 等 Run 运维入口，它们也不属于 Panel 交接协议，调用方不读取或维护恢复记录，失败候选不导入为正式产物。需要重做时由调用方重新准备并显式执行当前 Panel。

## 尾帧接力

当下一 Panel 或边界检查需要连续性输入时，调用方必须从当前 `ACCEPT` Clip 的实际输出提取真实末帧 PNG；没有下游用途时不做多余提取：

- 下一 Panel 使用 I2V 时，作为唯一 `first_frame`；
- 下一 Panel 使用 FL2V 时，按计划与真实首帧一起使用；
- T2V 或硬切 R2V 只用于人工边界检查，不作为模型首帧引用。

不得用文字描述替代真实末帧。末帧 hash 变化时，依赖它的下一 Panel 必须重新准备。

## 路径

输入 package 的相对素材路径以 package 所在目录为根。LFO 不修改源文件；导入后的媒体和当前 Panel 产物写入项目的既有布局：

```text
workspace/projects/<project_id>/
├── panel-P001.execution-package.json
├── panel-P002.execution-package.json
├── assembly.execution-package.json
├── outputs/<run_id>/clips/<clip_id>/
└── final/<output.directory>/
```

所有 Panel package 和 assembly package 都直接位于项目根目录，不能放进各自子目录；包内相对 URI 才能直接指向 `outputs/<run_id>/...` 的已接受视频或真实尾帧。

ComfyUI 提供方缓存不是最终交付位置；LFO 只记录复制到项目输出目录的文件。不要在 `workspace/` 根部创建 `runs`、`exports` 或临时目录。

全部 Panel `ACCEPT` 后，调用方创建一份含一个或多个 Clip 的纯 `video.passthrough` assembly package。它同样经过 `validate`、完整文件字节 SHA-256 批准和一次 `execute`；这是唯一允许的多 Clip 执行，也让单 Panel 项目应用最终配音、字幕和输出策略，并且不会再次调用 H3 生成。

assembly package 不得启用 `extensions.upscale`。若单 Panel 生成包显式启用它，Runtime 会在 H3 通过后仅提交一次 SeedVR2，并使用其原生自适应时域分块；`segment_seconds`、自动 OOM 回退和隐藏重投都不受支持。

## 环境检查

机器或 ComfyUI 安装变化后运行：

```powershell
python -m lfo.cli.main setup --machine-id local-windows
python -m lfo.cli.main doctor --machine-id local-windows
python -m lfo.cli.main preflight --machine-id local-windows
```

`setup` 只发现并保存 machine profile，不创建 `workspace/` 项目目录、SQLite/旧数据库 schema、环境快照，也不提交视频或 smoke 任务；当前公开入口不需要 `--smoke-level`。需要环境核验时直接运行 `doctor`/`preflight`。

`doctor` 与 `preflight` 默认检查 ComfyUI 可达性、`comfy` CLI、`ffmpeg` 和 `ffprobe`，无需调用方手写 `--tool-ids`；失败结果应包含检查 ID、原因和修复提示。它们只做环境核验，不提交视频任务，也不会创建后台恢复记录。

真实单 Panel 集成检查（需要本地 ComfyUI 和用户素材）：

```powershell
python scripts/live_e2e_execution_package.py path/to/execution-package.json --approved-sha256 <approved-sha256> --machine-id local-windows
```

项目没有 `lfo` console entry point；始终使用 `python -m lfo.cli.main`。
