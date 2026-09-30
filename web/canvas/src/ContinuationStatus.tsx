import { useState } from 'react';
import { Icon } from './Icon';
import type { ProductionCountMetric, ProductionSummary, ProductionTimingMetric } from './types';
export type { ProductionSummary } from './types';

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
  productionSummary?: ProductionSummary;
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

function formatDuration(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds) || seconds < 0) return '暂无可靠记录';
  const totalMinutes = Math.floor(seconds / 60);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  const remainingSeconds = Math.floor(seconds % 60);
  if (hours > 0) return `${hours}小时${minutes}分`;
  if (totalMinutes > 0) return `${totalMinutes}分${remainingSeconds}秒`;
  return `${remainingSeconds}秒`;
}

function timingText(value: ProductionTimingMetric): string {
  if (value.state === 'unknown') return '暂无可靠记录';
  const duration = formatDuration(value.seconds);
  return value.state === 'partial' ? `${duration}（部分任务缺少记录）` : duration;
}

function countText(value: ProductionCountMetric): string {
  if (value.value === null || value.state === 'unknown') return '待记录';
  return value.state === 'partial' ? `${value.value}（部分缺记录）` : String(value.value);
}

const RUN_STATUS_LABELS: Record<string, string> = {
  queued: '排队中',
  pending_agent: '待 Agent 接手',
  running: '执行中',
  succeeded: '已生成',
  failed: '执行失败',
  unknown: '状态待核实',
  cancelled: '已取消',
};

const ATTENTION_LABELS: Record<string, string> = {
  active: '继续跟进',
  paused: '跟进已暂停',
  abandoned: '已停止跟进',
};

const REVIEW_LABELS: Record<string, string> = {
  ACCEPT: '内容已接受',
  REJECT: '内容未通过',
  INCONCLUSIVE: '内容待核实',
  pending: '等待内容审查',
  not_ready: '尚未进入审查',
};

const PHASE_LABELS: Record<string, string> = {
  queue: '排队跨度',
  resource_wait: '资源等待',
  preparation: '输入准备',
  upload: '上传素材',
  submission: '提交生成',
  generation: '生成阶段',
  collection_review: '结果回收与媒体检查',
  review: '审查观察跨度',
};

function ProductionDetails({ summary }: { summary: ProductionSummary }) {
  const statusEntries = Object.entries(summary.run_counts.by_status).filter(([, value]) => (value.value ?? 0) > 0);
  const attentionEntries = Object.entries(summary.run_counts.by_attention).filter(([key, value]) => (value.value ?? 0) > 0 && (key !== 'active' || value.value !== summary.run_counts.total.value));
  const reviewEntries = Object.entries(summary.review_counts).filter(([, value]) => (value.value ?? 0) > 0);
  const phaseEntries = Object.entries(summary.timings.phases);
  return <section className="continuation-production" aria-label="制作进度">
    <div className="continuation-production-heading"><strong>制作进度</strong><span>截至 {formatUpdatedAt(summary.as_of)}</span></div>
    {summary.scope_note && <p className="continuation-reason">{summary.scope_note}</p>}
    {summary.manifest_error && <p className="continuation-warning" role="status">编辑清单未能核验：{summary.manifest_error}</p>}
    <div className="continuation-metrics" aria-label="运行状态">
      {statusEntries.map(([key, value]) => <span key={key}>{RUN_STATUS_LABELS[key] || key} <b>{countText(value)}</b></span>)}
      {statusEntries.length === 0 && <span>当前范围 <b>暂无运行</b></span>}
    </div>
    {attentionEntries.length > 0 && <div className="continuation-metrics" aria-label="跟进状态">
      {attentionEntries.map(([key, value]) => <span key={key}>{ATTENTION_LABELS[key] || key} <b>{countText(value)}</b></span>)}
    </div>}
    {summary.current_stages.length > 0 && <p className="continuation-reason">当前阶段：{summary.current_stages.map((stage) => `${stage.label} ${stage.count}`).join('、')}</p>}
    <div className="continuation-production-times">
      <p>时间线跨度 <b>{timingText(summary.timings.timeline_elapsed)}</b></p>
      <p>任务跨度累计 <b>{timingText(summary.timings.cumulative_task_time)}</b></p>
    </div>
    <ul className="continuation-detail-list" aria-label="各阶段观察跨度">
      {phaseEntries.map(([key, value]) => <li key={key}>{PHASE_LABELS[key] || key}：{timingText(value)}</li>)}
    </ul>
    {reviewEntries.length > 0 && <p className="continuation-reason">内容检查：{reviewEntries.map(([key, value]) => `${REVIEW_LABELS[key] || key} ${countText(value)}`).join('、')}</p>}
    <p className="continuation-reason">片段 {countText(summary.production_counts.segments)} · 已接受来源 {countText(summary.production_counts.accepted_sources)} · 运行请求 {countText(summary.production_counts.requests)}</p>
    {summary.continuation.state === 'paused' && <p className="continuation-warning" role="status">制作接续已暂停{summary.continuation.reason ? `：${summary.continuation.reason}` : ''}</p>}
    {summary.blockers.length > 0 && <ul className="continuation-detail-list" aria-label="当前阻塞">
      {summary.blockers.map((blocker, index) => <li key={`${blocker.node_id}-${blocker.kind}-${index}`}>{blocker.node_id}：{blocker.reason}</li>)}
    </ul>}
  </section>;
}

export function ContinuationStatus({ state, summary, productionSummary, onRefresh }: ContinuationStatusProps) {
  const [open, setOpen] = useState(false);
  const [expandedId, setExpandedId] = useState<string>();
  const current = summary || {
    status: 'disabled' as const,
    pendingCount: 0,
    blockedCount: 0,
    progressStalled: false,
    items: [],
  };
  const productionStage = productionSummary?.current_stages[0]?.label;
  const productionLabel = productionSummary ? `制作进度${productionStage ? `：${productionStage}` : ''}` : undefined;
  const label = state === 'loading' ? '读取接续状态…' : state === 'unavailable' ? '接续状态不可用' : current.status === 'disabled' && productionLabel ? productionLabel : STATUS_LABELS[current.status];
  const hasAttention = state === 'unavailable' || current.blockedCount > 0 || current.progressStalled || current.status === 'awaiting_main_session' || Boolean(productionSummary?.blockers.length) || (productionSummary?.run_counts.by_status.unknown?.value ?? 0) > 0 || (productionSummary?.run_counts.by_status.failed?.value ?? 0) > 0;
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
          {onRefresh && <button type="button" className="continuation-refresh" onClick={onRefresh}>立即刷新</button>}
        </div>

        {state === 'loading' && <p className="continuation-empty">正在读取当前画布的接续状态…</p>}
        {state === 'unavailable' && <p className="continuation-empty">暂时无法读取接续状态，画布仍可编辑。</p>}
        {productionSummary && <ProductionDetails summary={productionSummary} />}
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
