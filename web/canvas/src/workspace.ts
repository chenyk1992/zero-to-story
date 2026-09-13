import type { AssetRef, CanvasNodeData, CanvasNodeType, DerivedOutput, FlowNode, GenerationSnapshot, HistoryEntry, PreviewInfo, Run, RunOutput } from './types';

/** The story canvas metadata stays deliberately flat so a chapter remains easy to edit. */
export interface WorkspaceMeta {
  story: string;
  chapter: string;
  summary: string;
  source?: string;
  [key: string]: unknown;
}

export type StoryNodeType = CanvasNodeType | 'document' | 'section';

export type { DerivedOutput, GenerationSnapshot, HistoryEntry } from './types';

export interface StoryNodeData {
  nodeType: StoryNodeType;
  label: string;
  prompt: string;
  provider: string;
  model: string;
  mode: string;
  options: Record<string, Record<string, string | number | boolean | undefined>>;
  asset?: AssetRef;
  generation_snapshot?: GenerationSnapshot;
  history?: HistoryEntry[];
  derived_outputs?: DerivedOutput[];
  duration?: number;
  aspect_ratio?: string;
  megapixels?: number;
  runStatus?: CanvasNodeData['runStatus'];
  runError?: string;
  resultChanged?: boolean;
  latestPreview?: PreviewInfo;
  latestSuccessfulRun?: Run;
  runHistory?: Run[];
  onPreview?: (output?: RunOutput) => void;
  effectivePrompt?: string;
  content?: string;
  category?: string;
  description?: string;
  panel_id?: string;
  source_path?: string;
  story_source_path?: string;
  import_path?: string;
  import_source_path?: string;
  status?: string;
  width?: number;
  height?: number;
  [key: string]: unknown;
}

export type StoryNodePatch = Partial<Omit<StoryNodeData, 'nodeType'>>;

export type StoryFlowNode = FlowNode & { data: StoryNodeData };

export const DEFAULT_WORKSPACE: WorkspaceMeta = { story: '', chapter: '', summary: '' };

export const CATEGORY_LABELS: Record<string, string> = {
  character: '角色参考',
  storyboard: '故事板',
  board: '电影画面分镜板',
  image: '图片',
  video: '视频',
  document: '文档',
};

export const CATEGORY_OPTIONS = [
  { value: '', label: '未分类' },
  { value: 'character', label: '角色参考' },
  { value: 'storyboard', label: '故事板' },
  { value: 'board', label: '电影画面分镜板' },
  { value: 'image', label: '图片' },
  { value: 'video', label: '视频' },
  { value: 'document', label: '文档' },
];

export function normalizeWorkspace(value: unknown, fallbackStory = ''): WorkspaceMeta {
  const record = value && typeof value === 'object' ? value as Record<string, unknown> : {};
  return {
    ...record,
    story: typeof record.story === 'string' ? record.story : fallbackStory,
    chapter: typeof record.chapter === 'string' ? record.chapter : '',
    summary: typeof record.summary === 'string' ? record.summary : '',
    ...(typeof record.source === 'string' ? { source: record.source } : {}),
  };
}

export function isStoryNodeType(value: unknown): value is StoryNodeType {
  return typeof value === 'string' && ['asset', 'image', 'video', 'document', 'section'].includes(value);
}

export function isSectionNode(node: { data: { nodeType?: unknown } }): boolean {
  return node.data.nodeType === 'section';
}

export function categoryForNode(node: { data: Partial<StoryNodeData> }): string | undefined {
  const category = typeof node.data.category === 'string' ? node.data.category : '';
  if (category) return category;
  const nodeType = node.data.nodeType;
  if (nodeType === 'asset') {
    const kind = String(node.data.asset?.kind || '');
    if (kind.startsWith('image')) return 'image';
    if (kind.startsWith('video')) return 'video';
  }
  if (nodeType === 'document') return 'document';
  if (nodeType === 'image') return 'image';
  if (nodeType === 'video') return 'video';
  return undefined;
}

export function categoryLabelForNode(node: { data: Partial<StoryNodeData> }): string {
  const category = categoryForNode(node);
  return (category && CATEGORY_LABELS[category]) || (node.data.nodeType === 'section' ? '分区' : '未分类');
}

export function nodeSearchText(node: { id: string; data: Partial<StoryNodeData> }): string {
  const data = node.data;
  return [
    node.id,
    data.label,
    data.category,
    data.description,
    data.panel_id,
    data.prompt,
    data.content,
    data.asset?.name,
    data.asset?.path,
  ].filter(Boolean).join(' ').toLocaleLowerCase();
}

export function mediaCountForNode(node: { data: Partial<StoryNodeData> }): number {
  const data = node.data;
  return (data.asset?.path ? 1 : 0)
    + (data.history || []).filter((entry) => Boolean(entry.asset?.path)).length
    + (data.derived_outputs || []).filter((entry) => Boolean(entry.asset?.path)).length;
}
