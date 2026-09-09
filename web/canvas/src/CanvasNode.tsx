import { Handle, Position, useUpdateNodeInternals, type NodeProps } from '@xyflow/react';
import { useEffect, useState, type CSSProperties, type SyntheticEvent } from 'react';
import type { FlowNode, RunOutput } from './types';
import { assetToOutput } from './graph';
import { mediaUrl } from './api';
import { categoryLabelForNode, type StoryNodeData } from './workspace';
import { Icon, type IconName } from './Icon';
import './canvas-node.css';

const TONES = {
  asset: 'amber',
  image: 'cyan',
  video: 'rose',
  document: 'violet',
  section: 'section',
} as const;

const NODE_ICONS: Record<string, IconName> = {
  asset: 'asset',
  image: 'image',
  video: 'video',
  document: 'document',
  section: 'section',
};

const NODE_LABELS: Record<string, string> = {
  asset: '素材',
  image: '图片',
  video: '视频',
  document: '文档',
  section: '分区',
};

const TARGETS: Record<string, Array<{ id: string; label: string }>> = {
  image: [{ id: 'reference_image', label: '图片参考' }],
  // Keep every video input handle mounted. A mode can change during editing,
  // while an existing connection must remain addressable by React Flow.
  video: [
    { id: 'first_frame', label: '首帧' },
    { id: 'last_frame', label: '尾帧' },
    { id: 'reference_image', label: '图片参考' },
    { id: 'reference_video', label: '视频参考' },
    { id: 'reference_audio', label: '音频参考' },
  ],
};

const VIDEO_TARGETS_BY_MODE: Record<string, string[]> = {
  t2v: [],
  i2v: ['first_frame'],
  fl2v: ['first_frame', 'last_frame'],
  r2v: ['reference_image', 'reference_video', 'reference_audio'],
};

const MODE_LABELS: Record<string, string> = {
  create: '图像生成',
  t2v: '文生视频',
  i2v: '图生视频',
  fl2v: '首尾帧',
  r2v: '参考生视频',
};

function shorten(value: string, length = 94): string {
  const normalized = value.trim().replace(/\s+/g, ' ');
  return normalized.length > length ? `${normalized.slice(0, length)}…` : normalized;
}

function providerLabel(data: StoryNodeData): string {
  const provider = String(data.provider || '').trim();
  const normalized = provider.toLowerCase().replace(/[_\s-]/g, '');
  if (normalized.includes('imagegen')) return '内置生图';
  if (normalized.includes('comfy')) return 'Comfy / H3';
  if (!provider) return data.nodeType === 'image' || data.nodeType === 'video' ? '请选择生成方式' : '未选择生成方式';
  return provider;
}

function PreviewThumbnail({ path, kind, alt }: { path: string; kind: string; alt: string }) {
  const normalizedKind = kind.toLowerCase();
  const isImage = normalizedKind.startsWith('image') || /\.(png|jpe?g|webp|gif)$/i.test(path);
  if (isImage) return <img src={mediaUrl(path)} alt={alt} loading="lazy" />;
  if (normalizedKind.startsWith('audio') || /\.(mp3|wav|m4a|aac|ogg)$/i.test(path)) {
    return <span className="preview-audio-mark"><Icon name="audio" size={26} /></span>;
  }
  return <video src={mediaUrl(path)} muted preload="metadata" onLoadedMetadata={(event: SyntheticEvent<HTMLVideoElement>) => { const video = event.currentTarget; if (video.duration > 0) video.currentTime = Math.min(0.05, video.duration / 2); }} />;
}

function OutputPreviewButton({ output, label, current = false, onOpen }: { output: RunOutput; label: string; current?: boolean; onOpen: (output?: RunOutput) => void }) {
  return (
    <button className={`node-preview ${current ? 'current-output' : 'secondary-output'}`} type="button" onClick={(event) => { event.stopPropagation(); onOpen(current ? undefined : output); }} aria-label={`${label}，点击打开预览`}>
      <PreviewThumbnail path={output.path} kind={output.kind} alt={label} />
      <span className="node-preview-caption"><b>{label}</b><em><Icon name="expand" size={12} />{current ? '打开' : '查看'}</em></span>
    </button>
  );
}

function PortLabel({ children, className = '', style }: { children: string; className?: string; style?: CSSProperties }) {
  return <span className={`port-label ${className}`} style={style}>{children}</span>;
}

export function CanvasNode({ id, data: rawData, selected }: NodeProps<FlowNode>) {
  const updateNodeInternals = useUpdateNodeInternals();
  const [promptExpanded, setPromptExpanded] = useState(false);
  const [historyExpanded, setHistoryExpanded] = useState(false);
  const [derivedExpanded, setDerivedExpanded] = useState(false);
  const data = rawData as StoryNodeData;
  const kind = data.nodeType;
  const isMedia = kind === 'image' || kind === 'video';
  const targets = (TARGETS[kind] || []).filter((target) => kind !== 'video' || !data.mode || !VIDEO_TARGETS_BY_MODE[data.mode] || VIDEO_TARGETS_BY_MODE[data.mode].includes(target.id));
  const derivedOutputs = data.derived_outputs || [];
  const targetSignature = `${targets.map((target) => target.id).join('|')}::${derivedOutputs.map((output) => output.id).join('|')}`;
  const isRunning = data.runStatus === 'queued' || data.runStatus === 'pending_agent' || data.runStatus === 'running';
  const runLabel = data.runStatus === 'pending_agent' ? '待执行' : data.runStatus === 'queued' ? '已确认' : '生成中';
  const currentOutput = data.latestSuccessfulRun?.outputs?.[0] || assetToOutput(data.asset);
  const history = data.history || [];
  const previousRuns = (data.runHistory || []).filter((run) => run.id !== data.latestSuccessfulRun?.id && run.outputs?.[0]);
  const prompt = data.prompt || '';
  const promptCaption = promptExpanded ? prompt.trim() || '还没有填写提示词' : shorten(prompt);
  const tone = TONES[kind] || 'violet';
  const nodeIcon = NODE_ICONS[kind] || 'asset';
  const nodeLabel = NODE_LABELS[kind] || kind;

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => updateNodeInternals(id));
    return () => window.cancelAnimationFrame(frame);
  }, [id, targetSignature, updateNodeInternals]);

  const isSection = kind === 'section';
  const isDocument = kind === 'document';
  const sectionStyle = isSection ? { width: data.width || 620, height: data.height || 360 } : undefined;

  return (
    <article className={`canvas-node node-${tone}${isMedia ? ' media-node' : ''}${isSection ? ' section-node' : ''}${isDocument ? ' document-node' : ''}${selected ? ' is-selected' : ''}`} style={sectionStyle}>
      {isSection ? <>
        <div className="section-node-header">
          <span className="section-node-icon"><Icon name="section" size={17} /></span>
          <strong>{data.label || '镜头分区'}</strong>
          <span className="section-node-kind">分区</span>
          <span className="section-node-size">{data.width || 620} × {data.height || 360}</span>
        </div>
        {data.description && <p className="section-node-description">{data.description}</p>}
      </> : <>
        <div className="node-port-targets">
          {targets.map((target, index) => (
            <div className="target-port" key={target.id} style={{ top: `${28 + index * 18}px` }}>
              <Handle id={target.id} type="target" position={Position.Left} className="port port-target port-reference" />
              <PortLabel>{target.label}</PortLabel>
            </div>
          ))}
        </div>
        <Handle id="output" type="source" position={Position.Right} className="port port-source port-output" />
        <PortLabel className="source-port-label source-output-label">成品</PortLabel>
        {derivedOutputs.map((output, index) => (
          <span key={`derived-label-${output.id}`}>
            <Handle id={`output:${output.id}`} type="source" position={Position.Right} className="port port-source port-derived-source" style={{ top: `${44 + index * 22}px` }} />
            <PortLabel className="source-port-label source-derived-label" style={{ top: `${44 + index * 22}px` }}>{shorten(output.label || '派生成品', 14)}</PortLabel>
          </span>
        ))}
        <Handle id="related" type="target" position={Position.Left} className="port port-related" />
        <PortLabel className="related-port-label">资料关联</PortLabel>
        <div className="node-heading">
          <span className="node-icon"><Icon name={nodeIcon} size={15} /></span>
          <span className="node-heading-copy"><strong className="node-kind">{data.label || nodeLabel}</strong><small>{nodeLabel}</small></span>
          {isRunning && <span className="node-status node-running"><i />{runLabel}</span>}
          {data.runStatus === 'succeeded' && <span className="node-status node-success"><Icon name="check" size={12} />已完成</span>}
          {data.runStatus === 'failed' && <span className="node-status node-failed"><Icon name="alert" size={12} />失败</span>}
          {data.runStatus === 'unknown' && <span className="node-status node-attention"><Icon name="alert" size={12} />待核实</span>}
          {data.runStatus === 'cancelled' && <span className="node-status node-cancelled"><Icon name="close" size={12} />已取消</span>}
        </div>
        {kind === 'asset' && (
          <>
            <p className="node-copy asset-copy">{data.asset?.name || data.asset?.path || '拖入文件或填写本地素材路径'}</p>
            <div className="node-tags"><span>{categoryLabelForNode({ data })}</span>{data.panel_id && <span>{data.panel_id}</span>}</div>
            {currentOutput && <OutputPreviewButton output={currentOutput} label="当前素材" current onOpen={(output) => data.onPreview?.(output)} />}
          </>
        )}
        {isMedia && (
          <>
            {currentOutput && <OutputPreviewButton output={currentOutput} label={data.latestSuccessfulRun ? '最近成功成品' : '当前成品'} current onOpen={(output) => data.onPreview?.(output)} />}
            {prompt ? <button className={`node-prompt-summary${promptExpanded ? ' expanded' : ''}`} type="button" onClick={(event) => { event.stopPropagation(); setPromptExpanded((value) => !value); }} aria-expanded={promptExpanded}>
              <span className="node-prompt-copy"><Icon name="film" size={12} /><span>{promptCaption}</span></span>
              <b>{promptExpanded ? '收起' : '展开'}<Icon name={promptExpanded ? 'chevronUp' : 'chevronDown'} size={12} /></b>
            </button> : <div className="node-prompt-empty"><Icon name="info" size={13} /><span>未填写提示词</span></div>}
            <div className="node-meta" aria-label="生成规格">
              <span className="node-provider">{providerLabel(data)}</span>
              {data.mode && <span>{MODE_LABELS[data.mode] || data.mode}</span>}
              {kind === 'video' && data.duration ? <span>时长 {data.duration}s</span> : null}
              {data.aspect_ratio && <span>画幅 {data.aspect_ratio}</span>}
              {data.megapixels ? <span>预算 {data.megapixels} MP</span> : null}
            </div>
            {data.resultChanged && <div className="node-stale"><Icon name="alert" size={12} />参数已变更 · 结果来自上一版</div>}
            {derivedOutputs.length > 0 && <div className="node-output-group"><button className="node-output-heading node-output-heading-toggle" type="button" onClick={(event) => { event.stopPropagation(); setDerivedExpanded((value) => !value); }} aria-expanded={derivedExpanded}><span><Icon name="layers" size={13} />派生输出</span><small>{derivedOutputs.length} 项 <Icon name={derivedExpanded ? 'chevronUp' : 'chevronDown'} size={11} /></small></button>{derivedExpanded && <div className="node-output-list">{derivedOutputs.map((output) => { const media = assetToOutput(output.asset); return media ? <OutputPreviewButton key={output.id} output={media} label={output.label || '派生成品'} onOpen={(value) => data.onPreview?.(value)} /> : null; })}</div>}</div>}
            {(history.length > 0 || previousRuns.length > 0) && <div className="node-output-group history-output-group"><button className="node-output-heading node-output-heading-toggle" type="button" onClick={(event) => { event.stopPropagation(); setHistoryExpanded((value) => !value); }} aria-expanded={historyExpanded}><span><Icon name="history" size={13} />历史版本</span><small>{history.length + previousRuns.length} 项 <Icon name={historyExpanded ? 'chevronUp' : 'chevronDown'} size={11} /></small></button>{historyExpanded && <div className="node-output-list">
              {previousRuns.map((run) => <OutputPreviewButton key={`run-${run.id}`} output={run.outputs[0]} label={run.outputs[0].name || '历史成功成品'} onOpen={(value) => data.onPreview?.(value)} />)}
              {history.map((entry) => { const media = assetToOutput(entry.asset); return media ? <OutputPreviewButton key={entry.id} output={media} label={entry.label || '历史成品'} onOpen={(value) => data.onPreview?.(value)} /> : null; })}
            </div>}</div>}
            <div className="node-tags">{(data.category || data.panel_id) && <><span>{categoryLabelForNode({ data })}</span>{data.panel_id && <span>{data.panel_id}</span>}</>}</div>
          </>
        )}
        {isDocument && (
          <>
            <div className="document-category"><span>{categoryLabelForNode({ data })}</span>{data.panel_id && <span>{data.panel_id}</span>}</div>
            <p className="node-copy document-copy">{shorten(data.content || data.description || data.prompt) || '点击后在右侧编辑故事板或章节文档'}</p>
            {data.source_path && <div className="document-source">来源 · {data.source_path.split(/[\\/]/).pop()}</div>}
          </>
        )}
      </>}
    </article>
  );
}

export const nodeTypes = { canvas: CanvasNode };
