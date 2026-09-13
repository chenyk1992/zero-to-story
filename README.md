# zero-to-story

项目自有代码采用 [MIT](LICENSE)，第三方内容见[许可说明](THIRD_PARTY_NOTICES.md)。开发检查见[贡献指南](CONTRIBUTING.md)，公开源码准备见[发布检查](docs/open-source-release.md)。无本机素材依赖的画布示例见 [minimal-canvas.json](examples/minimal-canvas.json)。

这是一个以节点画布为唯一生产入口的故事创作工作空间。可以按故事或章节组织角色参考、故事板、黑白分镜、提示词、图片与视频；支持分类搜索、分区、组件编辑与连线，SQLite 自动保存。点击成品可以预览实际媒体、查看本次冻结参数并跳转关联资料。

所有生产任务先遵守[项目共享生产规则](docs/ai-system-prompt.md)；[Skill 路由](docs/ai-skill-routing.md)只说明职责边界。

从项目根启动：

```powershell
./scripts/start_canvas.ps1
```

首次使用先安装项目依赖并构建页面，步骤、对话操作和已知接入边界见[画布使用指南](docs/canvas-guide.md)。新增 Skill、能力描述和 MCP 配置都限定在当前项目。

本地 Comfy 视频走一条固定链路：页面确认后，画布服务冻结输入并创建 `queued` 运行；服务内部脚本 worker 启动 `comfy-video-executor` Python adapter；adapter 通过本地 ComfyUI HTTP 接口上传素材和读取 `/object_info`，再同步调用一次官方 `comfy run --wait --json`；实际视频经过媒体校验后回填画布。Comfy 不是 `pending_agent` 任务，页面确认也不会要求对话 Agent 再 claim 或再次提交。

画布使用 `VideoSubmissionGuard` 保证本机视频串行；机器级互斥覆盖一次提交和整个等待周期。若执行进程丢失，持久回执会继续阻塞未知任务，直到依据原任务证据核实结束。技术提交成功不等于内容接受；故事生产或明确要求内容验收的媒体任务，必须依据实际视频的实际末态和实际音频证据判断。

## 快速开始

```powershell
./scripts/bootstrap_dev.ps1
cd web/canvas
npm install
npm run build
cd ../..
./scripts/start_canvas.ps1
```

本地 ComfyUI 设置和检查见[本机环境](docs/local-windows.md)，当前 H3 模板与绑定规则见[工作流约定](docs/workflow-conventions.md)。

源码位于 `src/lfo/`，页面位于 `web/canvas/`，测试位于 `tests/`，用户视频与素材位于 `workspace/`。旧生产入口已经退役，但已有旧包、旧运行目录、最终产物和 `workspace/assets/sha256/` CAS 数据都是用户历史资产，不会因代码清理而删除、改名或搬迁。
