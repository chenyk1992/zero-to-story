import type { ContinuationPlan, ContinuationPlanSummary, ContinuationsResponse } from './types';
import type { ContinuationItem, ContinuationStatusKey, ContinuationSummary } from './ContinuationStatus';

function planStatus(plan: ContinuationPlan): ContinuationStatusKey {
  const summary = plan.summary;
  if (plan.state === 'paused' || summary.status === 'paused') return 'paused';
  if (summary.status === 'actionable') return 'awaiting_main_session';
  if (summary.status === 'waiting') {
    if (summary.stalled) return 'awaiting_main_session';
    return summary.nodes.some((node) => node.state === 'waiting') ? 'waiting_result' : 'in_progress';
  }
  if (summary.status === 'blocked') return 'blocked';
  return 'completed';
}

function waitingNodeCount(summary: ContinuationPlanSummary): number {
  return summary.nodes.filter((node) => node.state === 'waiting').length;
}

function blockedNodeCount(summary: ContinuationPlanSummary): number {
  return summary.nodes.filter((node) => node.state === 'blocked').length;
}

function uniqueReasons(plan: ContinuationPlan): string[] {
  const reasons = [
    ...plan.summary.actions.map((action) => action.reason),
    ...plan.summary.blocked_items.map((item) => item.reason),
    ...plan.summary.nodes.map((node) => node.reason || ''),
  ].filter((reason): reason is string => Boolean(reason && reason.trim()));
  return [...new Set(reasons)].slice(0, 6);
}

function toItem(plan: ContinuationPlan, index: number): ContinuationItem {
  const summary = plan.summary;
  const blockedCount = Math.max(summary.blocked_items.length, blockedNodeCount(summary));
  const reasons = uniqueReasons(plan);
  return {
    id: plan.id,
    title: `接续计划 ${index + 1}`,
    status: planStatus(plan),
    pendingCount: summary.actions.length + waitingNodeCount(summary),
    blockedCount,
    progressStalled: summary.stalled === true,
    reason: summary.reason || reasons[0] || null,
    details: reasons,
    stopAttempts: summary.stop_attempts,
    updatedAt: plan.updated_at || null,
  };
}

function aggregateStatus(items: ContinuationItem[]): ContinuationStatusKey {
  if (items.some((item) => item.status === 'awaiting_main_session')) return 'awaiting_main_session';
  if (items.some((item) => item.status === 'waiting_result')) return 'waiting_result';
  if (items.some((item) => item.status === 'in_progress')) return 'in_progress';
  if (items.some((item) => item.status === 'blocked')) return 'blocked';
  if (items.some((item) => item.status === 'paused')) return 'paused';
  return 'completed';
}

function aggregateReason(items: ContinuationItem[], status: ContinuationStatusKey): string | null {
  return items.find((item) => item.status === status)?.reason || items.find((item) => item.reason)?.reason || null;
}

export function summarizeContinuations(response: ContinuationsResponse): ContinuationSummary {
  const plans = Array.isArray(response.plans) ? response.plans : [];
  if (plans.length === 0) {
    return { status: 'disabled', pendingCount: 0, blockedCount: 0, progressStalled: false, reason: null, items: [] };
  }
  const items = plans.map(toItem);
  const status = aggregateStatus(items);
  return {
    status,
    pendingCount: items.reduce((total, item) => total + item.pendingCount, 0),
    blockedCount: items.reduce((total, item) => total + item.blockedCount, 0),
    progressStalled: plans.some((plan) => plan.summary.stalled === true),
    reason: aggregateReason(items, status),
    items,
  };
}

