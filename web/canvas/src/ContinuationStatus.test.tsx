// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ContinuationStatus, type ContinuationSummary, type ProductionSummary } from './ContinuationStatus';

let container: HTMLDivElement;
let root: Root;

const activeSummary: ContinuationSummary = {
  status: 'in_progress',
  pendingCount: 2,
  blockedCount: 1,
  progressStalled: true,
  reason: '等待主会话处理一个已完成的下游结果。',
  items: [
    {
      id: 'plan-a',
      title: '第一场镜头接续',
      status: 'waiting_result',
      pendingCount: 1,
      blockedCount: 0,
      progressStalled: false,
      progress: '2 / 4',
      reason: '等待执行结果回填。',
      updatedAt: '2026-09-10T10:30:00Z',
    },
    {
      id: 'plan-b',
      title: '第二场镜头接续',
      status: 'blocked',
      pendingCount: 1,
      blockedCount: 1,
      progressStalled: true,
      reason: '需要主会话决定下一步。',
    },
  ],
};

const productionSummary: ProductionSummary = {
  as_of: '2026-09-30T10:00:00Z',
  scope_note: '制作统计覆盖当前整张画布；接续状态来自最近计划。',
  manifest_error: '编辑清单缺少有效的 SHA-256 版本绑定',
  scope_node_ids: ['video-a'],
  run_counts: {
    total: { value: 2, state: 'observed', sources: ['run:r1', 'run:r2'] },
    by_status: {
      running: { value: 1, state: 'observed', sources: ['run:r1:status'] },
      failed: { value: 0, state: 'observed', sources: [] },
      unknown: { value: 1, state: 'observed', sources: ['run:r2:status'] },
    },
    by_attention: {
      active: { value: 1, state: 'observed', sources: ['run:r1:attention_state'] },
      paused: { value: 1, state: 'observed', sources: ['run:r2:attention_state'] },
    },
  },
  review_counts: {
    ACCEPT: { value: 1, state: 'observed', sources: ['run:r1:review'] },
    REJECT: { value: 0, state: 'observed', sources: [] },
  },
  current_stages: [{ stage: 'generation', label: '生成中', count: 1 }],
  continuation: { state: 'paused', reason: '等用户检查预览' },
  blockers: [{ node_id: 'video-a', reason: '等待参考素材', kind: 'explicit', source: 'test' }],
  timings: {
    timeline_elapsed: { state: 'observed', seconds: 3661, observed_runs: 2, unknown_runs: 0, sources: [] },
    cumulative_task_time: { state: 'partial', seconds: 1800, observed_runs: 1, unknown_runs: 1, sources: [] },
    phases: {
      review: { state: 'unknown', seconds: null, observed_runs: 0, unknown_runs: 2, sources: [], note: '缺少边界' },
      resource_wait: { state: 'unknown', seconds: null, observed_runs: 0, unknown_runs: 0, sources: [], note: '没有资源事件' },
    },
  },
  production_counts: {
    requests: { value: 2, state: 'observed', sources: [] },
    accepted_sources: { value: null, state: 'unknown', sources: [], note: '没有编辑清单' },
    segments: { value: null, state: 'unknown', sources: [], note: '没有编辑清单' },
  },
};

beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  container = document.createElement('div');
  document.body.append(container);
  root = createRoot(container);
});

afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
});

async function renderStatus(props: React.ComponentProps<typeof ContinuationStatus>) {
  await act(async () => root.render(<ContinuationStatus {...props} />));
}

describe('ContinuationStatus', () => {
  it('keeps an unconfigured canvas lightweight and readable', async () => {
    await renderStatus({
      state: 'available',
      summary: { status: 'disabled', pendingCount: 0, blockedCount: 0, progressStalled: false, items: [] },
    });

    const trigger = container.querySelector<HTMLButtonElement>('.continuation-trigger');
    expect(trigger?.textContent).toContain('接续未启用');
    expect(container.querySelector('.continuation-popover')).toBeNull();

    await act(async () => trigger?.click());
    expect(container.querySelector('.continuation-popover')?.textContent).toContain('当前画布未配置接续计划');
    expect(container.querySelector('.continuation-list')).toBeNull();
  });

  it('shows compact counts, stalled progress and expandable plan details', async () => {
    await renderStatus({ state: 'available', summary: activeSummary });
    const trigger = container.querySelector<HTMLButtonElement>('.continuation-trigger');
    expect(trigger?.textContent).toContain('接续进行中');
    expect(trigger?.querySelector('.continuation-attention')).not.toBeNull();

    await act(async () => trigger?.click());
    const panel = container.querySelector('.continuation-popover');
    expect(panel?.textContent).toContain('待处理 2');
    expect(panel?.textContent).toContain('阻塞 1');
    expect(panel?.textContent).toContain('进展停滞，需要主会话处理');
    expect(panel?.textContent).toContain('第一场镜头接续');
    expect(panel?.textContent).toContain('等待结果');
    expect(panel?.textContent).toContain('第二场镜头接续');
    expect(panel?.textContent).toContain('接续阻塞');

    const firstPlan = container.querySelector<HTMLButtonElement>('.continuation-item-trigger');
    expect(firstPlan?.getAttribute('aria-expanded')).toBe('false');
    await act(async () => firstPlan?.click());
    expect(firstPlan?.getAttribute('aria-expanded')).toBe('true');
    expect(container.querySelector('.continuation-item-details')?.textContent).toContain('等待执行结果回填');
    expect(container.querySelector('.continuation-item-details')?.textContent).toContain('2 / 4');
  });

  it('reports unavailable status without blocking the surrounding canvas', async () => {
    const onRefresh = vi.fn();
    await renderStatus({ state: 'unavailable', onRefresh });
    const trigger = container.querySelector<HTMLButtonElement>('.continuation-trigger');
    expect(trigger?.textContent).toContain('接续状态不可用');

    await act(async () => trigger?.click());
    expect(container.querySelector('.continuation-popover')?.textContent).toContain('画布仍可编辑');
    const refresh = container.querySelector<HTMLButtonElement>('.continuation-refresh');
    expect(refresh).not.toBeNull();
    await act(async () => refresh?.click());
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });

  it('uses explicit paused and completed labels', async () => {
    await renderStatus({
      state: 'available',
      summary: { status: 'paused', pendingCount: 0, blockedCount: 0, progressStalled: false, items: [] },
    });
    expect(container.querySelector('.continuation-trigger')?.textContent).toContain('接续已暂停');

    await renderStatus({
      state: 'available',
      summary: { status: 'completed', pendingCount: 0, blockedCount: 0, progressStalled: false, items: [] },
    });
    expect(container.querySelector('.continuation-trigger')?.textContent).toContain('接续已完成');
  });

  it('shows production progress when continuation is disabled, without hiding unknowns or conflating review rejects', async () => {
    await renderStatus({
      state: 'available',
      summary: { status: 'disabled', pendingCount: 0, blockedCount: 0, progressStalled: false, items: [] },
      productionSummary,
    });
    const trigger = container.querySelector<HTMLButtonElement>('.continuation-trigger');
    expect(trigger?.textContent).toContain('制作进度：生成中');
    expect(trigger?.querySelector('.continuation-attention')).not.toBeNull();
    await act(async () => trigger?.click());
    const panel = container.querySelector('.continuation-popover');
    expect(panel?.textContent).toContain('时间线跨度 1小时1分');
    expect(panel?.textContent).toContain('任务跨度累计 30分0秒（部分任务缺少记录）');
    expect(panel?.textContent).toContain('状态待核实 1');
    expect(panel?.textContent).toContain('跟进已暂停 1');
    expect(panel?.textContent).toContain('内容已接受 1');
    expect(panel?.textContent).toContain('制作接续已暂停：等用户检查预览');
    expect(panel?.textContent).toContain('video-a：等待参考素材');
    expect(panel?.textContent).toContain('片段 待记录');
    expect(panel?.textContent).toContain('审查观察跨度：暂无可靠记录');
    expect(panel?.textContent).toContain('当前整张画布');
    expect(panel?.textContent).toContain('清单未能核验');
  });
});
