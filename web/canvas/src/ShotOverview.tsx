import type { Edge } from '@xyflow/react';
import { useMemo, useState } from 'react';
import { mediaUrl } from './api';
import { cardDescription } from './cardPresentation';
import { resolveMediaOutput, sortRuns } from './graph';
import { Icon } from './Icon';
import type { FlowNode, Run, RunOutput } from './types';
import { categoryLabelForNode, type StoryNodeData } from './workspace';
import './shot-overview.css';

export interface ShotOverviewProps {
  nodes: FlowNode[];
  edges: Edge[];
  runs: Run[];
  selectedId?: string;
  onSelect: (id: string) => void;
  onLocate: (id: string) => void;
  onPreview: (id: string, output?: RunOutput) => void;
  onAdd: () => void;
}

type ShotFilter = 'all' | 'ready' | 'draft';

const FILTERS: Array<{ value: ShotFilter; label: string }> = [
  { value: 'all', label: '全部' },
  { value: 'ready', label: '有成品' },
  { value: 'draft', label: '待生成' },
];

const RUN_LABELS: Record<Run['status'], string> = {
  queued: '排队中',
  pending_agent: '待执行',
  running: '生成中',
  succeeded: '已生成',
  failed: '生成失败',
  unknown: '状态待核实',
  cancelled: '已取消',
};

function isShot(node: FlowNode): boolean {
  const data = node.data as StoryNodeData;
  if (data.category === 'character' || data.category === 'document' || ['document', 'section', 'audio'].includes(data.nodeType)) return false;
  return data.nodeType === 'video' || data.nodeType === 'image' || data.category === 'storyboard' || data.category === 'board';
}

function visualKind(output?: RunOutput): 'image' | 'video' | undefined {
  if (!output?.path) return undefined;
  if (output.kind.toLowerCase().startsWith('image') || /\.(png|jpe?g|webp|gif)$/i.test(output.path)) return 'image';
  if (output.kind.toLowerCase().startsWith('video') || /\.(mp4|webm|mov|m4v)$/i.test(output.path)) return 'video';
  return undefined;
}

export function ShotOverview({ nodes, edges, runs, selectedId, onSelect, onLocate, onPreview, onAdd }: ShotOverviewProps) {
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<ShotFilter>('all');
  const shots = useMemo(() => {
    const orderedRuns = sortRuns(runs);
    return nodes.filter(isShot).map((node, index) => {
      const data = node.data as StoryNodeData;
      const resolved = resolveMediaOutput(node.id, nodes, edges, orderedRuns);
      const kind = visualKind(resolved);
      const output = kind ? resolved : undefined;
      const nodeRuns = orderedRuns.filter((run) => run.node_id === node.id);
      const outputRun = output && nodeRuns.find((run) => run.status === 'succeeded' && run.outputs?.[0]?.path === output.path);
      return {
        node, data, index, output, kind, latestRun: nodeRuns[0],
        panelId: typeof data.panel_id === 'string' ? data.panel_id.trim() : '',
        accepted: outputRun?.review?.decision === 'ACCEPT',
      };
    }).sort((left, right) => {
      if (left.panelId && right.panelId) return left.panelId.localeCompare(right.panelId, 'zh-CN', { numeric: true, sensitivity: 'base' }) || left.index - right.index;
      if (left.panelId) return -1;
      if (right.panelId) return 1;
      return left.index - right.index;
    });
  }, [nodes, edges, runs]);
  const normalizedQuery = query.trim().toLocaleLowerCase();
  const visibleShots = shots.filter((shot) => {
    if (filter === 'ready' && !shot.output) return false;
    if (filter === 'draft' && shot.output) return false;
    return !normalizedQuery || `${shot.data.label} ${shot.panelId}`.toLocaleLowerCase().includes(normalizedQuery);
  });
  const readyCount = shots.filter((shot) => shot.output).length;

  return (
    <section className="shot-overview" aria-label="镜头总览">
      <header className="shot-overview-header">
        <div>
          <span className="shot-overview-eyebrow"><Icon name="storyboard" size={14} />故事与画面</span>
          <h2>镜头总览 <span>{shots.length}</span></h2>
          <p>从一张画面，看到整个故事。</p>
        </div>
        {shots.length > 0 && <div className="shot-overview-progress"><strong>{readyCount}<span> / {shots.length}</span></strong><span>镜头有成品</span></div>}
      </header>

      {shots.length > 0 && <div className="shot-overview-toolbar">
        <div className="shot-overview-filters" role="group" aria-label="按成品筛选">
          {FILTERS.map((item) => <button type="button" key={item.value} aria-pressed={filter === item.value} onClick={() => setFilter(item.value)}>{item.label}</button>)}
        </div>
        <label className="shot-overview-search"><Icon name="search" size={15} /><input type="search" aria-label="搜索镜头标题或编号" placeholder="搜索标题或镜头编号" value={query} onChange={(event) => setQuery(event.target.value)} /></label>
      </div>}

      {shots.length === 0 ? <div className="shot-overview-empty">
        <span className="shot-overview-empty-icon"><Icon name="film" size={34} /></span>
        <h3>故事，从第一个镜头开始</h3>
        <p>添加视频草稿，准备你的第一段画面。</p>
        <button type="button" onClick={onAdd}><Icon name="plus" size={15} />添加视频草稿</button>
      </div> : visibleShots.length === 0 ? <div className="shot-overview-empty shot-overview-no-results">
        <Icon name="search" size={28} /><h3>没有找到对应镜头</h3><p>试试其他标题、编号，或调整筛选。</p>
        <button type="button" onClick={() => { setQuery(''); setFilter('all'); }}>查看全部镜头</button>
      </div> : <div className="shot-overview-grid">
        {visibleShots.map(({ node, data, panelId, output, kind, latestRun, accepted }) => {
          const title = data.label || '未命名镜头';
          const actualDuration = output?.metadata?.duration_ms;
          const duration = typeof actualDuration === 'number' && actualDuration > 0 ? `${Number((actualDuration / 1000).toFixed(1))} 秒` : data.duration ? `计划 ${data.duration} 秒` : '';
          const description = cardDescription(data);
          const status = latestRun?.status || (output ? 'available' : 'draft');
          const savedOutputNote = output && latestRun?.matches_current === false
            ? '草稿已修改，预览仍为已保存成品'
            : output && latestRun && latestRun.status !== 'succeeded' ? '保留上次成品' : '';
          return <article key={node.id} data-node-id={node.id} className={`shot-overview-card${selectedId === node.id ? ' is-selected' : ''}`} aria-label={title}>
            <button className="shot-overview-media" type="button" disabled={!output} onClick={() => onPreview(node.id, output)} aria-label={`预览 ${title}`}>
              {kind === 'image' && output ? <img src={mediaUrl(output.path)} alt={title} loading="lazy" /> : kind === 'video' && output ? <video src={mediaUrl(output.path)} muted playsInline preload="metadata" onLoadedMetadata={(event) => { const video = event.currentTarget; if (video.duration > 0) video.currentTime = Math.min(0.05, video.duration / 2); }} /> : <span className="shot-overview-placeholder"><Icon name={data.nodeType === 'video' ? 'film' : 'image'} size={30} /><span>画面待生成</span></span>}
              {output && <span className="shot-overview-preview-hint"><Icon name={kind === 'video' ? 'play' : 'expand'} size={13} />查看成品</span>}
            </button>
            <div className="shot-overview-card-body">
              <div className="shot-overview-card-meta"><span className="shot-overview-panel-id">{panelId || '未编号'}</span><span>{categoryLabelForNode(node)}</span></div>
              <h3 title={title}>{title}</h3>
              {description && <p className="shot-overview-description">{description}</p>}
              <div className="shot-overview-card-details"><span>{[data.aspect_ratio, duration].filter(Boolean).join(' · ') || '画面规格待设置'}</span><div className="shot-overview-statuses"><span className={`shot-overview-status status-${status}`}>{latestRun ? RUN_LABELS[latestRun.status] : output ? '有成品' : '待生成'}</span>{accepted && <span className="shot-overview-accepted"><Icon name="check" size={11} />已采用</span>}</div></div>
              {savedOutputNote && <p className="shot-overview-stale">{savedOutputNote}</p>}
            </div>
            <footer className="shot-overview-card-actions">
              <button type="button" onClick={() => onSelect(node.id)}>编辑</button>
              <button type="button" onClick={() => onLocate(node.id)} aria-label={`在画布中定位 ${title}`}><Icon name="fit" size={13} />画布定位</button>
              <button className="shot-overview-open" type="button" disabled={!output} onClick={() => onPreview(node.id, output)}>预览<Icon name="arrowUpRight" size={13} /></button>
            </footer>
          </article>;
        })}
      </div>}
      {shots.length > 0 && <p className="shot-overview-order-note">按镜头编号浏览 · 未编号镜头保留画布顺序</p>}
    </section>
  );
}
