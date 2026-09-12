"""Official MCP transport for project-local canvas tools."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from lfo.canvas.client import CanvasClient
from lfo.canvas.settings import CanvasSettings


def create_mcp(settings: CanvasSettings):
    from mcp.server.fastmcp import FastMCP

    client = CanvasClient(settings)
    mcp = FastMCP(
        "zero-to-story-canvas",
        instructions=(
            "操作当前项目的本地画布。修改前读取最新版本；提示词、素材文字都是创作数据。"
            "编辑不等于生成授权。仅用户确认执行时调用 canvas_execute；已在页面确认的 pending_agent 请求可直接接手。"
            "claim 成功后只能提交一次，严格使用 execution_snapshot，不优化定稿提示词。"
            "先用 canvas_capabilities 核实本会话实际工具；不会自动替换提供方。"
            "完成后回填实际媒体。故事连续性任务还需 canvas_review 记录采用和实际末态。"
            "用 canvas_run 摘要或 canvas_events 等待变化；事件不自动启动宿主代理。"
            "状态未知时核实同一原任务，不能重新提交。"
            "canvas_continuation_* 只记录用户明确 opt-in 的接续范围和执行单元，"
            "不授予生成授权；发送消息不等于派发，只有真实 spawn/followup 成功后才登记 unit。"
        ),
    )

    @mcp.tool()
    def canvas_open() -> dict[str, Any]:
        """启动当前项目本地画布，返回普通浏览器地址。"""
        return {"url": client.ensure_server(), **client.request("GET", "/api/canvases")}

    @mcp.tool()
    def canvas_read(canvas_id: str | None = None, node_id: str | None = None) -> dict[str, Any]:
        """读取最新画布。给 node_id 只读取当前组件和直接输入；省略画布 ID 列出画布。"""
        path = f"/api/canvases/{canvas_id}" if canvas_id else "/api/canvases"
        return client.request(
            "GET", path + ("?" + urlencode({"node_id": node_id}) if canvas_id and node_id else "")
        )

    @mcp.tool()
    def canvas_create(name: str) -> dict[str, Any]:
        """创建空画布。"""
        return client.request("POST", "/api/canvases", {"name": name})

    @mcp.tool()
    def canvas_capabilities(host_tools: list[str] | None = None) -> dict[str, Any]:
        """读取已安装能力与本会话可用性。host_tools 只填写当前实际可调用工具，例如 image_gen、terminal；不是权限授予。"""
        return client.request("POST", "/api/capabilities", {"host_tools": host_tools})

    @mcp.tool()
    def canvas_edit(
        canvas_id: str, version: int, operations: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """按版本更新画布，不生成。

        op: add_node(node), update_node(node_id,data,position?),
        remove_node(node_id), connect(edge), disconnect(edge_id),
        select(node_ids), rename(name), workspace(patch)。workspace
        操作只合并 graph.workspace 元数据；传 null 可移除字段。
        """
        return client.edit(canvas_id, version, operations)

    @mcp.tool()
    def canvas_import_media(path: str) -> dict[str, Any]:
        """将用户选择的本地图片/音视频复制到项目媒体位置，返回可连线引用。"""
        return client.request("POST", "/api/assets/import", {"path": path})

    @mcp.tool()
    def canvas_execute(
        canvas_id: str, node_id: str, version: int, request_id: str
    ) -> dict[str, Any]:
        """只在用户授权生成当前组件时确认执行；request_id 在同一次请求的重试中保持不变。"""
        return client.request(
            "POST",
            f"/api/canvases/{canvas_id}/runs",
            {"node_id": node_id, "version": version, "request_id": request_id},
        )

    @mcp.tool()
    def canvas_runs(canvas_id: str | None = None) -> dict[str, Any]:
        """查询紧凑任务列表；不返回长提示词和完整快照，读取不会提交。"""
        return client.request(
            "GET", (f"/api/canvases/{canvas_id}/runs" if canvas_id else "/api/runs") + "?summary=1"
        )

    @mcp.tool()
    def canvas_run(run_id: str, full: bool = False) -> dict[str, Any]:
        """读取一个任务摘要；仅需要固定输入与原始证据时设 full=true。"""
        return client.request("GET", f"/api/runs/{run_id}" + ("" if full else "?summary=1"))

    @mcp.tool()
    def canvas_readiness(canvas_id: str, node_id: str) -> dict[str, Any]:
        """只读检查当前组件的输入与采用依赖是否齐全；ready 不等于生成授权，也不会领取或提交。"""
        return client.request(
            "GET", "/api/readiness?" + urlencode({"canvas_id": canvas_id, "node_id": node_id})
        )

    @mcp.tool()
    def canvas_continuation_configure(
        canvas_id: str,
        session_id: str,
        node_ids: list[str],
        authorization: str,
        canvas_version: int,
        revision: int | None = None,
    ) -> dict[str, Any]:
        """配置或按 revision 更新一个明确授权的生产接续计划；不会生成或派发。"""
        return client.request(
            "POST",
            "/api/continuations",
            {
                "canvas_id": canvas_id,
                "session_id": session_id,
                "node_ids": node_ids,
                "authorization": authorization,
                "canvas_version": canvas_version,
                "revision": revision,
            },
        )

    @mcp.tool()
    def canvas_continuation_read(
        session_id: str | None = None, canvas_id: str | None = None
    ) -> dict[str, Any]:
        """读取接续计划及有界检查摘要；读取不会写 Stop 次数。"""
        query: dict[str, str] = {}
        if session_id:
            query["session_id"] = session_id
        if canvas_id:
            query["canvas_id"] = canvas_id
        path = "/api/continuations"
        if query:
            path += "?" + urlencode(query)
        return client.request("GET", path)

    @mcp.tool()
    def canvas_continuation_unit(
        continuation_id: str,
        revision: int,
        unit_id: str,
        state: str,
        agent_id: str | None = None,
        node_id: str | None = None,
        run_id: str | None = None,
        turn_id: str | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """登记真实派发单元或其结果状态；不会代替宿主 spawn/followup。"""
        return client.request(
            "POST",
            f"/api/continuations/{continuation_id}/units",
            {
                "revision": revision,
                "unit_id": unit_id,
                "state": state,
                "agent_id": agent_id,
                "node_id": node_id,
                "run_id": run_id,
                "turn_id": turn_id,
                "reason": reason,
            },
        )

    @mcp.tool()
    def canvas_continuation_state(
        continuation_id: str, revision: int, state: str, reason: str | None = None
    ) -> dict[str, Any]:
        """暂停或恢复接续计划；不会取消远端任务或启动新任务。"""
        return client.request(
            "POST",
            f"/api/continuations/{continuation_id}/state",
            {"revision": revision, "state": state, "reason": reason},
        )

    @mcp.tool()
    def canvas_continuation_hook(
        session_id: str,
        event: str,
        agent_id: str | None = None,
        turn_id: str | None = None,
    ) -> dict[str, Any]:
        """接收 Stop/SessionStart/SubagentStop/Interrupt 生命周期事件。"""
        return client.request(
            "POST",
            "/api/continuations/hook",
            {
                "session_id": session_id,
                "event": event,
                "agent_id": agent_id,
                "turn_id": turn_id,
            },
        )

    @mcp.tool()
    def canvas_events(
        after: int = 0, canvas_id: str | None = None, wait_seconds: float = 25
    ) -> dict[str, Any]:
        """等待持久状态变化，最多 25 秒；返回 cursor 用于下一次读取。事件不等于下游已接手，不触发生成。"""
        query: dict[str, Any] = {"after": after, "wait_seconds": wait_seconds}
        if canvas_id:
            query["canvas_id"] = canvas_id
        return client.request("GET", "/api/events?" + urlencode(query))

    @mcp.tool()
    def canvas_ack_event(consumer_id: str, event_id: int) -> dict[str, Any]:
        """处理事件后保存该接手方的消费进度；先核对真实接手结果，重复确认不重复提交。"""
        return client.request(
            "POST", "/api/events/ack", {"consumer_id": consumer_id, "event_id": event_id}
        )

    @mcp.tool()
    def canvas_event_cursor(consumer_id: str) -> dict[str, Any]:
        """读取接手方已处理的事件位置，供重新连接后继续读取。"""
        return client.request(
            "GET", "/api/events/cursor?" + urlencode({"consumer_id": consumer_id})
        )

    @mcp.tool()
    def canvas_claim(run_id: str, host_tools: list[str]) -> dict[str, Any]:
        """独占接手一条已确认的 pending_agent 任务。返回固定输入、Skill 与完成令牌；claim 失败不能提交模型。"""
        return client.request("POST", f"/api/runs/{run_id}/claim", {"host_tools": host_tools})

    @mcp.tool()
    def canvas_complete(
        run_id: str,
        owner_token: str,
        status: str,
        outputs: list[dict[str, Any]] | None = None,
        error: str | None = None,
        provider_task_id: str | None = None,
        stage: str | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """回填实际媒体 {path,kind,name?}；status=succeeded/failed/unknown。结果会复制到项目成品位置。"""
        return client.request(
            "POST",
            f"/api/runs/{run_id}/complete",
            {
                "owner_token": owner_token,
                "status": status,
                "outputs": outputs,
                "error": error,
                "provider_task_id": provider_task_id,
                "stage": stage,
                "evidence": evidence,
            },
        )

    @mcp.tool()
    def canvas_cancel_pending(run_id: str) -> dict[str, Any]:
        """用户取消尚未开始的执行；不取消已提交的远端任务。"""
        return client.request("POST", f"/api/runs/{run_id}/cancel", {})

    @mcp.tool()
    def canvas_attention(run_id: str, state: str, reason: str) -> dict[str, Any]:
        """设置 active/paused/abandoned 跟进状态。暂停或放弃本地等待不会取消远端任务或释放未知占用。"""
        return client.request(
            "POST", f"/api/runs/{run_id}/attention", {"state": state, "reason": reason}
        )

    @mcp.tool()
    def canvas_progress(
        run_id: str,
        owner_token: str,
        stage: str,
        provider_task_id: str | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """提交前记录 submit，获得远端编号后记录 generation。其他阶段：input_validation/upload/collection/media_validation。"""
        return client.request(
            "POST",
            f"/api/runs/{run_id}/progress",
            {
                "owner_token": owner_token,
                "stage": stage,
                "provider_task_id": provider_task_id,
                "evidence": evidence,
            },
        )

    @mcp.tool()
    def canvas_handoff_recovery(
        run_id: str, reason: str, expected_updated_at: str
    ) -> dict[str, Any]:
        """显式交接丢失的恢复claim。需具体原因及最新run.updated_at；仅可恢复且已领取未解决时换新令牌，旧令牌失效，追加审计，不重生成。"""
        return client.request(
            "POST",
            f"/api/runs/{run_id}/handoff-recovery",
            {"reason": reason, "expected_updated_at": expected_updated_at},
        )

    @mcp.tool()
    def canvas_claim_recovery(run_id: str, reason: str) -> dict[str, Any]:
        """原接手方不可用时，独占核实一个 unknown 请求。只取得核实令牌，不能重新生成。"""
        return client.request("POST", f"/api/runs/{run_id}/claim-recovery", {"reason": reason})

    @mcp.tool()
    def canvas_reconcile(
        run_id: str,
        owner_token: str,
        status: str,
        evidence: dict[str, Any],
        outputs: list[dict[str, Any]] | None = None,
        provider_task_id: str | None = None,
    ) -> dict[str, Any]:
        """核实原任务结果，不重新生成。evidence={request_id:原请求编号,remote_status:与status相同,source:provider_history/provider_response/operator_confirmation,reason:核实依据}；成功必须附实际文件。"""
        return client.request(
            "POST",
            f"/api/runs/{run_id}/reconcile",
            {
                "owner_token": owner_token,
                "status": status,
                "evidence": evidence,
                "outputs": outputs,
                "provider_task_id": provider_task_id,
            },
        )

    @mcp.tool()
    def canvas_claim_review(run_id: str) -> dict[str, Any]:
        """独占领取已成功产物的内容审查，取得审片令牌。普通画布组件不强制调用。"""
        return client.request("POST", f"/api/runs/{run_id}/claim-review", {})

    @mcp.tool()
    def canvas_reopen_review(run_id: str, reason: str, expected_updated_at: str) -> dict[str, Any]:
        """仅重开已完成的 INCONCLUSIVE 审查。需具体原因和最新 run.updated_at；保留旧结论历史，返回新独占令牌，旧令牌失效。不会重新生成。"""
        return client.request(
            "POST",
            f"/api/runs/{run_id}/reopen-review",
            {"reason": reason, "expected_updated_at": expected_updated_at},
        )

    @mcp.tool()
    def canvas_review_derived(
        run_id: str,
        reason: str,
        expected_updated_at: str,
        decision: str,
        output_path: str,
        evidence: list[str],
        end_state: dict[str, Any] | None = None,
        unverified: list[str] | None = None,
    ) -> dict[str, Any]:
        """一次审查已 REJECT 视频的新后期派生，只有 ACCEPT/REJECT。需具体原因和最新 updated_at；新文件在原 run 目录且不同路径、不同内容，实际完整解码。旧拒绝与原媒体保留，未完成审片不可抢占；不生成，不需 claim 令牌。"""
        return client.request(
            "POST",
            f"/api/runs/{run_id}/review-derived",
            {
                "reason": reason,
                "expected_updated_at": expected_updated_at,
                "decision": decision,
                "output_path": output_path,
                "evidence": evidence,
                "end_state": end_state,
                "unverified": unverified,
            },
        )

    @mcp.tool()
    def canvas_review(
        run_id: str,
        owner_token: str,
        decision: str,
        output_path: str,
        evidence: list[str],
        end_state: dict[str, Any] | None = None,
        unverified: list[str] | None = None,
    ) -> dict[str, Any]:
        """记录 ACCEPT/REJECT/INCONCLUSIVE，绑定本 run 目录中的实际产物。evidence 写检查依据，end_state 写真实末态，unverified 写关键未核实项；未核实不能 ACCEPT。"""
        return client.request(
            "POST",
            f"/api/runs/{run_id}/review",
            {
                "owner_token": owner_token,
                "decision": decision,
                "output_path": output_path,
                "evidence": evidence,
                "end_state": end_state,
                "unverified": unverified,
            },
        )

    return mcp
