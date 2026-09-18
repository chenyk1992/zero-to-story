# 当前仓库发布检查

项目直接在当前代码仓库维护和开源。项目自有代码使用 Apache License 2.0，第三方内容保留各自 LICENSE 和 NOTICE，见 [许可说明](../THIRD_PARTY_NOTICES.md)。

`workspace/` 保存本机工作流验证产物，不纳入 Git。历史测试目录 `.short-drama/`、运行数据库和本地迭代记录 `docs/` 也由忽略规则排除。长期操作说明和 Agent 必需规则放在 `guides/`，必须随代码分发。已跟踪文件需使用 `git rm --cached` 取消跟踪，本机文件可继续使用；不需要另建仓库或导出源码。

提交前检查：

```powershell
git ls-files -- workspace .short-drama db docs
git check-ignore workspace/projects/example/outputs/example.mp4
git diff --cached --stat
```

第一条应无输出，第二条应命中忽略规则。不要用 `git add -f` 将运行产物重新加入。旧提交里的工作流测试数据不影响当前代码仓库开源；本次不重写历史。

运行 [贡献指南](../CONTRIBUTING.md) 中的检查，再审阅本次代码差异。画布、项目 Skills、通用媒体工具与必要的测试夹具保留在仓库；特定剧集、Panel 或 run 的一次性脚本不作为运行依赖。提交、推送或发布按维护者指令执行。
