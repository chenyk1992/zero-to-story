# 参与开发

从完整源码目录安装，使用 Python 3.12 和 Node.js 22.12 或更高的受支持版本：

```powershell
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[dev,canvas]"
cd web/canvas
npm ci
npm test
npm run build
```

回到仓库根目录后运行：

```powershell
./.venv/Scripts/python.exe -m ruff check src tests
./.venv/Scripts/python.exe -m pyright
./.venv/Scripts/python.exe scripts/validate_ai_config.py
./.venv/Scripts/python.exe -m pytest tests/ -v
```

媒体集成测试需要 PATH 中的 FFmpeg 和 ffprobe。没有这些工具时跳过项不代表媒体能力验证通过。测试使用系统临时目录，不使用真实用户工作区，不提交付费生成。

运行时改动应附上能复现问题的行为测试；画布协议或媒体绑定变更运行全量检查。遵循 [AGENTS.md](AGENTS.md) 和 [共享生产规则](docs/ai-system-prompt.md)，保留未提交修改和用户数据。PR 描述说明问题、最终行为与实际验证结果。

当前 wheel 只打包 `src/lfo`；完整画布还需要源码树的 Web 构建和项目 Skills，不能将单独 wheel 当作完整桌面发行版。
