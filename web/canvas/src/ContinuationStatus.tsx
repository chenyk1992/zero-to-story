import { useState } from 'react';
import { Icon } from './Icon';

export type ContinuationStatusKey =
  | 'disabled'
  | 'in_progress'
  | 'waiting_result'
  | 'awaiting_main_session'
  | 'blocked'
  | 'paused'
  | 'completed';

export type ContinuationLoadState = 'loading' | 'available' | 'unavailable';

/** A user-facing continuation row, already normalized by the API boundary. */
export interface ContinuationItem {
  id: string;
  title: string;
  status: ContinuationStatusKey;
  pendingCount: number;
  blockedCount: number;
  progressStalled: boolean;
  reason?: string | null;
  details?: string[];
  progress?: string | null;
  stopAttempts?: number;
  updatedAt?: string | null;
}

export interface ContinuationSummary {
  status: ContinuationStatusKey;
  pendingCount: number;
  blockedCount: number;
  progressStalled: boolean;
  reason?: string | null;
  items: ContinuationItem[];
}

export interface ContinuationStatusProps {
  state: ContinuationLoadState;
  summary?: ContinuationSummary;
  onRefresh?: () => void;
}

const STATUS_LABELS: Record<ContinuationStatusKey, string> = {
  disabled: '接续未启用',
  in_progress: '接续进行中',
  waiting_result: '等待结果',
  awaiting_main_session: '待主会话处理',
  blocked: '接续阻塞',
  paused: '接续已暂停',
  completed: '接续已完成',
};

function statusIcon(status: ContinuationStatusKey, state: ContinuationLoadState) {
  if (state === 'unavailable' || status === 'blocked') return 'alert' as const;
  if (status === 'completed') return 'check' as const;
  if (status === 'paused') return 'pause' as const;
  if (status === 'disabled') return 'history' as const;
  return 'history' as const;
}

function formatUpdatedAt(value?: string | null): string {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function metric(value: number): number {
  return Number.isFinite(value) && value >= 0 ? Math.round(value) : 0;
}

export function ContinuationStatus({ state, summary, onRefresh }: ContinuationStatusProps) {
  const [open, setOpen] = useState(false);
  const [expandedId, setExpandedId] = useState<string>();
  const current = summary || {
    status: 'disabled' as const,
    pendingCount: 0,
    blockedCount: 0,
    progressStalled: false,
    items: [],
  };
  const label = state === 'loading' ? '读取接续状态…' : state === 'unavailable' ? '接续状态不可用' : STATUS_LABELS[current.status];
  const hasAttention = state === 'unavailable' || current.blockedCount > 0 || current.progressStalled || current.status === 'awaiting_main_session';
  const panelId = 'continuation-status-details';

  return (
    <div className={`continuation-widget continuation-${state} continuation-${current.status}`}>
      <button
        className="continuation-trigger"
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
        title={label}
      >
        <Icon name={statusIcon(current.status, state)} size={14} />
        <span>{label}</span>
        {hasAttention && <i className="continuation-attention" aria-label="接续需要关注" />}
        <Icon name={open ? 'chevronUp' : 'chevronDown'} size={13} />
      </button>

      {open && <section id={panelId} className="continuation-popover" aria-label="接续状态详情">
        <div className="continuation-popover-heading">
          <div>
            <span className="continuation-eyebrow">主会话接续</span>
            <strong>{label}</strong>
          </div>
          {state === 'unavailable' && onRefresh && <button type="button" className="continuation-refresh" onClick={onRefresh}>重新读取</button>}
        </div>

        {state === 'loading' && <p className="continuation-empty">正在读取当前画布的接续状态…</p>}
        {state === 'unavailable' && <p className="continuation-empty">暂时无法读取接续状态，画布仍可编辑。</p>}
        {state === 'available' && current.status === 'disabled' && <p className="continuation-empty">当前画布未配置接续计划。</p>}
        {state === 'available' && current.status !== 'disabled' && <>
          <div className="continuation-metrics" aria-label="接续统计">
            <span>待处理 <b>{metric(current.pendingCount)}</b></span>
            <span className={current.blockedCount > 0 ? 'has-value' : ''}>阻塞 <b>{metric(current.blockedCount)}</b></span>
            <span>计划 <b>{current.items.length}</b></span>
          </div>
          {current.progressStalled && <p className="continuation-warning" role="status"><Icon name="alert" size={13} />进展停滞，需要主会话处理</p>}
          {current.reason && <p className="continuation-reason">{current.reason}</p>}
          {current.items.length > 0 && <ul className="continuation-list">
            {current.items.map((item) => {
              const itemPanelId = `continuation-item-${item.id}`;
              const itemOpen = expandedId === item.id;
              return (
                <li key={item.id} className={`continuation-item continuation-item-${item.status}`}>
                  <button
                    type="button"
                    className="continuation-item-trigger"
                    aria-expanded={itemOpen}
                    aria-controls={itemPanelId}
                    onClick={() => setExpandedId((value) => value === item.id ? undefined : item.id)}
                  >
                    <span className="continuation-item-title">{item.title}</span>
                    <span className="continuation-item-status">{STATUS_LABELS[item.status]}</span>
                    <Icon name={itemOpen ? 'chevronUp' : 'chevronDown'} size={12} />
                  </button>
                  {itemOpen && <div id={itemPanelId} className="continuation-item-details">
                    <div className="continuation-item-metrics"><span>待处理 <b>{metric(item.pendingCount)}</b></span><span>阻塞 <b>{metric(item.blockedCount)}</b></span>{item.progress && <span>进度 <b>{item.progress}</b></span>}</div>
                    {item.progressStalled && <p className="continuation-warning" role="status"><Icon name="alert" size={12} />进展停滞，需要主会话处理</p>}
                    {item.reason && <p className="continuation-reason">{item.reason}</p>}
                    {item.stopAttempts !== undefined && item.stopAttempts > 0 && <p className="continuation-updated">连续等待处理 {metric(item.stopAttempts)} 次</p>}
                    {item.details && item.details.length > 0 && <ul className="continuation-detail-list">{item.details.map((detail, index) => <li key={`${item.id}-detail-${index}`}>{detail}</li>)}</ul>}
                    {formatUpdatedAt(item.updatedAt) && <time className="continuation-updated" dateTime={item.updatedAt || undefined}>最近更新 {formatUpdatedAt(item.updatedAt)}</time>}
                  </div>}
                </li>
              );
            })}
          </ul>}
        </>}
      </section>}
    </div>
  );
}
