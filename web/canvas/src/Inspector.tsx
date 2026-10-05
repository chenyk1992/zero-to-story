import { useMemo, useRef, useState, type ChangeEvent, type ReactNode, type Ref } from 'react';
import type { Edge } from '@xyflow/react';
import { capabilityLabel, hasExecutableSelection, isCapabilitySelectable } from './capabilities';
import { assetToOutput, resolveMediaOutput, sortRuns } from './graph';
import { mediaUrl } from './api';
import type { Capability, CapabilityField, CanvasNodeData, CanvasNodeType, FlowNode, Run, RunOutput } from './types';
import { CATEGORY_OPTIONS, categoryLabelForNode, isSectionNode, type GenerationSnapshot, type HistoryEntry, type StoryNodeData, type StoryNodePatch, type StoryNodeType } from './workspace';
import { Icon } from './Icon';
import './inspector.css';

interface InspectorProps {
  embedded?: boolean;
  node?: FlowNode;
  nodes: FlowNode[];
  edges: Edge[];
  capabilities: Capability[];
  runs: Run[];
  canExecute: boolean;
  saveBlocked: boolean;
  onUpdate: (patch: StoryNodePatch) => void;
  onUpdateOptions: (provider: string, key: string, value: string | number | boolean | undefined) => void;
  onMoveReference?: (edgeId: string, direction: -1 | 1) => void;
  onSelectNode: (nodeId: string) => void;
  onRemove: () => void;
  onExecute: () => void;
  onUploadAsset: (file: File) => Promise<void>;
  onImportAssetPath: () => Promise<void>;
  onCompositionChange: (composing: boolean) => void;
  onOpenPreview: (run: Run) => void;
  onOpenMedia: (output: Run['outputs'][number]) => void;
  onClose?: () => void;
}

const KIND_LABELS: Record<CanvasNodeType, string> = {
  asset: '素材组件',
  image: '图片创作卡',
  video: '视频创作卡',
  audio: '音频生成卡',
};
const STORY_KIND_LABELS: Record<StoryNodeType, string> = { ...KIND_LABELS, document: '文档组件', section: '分区组件' };

const TARGET_LABELS: Record<string, string> = {
  first_frame: '首帧',
  last_frame: '尾帧',
  reference_image: '图片参考',
  reference_video: '视频参考',
  reference_audio: '音频参考',
};

const RUN_STATUS_LABELS: Record<string, string> = {
  queued: '已确认',
  pending_agent: '已确认，待 Agent 执行',
  running: '生成中',
  succeeded: '生成完成',
  failed: '执行失败',
  unknown: '远端状态待核实',
  cancelled: '已取消未提交任务',
};

function stableSnapshotValue(value: unknown): string {
  if (value === undefined || value === null || value === '') return '∅';
  if (Array.isArray(value)) return `[${value.map(stableSnapshotValue).join(',')}]`;
  if (typeof value === 'object') {
    return `{${Object.entries(value as Record<string, unknown>).sort(([left], [right]) => left.localeCompare(right)).map(([key, item]) => `${key}:${stableSnapshotValue(item)}`).join('|')}}`;
  }
  return JSON.stringify(value);
}

function draftDiffersFromRun(data: StoryNodeData, run?: Run): boolean {
  if (!run) return false;
  if (run.matches_current === false) return true;
  const snapshot = run.snapshot;
  if (snapshot.provider !== data.provider || snapshot.model !== data.model || snapshot.mode !== data.mode || snapshot.prompt !== data.prompt) return true;
  const currentParameters: Record<string, unknown> = {
    duration: data.duration,
    aspect_ratio: data.aspect_ratio,
    megapixels: data.megapixels,
    ...(data.options[data.provider] || {}),
  };
  const snapshotParameters = snapshot.parameters || {};
  const keys = new Set([...Object.keys(currentParameters), ...Object.keys(snapshotParameters)]);
  return [...keys].some((key) => stableSnapshotValue(currentParameters[key]) !== stableSnapshotValue(snapshotParameters[key]));
}

function dataForNode(node: FlowNode, key: 'duration' | 'aspect_ratio' | 'megapixels'): unknown {
  return node.data[key];
}

function FieldLabel({ children, optional = false, required = false }: { children: ReactNode; optional?: boolean; required?: boolean }) {
  return <span className="field-label">{children}{required && <em className="required-mark">必填</em>}{optional && <em>可选</em>}</span>;
}

function Section({ title, children, collapsed = false, className = '', sectionRef }: { title: string; children: ReactNode; collapsed?: boolean; className?: string; sectionRef?: Ref<HTMLElement> }) {
  return (
    <section ref={sectionRef} className={`inspector-section${collapsed ? ' section-collapsed' : ''}${className ? ` ${className}` : ''}`}>
      <div className="section-title">
        <h3>{title}</h3>
      </div>
      {children}
    </section>
  );
}

function TextField({ label, value, onChange, placeholder, multiline = false, rows = 5, optional = false, required = false, readOnly = false, onCompositionStart, onCompositionEnd }: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  multiline?: boolean;
  rows?: number;
  optional?: boolean;
  required?: boolean;
  readOnly?: boolean;
  onCompositionStart?: () => void;
  onCompositionEnd?: () => void;
}) {
  return (
    <label className="field">
      <FieldLabel optional={optional} required={required}>{label}</FieldLabel>
      {multiline ? (
        <textarea
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onCompositionStart={onCompositionStart}
          onCompositionEnd={onCompositionEnd}
          placeholder={placeholder}
          readOnly={readOnly}
          rows={rows}
        />
      ) : (
        <input
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onCompositionStart={onCompositionStart}
          onCompositionEnd={onCompositionEnd}
          placeholder={placeholder}
          readOnly={readOnly}
        />
      )}
    </label>
  );
}

function NumberField({ label, value, onChange, min, max, step = 1, placeholder, optional = false, required = false }: {
  label: string;
  value?: number;
  onChange: (value: number | undefined) => void;
  min?: number;
  max?: number;
  step?: number;
  placeholder?: string;
  optional?: boolean;
  required?: boolean;
}) {
  return (
    <label className="field">
      <FieldLabel optional={optional} required={required}>{label}</FieldLabel>
      <input
        type="number"
        value={value ?? ''}
        min={min}
        max={max}
        step={step}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value === '' ? undefined : Number(event.target.value))}
      />
    </label>
  );
}

function SelectField({ label, value, options, onChange, disabled = false, optional = false, required = false }: {
  label: string;
  value: string;
  options: Array<{ value: string; label: string; disabled?: boolean }>;
  onChange: (value: string) => void;
  disabled?: boolean;
  optional?: boolean;
  required?: boolean;
}) {
  return (
    <label className="field">
      <FieldLabel optional={optional} required={required}>{label}</FieldLabel>
      <select value={value} onChange={(event) => onChange(event.target.value)} disabled={disabled}>
        {options.map((option) => <option disabled={option.disabled} key={option.value} value={option.value}>{option.label}</option>)}
      </select>
    </label>
  );
}

function IncomingSources({ node, nodes, edges, runs, onSelectNode, onMoveReference }: Pick<InspectorProps, 'node' | 'nodes' | 'edges' | 'runs' | 'onSelectNode' | 'onMoveReference'>) {
  if (!node) return null;
  const incoming = edges.filter((edge) => edge.target === node.id && edge.targetHandle !== 'related');
  if (!incoming.length) return <p className="muted-note input-empty-note"><Icon name="link" size={14} />还没有接入素材。可以从其他节点右侧的圆点拖到这里。</p>;
  const references = incoming.filter((edge) => edge.targetHandle === 'reference_image');
  let referenceNumber = 0;
  return (
    <div className="source-list">
      {incoming.map((edge) => {
        const source = nodes.find((item) => item.id === edge.source);
        const derivedId = edge.sourceHandle?.startsWith('output:') ? edge.sourceHandle.slice('output:'.length) : '';
        const derived = derivedId ? source?.data.derived_outputs?.find((item) => item.id === derivedId) : undefined;
        const sourceLabel = derived ? `${source?.data.label || '未知节点'} · ${derived.label || '派生输出'}` : (source?.data.label || '未知节点');
        const isReference = edge.targetHandle === 'reference_image';
        const sourceRun = sortRuns(runs).find((run) => run.node_id === edge.source && run.status === 'succeeded'
          && (!edge.data?.source_run_id || run.id === edge.data.source_run_id));
        const count = derived || edge.data?.require_accept ? 1 : Math.max(1, sourceRun?.outputs.filter((output) => output.kind === 'image').length || 0);
        const firstNumber = referenceNumber + 1;
        if (isReference) referenceNumber += count;
        const referenceLabel = count === 1 ? `图 ${firstNumber}` : `图 ${firstNumber}–${referenceNumber}`;
        const position = references.findIndex((item) => item.id === edge.id);
        return (
          <div key={edge.id}>
          <button className="source-chip" type="button" onClick={() => source && onSelectNode(source.id)}>
            <Icon name="link" size={14} />
            <span>{isReference ? `${referenceLabel} · ` : ''}{sourceLabel}</span>
            <small><Icon name="arrowUpRight" size={12} />{TARGET_LABELS[edge.targetHandle || ''] || '输入'}</small>
          </button>
          {isReference && onMoveReference && <div className="reference-order">
            <button type="button" disabled={position === 0} onClick={() => onMoveReference(edge.id, -1)} aria-label={`${referenceLabel}上移`}>上移</button>
            <button type="button" disabled={position === references.length - 1} onClick={() => onMoveReference(edge.id, 1)} aria-label={`${referenceLabel}下移`}>下移</button>
          </div>}
          </div>
        );
      })}
    </div>
  );
}

function RelatedComponents({ node, nodes, edges, onSelectNode }: Pick<InspectorProps, 'node' | 'nodes' | 'edges' | 'onSelectNode'>) {
  const [collapsed, setCollapsed] = useState(true);
  if (!node) return null;
  const related = Array.from(new Map(edges
    .filter((edge) => edge.targetHandle === 'related' && (edge.source === node.id || edge.target === node.id))
    .map((edge) => {
      const incoming = edge.target === node.id;
      const other = nodes.find((item) => item.id === (incoming ? edge.source : edge.target));
      return other && !isSectionNode(other) ? { id: `${edge.id}-${other.id}`, node: other, direction: incoming ? '来自' : '关联到' } : undefined;
    })
    .filter((item): item is { id: string; node: FlowNode; direction: string } => Boolean(item))
    .map((item) => [`${item.node.id}-${item.direction}`, item] as const)).values());

  return (
    <Section title={`关联组件${related.length ? `（${related.length}）` : ''}`} className="related-section">
      <button className="collapse-button related-toggle" type="button" onClick={() => setCollapsed((value) => !value)} aria-expanded={!collapsed}>
        <span>{collapsed ? '展开关联组件' : '收起关联组件'}</span><Icon name={collapsed ? 'chevronDown' : 'chevronUp'} size={15} />
      </button>
      {!collapsed && (related.length ? (
        <div className="source-list related-list">
          {related.map(({ id, node: other, direction }) => {
            const otherData = other.data as unknown as StoryNodeData;
            return (
              <button className="source-chip related-chip" type="button" key={id} onClick={() => onSelectNode(other.id)}>
                <Icon name="link" size={14} />
                <span className="related-chip-copy"><strong>{otherData.label || '未命名组件'}</strong><small>{categoryLabelForNode({ data: otherData })}{otherData.panel_id ? ` · ${otherData.panel_id}` : ''}</small></span>
                <small className="related-direction">{direction}</small>
              </button>
            );
          })}
        </div>
      ) : <p className="muted-note">还没有资料关联。可以把其他组件的输出圆点拖到这个组件左侧的“关联”端口。</p>)}
    </Section>
  );
}

function CapabilityFieldEditor({ field, value, onChange }: { field: CapabilityField; value: string | number | boolean | undefined; onChange: (value: string | number | boolean | undefined) => void }) {
  const effectiveValue = field.required ? value : value ?? field.default;
  const defaultHint = field.default === undefined ? undefined : `默认值 ${String(field.default)}`;
  const selectPlaceholder = field.required ? defaultHint || '请选择' : '未设置';
  if (field.type === 'number' && field.values) {
    return <SelectField label={field.label} value={String(effectiveValue ?? '')} options={[{ value: '', label: selectPlaceholder }, ...field.values.map((item) => ({ value: String(item), label: String(item) }))]} onChange={(item) => onChange(item === '' ? undefined : Number(item))} optional={!field.required} required={field.required} />;
  }
  if (field.type === 'boolean') {
    return <label className="toggle-field"><input type="checkbox" checked={Boolean(effectiveValue)} onChange={(event) => onChange(event.target.checked)} /><span>{field.label}</span></label>;
  }
  if (field.type === 'select') {
    return <SelectField label={field.label} value={String(effectiveValue ?? '')} options={[{ value: '', label: selectPlaceholder }, ...(field.options || [])]} onChange={onChange} optional={!field.required} required={field.required} />;
  }
  if (field.type === 'number') {
    return <NumberField label={field.label} value={typeof effectiveValue === 'number' ? effectiveValue : effectiveValue === undefined || effectiveValue === '' ? undefined : Number(effectiveValue)} min={field.min} max={field.max} step={field.integer ? 1 : undefined} placeholder={field.required ? defaultHint : undefined} onChange={onChange} optional={!field.required} required={field.required} />;
  }
  return <TextField label={field.label} value={String(effectiveValue ?? '')} onChange={onChange} placeholder={field.required ? defaultHint : undefined} multiline={field.multiline} optional={!field.required} required={field.required} />;
}

function SettingsDetails({ embedded, title, className = '', children }: { embedded: boolean; title: string; className?: string; children: ReactNode }) {
  return embedded ? (
    <details className={`node-settings-details ${className}`}>
      <summary>{title}</summary>
      {children}
    </details>
  ) : children;
}

export function Inspector({ embedded = false, node, nodes, edges, capabilities, runs, canExecute, saveBlocked, onUpdate, onUpdateOptions, onMoveReference, onSelectNode, onRemove, onExecute, onUploadAsset, onImportAssetPath, onCompositionChange, onOpenPreview, onOpenMedia, onClose }: InspectorProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const promptRef = useRef<HTMLElement>(null);
  const inputRef = useRef<HTMLElement>(null);
  const routeRef = useRef<HTMLElement>(null);
  const outputRef = useRef<HTMLElement>(null);
  const [reorderedRun, setReorderedRun] = useState<string>();
  const [uploading, setUploading] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showStoryboard, setShowStoryboard] = useState(false);
  const [showMediaImport, setShowMediaImport] = useState(false);
  const [showStoryContext, setShowStoryContext] = useState(false);
  const [showAssetPath, setShowAssetPath] = useState(false);
  const [composing, setComposing] = useState(false);

  const providerCaps = useMemo(() => capabilities.filter((capability) => capability.node_types.includes((node?.data.nodeType || 'video') as CanvasNodeType)), [capabilities, node?.data.nodeType]);
  const currentCapability = providerCaps.find((capability) => capability.id === node?.data.provider);
  const providerOptions = providerCaps.length
    ? [
      { value: '', label: '请选择生成方式', disabled: false },
      ...providerCaps.map((capability) => ({
        value: capability.id,
        label: capabilityLabel(capability),
        disabled: !isCapabilitySelectable(capability, (node?.data.nodeType || 'video') as CanvasNodeType),
      })),
      ...(node?.data.provider && !currentCapability
        ? [{ value: node.data.provider, label: `${node.data.provider}（当前配置不可用）`, disabled: true }]
        : []),
    ]
    : node?.data.provider
      ? [{ value: node.data.provider, label: `${node.data.provider}（等待能力信息）`, disabled: false }]
      : [{ value: '', label: '请选择生成方式', disabled: false }];
  const modelOptions = currentCapability?.models?.map((option) => ({ value: option.id, label: option.label })) || [];
  const modeOptions = currentCapability?.modes?.map((option) => ({ value: option.id, label: option.label })) || [];
  const applicable = (field: CapabilityField) => !field.modes || field.modes.includes(node?.data.mode || '');
  const dynamicSpecFields = currentCapability?.fields?.filter((field) => applicable(field) && field.group === 'specs' && !['duration', 'aspect_ratio', 'megapixels'].includes(field.key)) || [];
  const advancedFields = currentCapability?.fields?.filter((field) => applicable(field) && field.group === 'advanced') || [];
  const inactiveFields = currentCapability?.fields?.filter((field) => !applicable(field)
    && node?.data.options[node.data.provider]?.[field.key] !== undefined
    && node?.data.options[node.data.provider]?.[field.key] !== '') || [];
  const durationField = currentCapability?.fields.find((field) => field.key === 'duration');
  const aspectField = currentCapability?.fields.find((field) => field.key === 'aspect_ratio');
  const megapixelsField = currentCapability?.fields.find((field) => field.key === 'megapixels');
  const unsupportedCommonFields = currentCapability && currentCapability.fields.length > 0
    ? (['duration', 'aspect_ratio', 'megapixels'] as const).filter((key) => node && dataForNode(node, key) !== undefined && !currentCapability.fields.some((field) => field.key === key && applicable(field)))
    : [];
  const orderedRuns = useMemo(() => sortRuns(runs), [runs]);
  const orderedLatestRun = useMemo(() => orderedRuns.find((run) => run.node_id === node?.id), [orderedRuns, node?.id]);
  const orderedLatestSuccess = useMemo(() => orderedRuns.find((run) => run.node_id === node?.id && run.status === 'succeeded' && run.outputs?.length), [orderedRuns, node?.id]);
  const linkedMedia = useMemo(() => node ? resolveMediaOutput(node.id, nodes, edges, runs) : undefined, [node, nodes, edges, runs]);

  if (!node) {
    if (embedded) return null;
    return (
      <aside className="inspector empty-inspector">
        <div className="empty-inspector-art"><Icon name="panelRight" size={22} /></div>
        <h2>选中一个组件</h2>
        <p>从左侧拖入组件，或者点击组件将它放到画布中央。</p>
        <div className="shortcut-note"><Icon name="hand" size={14} />使用抓手，或按住空格拖动来平移画布</div>
        {onClose && <button className="empty-close-button" type="button" onClick={onClose}><Icon name="close" size={15} />关闭编辑栏</button>}
      </aside>
    );
  }

  const data = node.data as unknown as StoryNodeData;
  const isGeneration = data.nodeType === 'image' || data.nodeType === 'video' || data.nodeType === 'audio';
  const hasInputSection = isGeneration && (data.nodeType !== 'audio' || data.mode === 'clone' || edges.some((edge) => edge.target === node.id && edge.targetHandle === 'reference_audio'));
  const isMusic = data.nodeType === 'audio' && data.provider === 'comfy-minimax-music';
  const referenceRunKey = orderedLatestRun ? `${node.id}:${orderedLatestRun.id}` : undefined;
  const draftChanged = Boolean((referenceRunKey && reorderedRun === referenceRunKey) || data.resultChanged || draftDiffersFromRun(data, orderedLatestRun));
  const effectiveRunStatus = orderedLatestRun?.status || data.runStatus;
  const effectiveRunError = orderedLatestRun?.error || data.runError;
  const selectionReady = hasExecutableSelection(data.provider, data.model, data.mode, data.nodeType as CanvasNodeType, capabilities, data.options[data.provider] || {});
  const currentOutput = orderedLatestSuccess?.outputs[0] || linkedMedia;
  const importPath = data.import_path ?? data.asset?.path ?? '';
  const historyEntries: HistoryEntry[] = [
    ...(data.history || []),
    ...(data.runHistory || [])
      .filter((run) => run.id !== orderedLatestSuccess?.id && run.status === 'succeeded' && run.outputs?.length)
      .map((run) => ({
        id: `run-${run.id}`,
        label: run.outputs[0].name || '历史成功成品',
        asset: { path: run.outputs[0].path, kind: run.outputs[0].kind, name: run.outputs[0].name || '历史成功成品' },
        generation_snapshot: run.snapshot,
        status: '历史成功',
      })),
  ];
  const updatePrompt = (prompt: string) => onUpdate({ prompt });
  const updateLabel = (label: string) => onUpdate({ label });
  const handleAssetUpload = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      await onUploadAsset(file);
    } finally {
      setUploading(false);
      event.target.value = '';
    }
  };

  const beginComposition = () => { setComposing(true); onCompositionChange(true); };
  const endComposition = () => { setComposing(false); onCompositionChange(false); };
  const scrollToSection = (target: HTMLElement | null) => {
    if (!target || !scrollRef.current?.contains(target)) return;
    const options: ScrollIntoViewOptions & { container: 'nearest' } = {
      block: 'start', inline: 'nearest', container: 'nearest',
      behavior: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth',
    };
    target.scrollIntoView(options);
  };
  const Container = embedded ? 'div' : 'aside';
  const information = <>
    {data.nodeType !== 'section' && (
      <Section title="故事关联" className="story-section">
        <button className="collapse-button" type="button" onClick={() => setShowStoryContext((value) => !value)} aria-expanded={showStoryContext}>
          <span>{showStoryContext ? '收起故事信息' : data.category || data.panel_id || data.description ? '展开故事信息（已有内容）' : '展开故事信息'}</span>
          <Icon name={showStoryContext ? 'chevronUp' : 'chevronDown'} size={15} />
        </button>
        {showStoryContext && <div className="story-fields">
          <SelectField label="资产分类" value={data.category || ''} options={CATEGORY_OPTIONS} onChange={(category) => onUpdate({ category })} />
          <TextField label="镜头 / 角色编号" value={data.panel_id || ''} onChange={(panel_id) => onUpdate({ panel_id })} placeholder="例如：P06 / 林默" optional />
          {!embedded && <TextField label="说明" value={data.description || ''} onChange={(description) => onUpdate({ description })} placeholder="它在这一章里的用途或状态" multiline rows={3} optional onCompositionStart={beginComposition} onCompositionEnd={endComposition} />}
        </div>}
      </Section>
    )}
    {data.nodeType !== 'section' && <RelatedComponents node={node} nodes={nodes} edges={edges} onSelectNode={onSelectNode} />}
    {embedded && <button className="inline-remove-button danger-hover" type="button" onClick={onRemove} aria-label="删除组件"><Icon name="trash" size={13} />删除组件</button>}
  </>;

  return (
    <Container className={`inspector${embedded ? ' inspector-inline nodrag nowheel' : ''}`} aria-label={embedded ? '卡片设置' : '组件编辑栏'}
      onPointerDown={embedded ? (event) => event.stopPropagation() : undefined}
      onKeyDown={embedded ? (event) => event.stopPropagation() : undefined}
      onClick={embedded ? (event) => event.stopPropagation() : undefined}>
      {!embedded && <div className="inspector-topline">
        <div className="inspector-title-wrap">
          <span className={`inspector-kind-icon kind-${data.nodeType}`}>
            <Icon name={data.nodeType === 'image' ? 'image' : data.nodeType === 'video' ? 'video' : data.nodeType === 'audio' ? 'audio' : data.nodeType === 'asset' ? 'asset' : data.nodeType === 'document' ? 'document' : 'section'} size={17} />
          </span>
          <div className="inspector-heading-copy"><span className="inspector-kicker">编辑组件</span><h2>{STORY_KIND_LABELS[data.nodeType] || '组件设置'}</h2><span className="inspector-node-label">{data.label || '未命名组件'}</span></div>
        </div>
        <div className="inspector-header-actions">
          {onClose && <button className="icon-button" type="button" onClick={onClose} title="收起编辑栏" aria-label="收起编辑栏"><Icon name="close" size={16} /></button>}
          <button className="icon-button danger-hover" type="button" onClick={onRemove} title="删除组件" aria-label="删除组件"><Icon name="trash" size={16} /></button>
        </div>
      </div>}
      {!embedded && isGeneration && <nav className="inspector-section-nav" aria-label="编辑栏快捷导航">
        <button type="button" onClick={() => scrollToSection(promptRef.current)}>创作</button>
        {hasInputSection && <button type="button" onClick={() => scrollToSection(inputRef.current)}>输入</button>}
        <button type="button" onClick={() => scrollToSection(routeRef.current)}>参数</button>
        {currentOutput && <button type="button" onClick={() => scrollToSection(outputRef.current)}>成品</button>}
      </nav>}
      {embedded && data.nodeType === 'asset' && <div className="inline-asset-controls">
        <div className="upload-row">
          <button className="outline-button" type="button" onClick={() => fileRef.current?.click()} disabled={uploading || Boolean(orderedLatestSuccess)}><Icon name="upload" size={14} />{uploading ? '上传中…' : data.asset ? '替换素材' : '上传素材'}</button>
          <button className="asset-path-toggle" type="button" onClick={() => setShowAssetPath((value) => !value)} aria-expanded={showAssetPath}>路径导入<Icon name={showAssetPath ? 'chevronUp' : 'chevronDown'} size={13} /></button>
        </div>
        <input ref={fileRef} className="visually-hidden" type="file" accept="image/*,video/*,audio/*" onChange={handleAssetUpload} />
        {showAssetPath && <div className="asset-path-import">
          <TextField label="本地文件路径" value={importPath} onChange={(import_path) => onUpdate({ import_path })} placeholder="C:\\素材\\reference.png" />
          <button className="outline-button" type="button" onClick={() => void onImportAssetPath()} disabled={uploading || Boolean(orderedLatestSuccess) || !importPath}><Icon name="link" size={14} />导入路径</button>
        </div>}
      </div>}
      <SettingsDetails embedded={embedded && !isGeneration} title={data.nodeType === 'section' ? '分区设置' : '更多信息'} className="node-info-details">
      <div ref={scrollRef} className="inspector-scroll">
        {!embedded && <Section title="基本信息" className="identity-section">
          <TextField label="组件名称" value={data.label} onChange={updateLabel} placeholder={STORY_KIND_LABELS[data.nodeType] || '组件'} />
        </Section>}

        {!embedded && isGeneration && (
          <Section title="提示词" className="prompt-section" sectionRef={promptRef}>
            <TextField label={data.nodeType === 'image' ? '图片提示词' : isMusic ? '音乐描述' : data.nodeType === 'audio' ? '逐字台词' : '视频提示词'} value={data.prompt} onChange={updatePrompt} placeholder={data.nodeType === 'image' ? '描述想要的画面…' : isMusic ? '描述曲风、人声、编曲和情绪变化…' : data.nodeType === 'audio' ? '输入需要合成的台词，保持文字原样…' : '描述主体、动作、镜头运动和风格…'} multiline rows={6} onCompositionStart={beginComposition} onCompositionEnd={endComposition} />
            <p className="field-help prompt-help">保存会更新草稿；确认执行后才会固定本次输入。</p>
          </Section>
        )}

        {data.nodeType === 'document' && (
          <Section title="文档内容">
            {!embedded && <TextField label="文档正文" value={data.content || ''} onChange={(content) => onUpdate({ content })} placeholder="输入故事板、电影画面分镜板或章节说明…" multiline rows={16} onCompositionStart={beginComposition} onCompositionEnd={endComposition} />}
            <TextField label="来源文件" value={data.source_path || ''} onChange={(source_path) => onUpdate({ source_path })} placeholder="可选的原始文件路径" optional />
            <p className="field-help">文档只保存到当前画布引用，编辑不会改写原始文件。</p>
          </Section>
        )}

        {data.nodeType === 'section' && (
          <Section title="分区设置">
            {!embedded && <TextField label="分区说明" value={data.description || ''} onChange={(description) => onUpdate({ description })} placeholder="例如：P06 · 车站月台" multiline rows={3} optional onCompositionStart={beginComposition} onCompositionEnd={endComposition} />}
            <div className="field-grid two-cols">
              <NumberField label="宽度" value={data.width} min={240} max={2400} step={16} onChange={(width) => onUpdate({ width })} />
              <NumberField label="高度" value={data.height} min={160} max={1800} step={16} onChange={(height) => onUpdate({ height })} />
            </div>
            <p className="field-help">分区是画布背景范围，不会参与生成任务或提交执行。</p>
          </Section>
        )}

        {data.nodeType === 'asset' && !embedded && (
          <Section title="素材内容">
              <div className="upload-row"><button className="outline-button" type="button" onClick={() => fileRef.current?.click()} disabled={uploading || Boolean(orderedLatestSuccess)}><Icon name="upload" size={14} />{uploading ? '上传中…' : '上传文件'}</button><button className="outline-button" type="button" onClick={() => void onImportAssetPath()} disabled={uploading || Boolean(orderedLatestSuccess) || !importPath}><Icon name="link" size={14} />导入路径</button><span>或填写本地路径</span></div>
            <input ref={fileRef} className="visually-hidden" type="file" accept="image/*,video/*,audio/*" onChange={handleAssetUpload} />
            <TextField label="导入路径" value={importPath} onChange={(import_path) => onUpdate({ import_path })} placeholder="C:\\素材\\reference.png" optional />
            {data.asset && <div className="asset-status"><span className="status-dot success" />{data.asset.name}<small>{data.asset.kind}</small></div>}
            {!embedded && linkedMedia && <OutputPreview output={linkedMedia} title="素材预览" status="可预览" help="点击查看这份已导入的素材。" onOpen={() => onOpenMedia(linkedMedia)} />}
            {data.generation_snapshot && <SnapshotDetails snapshot={data.generation_snapshot as GenerationSnapshot} title="原成品使用的参数" />}
            <p className="field-help">点击“上传文件”添加素材，或填写本地路径后点击“导入路径”。素材会保存到当前节点。</p>
          </Section>
        )}
        {data.nodeType === 'asset' && embedded && data.generation_snapshot && <SnapshotDetails snapshot={data.generation_snapshot as GenerationSnapshot} title="原成品使用的参数" />}

        {(data.nodeType === 'image' || data.nodeType === 'video' || data.nodeType === 'audio') && (
          <>
            <SettingsDetails embedded={embedded} title="生成设置">
            <div className="node-generation-fields">
            {hasInputSection && <Section title="输入素材" className="input-section" sectionRef={inputRef}>
              <IncomingSources node={node} nodes={nodes} edges={edges} runs={runs} onSelectNode={onSelectNode} onMoveReference={onMoveReference ? (edgeId, direction) => {
                setReorderedRun(referenceRunKey);
                onMoveReference(edgeId, direction);
              } : undefined} />
              {data.provider === 'comfy-qwen-image' && <p className="field-help">最多 10 张输入图，按显示顺序对应 &lt;image1&gt;～&lt;image10&gt;。编辑时第 1 张是待编辑图，其余为辅助参考；请在提示词写清每张图的用途。调整顺序后也请检查提示词中的编号。</p>}
            </Section>}
            {(data.nodeType === 'video' || data.nodeType === 'image' || data.nodeType === 'audio') && (
              <>
                <Section title="生成方式" className="route-section" sectionRef={routeRef}>
                  <SelectField label={embedded ? '生成服务' : '后端'} value={data.provider} options={providerOptions} onChange={(provider) => onUpdate({ provider, model: '', mode: '' })} />
                  {currentCapability?.reason && !currentCapability.available && <p className="capability-warning">{currentCapability.reason}</p>}
                  {modelOptions.length > 0 && <SelectField label="模型" value={data.model} options={[{ value: '', label: modelOptions.length === 1 ? '请选择模型' : '请选择模型' }, ...modelOptions]} onChange={(model) => onUpdate({ model })} optional={modelOptions.length !== 1} required={!data.model} />}
                  {modeOptions.length > 0 && <SelectField label="模式" value={data.mode} options={[{ value: '', label: '请选择模式' }, ...modeOptions]} onChange={(mode) => onUpdate({ mode })} optional={!data.mode} required={!data.mode} />}
                  {!currentCapability && <p className="field-help">能力信息尚未返回时只保留通用配置；执行前服务端仍会再次校验。</p>}
                  {inactiveFields.map((field) => <div className="unsupported-field-warning" key={field.key}>当前模式不支持{field.label}。已保留当前值；请清空后再执行。<button type="button" onClick={() => onUpdateOptions(data.provider, field.key, undefined)}>清空</button></div>)}
                </Section>
                <Section title={data.nodeType === 'video' ? '视频规格' : isMusic ? '音乐规格' : data.nodeType === 'audio' ? '语音规格' : '图片规格'} className="specs-section">
                  <div className="field-grid two-cols">
                    {data.nodeType === 'video' && <NumberField label="时长（秒）" value={data.duration} min={durationField?.min ?? 1} max={durationField?.max ?? 60} step={durationField?.integer ? 1 : 0.1} onChange={(duration) => onUpdate({ duration })} optional={!durationField?.required} required={durationField?.required} />}
                    {data.nodeType !== 'audio' && (!aspectField || applicable(aspectField)) && (aspectField?.options?.length ? <SelectField label="画幅比例" value={data.aspect_ratio || ''} options={[{ value: '', label: aspectField.required ? '请选择' : '未设置' }, ...aspectField.options]} onChange={(aspect_ratio) => onUpdate({ aspect_ratio })} optional={!aspectField.required} required={aspectField.required} /> : <TextField label="画幅比例" value={data.aspect_ratio || ''} onChange={(aspect_ratio) => onUpdate({ aspect_ratio })} placeholder="9:16" optional={!aspectField?.required} required={aspectField?.required} />)}
                  </div>
                  {data.nodeType !== 'audio' && (data.nodeType === 'video' || megapixelsField && applicable(megapixelsField)) && <NumberField label="生成像素预算（MP）" value={data.megapixels} min={megapixelsField?.min ?? 0.01} max={megapixelsField?.max ?? 10} step={0.01} onChange={(megapixels) => onUpdate({ megapixels })} placeholder={megapixelsField?.required ? '请输入像素预算' : '由生成方式决定'} optional={!megapixelsField?.required} required={megapixelsField?.required} />}
                  {data.nodeType === 'audio' ? <p className="field-help">{isMusic ? '音乐描述与歌词分别保存；最长生成时长是上限，采用实际歌曲前请听审。' : '按原文合成台词；语音角色、语言和语速由当前能力设置。'}</p> : <p className="field-help">{data.nodeType === 'video' ? '画幅比例和像素预算是两项设置。当前方式将按能力信息判断必填项。' : data.provider === 'comfy-qwen-image' ? (data.mode === 'edit' ? '编辑沿用第 1 张图处理后的尺寸，并对齐 32 像素；无需设置新画幅。' : '画幅与像素预算共同决定输出尺寸，并对齐 32 像素。1 MP 为约 1024×1024 像素；默认 25 步。') : '选择图片画幅偏好；连接参考图后，请在“模式”中选择参考图片编辑。'}</p>}
                  {data.nodeType !== 'audio' && unsupportedCommonFields.map((key) => <div className="unsupported-field-warning" key={key}>当前方式不支持{key === 'megapixels' ? '生成像素预算' : key === 'duration' ? '时长' : '画幅比例'}。已保留当前值；请清空后再执行。<button type="button" onClick={() => onUpdate({ [key]: undefined })}>清空</button></div>)}
                  {dynamicSpecFields.map((field) => <CapabilityFieldEditor key={field.key} field={field} value={data.options[data.provider]?.[field.key]} onChange={(value) => onUpdateOptions(data.provider, field.key, value)} />)}
                </Section>
                {(advancedFields.length > 0 || data.options[data.provider] && Object.keys(data.options[data.provider]).length > 0) && (
                  <Section title="高级参数" collapsed={!showAdvanced} className="advanced-section">
                    <button className="collapse-button" type="button" onClick={() => setShowAdvanced((value) => !value)} aria-expanded={showAdvanced}><span>{showAdvanced ? '收起高级参数' : `展开高级参数（${advancedFields.length}项）`}</span><Icon name={showAdvanced ? 'chevronUp' : 'chevronDown'} size={15} /></button>
                    {showAdvanced && <div className="advanced-fields">{advancedFields.map((field) => <CapabilityFieldEditor key={field.key} field={field} value={data.options[data.provider]?.[field.key]} onChange={(value) => onUpdateOptions(data.provider, field.key, value)} />)}</div>}
                  </Section>
                )}
              </>
            )}
            {!embedded && currentOutput && <OutputPreview sectionRef={outputRef} output={currentOutput} title={orderedLatestSuccess ? '最近成功成品' : '当前成品'} status={orderedLatestSuccess ? '已完成' : '已导入素材'} help="编辑只影响下一次生成，已有成品保留原参数。" onOpen={() => orderedLatestSuccess ? onOpenPreview(orderedLatestSuccess) : onOpenMedia(currentOutput)} />}
            </div>
            </SettingsDetails>
            <SettingsDetails embedded={embedded} title="更多信息" className="node-info-details">
            <div className="node-information-fields">
            {data.asset && !orderedLatestSuccess && !data.generation_snapshot && <p className="field-help import-provenance-note">原提示词未记录；这份内容仅作为导入素材保存。</p>}
            <Section title="导入现有成品" className="media-import-section">
              <button className="collapse-button" type="button" onClick={() => setShowMediaImport((value) => !value)} aria-expanded={showMediaImport}><span>{showMediaImport ? '收起导入设置' : '展开导入已有成品'}</span><Icon name={showMediaImport ? 'chevronUp' : 'chevronDown'} size={15} /></button>
              {showMediaImport && <>
              <div className="upload-row"><button className="outline-button" type="button" onClick={() => fileRef.current?.click()} disabled={uploading || Boolean(orderedLatestSuccess)}><Icon name="upload" size={14} />{uploading ? '上传中…' : '上传文件'}</button><button className="outline-button" type="button" onClick={() => void onImportAssetPath()} disabled={uploading || Boolean(orderedLatestSuccess) || !importPath}><Icon name="link" size={14} />导入路径</button><span>只写入当前成品</span></div>
                <input ref={fileRef} className="visually-hidden" type="file" accept="image/*,video/*,audio/*" onChange={handleAssetUpload} />
                <TextField label="本地文件路径" value={importPath} onChange={(import_path) => onUpdate({ import_path })} placeholder="C:\\素材\\existing.mp4" optional />
                <p className="field-help">{orderedLatestSuccess ? '已有成功成品，当前导入已暂停；请新建媒体组件保留另一份成品。' : '导入仅保存素材，不会提交生成，也不会改变当前生成方式。'}</p>
              </>}
            </Section>
            <Section title="镜头故事板">
              <button className="collapse-button" type="button" onClick={() => setShowStoryboard((value) => !value)} aria-expanded={showStoryboard}><span>{showStoryboard ? '收起镜头故事板' : data.content ? '展开镜头故事板（已有正文）' : '展开镜头故事板'}</span><Icon name={showStoryboard ? 'chevronUp' : 'chevronDown'} size={15} /></button>
              {showStoryboard && <>
                <TextField label="镜头故事板" value={data.content || ''} onChange={(content) => onUpdate({ content })} placeholder="记录这一个镜头的起止状态、动作和对白…" multiline rows={12} optional onCompositionStart={beginComposition} onCompositionEnd={endComposition} />
                <TextField label="故事来源文件" value={data.story_source_path || data.source_path || ''} onChange={(story_source_path) => onUpdate({ story_source_path })} placeholder="可选的原始故事板文件" optional />
                <p className="field-help">这是当前媒体组件的镜头创作草稿，编辑不会改写历史成品快照。</p>
              </>}
            </Section>
            {data.generation_snapshot && <SnapshotDetails snapshot={data.generation_snapshot as GenerationSnapshot} title="原成品使用的参数" />}
            {historyEntries.length ? <HistoryPreviewList entries={historyEntries} onOpen={onOpenMedia} /> : null}
            {data.derived_outputs?.length ? <DerivedOutputList outputs={data.derived_outputs} onOpen={onOpenMedia} /> : null}
            {information}
            </div>
            </SettingsDetails>
          </>
        )}

        {!isGeneration && information}
      </div>
      </SettingsDetails>
      {(data.nodeType === 'video' || data.nodeType === 'image' || data.nodeType === 'audio') && (
        <div className="inspector-action">
          {effectiveRunStatus === 'failed' && <div className="run-error">{effectiveRunError || '上一次执行失败'}</div>}
          {draftChanged && (!embedded || !data.resultChanged) && <div className="stale-note">当前草稿已有修改，尚未用于生成。已有任务继续使用确认时的输入。</div>}
          <button className="execute-button" type="button" onClick={onExecute} disabled={!canExecute || !selectionReady || saveBlocked || composing || ['pending_agent', 'queued', 'running', 'unknown'].includes(effectiveRunStatus || '')}>
            <span>{effectiveRunStatus === 'pending_agent' ? '待 Agent 接手' : effectiveRunStatus === 'queued' ? '等待执行' : effectiveRunStatus === 'running' ? '生成中…' : effectiveRunStatus === 'unknown' ? '等待核实原任务' : '确认执行'}</span><Icon name={effectiveRunStatus === 'succeeded' ? 'check' : 'arrowUpRight'} size={17} />
          </button>
          {saveBlocked && <p className="action-help error-text">当前画布版本冲突，已保留草稿；解决保存冲突后才能执行。</p>}
          {!saveBlocked && !selectionReady && <p className="action-help">请选择可用的生成方式、模型和模式后再确认执行。</p>}
          {!saveBlocked && (!embedded || selectionReady && !['queued', 'pending_agent', 'running', 'unknown'].includes(effectiveRunStatus || '')) && <p className="action-help">{embedded ? '确认后开始生成，修改会自动保存。' : '执行前会先保存当前输入。任务提交后参数会固定。'}</p>}
          {orderedLatestRun && <TaskRecords
            key={orderedLatestRun.id}
            run={orderedLatestRun}
            embedded={embedded}
            initialExpanded={!embedded && (['queued', 'pending_agent', 'running', 'unknown'].includes(orderedLatestRun.status) || draftChanged)}
          />}
        </div>
      )}
    </Container>
  );
}

function TaskRecords({ run, embedded, initialExpanded }: { run: Run; embedded: boolean; initialExpanded: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const label = RUN_STATUS_LABELS[run.status] || run.status;
  if (!embedded) return <>
    <RunSummary run={run} />
    <SnapshotDetails snapshot={run.snapshot} title={`本次任务实际使用的输入 · ${label}`} frozen initialExpanded={initialExpanded} />
  </>;
  const showStatus = run.status !== 'succeeded' || run.review && run.review.decision !== 'ACCEPT' || run.attention_state && run.attention_state !== 'active';
  return <>
    {showStatus && <RunSummary run={run} />}
    <div className="node-task-records">
      <button type="button" className="snapshot-toggle" onClick={() => setExpanded((value) => !value)} aria-expanded={expanded} aria-label={`任务记录：${label}`}>
        <span><Icon name="history" size={14} />任务记录</span><small>{label}<Icon name={expanded ? 'chevronUp' : 'chevronDown'} size={14} /></small>
      </button>
      {expanded && <div className="node-task-body">
        {!showStatus && <RunSummary run={run} />}
        <SnapshotDetails snapshot={run.snapshot} frozen contentOnly />
      </div>}
    </div>
  </>;
}

function RunSummary({ run }: { run: Run }) {
  const stages: Record<string, string> = { input_validation: '检查输入', upload: '上传素材', submit: '提交生成', generation: '生成', collection: '收集结果', media_validation: '检查媒体' };
  const decisions: Record<string, string> = { ACCEPT: '已采用', REJECT: '需要修复', INCONCLUSIVE: '需要局部复核' };
  const attentionLabels: Record<string, string> = { paused: '已暂停', abandoned: '已放弃' };
  const attention = run.attention_state && run.attention_state !== 'active'
    ? ` · ${attentionLabels[run.attention_state] || '需要关注'}${run.attention_reason ? `：${run.attention_reason}` : ''}`
    : '';
  return <div className={`run-summary run-${run.status}`}><span className="run-summary-dot" /><span>{RUN_STATUS_LABELS[run.status] || run.status}{run.stage ? ` · ${stages[run.stage] || run.stage}` : ''}{run.review ? ` · ${decisions[run.review.decision]}` : ''}{attention}</span>{run.outputs?.length > 0 && <small>{run.outputs.length} 个输出</small>}</div>;
}

function OutputPreview({ output, title, status, help, onOpen, sectionRef }: { output: Run['outputs'][number]; title: string; status: string; help: string; onOpen: () => void; sectionRef?: Ref<HTMLElement> }) {
  if (!output) return null;
  const isImage = output.kind.startsWith('image') || /\.(png|jpe?g|webp|gif)$/i.test(output.path);
  const isAudio = output.kind.startsWith('audio') || /\.(mp3|wav|m4a|aac|ogg|flac)$/i.test(output.path);
  const durationMs = output.metadata?.duration_ms;
  return (
    <section ref={sectionRef} className="preview-section">
      <div className="section-title"><h3><Icon name={isImage ? 'image' : isAudio ? 'audio' : 'film'} size={15} />{title}</h3><span className="success-badge">{status}</span></div>
      <button className="preview-card" type="button" onClick={onOpen}>
        {isImage ? <img src={mediaUrl(output.path)} alt={output.name || '生成图片'} /> : isAudio ? <span className="preview-audio-placeholder"><Icon name="audio" size={32} /><span>{output.name || '音频素材'}</span></span> : <video src={mediaUrl(output.path)} muted preload="metadata" onLoadedMetadata={(event) => { const video = event.currentTarget; if (video.duration > 0) video.currentTime = Math.min(0.05, video.duration / 2); }} />}
        <span className="preview-overlay"><Icon name={isImage ? 'expand' : isAudio ? 'play' : 'play'} size={13} />{isImage ? '查看原图' : isAudio ? '播放音频' : '播放视频'}</span>
      </button>
      <p className="field-help">{help}</p>
      {isAudio && typeof durationMs === 'number' && <p className="field-help">实际时长 {(durationMs / 1000).toFixed(2)} 秒</p>}
      {isImage && output.metadata?.width && output.metadata?.height && <p className="field-help">实际尺寸 {output.metadata.width} × {output.metadata.height}{output.metadata.has_transparency ? ' · 含透明区域' : ''}{output.metadata.steps ? ` · ${output.metadata.steps} 步` : ''}</p>}
    </section>
  );
}

function HistoryPreviewList({ entries, onOpen }: { entries: HistoryEntry[]; onOpen: (output: RunOutput) => void }) {
  const usable = entries.filter((entry) => Boolean(entry.asset?.path));
  const [expanded, setExpanded] = useState(false);
  if (!usable.length) return null;
  return (
    <Section title={`历史版本（${usable.length}）`} className="archive-section history-section">
      <button className="collapse-button archive-toggle" type="button" onClick={() => setExpanded((value) => !value)} aria-expanded={expanded}><span>{expanded ? '收起历史版本' : '展开历史版本'}</span><Icon name={expanded ? 'chevronUp' : 'chevronDown'} size={15} /></button>
      {expanded && <div className="history-inspector-list">
        {usable.map((entry) => {
          const output = assetToOutput(entry.asset);
          if (!output) return null;
          return <div className="history-inspector-item" key={entry.id}>
            <OutputPreview output={output} title={entry.label || '历史成品'} status={entry.status || '只读历史'} help={entry.source_path ? `来源 · ${entry.source_path.split(/[\\/]/).pop()}` : '历史成品只用于预览，不会替换当前草稿。'} onOpen={() => onOpen(output)} />
            {entry.generation_snapshot && <SnapshotDetails snapshot={entry.generation_snapshot} title="历史成品使用的参数" />}
          </div>;
        })}
      </div>}
    </Section>
  );
}

function DerivedOutputList({ outputs, onOpen }: { outputs: StoryNodeData['derived_outputs']; onOpen: (output: RunOutput) => void }) {
  const usable = (outputs || []).filter((entry) => Boolean(entry.asset?.path));
  const [expanded, setExpanded] = useState(false);
  if (!usable.length) return null;
  return (
    <Section title={`派生输出（${usable.length}）`} className="archive-section derived-section">
      <button className="collapse-button archive-toggle" type="button" onClick={() => setExpanded((value) => !value)} aria-expanded={expanded}><span>{expanded ? '收起派生输出' : '展开派生输出'}</span><Icon name={expanded ? 'chevronUp' : 'chevronDown'} size={15} /></button>
      {expanded && <div className="history-inspector-list">
        {usable.map((entry) => {
          const output = assetToOutput(entry.asset);
          if (!output) return null;
          return <div className="history-inspector-item" key={entry.id}>
            <OutputPreview output={output} title={entry.label || '派生成品'} status="只读输出" help="派生输出可以作为下游组件的独立输入，不会替换当前成品。" onOpen={() => onOpen(output)} />
          </div>;
        })}
      </div>}
    </Section>
  );
}

type SnapshotView = GenerationSnapshot | Run['snapshot'];

function SnapshotDetails({ snapshot, title = '本次成品使用的参数', frozen = false, initialExpanded = false, contentOnly = false }: { snapshot: SnapshotView; title?: string; frozen?: boolean; initialExpanded?: boolean; contentOnly?: boolean }) {
  const [open, setOpen] = useState(initialExpanded);
  const expanded = contentOnly || open;
  const parameters = snapshot.parameters || {};
  return (
    <div className="snapshot-details">
      {!contentOnly && <button type="button" className="snapshot-toggle" onClick={() => setOpen((value) => !value)} aria-expanded={expanded}><span><Icon name="settings" size={14} />{title}</span><small>{expanded ? '收起' : '查看'}<Icon name={expanded ? 'chevronUp' : 'chevronDown'} size={14} /></small></button>}
      {frozen && expanded && <p className="snapshot-frozen-note">以下是本次任务确认时保存的冻结输入，后续修改不会改变它。</p>}
      {expanded && <div className="snapshot-body"><div><b>提示词</b><p>{typeof snapshot.prompt === 'string' && snapshot.prompt.trim() ? snapshot.prompt : '原提示词未记录'}</p></div><FriendlySnapshot title="生成方式" values={{ provider: snapshot.provider, model: snapshot.model, mode: snapshot.mode }} /><FriendlySnapshot title="规格与参数" values={parameters} /><FriendlySnapshot title="输入素材" values={snapshot.inputs || {}} /></div>}
    </div>
  );
}

function FriendlySnapshot({ title, values }: { title: string; values: Record<string, unknown> }) {
  const entries = Object.entries(values).filter(([key]) => !/(hash|task|request|run.?id|node.?id|frozen_path|source_run_id)/i.test(key));
  if (!entries.length) return null;
  return <div className="friendly-snapshot"><b>{title}</b><dl>{entries.map(([key, value]) => <div key={key}><dt>{friendlyKey(key)}</dt><dd>{friendlyValue(value, key)}</dd></div>)}</dl></div>;
}

function friendlyKey(key: string): string {
  const labels: Record<string, string> = { duration: '时长', aspect_ratio: '画幅比例', megapixels: '像素预算', fps: '帧率', model: '模型', mode: '模式', provider: '生成方式', first_frame: '首帧', last_frame: '尾帧', reference_images: '图片参考', reference_videos: '视频参考', reference_audios: '音频参考', reference_image: '图片参考', reference_video: '视频参考', reference_audio: '音频参考', sampler_profile: '采样配置', steps: '采样步数', seed: '随机种子', reference_image_size: '参考图尺寸', speaker: '声音角色', language: '语言', tempo: '语速', instruct: '语音风格指令', max_new_tokens: '最大新 token 数' };
  return labels[key] || key.replace(/_/g, ' ');
}

function friendlyValue(value: unknown, key = ''): string {
  if (value === undefined || value === null || value === '') return '未设置';
  if (Array.isArray(value)) {
    const items = value.map((item) => friendlyValue(item, key)).filter((item) => item !== '未设置');
    return items.length ? items.join('、') : '无';
  }
  if (typeof value === 'object') {
    const record = value as Record<string, unknown>;
    if ('kind' in record && ('name' in record || 'path' in record)) {
      const name = typeof record.name === 'string' && record.name ? record.name : typeof record.path === 'string' ? record.path.split(/[\\/]/).pop() : undefined;
      return name ? `${name}${record.kind ? `（${record.kind}）` : ''}` : '关联媒体';
    }
    return Object.entries(record).filter(([entryKey]) => !/(hash|frozen_path|source_run_id|request|task|run.?id|node.?id|path)/i.test(entryKey)).map(([entryKey, entryValue]) => `${friendlyKey(entryKey)}：${friendlyValue(entryValue, entryKey)}`).join('；') || '无';
  }
  return String(value);
}
