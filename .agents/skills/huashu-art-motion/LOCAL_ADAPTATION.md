# 本项目安装记录

上游：<https://github.com/alchaincyf/huashu-art-motion>

固定提交：`8a0d7d72ca65fcce6f8ba82c4a6c8dfe35b8422c`，版本1.2.0。使用Codex skill-installer安装到项目 `.agents/skills/huashu-art-motion/`，没有安装全局Skill。

Windows本机兼容调整三项：

- `scripts/engine/render.py` 与 `scripts/qa.py` 复用已安装Chrome，默认channel为chrome，可通过本次进程环境变量HUASHU_BROWSER_CHANNEL选择其他已支持channel；渲染器保留正常浏览器安全检查。
- `scripts/engine/index.html` 与 `scripts/engine/clip.html` 加入空data favicon，避免图标404被上游的页面错误检查误报为渲染失败。修正前后均有实际运行记录。
- 上述HTML仅在`?render=1`离线模式中为Canvas2D设置`willReadFrequently:true`，统一读回路径。未设置时，完整QA曾有哥特场景最大像素差18、延长末段最大差13；设置后完整15场景逐像素一致。此结论仅覆盖本机Chrome与本次工程，不保证所有浏览器。

安装内容中的场景、画笔、转场与原版时间表没有改写。运行项目复制到 workspace/projects/huashu-full-run-20261023/；仅该运行副本把总时长延长至原有结尾动作与示例音乐结束，按实际15场景对齐配乐。该项目为本次用户明确要求的完整上游框架本机复现，不是新的原创成片，也不代表指定商业模型的一次生成评测。后续原创创作仍遵守项目当前入口与用户当次授权。

本轮用户明确指定安装并运行此代码动画流程，使用本机Chrome、FFmpeg和免费Python依赖；没有Comfy或付费服务提交。写代码的当前宿主订阅和设备费用不因此变成零。

当前宿主已直接读取并执行本Skill；自动技能列表在后续回合更新。本记录不是另一个执行器，不改变上游质量标准、独立审片或来源要求。
