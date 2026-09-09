import { describe, expect, it } from 'vitest';
import { summarizeContinuations } from './continuations';
import type { ContinuationPlan } from './types';

function plan(overrides: Partial<ContinuationPlan> = {}): ContinuationPlan {
  return {
    id: 'plan-1',
    canvas_id: 'canvas-1',
    node_ids: ['node-1'],
    state: 'active',
    revision: 1,
    summary: {
      status: 'waiting',
      actions: [],
      blocked_items: [],
      nodes: [{ node_id: 'node-1', state: 'waiting', reason: '等待执行结果回填' }],
      allow_stop: false,
      reason: '等待结果',
    },
    ...overrides,
  };
}

describe('summarizeContinuations', () => {
  it('treats an empty plan collection as an unconfigured continuation feature', () => {
    expect(summarizeContinuations({ plans: [] })).toEqual({
      status: 'disabled',
      pendingCount: 0,
      blockedCount: 0,
      progressStalled: false,
      reason: null,
      items: [],
    });
  });

  it('maps the backend summary once while keeping counts and reasons', () => {
    const result = summarizeContinuations({ plans: [plan({
      summary: {
        status: 'actionable',
        actions: [{ kind: 'handle_unit', reason: '先处理执行单元结果' }],
        blocked_items: [],
        nodes: [],
        allow_stop: false,
        reason: '有可交接的下一步',
        stalled: true,
        stop_attempts: 2,
      },
      updated_at: '2026-09-10T10:30:00Z',
    })] });

    expect(result.status).toBe('awaiting_main_session');
    expect(result.pendingCount).toBe(1);
    expect(result.blockedCount).toBe(0);
    expect(result.progressStalled).toBe(true);
    expect(result.items[0]).toMatchObject({
      title: '接续计划 1',
      status: 'awaiting_main_session',
      pendingCount: 1,
      stopAttempts: 2,
      details: ['先处理执行单元结果'],
    });
  });

  it('maps waiting nodes to waiting-result and keeps blocked items visible', () => {
    const waiting = plan();
    const blocked = plan({
      id: 'plan-2',
      summary: {
        status: 'blocked',
        actions: [],
        blocked_items: [{ node_id: 'node-2', reason: '前段尚未 ACCEPT' }],
        nodes: [{ node_id: 'node-2', state: 'blocked', reason: '前段尚未 ACCEPT' }],
        allow_stop: true,
        reason: '范围中有节点被阻塞',
      },
    });
    const result = summarizeContinuations({ plans: [waiting, blocked] });

    expect(result.status).toBe('waiting_result');
    expect(result.pendingCount).toBe(1);
    expect(result.blockedCount).toBe(1);
    expect(result.items[0].status).toBe('waiting_result');
    expect(result.items[1]).toMatchObject({ status: 'blocked', blockedCount: 1 });
    expect(result.items[1].details).toEqual(['前段尚未 ACCEPT']);
  });

  it('lets stalled waiting progress surface as main-session attention', () => {
    const result = summarizeContinuations({ plans: [plan({
      summary: {
        status: 'waiting',
        actions: [],
        blocked_items: [],
        nodes: [],
        allow_stop: false,
        reason: '等待宿主长等待',
        stalled: true,
      },
    })] });

    expect(result.status).toBe('awaiting_main_session');
    expect(result.items[0].status).toBe('awaiting_main_session');
    expect(result.reason).toBe('等待宿主长等待');
  });

  it('keeps an active waiting plan in the in-progress state when no result is ready yet', () => {
    const result = summarizeContinuations({ plans: [plan({
      summary: {
        status: 'waiting',
        actions: [],
        blocked_items: [],
        nodes: [],
        allow_stop: false,
        reason: '等待宿主长等待',
      },
    })] });

    expect(result.status).toBe('in_progress');
    expect(result.items[0].status).toBe('in_progress');
  });

  it('preserves paused and complete plan states in the aggregate', () => {
    const paused = plan({
      state: 'paused',
      summary: { status: 'paused', actions: [], blocked_items: [], nodes: [], allow_stop: true, reason: '用户已暂停' },
    });
    const complete = plan({
      id: 'plan-2',
      summary: { status: 'complete', actions: [], blocked_items: [], nodes: [], allow_stop: true, reason: '全部完成' },
    });

    expect(summarizeContinuations({ plans: [paused] }).status).toBe('paused');
    expect(summarizeContinuations({ plans: [complete] }).status).toBe('completed');
  });
});
