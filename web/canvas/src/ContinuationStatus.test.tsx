// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ContinuationStatus, type ContinuationSummary } from './ContinuationStatus';

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
});
