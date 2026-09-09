import type { Connection, Edge, Viewport, XYPosition } from '@xyflow/react';
import { addEdge } from '@xyflow/react';
import type {
  ApiEdge,
  ApiNode,
  CanvasGraph,
  CanvasNodeData,
  CanvasNodeType,
  FlowNode,
  Run,
  RunOutput,
} from './types';

export const DEFAULT_VIEWPORT: Viewport = { x: 0, y: 0, zoom: 1 };

const LABELS: Record<CanvasNodeType, string> = {
  asset: '素材',
  image: '图片',
  video: '视频',
};

export function newId(prefix: string): string {
  const random = typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID().slice(0, 8)
    : Math.random().toString(36).slice(2, 10);
  return `${prefix}-${random}`;
}

export function createNodeData(nodeType: CanvasNodeType): CanvasNodeData {
  return {
    nodeType,
    label: LABELS[nodeType],
    prompt: '',
    duration: undefined,
    aspect_ratio: undefined,
    megapixels: undefined,
    provider: '',
    model: '',
    mode: '',
    options: {},
  };
}

export function createFlowNode(nodeType: CanvasNodeType, position: XYPosition, id = newId(nodeType)): FlowNode {
  return {
    id,
    type: 'canvas',
    position,
    data: createNodeData(nodeType),
  };
}

function asNodeType(value: unknown): CanvasNodeType {
  return typeof value === 'string' && (['asset', 'image', 'video'] as string[]).includes(value)
    ? value as CanvasNodeType
    : 'asset';
}

export function toFlowNode(node: ApiNode): FlowNode {
  const nodeType = asNodeType(node.type ?? node.data?.nodeType);
  const defaults = createNodeData(nodeType);
  const input = node.data || {};
  return {
    id: node.id,
    type: 'canvas',
    position: node.position ?? { x: 80, y: 80 },
    data: {
      ...defaults,
      ...input,
      nodeType,
      label: input.label || LABELS[nodeType],
      prompt: typeof input.prompt === 'string' ? input.prompt : '',
      provider: typeof input.provider === 'string' ? input.provider : defaults.provider,
      model: typeof input.model === 'string' ? input.model : defaults.model,
      mode: typeof input.mode === 'string' ? input.mode : defaults.mode,
      options: input.options || {},
    },
  };
}

export function toApiNode(node: FlowNode): ApiNode {
  const {
    runStatus: _runStatus,
    runError: _runError,
    resultChanged: _resultChanged,
    latestPreview: _latestPreview,
    latestSuccessfulRun: _latestSuccessfulRun,
    runHistory: _runHistory,
    onPreview: _onPreview,
    nodeType,
    ...data
  } = node.data;
  return {
    id: node.id,
    type: nodeType,
    position: { x: Math.round(node.position.x), y: Math.round(node.position.y) },
    data: {
      ...data,
      label: node.data.label || LABELS[nodeType],
      prompt: node.data.prompt || '',
      provider: node.data.provider || '',
      model: node.data.model || '',
      mode: node.data.mode || '',
      options: node.data.options || {},
    },
  };
}

export function normalizeEdges(edges: ApiEdge[] | undefined): Edge[] {
  return (edges || []).map((edge) => ({
    id: edge.id || `${edge.source}-${edge.target}-${edge.targetHandle || 'related'}`,
    source: edge.source,
    target: edge.target,
    sourceHandle: edge.sourceHandle || 'output',
    targetHandle: edge.targetHandle || 'related',
    data: { source_run_id: edge.source_run_id, require_accept: edge.require_accept },
    animated: false,
  }));
}

export function toApiEdge(edge: Edge): ApiEdge {
  return {
    id: edge.id,
    source: edge.source,
    target: edge.target,
    sourceHandle: edge.sourceHandle || 'output',
    targetHandle: edge.targetHandle || 'related',
    ...(typeof edge.data?.source_run_id === 'string' ? { source_run_id: edge.data.source_run_id } : {}),
    ...(typeof edge.data?.require_accept === 'boolean' ? { require_accept: edge.data.require_accept } : {}),
  };
}

export function normalizeGraph(graph?: Partial<CanvasGraph>): CanvasGraph {
  return {
    nodes: graph?.nodes || [],
    edges: graph?.edges || [],
    viewport: graph?.viewport || DEFAULT_VIEWPORT,
    selection: graph?.selection || [],
  };
}

export function serializeGraph(nodes: FlowNode[], edges: Edge[], viewport: Viewport, selection: string[]): CanvasGraph {
  return {
    nodes: nodes.map(toApiNode),
    edges: edges.map(toApiEdge),
    viewport,
    selection,
  };
}

export const SOURCE_HANDLE = 'output';

export const TARGET_HANDLES: Record<CanvasNodeType, string[]> = {
  asset: [],
  image: ['reference_image'],
  video: ['first_frame', 'last_frame', 'reference_image', 'reference_video', 'reference_audio'],
};

export function isOutputHandle(handle?: string | null): boolean {
  return !handle || handle === SOURCE_HANDLE || handle.startsWith(`${SOURCE_HANDLE}:`);
}

export function targetHandlesFor(nodeType: CanvasNodeType): string[] {
  return TARGET_HANDLES[nodeType] || [];
}

export function assetToOutput(asset?: { path: string; kind: string; name: string }): RunOutput | undefined {
  return asset?.path ? { path: asset.path, kind: asset.kind || 'file', name: asset.name } : undefined;
}

/** Keep run ordering identical across the canvas, inspector, and connection resolution. */
export function sortRuns(runs: Run[]): Run[] {
  return [...runs].sort((left, right) => `${right.created_at || ''}\u0000${right.id}`.localeCompare(`${left.created_at || ''}\u0000${left.id}`));
}

function knownKind(output?: RunOutput): 'image' | 'video' | 'audio' | undefined {
  if (!output) return undefined;
  const kind = output.kind.toLowerCase();
  if (kind.startsWith('image') || /\.(png|jpe?g|webp|gif)$/i.test(output.path)) return 'image';
  if (kind.startsWith('video') || /\.(mp4|webm|mov|m4v)$/i.test(output.path)) return 'video';
  if (kind.startsWith('audio') || /\.(mp3|wav|m4a|aac|ogg)$/i.test(output.path)) return 'audio';
  return undefined;
}

/** Resolve one explicit output handle, keeping derived outputs separate from the current media. */
export function outputForNode(node: FlowNode, sourceHandle: string | null = SOURCE_HANDLE, runs: Run[] = []): RunOutput | undefined {
  const normalizedHandle = sourceHandle || SOURCE_HANDLE;
  if (normalizedHandle.startsWith(`${SOURCE_HANDLE}:`)) {
    const outputId = normalizedHandle.slice(`${SOURCE_HANDLE}:`.length);
    const derived = node.data.derived_outputs?.find((item) => item.id === outputId);
    return assetToOutput(derived?.asset);
  }
  if (node.data.nodeType === 'image' || node.data.nodeType === 'video') {
    const success = sortRuns(runs).find((run) => run.node_id === node.id && run.status === 'succeeded' && run.outputs?.length);
    if (success?.outputs?.[0]) return success.outputs[0];
  }
  return assetToOutput(node.data.asset);
}

function sourceMatches(source: FlowNode, sourceHandle: string | null | undefined, expected: 'image' | 'video' | 'audio'): boolean {
  const output = outputForNode(source, sourceHandle || SOURCE_HANDLE);
  const outputKind = knownKind(output);
  if (outputKind) return outputKind === expected;
  if (source.data.nodeType === expected) return true;
  if (source.data.nodeType === 'asset') {
    const kind = source.data.asset?.kind?.toLowerCase() || '';
    return !kind || kind.startsWith(expected);
  }
  return false;
}

export function isValidConnection(connection: Connection, nodes: FlowNode[]): boolean {
  if (!connection.source || !connection.target || connection.source === connection.target) return false;
  const target = nodes.find((node) => node.id === connection.target);
  const source = nodes.find((node) => node.id === connection.source);
  if (!target || !source || !isOutputHandle(connection.sourceHandle)) return false;
  const targetHandle = connection.targetHandle;
  if (!targetHandle) return false;
  if (!targetHandlesFor(target.data.nodeType).includes(targetHandle)) return false;
  if (target.data.nodeType === 'asset') return false;
  if (targetHandle === 'first_frame' || targetHandle === 'last_frame' || targetHandle === 'reference_image') {
    return sourceMatches(source, connection.sourceHandle, 'image');
  }
  if (targetHandle === 'reference_video') return sourceMatches(source, connection.sourceHandle, 'video');
  if (targetHandle === 'reference_audio') {
    const outputKind = knownKind(outputForNode(source, connection.sourceHandle || SOURCE_HANDLE));
    return outputKind ? outputKind === 'audio' : source.data.nodeType === 'video' || sourceMatches(source, connection.sourceHandle, 'audio');
  }
  return false;
}

export function addCanvasEdge(edges: Edge[], connection: Connection): Edge[] {
  return addEdge({
    ...connection,
    sourceHandle: connection.sourceHandle || SOURCE_HANDLE,
    targetHandle: connection.targetHandle || 'related',
    animated: false,
  }, edges);
}

export function graphHasNode(graph: CanvasGraph, nodeId: string): boolean {
  return graph.nodes.some((node) => node.id === nodeId);
}

/** Resolve a media input/output without ever using a history entry as the current output. */
export function resolveMediaOutput(nodeId: string, nodes: FlowNode[], edges: Edge[], runs: Run[], visited = new Set<string>()): RunOutput | undefined {
  if (visited.has(nodeId)) return undefined;
  visited.add(nodeId);
  const node = nodes.find((item) => item.id === nodeId);
  if (!node) return undefined;
  return outputForNode(node, SOURCE_HANDLE, runs);
}
