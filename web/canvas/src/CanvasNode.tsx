import { Handle, Position, useUpdateNodeInternals, type NodeProps } from '@xyflow/react';
import { useEffect, useState, type CSSProperties, type SyntheticEvent } from 'react';
import type { FlowNode, RunOutput } from './types';
import { assetToOutput, outputForRun } from './graph';
import { mediaUrl } from './api';
import { categoryLabelForNode, type StoryNodeData } from './workspace';
import { Icon, type IconName } from './Icon';
import { cardDescription } from './cardPresentation';
import { useNodeEditing } from './NodeEditing';
import { InlineTextField } from './InlineTextField';
import './canvas-node.css';

const TONES = {
  asset: 'amber',
  image: 'cyan',
  video: 'rose',
  audio: 'amber',
  document: 'violet',
  section: 'section',
} as const;

const NODE_ICONS: Record<string, IconName> = {
  asset: 'asset',
  image: 'image',
  video: 'video',
  audio: 'audio',
  document: 'document',
  section: 'section',
};

const NODE_LABELS: Record<string, string> = {
  asset: '素材',
  image: '图片',
  video: '视频',
  audio: '音频',
  document: '文档',
  section: '分区',
};

const TARGETS: Record<string, Array<{ id: string; label: string }>> = {
  image: [{ id: 'reference_image', label: '图片参考' }],
  audio: [{ id: 'reference_audio', label: '声音参考' }],
  // Input IDs are stable; each mode exposes its supported inputs below.
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

function videoTargetIds(data: StoryNodeData): string[] {
  const modeTargets = VIDEO_TARGETS_BY_MODE[data.mode];
  if (!modeTargets) return TARGETS.video.map((target) => target.id);
  if (data.provider === 'comfy' && data.mode === 'r2v') return ['first_frame', ...modeTargets];
  return modeTargets;
}

const MODE_LABELS: Record<string, string> = {
  create: '图像生成',
  reference: '图片参考生成',
  edit: '图片编辑',
  t2v: '文生视频',
  i2v: '图生视频',
  fl2v: '首尾帧',
  r2v: '参考生视频',
  tts: '语音合成',
  design: '声音设计',
  clone: '音色克隆',
};

function shorten(value: string, length = 94): string {
  const normalized = value.trim().replace(/\s+/g, ' ');
  return normalized.length > length ? `${normalized.slice(0, length)}…` : normalized;
}

function providerLabel(data: StoryNodeData): string {
  const provider = String(data.provider || '').trim();
  const normalized = provider.toLowerCase().replace(/[_\s-]/g, '');
  if (provider === 'comfy-qwen-image') return 'Qwen 2.1';
  if (provider === 'comfy-qwen-tts') return 'Qwen3-TTS';
  if (provider === 'comfy-minimax-music') return 'Music 3';
  if (normalized.includes('imagegen')) return '内置生图';
  if (provider === 'comfy') return 'Comfy / H3';
  if (!provider) return data.nodeType === 'image' || data.nodeType === 'video' || data.nodeType === 'audio' ? '请选择生成方式' : '未选择生成方式';
  return provider;
}

function validRatio(width?: number, height?: number): number | undefined {
  return width && height && width > 0 && height > 0 && Number.isFinite(width / height) ? width / height : undefined;
}

function plannedRatio(value?: string): number {
  const [width, height] = (value || '').split(/[:/]/).map(Number);
  return validRatio(width, height) || 16 / 9;
}

function isAudioOutput(output: RunOutput): boolean {
  return output.kind.toLowerCase().startsWith('audio') || /\.(mp3|wav|m4a|aac|ogg|flac)$/i.test(output.path);
}

function PreviewThumbnail({ path, kind, alt, onDimensions, onVideoMetadata }: { path: string; kind: string; alt: string; onDimensions: (width: number, height: number) => void; onVideoMetadata?: (durationMs: number) => void }) {
  const normalizedKind = kind.toLowerCase();
  const isImage = normalizedKind.startsWith('image') || /\.(png|jpe?g|webp|gif)$/i.test(path);
  if (isImage) return <img src={mediaUrl(path)} alt={alt} loading="lazy" onLoad={(event) => onDimensions(event.currentTarget.naturalWidth, event.currentTarget.naturalHeight)} />;
  if (normalizedKind.startsWith('audio') || /\.(mp3|wav|m4a|aac|ogg|flac)$/i.test(path)) {
    return <span className="preview-audio-mark"><Icon name="audio" size={26} /></span>;
  }
  return <video src={mediaUrl(path)} muted preload="metadata" onLoadedMetadata={(event: SyntheticEvent<HTMLVideoElement>) => { const video = event.currentTarget; onDimensions(video.videoWidth, video.videoHeight); if (video.duration > 0) { onVideoMetadata?.(video.duration * 1000); video.currentTime = Math.min(0.05, video.duration / 2); } }} />;
}

function OutputPreviewButton({ output, label, current = false, fallbackRatio = 16 / 9, onRatio, onOpen }: { output: RunOutput; label: string; current?: boolean; fallbackRatio?: number; onRatio?: (path: string, ratio: number) => void; onOpen: (output?: RunOutput) => void }) {
  const [naturalSize, setNaturalSize] = useState<{ path: string; ratio: number }>();
  const [actualDuration, setActualDuration] = useState<{ path: string; durationMs: number }>();
  const metadataRatio = validRatio(output.metadata?.width, output.metadata?.height);
  const ratio = metadataRatio || (naturalSize?.path === output.path ? naturalSize.ratio : undefined) || fallbackRatio;
  const audio = isAudioOutput(output);
  const onDimensions = (width: number, height: number) => {
    const nextRatio = validRatio(width, height);
    if (!nextRatio) return;
    setNaturalSize({ path: output.path, ratio: nextRatio });
    onRatio?.(output.path, metadataRatio || nextRatio);
  };
  const seconds = output.metadata?.duration_ms ?? (actualDuration?.path === output.path ? actualDuration.durationMs : undefined);
  return (
    <button className={`node-preview nodrag ${current ? 'current-output' : 'secondary-output'}`} style={audio ? { aspectRatio: 'auto', height: 92 } : { '--node-media-ratio': ratio, aspectRatio: ratio, height: 'auto' } as CSSProperties} type="button" onPointerDown={(event) => event.stopPropagation()} onKeyDown={(event) => event.stopPropagation()} onClick={(event) => { event.stopPropagation(); onOpen(current ? undefined : output); }} aria-label={`${label}，点击打开预览`}>
      <PreviewThumbnail key={output.path} path={output.path} kind={output.kind} alt={label} onDimensions={onDimensions} onVideoMetadata={(durationMs) => setActualDuration({ path: output.path, durationMs })} />
      {current && <span className="node-preview-source">{label}</span>}
      {current && typeof seconds === 'number' && seconds > 0 && <span className="node-preview-duration" title="实际成品时长">{Number((seconds / 1000).toFixed(1))} 秒</span>}
      <span className="node-preview-caption"><b>{label}</b><em><Icon name="expand" size={12} />{current ? '打开' : '查看'}</em></span>
    </button>
  );
}

function PortLabel({ children, className = '', style }: { children: string; className?: string; style?: CSSProperties }) {
  return <span className={`port-label ${className}`} style={style}>{children}</span>;
}

export function CanvasNode({ id, data: rawData, selected }: NodeProps<FlowNode>) {
  const updateNodeInternals = useUpdateNodeInternals();
  const editing = useNodeEditing();
  const isEditing = Boolean(selected && editing);
  const [promptExpanded, setPromptExpanded] = useState(false);
  const [historyExpanded, setHistoryExpanded] = useState(false);
  const [derivedExpanded, setDerivedExpanded] = useState(false);
  const [descriptionExpanded, setDescriptionExpanded] = useState(Boolean(rawData.description));
  const [currentMediaSize, setCurrentMediaSize] = useState<{ path: string; ratio: number }>();
  const data = rawData as StoryNodeData;
  const kind = data.nodeType;
  const isMedia = kind === 'image' || kind === 'video' || kind === 'audio';
  const targets = (TARGETS[kind] || []).filter((target) => {
    if (kind === 'audio' && data.provider === 'comfy-minimax-music') return false;
    return kind !== 'video' || !data.mode || videoTargetIds(data).includes(target.id);
  });
  const derivedOutputs = data.derived_outputs || [];
  const targetSignature = `${targets.map((target) => target.id).join('|')}::${derivedOutputs.map((output) => output.id).join('|')}`;
  const isRunning = data.runStatus === 'queued' || data.runStatus === 'pending_agent' || data.runStatus === 'running';
  const runLabel = data.runStatus === 'pending_agent' ? '待接手' : data.runStatus === 'queued' ? '排队中' : '生成中';
  const currentOutput = outputForRun(data.latestSuccessfulRun) || assetToOutput(data.asset);
  const isAudioCard = kind === 'audio' || Boolean(currentOutput && isAudioOutput(currentOutput));
  const mediaRatio = validRatio(currentOutput?.metadata?.width, currentOutput?.metadata?.height) || (currentOutput && currentMediaSize?.path === currentOutput.path ? currentMediaSize.ratio : undefined) || plannedRatio(data.aspect_ratio);
  const onCurrentRatio = (path: string, ratio: number) => setCurrentMediaSize({ path, ratio });
  const history = data.history || [];
  const previousRuns = (data.runHistory || []).filter((run) => run.id !== data.latestSuccessfulRun?.id && run.outputs?.[0]);
  const originalAcceptedOutput = data.latestSuccessfulRun?.outputs?.[0];
  const hasAcceptedDerivedOutput = Boolean(originalAcceptedOutput && currentOutput && originalAcceptedOutput.path !== currentOutput.path);
  const prompt = data.prompt || '';
  const description = cardDescription(data);
  const promptLabel = kind === 'audio' ? data.provider === 'comfy-minimax-music' ? '音乐描述' : '配音台词' : '提示词';
  const editorPromptLabel = kind === 'audio' ? data.provider === 'comfy-minimax-music' ? '音乐描述' : '逐字台词' : kind === 'video' ? '视频提示词' : '图片提示词';
  const tone = TONES[kind] || 'violet';
  const nodeIcon = NODE_ICONS[kind] || 'asset';
  const nodeLabel = NODE_LABELS[kind] || kind;
  const category = categoryLabelForNode({ data });
  const identity = category === '未分类' ? nodeLabel : category;
  const title = data.label || nodeLabel;
  const hasEarlierOutput = Boolean(currentOutput && data.latestSuccessfulRun && (data.resultChanged || data.runStatus && data.runStatus !== 'succeeded'));
  const outputLabel = hasEarlierOutput ? '上次成功成品' : hasAcceptedDerivedOutput ? '已采用版本' : data.latestSuccessfulRun ? '生成成品' : '导入素材';
  const spec = [kind === 'video' && data.duration ? `计划 ${data.duration} 秒` : '', kind !== 'audio' ? data.aspect_ratio : ''].filter(Boolean).join(' · ');
  const specDetails = [providerLabel(data), data.model, MODE_LABELS[data.mode] || data.mode, spec, data.megapixels ? `${data.megapixels} MP` : ''].filter(Boolean).join(' · ');
  const placeholderTitle = data.runStatus === 'unknown' ? '等待核实原任务' : data.runStatus === 'failed' ? '本次未生成成品' : isRunning ? kind === 'audio' ? '正在准备声音' : '正在准备画面' : data.runStatus === 'cancelled' ? '本次任务已取消' : kind === 'asset' ? '添加参考素材' : kind === 'audio' ? '等待第一版声音' : '等待第一版画面';
  const placeholderHelp = data.runStatus === 'unknown' ? '选中卡片查看任务状态' : data.runStatus === 'failed' ? '选中卡片查看失败原因' : isRunning ? '任务完成后会在这里显示' : kind === 'asset' ? '选中后上传文件或导入路径' : '选中卡片，直接完善创作';
  const placeholder = <div className="node-media-placeholder"><Icon name={nodeIcon} size={26} /><strong>{placeholderTitle}</strong><small>{placeholderHelp}</small></div>;
  const assetName = data.asset?.name || data.asset?.path.split(/[\\/]/).pop() || '';
  const textField = (field: 'label' | 'prompt' | 'content' | 'description', label: string, className: string, placeholder?: string) => <InlineTextField key={`${id}:${field}`} value={String(data[field] || '')} label={label} className={className} placeholder={placeholder} onChange={(value) => editing?.updateNode(id, { [field]: value })} onComposingChange={(composing) => editing?.setComposing(id, composing)} />;
  const descriptionEditor = <label className="node-inline-field"><span>创作说明</span>{textField('description', '创作说明', 'node-description-editor', '记录这张卡片的创作意图')}</label>;
  const finishButton = isEditing && editing?.finishEditing && <button type="button" className="node-edit-done nodrag" aria-label="完成卡片编辑" title="完成编辑，返回浏览" onPointerDown={(event) => event.stopPropagation()} onKeyDown={(event) => event.stopPropagation()} onClick={(event) => { event.stopPropagation(); editing.finishEditing?.(id); }}><Icon name="check" size={13} />完成</button>;
  const descriptionField = <details className="node-description-details nodrag nowheel" open={descriptionExpanded} onToggle={(event) => setDescriptionExpanded(event.currentTarget.open)} onPointerDown={(event) => event.stopPropagation()} onKeyDown={(event) => event.stopPropagation()}><summary>创作说明</summary>{descriptionEditor}</details>;

  useEffect(() => {
    if (data.description) setDescriptionExpanded(true);
  }, [data.description]);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => updateNodeInternals(id));
    return () => window.cancelAnimationFrame(frame);
  }, [id, targetSignature, isEditing, updateNodeInternals]);

  const isSection = kind === 'section';
  const isDocument = kind === 'document';
  const nodeStyle = isSection
    ? { width: data.width || 620, height: data.height || 360 }
    : { '--node-media-ratio': mediaRatio, '--node-card-width': isAudioCard ? '320px' : mediaRatio < 0.9 ? '280px' : mediaRatio <= 1.1 ? '304px' : '340px', ...(targets.length ? { minHeight: Math.max(116, 64 + targets.length * 22), '--related-port-top': `${37 + targets.length * 22}px` } : {}) } as CSSProperties;

  return (
    <article className={`canvas-node node-${tone}${isMedia ? ' media-node' : ''}${isAudioCard ? ' is-audio' : ''}${isSection ? ' section-node' : ''}${isDocument ? ' document-node' : ''}${selected ? ' is-selected' : ''}${isEditing ? ' is-editing' : ''}`} style={nodeStyle}>
      {isSection ? <>
        <div className="section-node-header">
          <span className="section-node-icon"><Icon name="section" size={17} /></span>
          {isEditing ? textField('label', '卡片名称', 'node-title-editor', '镜头分区') : <strong>{data.label || '镜头分区'}</strong>}
          <span className="section-node-kind">分区</span>
          <span className="section-node-size">{data.width || 620} × {data.height || 360}</span>
          {finishButton}
        </div>
        {isEditing ? descriptionField : data.description && <p className="section-node-description">{data.description}</p>}
      </> : <>
        <div className="node-port-targets">
          {targets.map((target, index) => (
            <div className="target-port" key={target.id} style={{ top: `${28 + index * 22}px` }}>
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
          <span className="node-heading-copy"><small className="node-eyebrow">{data.panel_id && <b className="node-panel-id">{data.panel_id}</b>}{identity}</small>{isEditing ? textField('label', '卡片名称', 'node-title-editor', nodeLabel) : <strong className="node-kind" title={title}>{title}</strong>}</span>
          {isRunning && <span className="node-status node-running"><i />{runLabel}</span>}
          {data.runStatus === 'succeeded' && <span className="node-status node-success"><Icon name="check" size={12} />已生成</span>}
          {data.runStatus === 'failed' && <span className="node-status node-failed" title={data.runError}><Icon name="alert" size={12} />生成失败</span>}
          {data.runStatus === 'unknown' && <span className="node-status node-attention"><Icon name="alert" size={12} />待核实</span>}
          {data.runStatus === 'cancelled' && <span className="node-status node-cancelled"><Icon name="close" size={12} />已取消</span>}
          {finishButton}
        </div>
        {kind === 'asset' && (
          <>
            {currentOutput ? <OutputPreviewButton output={currentOutput} label="当前素材" current fallbackRatio={mediaRatio} onRatio={onCurrentRatio} onOpen={(output) => data.onPreview?.(output)} /> : placeholder}
            {isEditing ? descriptionField : description && <p className="node-creative-summary">{shorten(description, 160)}</p>}
            {assetName && <div className="node-file-caption" title={assetName}><Icon name="asset" size={12} /><span>{assetName}</span></div>}
          </>
        )}
        {isMedia && (
          <>
            {currentOutput ? <OutputPreviewButton output={currentOutput} label={outputLabel} current fallbackRatio={mediaRatio} onRatio={onCurrentRatio} onOpen={(output) => data.onPreview?.(output)} /> : placeholder}
            {isEditing ? <><label className="node-inline-field"><span>{editorPromptLabel}</span>{textField('prompt', editorPromptLabel, 'node-prompt-editor', kind === 'audio' ? '写下完整声音内容' : '描述要生成的画面')}</label>{descriptionField}</> : <>
            {description && <p className="node-creative-summary">{shorten(description, 160)}</p>}
            {prompt && <><button className={`node-prompt-summary nodrag${promptExpanded ? ' expanded' : ''}`} type="button" onPointerDown={(event) => event.stopPropagation()} onKeyDown={(event) => event.stopPropagation()} onClick={(event) => { event.stopPropagation(); setPromptExpanded((value) => !value); }} aria-label={`${promptExpanded ? '收起' : '查看'}完整${promptLabel}`} aria-expanded={promptExpanded}>
              <span className="node-prompt-copy"><Icon name={kind === 'audio' ? 'audio' : 'document'} size={13} /><span>{promptLabel}</span></span>
              <Icon name={promptExpanded ? 'chevronUp' : 'chevronDown'} size={13} />
            </button>{promptExpanded && <pre className="node-prompt-full nodrag nowheel" tabIndex={0} onKeyDown={(event) => event.stopPropagation()}>{prompt}</pre>}</>}
            </>}
            {data.resultChanged && <div className="node-stale"><Icon name="alert" size={12} />{currentOutput ? '草稿已修改 · 预览保留原成品' : '草稿已修改 · 尚未生成'}</div>}
            <div className="node-meta" aria-label="草稿规格" title={specDetails}><span className="node-spec">{spec}</span><span className="node-provider" title={specDetails}>{data.provider ? providerLabel(data) : '待选生成方式'}</span></div>
            {derivedOutputs.length > 0 && <div className="node-output-group"><button className="node-output-heading node-output-heading-toggle nodrag" type="button" onClick={(event) => { event.stopPropagation(); setDerivedExpanded((value) => !value); }} aria-expanded={derivedExpanded}><span><Icon name="layers" size={13} />派生输出</span><small>{derivedOutputs.length} 项 <Icon name={derivedExpanded ? 'chevronUp' : 'chevronDown'} size={11} /></small></button>{derivedExpanded && <div className="node-output-list">{derivedOutputs.map((output) => { const media = assetToOutput(output.asset); return media ? <OutputPreviewButton key={output.id} output={media} label={output.label || '派生成品'} onOpen={(value) => data.onPreview?.(value)} /> : null; })}</div>}</div>}
            {(history.length > 0 || previousRuns.length > 0 || hasAcceptedDerivedOutput) && <div className="node-output-group history-output-group"><button className="node-output-heading node-output-heading-toggle nodrag" type="button" onClick={(event) => { event.stopPropagation(); setHistoryExpanded((value) => !value); }} aria-expanded={historyExpanded}><span><Icon name="history" size={13} />历史版本</span><small>{history.length + previousRuns.length + Number(hasAcceptedDerivedOutput)} 项 <Icon name={historyExpanded ? 'chevronUp' : 'chevronDown'} size={11} /></small></button>{historyExpanded && <div className="node-output-list">
              {hasAcceptedDerivedOutput && originalAcceptedOutput && <OutputPreviewButton key={`${data.latestSuccessfulRun?.id}-original`} output={originalAcceptedOutput} label="原始生成版" onOpen={(value) => data.onPreview?.(value)} />}
              {previousRuns.map((run) => <OutputPreviewButton key={`run-${run.id}`} output={run.outputs[0]} label={run.outputs[0].name || '历史成功成品'} onOpen={(value) => data.onPreview?.(value)} />)}
              {history.map((entry) => { const media = assetToOutput(entry.asset); return media ? <OutputPreviewButton key={entry.id} output={media} label={entry.label || '历史成品'} onOpen={(value) => data.onPreview?.(value)} /> : null; })}
            </div>}</div>}
          </>
        )}
        {isDocument && (
          <>
            {isEditing ? <><label className="node-inline-field"><span>文档正文</span>{textField('content', '文档正文', 'node-document-editor', '记录故事或镜头说明')}</label>{descriptionField}</> : <p className="node-copy document-copy">{shorten(description, 220) || '选中卡片，直接记录故事或镜头说明。'}</p>}
            {data.source_path && <div className="document-source">来源 · {data.source_path.split(/[\\/]/).pop()}</div>}
          </>
        )}
      </>}
      {isEditing && editing?.renderSettings(id)}
    </article>
  );
}

export const nodeTypes = { canvas: CanvasNode };
