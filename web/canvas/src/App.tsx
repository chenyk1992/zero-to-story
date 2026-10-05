import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import {
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  Background,
  ConnectionMode,
  MiniMap,
  Panel,
  ReactFlow,
  ReactFlowProvider,
  useNodesInitialized,
  useReactFlow,
  useUpdateNodeInternals,
  type Connection,
  type Edge,
  type EdgeChange,
  type NodeChange,
  type Viewport,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import './styles.css';
import { Icon } from './Icon';
import { connectionPresentation } from './connectionFocus';
import { autoCapabilityForNode, hasExecutableSelection, isCapabilitySelectable } from './capabilities';
import { Palette } from './Palette';
import { NodeEditingProvider } from './NodeEditing';
import { ShotOverview } from './ShotOverview';
import { CanvasNode, nodeTypes } from './CanvasNode';
import { Inspector } from './Inspector';
import { importedAssetPatch, sameImportRequest } from './imports';
import {
  ApiError,
  createCanvas,
  executeNode,
  getCanvas,
  getCanvases,
  getCapabilities,
  getContinuations,
  getProductionMetrics,
  getRuns,
  importAssetPath,
  mediaUrl,
  updateCanvas,
  uploadAsset,
} from './api';
import {
  addCanvasEdge,
  moveReferenceEdge,
  createFlowNode,
  DEFAULT_VIEWPORT,
  isValidConnection,
  normalizeEdges,
  resolveMediaOutput,
  serializeGraph,
  sortRuns,
  toFlowNode,
} from './graph';
import type { AssetRef, Canvas, CanvasNodeData, CanvasNodeType, Capability, FlowNode, Run, RunOutput, ProductionSummary } from './types';
import type { PreviewInfo } from './types';
import { ContinuationStatus, type ContinuationLoadState, type ContinuationSummary } from './ContinuationStatus';
import { summarizeContinuations } from './continuations';
import {
  DEFAULT_WORKSPACE,
  isSectionNode,
  isStoryNodeType,
  mediaCountForNode,
  normalizeWorkspace,
  type StoryNodeData,
  type StoryNodePatch,
  type StoryNodeType,
  type WorkspaceMeta,
} from './workspace';
import './workbench.css';

type SaveState = 'idle' | 'dirty' | 'saving' | 'saved' | 'conflict' | 'error';

const GENERATION_KINDS = new Set<CanvasNodeType>(['image', 'video', 'audio']);
const NON_REEXECUTABLE_STATUSES = new Set(['pending_agent', 'queued', 'running', 'unknown']);
const GRAPH_BASE_KEYS = new Set(['nodes', 'edges', 'viewport', 'selection', 'workspace']);

type RawApiNode = {
  id?: string;
  type?: string;
  position?: { x: number; y: number };
  data?: Record<string, unknown>;
};

function extendedData(data: CanvasNodeData, nodeType: StoryNodeType, patch: Partial<StoryNodeData> = {}): CanvasNodeData {
  return { ...data, ...patch, nodeType } as CanvasNodeData;
}

function createWorkspaceNode(nodeType: StoryNodeType, position: { x: number; y: number }): FlowNode {
  if (nodeType !== 'document' && nodeType !== 'section') return createFlowNode(nodeType as CanvasNodeType, position);
  const fallback = createFlowNode('asset', position);
  const data = nodeType === 'document'
    ? extendedData(fallback.data, nodeType, { label: '新文档', content: '# 新文档\n\n记录这一章的故事、分镜或创作说明。', category: 'document', description: '' })
    : extendedData(fallback.data, nodeType, { label: '镜头分区', width: 620, height: 360, description: '拖入角色、分镜和视频卡到这个区域。' });
  return { ...fallback, data, zIndex: nodeType === 'section' ? -1 : 1 };
}

function applyCapabilityDefaults(node: FlowNode, capabilities: Capability[]): FlowNode {
  if (!GENERATION_KINDS.has(node.data.nodeType)) return node;
  const capability = node.data.provider
    ? capabilities.find((item) => item.id === node.data.provider && item.node_types.includes(node.data.nodeType))
    : autoCapabilityForNode(capabilities, node.data.nodeType);
  if (!capability || !isCapabilitySelectable(capability, node.data.nodeType)) return node;
  const provider = node.data.provider || capability.id;
  const model = !node.data.model && capability.models.length === 1 ? capability.models[0].id : node.data.model;
  const mode = !node.data.mode && capability.modes.length === 1 ? capability.modes[0].id : node.data.mode;
  if (provider === node.data.provider && model === node.data.model && mode === node.data.mode) return node;
  return { ...node, data: { ...node.data, provider, model, mode } };
}

function applyAudioCapabilityDefaults(node: FlowNode, capabilities: Capability[]): FlowNode {
  if (node.data.nodeType !== 'audio' || !node.data.provider) return node;
  const capability = capabilities.find((item) => item.id === node.data.provider && item.node_types.includes('audio'));
  if (!capability) return node;
  const current = node.data.options[node.data.provider] || {};
  const next = { ...current };
  let changed = false;
  for (const field of capability.fields) {
    if (field.default !== undefined && next[field.key] === undefined) {
      next[field.key] = field.default;
      changed = true;
    }
  }
  if (!changed) return node;
  return {
    ...node,
    data: {
      ...node.data,
      options: { ...node.data.options, [node.data.provider]: next },
    },
  };
}

function toWorkspaceNode(raw: RawApiNode): FlowNode {
  const rawType = raw.type || raw.data?.nodeType;
  if (isStoryNodeType(rawType) && (rawType === 'document' || rawType === 'section')) {
    const fallback = createWorkspaceNode(rawType, raw.position || { x: 80, y: 80 });
    return {
      ...fallback,
      id: raw.id || fallback.id,
      position: raw.position || fallback.position,
      data: extendedData(fallback.data, rawType, (raw.data || {}) as Partial<StoryNodeData>),
      zIndex: rawType === 'section' ? -1 : 1,
    };
  }
  const node = toFlowNode(raw as never);
  const nodeType = (node.data.nodeType || rawType) as StoryNodeType;
  return isStoryNodeType(nodeType) ? { ...node, zIndex: nodeType === 'section' ? -1 : 1, data: node.data } : node;
}

function styledEdges(edges: Edge[]): Edge[] {
  return edges.map((edge) => edge.targetHandle === 'related'
    ? { ...edge, type: 'smoothstep', className: `${edge.className || ''} related-edge`.trim(), style: { ...edge.style, stroke: '#71809a', strokeWidth: 1.4, strokeDasharray: '6 5' } }
    : edge);
}

function isRelatedConnection(connection: Connection, nodes: FlowNode[]): boolean {
  if (!connection.source || !connection.target || connection.source === connection.target || connection.targetHandle !== 'related') return false;
  const source = nodes.find((node) => node.id === connection.source);
  const target = nodes.find((node) => node.id === connection.target);
  return Boolean(source && target && !isSectionNode(source) && !isSectionNode(target) && (!connection.sourceHandle || connection.sourceHandle === 'output'));
}

function requestId(): string {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function nowLabel(value?: string): string {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
}

function latestSuccessfulRun(runs: Run[], nodeId: string): Run | undefined {
  return sortRuns(runs).find((run) => run.node_id === nodeId && run.status === 'succeeded' && run.outputs?.length);
}

function latestRun(runs: Run[], nodeId: string): Run | undefined {
  return sortRuns(runs).find((run) => run.node_id === nodeId);
}

function firstOutput(run?: Run): RunOutput | undefined {
  return run?.outputs?.[0];
}

function decorateNodes(nodes: FlowNode[], edges: Edge[], runs: Run[], onPreview: (nodeId: string, output?: RunOutput) => void): FlowNode[] {
  const runsByNode = new Map<string, Run[]>();
  for (const run of sortRuns(runs)) {
    const history = runsByNode.get(run.node_id) || [];
    history.push(run);
    runsByNode.set(run.node_id, history);
  }
  return nodes.map((node) => {
    const media = resolveMediaOutput(node.id, nodes, edges, runs);
    if (!GENERATION_KINDS.has(node.data.nodeType) && !media) return node;
    const nodeRuns = runsByNode.get(node.id) || [];
    const last = nodeRuns[0];
    const runHistory = nodeRuns.filter((run) => run.status === 'succeeded' && run.outputs?.length);
    const success = runHistory[0];
    const output = firstOutput(success) || media;
    const preview: PreviewInfo | undefined = output ? { runId: success?.id || `asset-${node.id}`, output } : undefined;
    return {
      ...node,
      data: {
        ...node.data,
        runStatus: last?.status,
        runError: last?.error,
        resultChanged: last?.matches_current === false,
        latestPreview: preview,
        latestSuccessfulRun: success,
        runHistory,
        onPreview: preview ? (requestedOutput) => onPreview(node.id, requestedOutput) : undefined,
      },
    };
  });
}

function App() {
  const [canvases, setCanvases] = useState<Canvas[]>([]);
  const [activeId, setActiveId] = useState<string>();
  const [canvasName, setCanvasName] = useState('');
  const [workspaceMeta, setWorkspaceMeta] = useState<WorkspaceMeta>(DEFAULT_WORKSPACE);
  const [version, setVersion] = useState(0);
  const [nodes, setNodes] = useState<FlowNode[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [viewport, setViewport] = useState<Viewport>(DEFAULT_VIEWPORT);
  const [selectedId, setSelectedId] = useState<string>();
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [continuationState, setContinuationState] = useState<ContinuationLoadState>('loading');
  const [continuationSummary, setContinuationSummary] = useState<ContinuationSummary>();
  const [productionSummary, setProductionSummary] = useState<ProductionSummary>();
  const [dirty, setDirty] = useState(false);
  const [saveState, setSaveState] = useState<SaveState>('idle');
  const [saveError, setSaveError] = useState('');
  const [saveBlocked, setSaveBlocked] = useState(false);
  const [loading, setLoading] = useState(true);
  const [connectionError, setConnectionError] = useState('');
  const [previewRun, setPreviewRun] = useState<Run>();
  const [previewMedia, setPreviewMedia] = useState<RunOutput>();
  const [isComposing, setIsComposing] = useState(false);
  const composingNodesRef = useRef(new Set<string>());
  const submissionsRef = useRef(new Set<string>());
  const [submittingNodes, setSubmittingNodes] = useState(new Set<string>());
  const [storyInfoOpen, setStoryInfoOpen] = useState(false);

  const versionRef = useRef(version);
  const nameRef = useRef(canvasName);
  const activeIdRef = useRef(activeId);
  const nodesRef = useRef(nodes);
  const edgesRef = useRef(edges);
  const runsRef = useRef(runs);
  const runsRequestRef = useRef(0);
  const continuationsRequestRef = useRef(0);
  const productionRequestRef = useRef(0);
  const viewportRef = useRef(viewport);
  const selectedIdRef = useRef(selectedId);
  const dirtyRef = useRef(dirty);
  const draftRevisionRef = useRef(0);
  const composingRef = useRef(false);
  const saveTimerRef = useRef<number | undefined>(undefined);
  const savePromisesRef = useRef(new Map<string, Promise<boolean>>());
  const saveRequestTokensRef = useRef(new Map<string, symbol>());
  const saveCanvasRef = useRef<((force?: boolean) => Promise<boolean>) | undefined>(undefined);
  const pendingAudioDefaultsRef = useRef(new Set<string>());
  const bootRef = useRef(false);
  const workspaceRef = useRef<WorkspaceMeta>(DEFAULT_WORKSPACE);
  const graphMetaRef = useRef<Record<string, unknown>>({});

  versionRef.current = version;
  nameRef.current = canvasName;
  activeIdRef.current = activeId;
  nodesRef.current = nodes;
  edgesRef.current = edges;
  runsRef.current = runs;
  viewportRef.current = viewport;
  selectedIdRef.current = selectedId;
  dirtyRef.current = dirty;



  const applyCanvas = useCallback((canvas: Canvas, preserveSelection = false) => {
    if (activeIdRef.current !== canvas.id) {
      composingNodesRef.current.clear();
      composingRef.current = false;
      setIsComposing(false);
      pendingAudioDefaultsRef.current.clear();
      activeIdRef.current = canvas.id;
      runsRequestRef.current += 1;
      continuationsRequestRef.current += 1;
      productionRequestRef.current += 1;
      setRuns([]);
      setContinuationSummary(undefined);
      setProductionSummary(undefined);
      setContinuationState('loading');
    }
    setActiveId(canvas.id);
    setCanvasName(canvas.name);
    setVersion(canvas.version);
    const rawGraph = (canvas.graph || {}) as unknown as Record<string, unknown>;
    const nextWorkspace = normalizeWorkspace(rawGraph.workspace, canvas.name);
    const graphMeta = Object.fromEntries(Object.entries(rawGraph).filter(([key]) => !GRAPH_BASE_KEYS.has(key)));
    workspaceRef.current = nextWorkspace;
    graphMetaRef.current = graphMeta;
    setWorkspaceMeta(nextWorkspace);
    const nextEdges = styledEdges(normalizeEdges(Array.isArray(rawGraph.edges) ? rawGraph.edges as never[] : undefined));
    const rawNodes = Array.isArray(rawGraph.nodes) ? rawGraph.nodes as RawApiNode[] : [];
    const nextNodes = rawNodes.map(toWorkspaceNode);
    setNodes(nextNodes);
    setEdges(nextEdges);
    nodesRef.current = nextNodes;
    edgesRef.current = nextEdges;
    setViewport(canvas.graph?.viewport || DEFAULT_VIEWPORT);
    const nextSelection = preserveSelection && selectedIdRef.current && nextNodes.some((node) => node.id === selectedIdRef.current) ? selectedIdRef.current : Array.isArray(rawGraph.selection) ? rawGraph.selection[0] as string | undefined : undefined;
    selectedIdRef.current = nextSelection;
    setSelectedId(nextSelection);

    if (typeof window !== 'undefined' && window.history?.replaceState) {
      const url = new URL(window.location.href);
      url.searchParams.set('canvas', canvas.id);
      window.history.replaceState(null, '', url);
    }
    setDirty(false);
    dirtyRef.current = false;
    setSaveBlocked(false);
    setSaveError('');
    setSaveState('saved');
    draftRevisionRef.current += 1;
  }, []);

  const refreshRuns = useCallback(async (canvasId: string) => {
    const requestNumber = ++runsRequestRef.current;
    try {
      const response = await getRuns(canvasId);
      if (activeIdRef.current !== canvasId || requestNumber !== runsRequestRef.current) return;
      setRuns(response.runs || []);
      setNodes((current) => decorateNodes(current, edgesRef.current, response.runs || [], (nodeId, requestedOutput) => {
        if (requestedOutput) {
          setPreviewMedia(requestedOutput);
          return;
        }
        const success = latestSuccessfulRun(response.runs || [], nodeId);
        if (success) setPreviewRun(success);
        else {
          // Resolve against the latest node ref when the preview is clicked.
          // Importing a replacement asset must never reopen a stale closure.
          const media = resolveMediaOutput(nodeId, nodesRef.current, edgesRef.current, response.runs || []);
          if (media) setPreviewMedia(media);
        }
      }));
    } catch {
      // The canvas remains usable when run history is temporarily unavailable.
    }
  }, []);

  const refreshContinuations = useCallback(async (canvasId: string) => {
    const requestNumber = ++continuationsRequestRef.current;
    const continuations = await Promise.allSettled([getContinuations(canvasId)]);
    if (activeIdRef.current !== canvasId || requestNumber !== continuationsRequestRef.current) return;
    if (continuations[0].status === 'fulfilled') {
      setContinuationSummary(summarizeContinuations(continuations[0].value));
      setContinuationState('available');
    } else {
      setContinuationSummary(undefined);
      setContinuationState('unavailable');
    }
  }, []);

  const refreshProductionSummary = useCallback(async (canvasId: string) => {
    const requestNumber = ++productionRequestRef.current;
    try {
      const production = await getProductionMetrics(canvasId);
      if (activeIdRef.current !== canvasId || requestNumber !== productionRequestRef.current) return;
      setProductionSummary(production);
    } catch {
      if (activeIdRef.current !== canvasId || requestNumber !== productionRequestRef.current) return;
      setProductionSummary(undefined);
    }
  }, []);

  useEffect(() => {
    if (bootRef.current) return;
    bootRef.current = true;
    let cancelled = false;
    setLoading(true);
    Promise.allSettled([getCanvases(), getCapabilities()]).then(async ([canvasResult, capabilityResult]) => {
      if (cancelled) return;
      if (capabilityResult.status === 'fulfilled') setCapabilities(capabilityResult.value.capabilities || []);
      else setConnectionError('能力信息暂时不可用，画布仍可编辑，执行前会由服务端再次校验。');
      if (canvasResult.status === 'fulfilled') {
        setCanvases(canvasResult.value.canvases || []);
        const requestedId = typeof window !== 'undefined' ? new URLSearchParams(window.location.search).get('canvas') : null;
        const first = canvasResult.value.canvases?.find((canvas) => canvas.id === requestedId) || canvasResult.value.canvases?.[0];
        if (first) {
          try {
            const full = await getCanvas(first.id);
            if (!cancelled) {
              applyCanvas(full);
              await Promise.all([refreshRuns(full.id), refreshContinuations(full.id)]);
              void refreshProductionSummary(full.id);
            }
          } catch {
            if (!cancelled) setConnectionError('无法打开第一个画布。请检查本地服务状态。');
          }
        } else {
          try {
              const created = await createCanvas('新故事 · 第1章');
            if (!cancelled) {
              setCanvases([created]);
              applyCanvas(created);
              await refreshContinuations(created.id);
              void refreshProductionSummary(created.id);
            }
          } catch {
            if (!cancelled) setConnectionError('还没有画布，点击“新建画布”后可以重试。');
          }
        }
      } else if (!cancelled) {
        setConnectionError('暂时无法连接画布服务。启动本地服务后可以重新加载。');
      }
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; };
  }, [applyCanvas, refreshContinuations, refreshProductionSummary, refreshRuns]);

  const markDirty = useCallback(() => {
    draftRevisionRef.current += 1;
    dirtyRef.current = true;
    setDirty(true);
    setSaveState('dirty');
    setSaveError('');
  }, []);

  const selectNode = useCallback((id?: string) => {

    if (selectedIdRef.current === id) return;
    selectedIdRef.current = id;
    setSelectedId(id);
    markDirty();
  }, [markDirty]);

  const updateWorkspace = useCallback((patch: Partial<WorkspaceMeta>) => {
    const next = { ...workspaceRef.current, ...patch };
    workspaceRef.current = next;
    setWorkspaceMeta(next);
    if (patch.story !== undefined) {
      const name = patch.story.trim() || '未命名故事';
      setCanvasName(name);
      nameRef.current = name;
    }
    markDirty();
  }, [markDirty]);

  useEffect(() => {
    if (!capabilities.length) return;
    setNodes((current) => {
      let changed = false;
      const next = current.map((node) => {
        const routed = applyCapabilityDefaults(node, capabilities);
        const hydrated = pendingAudioDefaultsRef.current.has(node.id)
          ? applyAudioCapabilityDefaults(routed, capabilities)
          : routed;
        if (pendingAudioDefaultsRef.current.has(node.id) && hydrated.data.provider) pendingAudioDefaultsRef.current.delete(node.id);
        if (hydrated !== node) changed = true;
        return hydrated;
      });
      if (changed) markDirty();
      return next;
    });
  }, [capabilities, markDirty]);

  const saveCanvas = useCallback(async (force = false): Promise<boolean> => {
    const canvasId = activeIdRef.current;
    if (!canvasId) return false;
    if (composingRef.current) return false;
    if (!force && !dirtyRef.current) return true;
    const existing = savePromisesRef.current.get(canvasId);
    if (existing) return existing;
    const revision = draftRevisionRef.current;
    const serialized = serializeGraph(nodesRef.current, edgesRef.current, viewportRef.current, selectedIdRef.current ? [selectedIdRef.current] : []);
    const graph = {
      ...graphMetaRef.current,
      ...serialized,
      workspace: workspaceRef.current,
    } as typeof serialized;
    const expectedVersion = versionRef.current;
    setSaveState('saving');
    const requestToken = Symbol(canvasId);
    saveRequestTokensRef.current.set(canvasId, requestToken);
    let saveSucceeded = false;
    const promise = updateCanvas(canvasId, expectedVersion, graph, nameRef.current)
      .then((saved) => {
        // A response may arrive after the user has switched canvases. It may
        // refresh the A entry in the selector, but must not overwrite B's
        // version, draft, or save indicator.
        if (activeIdRef.current === canvasId) {
          setVersion(saved.version);
          versionRef.current = saved.version;
          if (revision === draftRevisionRef.current) {
            setDirty(false);
            dirtyRef.current = false;
            setSaveState('saved');
          } else {
            setSaveState('dirty');
          }
          setSaveBlocked(false);
          setSaveError('');
        }
        setCanvases((current) => current.map((item) => item.id === saved.id ? saved : item));
        saveSucceeded = true;
        return true;
      })
      .catch((error: unknown) => {
        if (activeIdRef.current === canvasId) {
          const apiError = error instanceof ApiError ? error : undefined;
          const conflict = apiError?.status === 409 || apiError?.code === 'version_conflict';
          setSaveState(conflict ? 'conflict' : 'error');
          setSaveBlocked(conflict);
          setSaveError(conflict ? '服务端版本已变化，草稿仍保留在当前页面。请刷新服务版本后再决定是否覆盖。' : (error instanceof Error ? error.message : '保存失败'));
        }
        return false;
      })
      .finally(() => {
        if (saveRequestTokensRef.current.get(canvasId) === requestToken) {
          saveRequestTokensRef.current.delete(canvasId);
          savePromisesRef.current.delete(canvasId);
          if (saveSucceeded && activeIdRef.current === canvasId && dirtyRef.current && !composingRef.current) {
            window.setTimeout(() => {
              if (activeIdRef.current === canvasId && dirtyRef.current && !composingRef.current) void saveCanvasRef.current?.();
            }, 0);
          }
        }
      });
    savePromisesRef.current.set(canvasId, promise);
    return promise;
  }, []);
  saveCanvasRef.current = saveCanvas;

  useEffect(() => {
    if (!activeId || !dirty) return;
    if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current);
    saveTimerRef.current = window.setTimeout(() => {
      if (!composingRef.current) void saveCanvasRef.current?.();
    }, 800);
    return () => { if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current); };
  }, [activeId, dirty, nodes, edges, viewport, canvasName, workspaceMeta]);

  useEffect(() => {
    if (!activeId) return;
    const timer = window.setInterval(async () => {
      if (dirtyRef.current || composingRef.current || savePromisesRef.current.has(activeId)) {
        await Promise.all([refreshRuns(activeId), refreshContinuations(activeId)]);
        return;
      }
      try {
        const remote = await getCanvas(activeId);
        if (activeIdRef.current !== activeId) return;
        if (remote.version > versionRef.current && !dirtyRef.current && !composingRef.current && !savePromisesRef.current.has(activeId)) applyCanvas(remote, true);
      } catch {
        // Polling is best-effort and must never replace a local draft.
      }
      if (activeIdRef.current !== activeId) return;
      await Promise.all([refreshRuns(activeId), refreshContinuations(activeId)]);
    }, 3500);
    return () => window.clearInterval(timer);
  }, [activeId, applyCanvas, refreshContinuations, refreshRuns]);

  useEffect(() => {
    if (!activeId) return;
    const timer = window.setInterval(() => {
      void refreshProductionSummary(activeId);
    }, 15000);
    return () => window.clearInterval(timer);
  }, [activeId, refreshProductionSummary]);

  const updateNodeById = useCallback((id: string, patch: StoryNodePatch) => {
    const selected = nodesRef.current.find((node) => node.id === id);
    if (!selected) return;
    const changedAudioProvider = selected.data.nodeType === 'audio'
      && patch.provider !== undefined && patch.provider !== selected.data.provider;
    if (changedAudioProvider) pendingAudioDefaultsRef.current.delete(id);
    const next = nodesRef.current.map((node) => {
      if (node.id !== id) return node;
      const updated = { ...node, data: { ...node.data, ...patch, resultChanged: Boolean(node.data.latestSuccessfulRun) } };
      return changedAudioProvider ? applyAudioCapabilityDefaults(updated, capabilities) : updated;
    });
    nodesRef.current = next;
    setNodes(next);
    markDirty();
  }, [capabilities, markDirty]);

  const updateNodeOptions = useCallback((id: string, provider: string, key: string, value: string | number | boolean | undefined) => {
    const node = nodesRef.current.find((item) => item.id === id);
    if (!node) return;
    updateNodeById(id, { options: { ...node.data.options, [provider]: { ...node.data.options[provider], [key]: value } } });
  }, [updateNodeById]);

  const setNodeComposing = useCallback((id: string, composing: boolean) => {
    if (composing) composingNodesRef.current.add(id);
    else composingNodesRef.current.delete(id);
    composingRef.current = composingNodesRef.current.size > 0;
    setIsComposing(composingRef.current);
    if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current);
    if (!composingRef.current && dirtyRef.current) {
      saveTimerRef.current = window.setTimeout(() => void saveCanvasRef.current?.(), 250);
    }
  }, []);
  const addNodeAt = useCallback((nodeType: StoryNodeType, position: { x: number; y: number }) => {
    const routed = applyCapabilityDefaults(createWorkspaceNode(nodeType, position), capabilities);
    const node = applyAudioCapabilityDefaults(routed, capabilities);
    if (nodeType === 'audio' && !node.data.provider) pendingAudioDefaultsRef.current.add(node.id);
    setNodes((current) => [...current, node]);
    selectedIdRef.current = node.id;
    setSelectedId(node.id);

    markDirty();
  }, [capabilities, markDirty]);

  const removeNodeById = useCallback((id: string) => {
    setNodes((current) => current.filter((node) => node.id !== id));
    setEdges((current) => current.filter((edge) => edge.source !== id && edge.target !== id));
    selectedIdRef.current = undefined;
    setSelectedId(undefined);

    markDirty();
  }, [markDirty]);

  const handleCreate = useCallback(async () => {
    try {
      const created = await createCanvas('新故事 · 第1章');
      setCanvases((current) => [...current, created]);
      applyCanvas(created);
      updateWorkspace({ story: '新故事', chapter: '第1章', summary: '' });
      await refreshContinuations(created.id);
      void refreshProductionSummary(created.id);
      setConnectionError('');
    } catch (error) {
      setConnectionError(error instanceof Error ? error.message : '新建画布失败');
    }
  }, [applyCanvas, refreshContinuations, refreshProductionSummary, updateWorkspace]);

  const handleSelectCanvas = useCallback(async (canvasId: string) => {
    if (canvasId === activeIdRef.current) return;
    if (dirtyRef.current || composingRef.current) {
      const confirmed = window.confirm('当前画布有未保存改动。切换后会放弃这些改动，是否继续？');
      if (!confirmed) return;
    }
    try {
      const canvas = await getCanvas(canvasId);
      applyCanvas(canvas);
      await Promise.all([refreshRuns(canvas.id), refreshContinuations(canvas.id)]);
      void refreshProductionSummary(canvas.id);
    } catch (error) {
      setConnectionError(error instanceof Error ? error.message : '打开画布失败');
    }
  }, [applyCanvas, refreshContinuations, refreshProductionSummary, refreshRuns]);

  const handleNameChange = (name: string) => {
    setCanvasName(name);
    nameRef.current = name;
    markDirty();
  };

  const handleExecute = useCallback(async (nodeId: string) => {
    const node = nodesRef.current.find((item) => item.id === nodeId);
    const canvasId = activeIdRef.current;
    if (!node || !canvasId || !GENERATION_KINDS.has(node.data.nodeType) || saveBlocked || composingRef.current) return;
    if (NON_REEXECUTABLE_STATUSES.has(latestRun(runsRef.current, node.id)?.status || node.data.runStatus || '')) return;
    const submissionKey = `${canvasId}:${nodeId}`;
    if (submissionsRef.current.has(submissionKey)) return;
    submissionsRef.current.add(submissionKey);
    setSubmittingNodes(new Set(submissionsRef.current));
    try {
      const saved = await saveCanvas(true);
      if (activeIdRef.current !== canvasId || !saved || dirtyRef.current || saveBlocked || composingRef.current) return;
      const savedVersion = versionRef.current;
      const run = await executeNode(canvasId, node.id, savedVersion, requestId());
      if (activeIdRef.current !== canvasId) return;
      setRuns((current) => [run, ...current.filter((item) => item.id !== run.id)]);
      setNodes((current) => current.map((item) => item.id === node.id ? { ...item, data: { ...item.data, runStatus: run.status, runError: run.error, resultChanged: run.matches_current === false } } : item));
    } catch (error) {
      if (activeIdRef.current !== canvasId) return;
      const message = error instanceof Error ? error.message : '执行请求失败';
      setNodes((current) => current.map((item) => item.id === node.id ? { ...item, data: { ...item.data, runStatus: 'failed', runError: message } } : item));
    } finally {
      submissionsRef.current.delete(submissionKey);
      setSubmittingNodes(new Set(submissionsRef.current));
    }
  }, [saveBlocked, saveCanvas]);

  const handleUploadAsset = useCallback(async (nodeId: string, file: File) => {
    const canvasId = activeIdRef.current;
    if (!nodeId || !canvasId) return;
    if (latestSuccessfulRun(runsRef.current, nodeId)) {
      setConnectionError('这个组件已有成功成品，当前不会覆盖它。请新建一个图片或视频组件来导入另一份成品。');
      return;
    }
    const asset = await uploadAsset(file);
    if (activeIdRef.current !== canvasId) return;
    const current = nodesRef.current.find((node) => node.id === nodeId);
    if (!current) return;
    const patch = importedAssetPatch(current.data as unknown as StoryNodeData, asset as AssetRef);
    if (patch) updateNodeById(nodeId, patch);
  }, [updateNodeById]);

  const handleImportPath = useCallback(async (nodeId: string) => {
    const canvasId = activeIdRef.current;
    if (!nodeId || !canvasId) return;
    if (latestSuccessfulRun(runsRef.current, nodeId)) {
      setConnectionError('这个组件已有成功成品，当前不会覆盖它。请新建一个图片或视频组件来导入另一份成品。');
      return;
    }
    const node = nodesRef.current.find((item) => item.id === nodeId);
    const path = node?.data.import_path ?? node?.data.asset?.path;
    if (!path) return;
    if (node && sameImportRequest(node.data as unknown as StoryNodeData, path)) return;
    try {
      const asset = await importAssetPath(path);
      if (activeIdRef.current !== canvasId) return;
      const current = nodesRef.current.find((item) => item.id === nodeId);
      if (!current) return;
      const patch = importedAssetPatch(current.data as unknown as StoryNodeData, asset as AssetRef, path);
      if (patch) updateNodeById(nodeId, patch);
    } catch (error) {
      setConnectionError(error instanceof Error ? error.message : '导入素材失败');
    }
  }, [updateNodeById]);

  // Keep an unmount/blur from an old canvas from editing a reused node ID.
  const updateCurrentCanvasNode = (id: string, patch: StoryNodePatch) => {
    if (activeIdRef.current === activeId) updateNodeById(id, patch);
  };
  const setCurrentCanvasComposing = (id: string, composing: boolean) => {
    if (activeIdRef.current === activeId) setNodeComposing(id, composing);
  };
  const renderNodeSettings = (id: string) => {
    const node = nodes.find((item) => item.id === id);
    if (!node) return null;
    return <Inspector key={`${activeId}:${id}`} embedded node={node} nodes={nodes} edges={edges} capabilities={capabilities} runs={runs}
      canExecute={Boolean(activeId && !isComposing && !submittingNodes.has(`${activeId}:${id}`) && GENERATION_KINDS.has(node.data.nodeType) && hasExecutableSelection(node.data.provider, node.data.model, node.data.mode, node.data.nodeType, capabilities, node.data.options[node.data.provider] || {}))}
      saveBlocked={saveBlocked}
      onUpdate={(patch) => updateCurrentCanvasNode(id, patch)}
      onUpdateOptions={(provider, key, value) => updateNodeOptions(id, provider, key, value)}
      onMoveReference={(edgeId, direction) => { setEdges((current) => moveReferenceEdge(current, edgeId, direction)); markDirty(); }}
      onSelectNode={selectNode}
      onRemove={() => removeNodeById(id)}
      onExecute={() => void handleExecute(id)}
      onUploadAsset={(file) => handleUploadAsset(id, file)}
      onImportAssetPath={() => handleImportPath(id)}
      onCompositionChange={(composing) => setCurrentCanvasComposing(id, composing)}
      onOpenPreview={(run) => setPreviewRun(run)} onOpenMedia={(output) => setPreviewMedia(output)} />;
  };
  const currentCanvas = canvases.find((canvas) => canvas.id === activeId);
  const statusLabel = saveState === 'saving' ? '保存中' : saveState === 'dirty' ? '待保存' : saveState === 'conflict' ? '版本冲突' : saveState === 'error' ? '保存失败' : '已保存';
  const statusClass = saveState === 'saved' ? 'status-saved' : saveState === 'conflict' || saveState === 'error' ? 'status-error' : saveState === 'saving' ? 'status-saving' : 'status-dirty';

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="topbar-title"><div className="app-mark"><Icon name="film" size={20} /></div><strong>导演工作台</strong></div>
        <div className="canvas-switcher">
          <select value={activeId || ''} onChange={(event) => void handleSelectCanvas(event.target.value)} disabled={!canvases.length} aria-label="选择画布">
            {!canvases.length && <option value="">未连接</option>}
            {canvases.map((canvas) => <option key={canvas.id} value={canvas.id}>{canvas.name || '未命名画布'}</option>)}
          </select>
          <button className="new-canvas-button" type="button" onClick={() => void handleCreate()} title="新建故事画布" aria-label="新建画布"><Icon name="plus" /><span>新建</span></button>
        </div>
        <div className="topbar-actions">
          {connectionError && <span className="connection-note" title={connectionError}>服务提示</span>}
          <span className={`save-indicator ${statusClass}`} role="status" title={saveState === 'saved' ? `已自动保存 ${nowLabel(currentCanvas?.updated_at)}` : saveError || statusLabel}><Icon name={saveState === 'saved' ? 'check' : saveState === 'error' || saveState === 'conflict' ? 'alert' : 'history'} size={14} /><span>{statusLabel}</span></span>
          <ContinuationStatus state={continuationState} summary={continuationSummary} productionSummary={productionSummary} onRefresh={activeId ? () => {
            void Promise.all([refreshContinuations(activeId), refreshProductionSummary(activeId)]);
          } : undefined} />
          <button className={`inspector-toggle${storyInfoOpen ? ' active' : ''}`} type="button" onClick={() => setStoryInfoOpen((open) => !open)} aria-label="章节信息" aria-expanded={storyInfoOpen} title="编辑故事与章节信息"><Icon name="info" /><span>章节信息</span></button>
          {saveError && <button className="save-error-button" type="button" title={saveError} onClick={() => { setSaveBlocked(false); void saveCanvas(true); }}>重试</button>}
        </div>
      </header>
      {storyInfoOpen && <section className="story-meta-bar" aria-label="故事章节信息">
        <label className="story-meta-field story-title-field"><span>故事标题</span><input value={workspaceMeta.story} onChange={(event) => updateWorkspace({ story: event.target.value })} placeholder="例如：雨夜归途" /></label>
        <label className="story-meta-field story-chapter-field"><span>章节</span><input value={workspaceMeta.chapter} onChange={(event) => updateWorkspace({ chapter: event.target.value })} placeholder="第1章" /></label>
        <label className="story-meta-field story-summary-field"><span>章节摘要</span><input value={workspaceMeta.summary} onChange={(event) => updateWorkspace({ summary: event.target.value })} placeholder="这一章发生了什么？" /></label>
        <span className="story-meta-count">{nodes.filter((node) => !isSectionNode(node)).length} 个组件 · {nodes.reduce((count, node) => count + mediaCountForNode({ data: node.data as unknown as StoryNodeData }), 0)} 份已有媒体 · {nodes.filter((node) => isSectionNode(node)).length} 个分区</span>
      </section>}
      <div className="workspace">
        <NodeEditingProvider value={{ updateNode: updateCurrentCanvasNode, setComposing: setCurrentCanvasComposing, renderSettings: renderNodeSettings, finishEditing: () => selectNode(undefined) }}><ReactFlowProvider>
          <Workspace
            key={activeId}
            nodes={nodes}
            edges={edges}
            runs={runs}
            viewport={viewport}
            selectedId={selectedId}
            onAddNode={addNodeAt}
            onSelectNode={selectNode}
            onFocusNode={selectNode}
            onPreview={(_id, output) => { if (output) setPreviewMedia(output); }}
            onNodesChange={(changes) => {
              setNodes((current) => applyNodeChanges(changes, current) as FlowNode[]);
              const selectionChanges = changes.filter((change) => change.type === 'select');
              if (selectionChanges.length) {
                const selectedChange = [...selectionChanges].reverse().find((change) => change.type === 'select' && change.selected);
                if (selectedChange && 'id' in selectedChange) {
                  selectNode(selectedChange.id);
                } else if (selectionChanges.some((change) => change.type === 'select' && !change.selected && 'id' in change && change.id === selectedIdRef.current)) {
                  selectNode(undefined);
                }
              }
              if (changes.some((change) => ['add', 'remove', 'position', 'replace'].includes(change.type))) markDirty();
            }}
            onEdgesChange={(changes) => {
              setEdges((current) => {
                const nextEdges = applyEdgeChanges(changes, current);
                edgesRef.current = nextEdges;
                return nextEdges;
              });
              if (changes.some((change) => change.type !== 'select')) markDirty();
            }}
            onConnect={(connection) => {
              if (isRelatedConnection(connection, nodesRef.current) || isValidConnection(connection, nodesRef.current)) {
                setConnectionError('');
                setEdges((current) => {
                  const nextEdges = styledEdges(addCanvasEdge(current, connection));
                  edgesRef.current = nextEdges;
                  return nextEdges;
                });
                markDirty();
              }
            }}
            onViewportChange={(nextViewport) => {
              const previous = viewportRef.current;
              const unchanged = Math.abs(previous.x - nextViewport.x) < 0.01
                && Math.abs(previous.y - nextViewport.y) < 0.01
                && Math.abs(previous.zoom - nextViewport.zoom) < 0.0001;
              setViewport(nextViewport);
              viewportRef.current = nextViewport;
              if (!unchanged) markDirty();
            }}
            onDeleteNodes={(deleted) => { const deletedIds = new Set(deleted.map((node) => node.id)); setEdges((current) => current.filter((edge) => !deletedIds.has(edge.source) && !deletedIds.has(edge.target))); if (deletedIds.has(selectedIdRef.current || '')) { selectedIdRef.current = undefined; setSelectedId(undefined); } markDirty(); }}
          />
        </ReactFlowProvider></NodeEditingProvider>
      </div>
      {loading && <div className="loading-overlay"><div className="loader-ring" /><span>正在打开画布…</span></div>}
      {connectionError && !activeId && !loading && <div className="connection-overlay"><div className="connection-card"><div className="connection-icon"><Icon name="link" size={28} /></div><h2>画布服务暂时未连接</h2><p>{connectionError}</p><button type="button" onClick={() => window.location.reload()}>重新连接</button></div></div>}
      {previewRun && <PreviewModal run={previewRun} onClose={() => setPreviewRun(undefined)} />}
      {!previewRun && previewMedia && <MediaModal output={previewMedia} onClose={() => setPreviewMedia(undefined)} />}
    </main>
  );
}

interface WorkspaceProps {
  nodes: FlowNode[];
  edges: Edge[];
  runs: Run[];
  viewport: Viewport;
  selectedId?: string;
  onAddNode: (type: StoryNodeType, position: { x: number; y: number }) => void;
  onSelectNode: (id?: string) => void;
  onFocusNode: (id: string) => void;
  onPreview: (id: string, output?: RunOutput) => void;
  onNodesChange: (changes: NodeChange<FlowNode>[]) => void;
  onEdgesChange: (changes: EdgeChange[]) => void;
  onConnect: (connection: Connection) => void;
  onViewportChange: (viewport: Viewport) => void;
  onDeleteNodes: (nodes: FlowNode[]) => void;
}

function Workspace(props: WorkspaceProps) {
  const { screenToFlowPosition, fitView, zoomIn, zoomOut, zoomTo } = useReactFlow();
  const flowShellRef = useRef<HTMLElement>(null);
  const [paletteCollapsed, setPaletteCollapsed] = useState(() => window.innerWidth <= 1050);
  const [minimapOpen, setMinimapOpen] = useState(false);
  const [view, setView] = useState<'canvas' | 'shots'>('canvas');
  const [tool, setTool] = useState<'select' | 'hand'>('select');
  const [searchRequest, setSearchRequest] = useState(0);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [addMenuOpen, setAddMenuOpen] = useState(false);
  const shortcutButtonRef = useRef<HTMLButtonElement>(null);
  const addButtonRef = useRef<HTMLButtonElement>(null);
  const toolbarRef = useRef<HTMLDivElement>(null);
  const [connectionFocus, setConnectionFocus] = useState<{ id: string; pulse: number }>();
  const presentation = useMemo(() => connectionPresentation(
    props.nodes.map((node) => ({ ...node, selected: node.id === props.selectedId })),
    props.edges, connectionFocus?.id, connectionFocus?.pulse, props.viewport.zoom,
  ), [props.nodes, props.edges, props.selectedId, connectionFocus, props.viewport.zoom]);
  const focusedConnection = presentation.focus;
  const clearConnectionFocus = useCallback(() => setConnectionFocus(undefined), []);
  const highlightConnection = (id: string) => {
    setConnectionFocus((current) => ({ id, pulse: (current?.pulse || 0) + 1 }));
    props.onSelectNode(undefined);
  };
  useEffect(() => {
    if (!focusedConnection) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !event.defaultPrevented) clearConnectionFocus();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [focusedConnection?.edge.id, clearConnectionFocus]);
  useEffect(() => {
    const query = window.matchMedia('(max-width: 1050px)');
    const handleResize = () => setPaletteCollapsed(query.matches);
    query.addEventListener('change', handleResize);
    return () => query.removeEventListener('change', handleResize);
  }, []);
  const focusNode = (id: string) => {
    setView('canvas');
    clearConnectionFocus();
    if (window.innerWidth <= 1050) setPaletteCollapsed(true);
    props.onFocusNode(id);
    // Allow the inline editor to mount before focusing the card.
    window.requestAnimationFrame(() => void fitView({ nodes: [{ id }], padding: 0.3, maxZoom: 1.05, duration: 280 }));
  };
  const onDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    const type = event.dataTransfer.getData('application/x-canvas-node') as StoryNodeType;
    if (!type || !['document', 'section', 'asset', 'image', 'video', 'audio'].includes(type)) return;
    clearConnectionFocus();
    if (window.innerWidth <= 1050) setPaletteCollapsed(true);
    props.onAddNode(type, screenToFlowPosition({ x: event.clientX, y: event.clientY }));
  };
  const addFromPalette = (type: StoryNodeType) => {
    const bounds = flowShellRef.current?.getBoundingClientRect();
    if (!bounds) return;
    clearConnectionFocus();
    setView('canvas');
    setAddMenuOpen(false);
    if (window.innerWidth <= 1050) setPaletteCollapsed(true);
    // The canvas renderer can be hidden in shot overview. Use its visible shell
    // and the shared viewport instead of measuring the hidden React Flow DOM.
    const center = { x: (bounds.width / 2 - props.viewport.x) / props.viewport.zoom, y: (bounds.height / 2 - props.viewport.y) / props.viewport.zoom };
    props.onAddNode(type, { x: center.x - 160, y: center.y - 80 });
  };
  const openSearch = () => {
    setPaletteCollapsed(false);
    setSearchRequest((request) => request + 1);
  };
  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.isComposing || event.ctrlKey || event.metaKey || event.altKey || document.querySelector('[aria-modal="true"]')) return;
      const target = event.target instanceof Element ? event.target : null;
      if (target?.closest('input, textarea, select, [contenteditable="true"], [role="textbox"]')) return;
      if (event.key === 'Escape') {
        if (shortcutsOpen) { setShortcutsOpen(false); shortcutButtonRef.current?.focus(); }
        if (addMenuOpen) { setAddMenuOpen(false); addButtonRef.current?.focus(); }
        return;
      }
      if (event.key === '/') { event.preventDefault(); openSearch(); }
      else if (event.key === '?') { event.preventDefault(); setShortcutsOpen((open) => !open); setAddMenuOpen(false); }
      else if (view === 'canvas' && !event.repeat) {
        const key = event.key.toLowerCase();
        if (key === 'v') setTool('select');
        else if (key === 'h') setTool('hand');
        else if (key === 'f') {
          event.preventDefault();
          void fitView({ ...(event.shiftKey && props.selectedId ? { nodes: [{ id: props.selectedId }], maxZoom: 1.05 } : {}), padding: 0.2, duration: 280 });
        }
        else if (event.key === '0') { event.preventDefault(); void zoomTo(1, { duration: 220 }); }
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [view, shortcutsOpen, addMenuOpen, props.selectedId, fitView, zoomTo]);
  useEffect(() => {
    if (!shortcutsOpen && !addMenuOpen) return;
    const closeOutside = (event: PointerEvent) => {
      if (event.target instanceof Node && !toolbarRef.current?.contains(event.target)) { setShortcutsOpen(false); setAddMenuOpen(false); }
    };
    document.addEventListener('pointerdown', closeOutside);
    return () => document.removeEventListener('pointerdown', closeOutside);
  }, [shortcutsOpen, addMenuOpen]);
  return (
    <>
      <Palette nodes={props.nodes} selectedId={props.selectedId} searchRequest={searchRequest} onAdd={addFromPalette} onSelect={focusNode} collapsed={paletteCollapsed} onToggle={() => {
        setPaletteCollapsed((collapsed) => !collapsed);
      }} />
      <div className="workbench-stage">
      <div className="workspace-toolbar" ref={toolbarRef}>
        <div className="workspace-view-switch" role="group" aria-label="工作区视图">
          <button type="button" className={view === 'canvas' ? 'active' : ''} aria-pressed={view === 'canvas'} onClick={() => setView('canvas')}><Icon name="grid" size={16} />节点画布</button>
          <button type="button" className={view === 'shots' ? 'active' : ''} aria-pressed={view === 'shots'} onClick={() => { setView('shots'); clearConnectionFocus(); }}><Icon name="storyboard" size={16} />镜头总览</button>
        </div>
        <div className="workspace-toolbar-actions">
          <button type="button" onClick={openSearch} aria-label="查找组件" title="查找组件 /"><Icon name="search" size={16} /><span>查找</span><kbd>/</kbd></button>
          <button ref={shortcutButtonRef} type="button" aria-label="快捷键帮助" title="快捷键 ?" aria-expanded={shortcutsOpen} onClick={() => { setShortcutsOpen((open) => !open); setAddMenuOpen(false); }}><Icon name="keyboard" size={17} /></button>
          <button ref={addButtonRef} className="workspace-add-button" type="button" aria-expanded={addMenuOpen} onClick={() => { setAddMenuOpen((open) => !open); setShortcutsOpen(false); }}><Icon name="plus" size={16} /><span>添加</span><Icon name="chevronDown" size={12} /></button>
        </div>
        {addMenuOpen && <div className="workspace-add-menu" aria-label="添加组件">
          {(['document', 'section', 'asset', 'image', 'video', 'audio'] as const).map((type, index) => <button type="button" key={type} onClick={() => addFromPalette(type)}><Icon name={type} size={17} /><span>{['故事文档', '镜头分区', '参考素材', '图片创作', '视频镜头', '音乐与配音'][index]}</span></button>)}
          <small>添加后编辑草稿，再确认生成</small>
        </div>}
        {shortcutsOpen && <div className="shortcut-popover" aria-label="画布快捷键">
          <div className="shortcut-popover-head"><strong>更顺手地创作</strong><button type="button" aria-label="关闭快捷键帮助" onClick={() => { setShortcutsOpen(false); shortcutButtonRef.current?.focus(); }}><Icon name="close" size={16} /></button></div>
          <dl>{[['V', '选择与移动组件'], ['H', '抓手平移画布'], ['Space', '按住临时平移'], ['F', '查看全部组件'], ['Shift F', '定位选中组件'], ['0', '恢复 100%'], ['/', '搜索组件'], ['Delete', '删除选中组件或连线']].map(([key, label]) => <div key={key}><dt>{label}</dt><dd><kbd>{key}</kbd></dd></div>)}</dl>
          <p>编辑文字时不会触发画布快捷键。</p>
        </div>}
      </div>
      <section ref={flowShellRef} className="flow-shell" style={{ '--overview-label-size': `${Math.min(96, 10 / props.viewport.zoom)}px`, '--connection-ring': `${2 / props.viewport.zoom}px`, '--connection-gap': `${5 / props.viewport.zoom}px`, '--connection-label-size': `${11 / props.viewport.zoom}px`, '--connection-label-offset': `${27 / props.viewport.zoom}px` } as CSSProperties} onDrop={onDrop} onDragOver={(event) => { event.preventDefault(); event.dataTransfer.dropEffect = 'copy'; }}>
        {view === 'shots' && <ShotOverview nodes={props.nodes} edges={props.edges} runs={props.runs} selectedId={props.selectedId} onSelect={focusNode} onLocate={focusNode} onPreview={props.onPreview} onAdd={() => addFromPalette('video')} />}
        <div className="flow-viewport" hidden={view !== 'canvas'}>
        <ReactFlow<FlowNode, Edge>
          nodes={presentation.nodes}
          edges={presentation.edges}
          nodeTypes={nodeTypes}
          onNodesChange={props.onNodesChange}
          onEdgesChange={(changes) => {
            props.onEdgesChange(changes);
            const chosen = changes.find((change) => change.type === 'select' && change.selected);
            if (chosen && 'id' in chosen) highlightConnection(chosen.id);
            else if (changes.some((change) => 'id' in change && change.id === connectionFocus?.id && (change.type === 'remove' || change.type === 'select' && !change.selected))) clearConnectionFocus();
          }}
          onConnect={props.onConnect}
          onEdgeClick={(_, edge) => highlightConnection(edge.id)}
          onNodeClick={(_, node) => { clearConnectionFocus(); if (window.innerWidth <= 1050) setPaletteCollapsed(true); props.onSelectNode(node.id); }}
          onPaneClick={() => { clearConnectionFocus(); props.onSelectNode(undefined); }}
          onNodesDelete={props.onDeleteNodes}
          onMoveEnd={(_, nextViewport) => props.onViewportChange(nextViewport)}
          isValidConnection={(connection) => isRelatedConnection(connection as Connection, props.nodes) || isValidConnection(connection as Connection, props.nodes)}
          connectionMode={ConnectionMode.Strict}
          minZoom={0.04}
          maxZoom={2}
          deleteKeyCode={view === 'canvas' && !shortcutsOpen && !addMenuOpen ? ['Backspace', 'Delete'] : null}
          snapToGrid
          snapGrid={[16, 16]}
          nodesDraggable={tool === 'select'}
          nodesConnectable={tool === 'select'}
          panOnDrag={tool === 'hand' ? true : [1, 2]}
          selectionOnDrag={tool === 'select'}
          panActivationKeyCode="Space"
          selectionKeyCode="Shift"
          viewport={props.viewport}
          fitView={false}
          proOptions={{ hideAttribution: true }}
          className={`main-flow${props.viewport.zoom < 0.4 ? ' is-overview' : ''}${focusedConnection ? ' has-connection-focus' : ''}`}
        >
          <FlowInternalsSync nodes={props.nodes} />
          <Background color="#3a3e45" gap={24} size={1} />
          <Panel position="top-left" className="canvas-tool-modes" role="group" aria-label="画布工具">
            <button type="button" aria-label="选择工具" aria-pressed={tool === 'select'} title="选择与移动 · V" onClick={() => setTool('select')}><Icon name="cursor" size={17} /></button>
            <button type="button" aria-label="抓手工具" aria-pressed={tool === 'hand'} title="抓手平移 · H" onClick={() => setTool('hand')}><Icon name="hand" size={17} /></button>
            <span>{tool === 'select' ? '选择' : '平移'}</span>
          </Panel>
          <Panel position="bottom-left" className="view-controls">
            <button type="button" onClick={() => void zoomOut({ duration: 180 })} aria-label="缩小" title="缩小"><Icon name="zoomOut" /></button>
            <button type="button" onClick={() => void zoomTo(1, { duration: 220 })} className="zoom-value" title="恢复 100%" aria-label="恢复 100%">{Math.round(props.viewport.zoom * 100)}%</button>
            <button type="button" onClick={() => void zoomIn({ duration: 180 })} aria-label="放大" title="放大"><Icon name="zoomIn" /></button>
            <span className="control-divider" />
            <button type="button" onClick={() => void fitView({ padding: 0.12, duration: 320 })} aria-label="全局概览" title="全局概览"><Icon name="fit" /></button>
            <button type="button" disabled={!props.selectedId} onClick={() => { if (props.selectedId) focusNode(props.selectedId); }} aria-label="定位选中组件" title="定位选中 · Shift F"><Icon name="search" size={16} /></button>
            <button type="button" onClick={() => setMinimapOpen((open) => !open)} aria-label="缩略地图" aria-pressed={minimapOpen} title="缩略地图"><Icon name="layers" /></button>
          </Panel>
          {minimapOpen && <MiniMap nodeColor={(node) => {
            const kind = (node.data as unknown as { nodeType?: string } | undefined)?.nodeType;
            return kind === 'video' ? '#b8a5db' : kind === 'image' ? '#9cbddc' : kind === 'audio' ? '#d5ae76' : kind === 'asset' ? '#b3a286' : kind === 'document' ? '#8e98ae' : '#465160';
          }} maskColor="rgba(21, 23, 25, 0.72)" position="bottom-right" />}
          <Panel position="bottom-right" className="canvas-statusbar"><span>{props.nodes.filter((node) => !isSectionNode(node)).length} 张卡片</span><span className="connection-legend"><i className="input-line" />实际输入<i className="reference-line" />资料关联</span></Panel>
          {focusedConnection && <Panel position="top-left" className="connection-focus-panel">
            <div className="connection-focus-heading"><span><Icon name="link" size={15} />{focusedConnection.related ? '资料关联' : '实际输入'}</span><button type="button" className="icon-button" onClick={clearConnectionFocus} aria-label="取消连线高亮" title="取消高亮 · Esc"><Icon name="close" size={15} /></button></div>
            <div className="connection-endpoints" role="status">
              <button type="button" onClick={() => focusNode(focusedConnection.source.id)} title={`定位起点：${focusedConnection.source.data.label}`}><small>起点</small><strong>{focusedConnection.source.data.label}</strong></button>
              <Icon name="chevronRight" size={16} />
              <button type="button" onClick={() => focusNode(focusedConnection.target.id)} title={`定位终点：${focusedConnection.target.data.label}`}><small>终点</small><strong>{focusedConnection.target.data.label}</strong></button>
            </div>
            <div className="connection-focus-footer"><span>{focusedConnection.related ? '仅作资料关联，不参与生成输入' : '起点的输出作为终点的生成输入'}</span><button type="button" onClick={() => void fitView({ nodes: [{ id: focusedConnection.source.id }, { id: focusedConnection.target.id }], padding: { top: '230px', bottom: '60px', left: '50px', right: '50px' }, maxZoom: 1, duration: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 360 })}><Icon name="fit" size={14} />查看两端</button></div>
          </Panel>}
        </ReactFlow>
        {!props.nodes.length && <div className="canvas-empty-state"><div className="empty-state-icon"><Icon name="film" size={32} /></div><small>从一个想法，开始一场创作</small><h2>你的下一个故事，从这里开始</h2><p>先写故事、放入参考，或直接创建第一个镜头。<br />用连线把创作需要的内容连接起来。</p><div className="empty-actions"><button type="button" onClick={() => addFromPalette('document')}><Icon name="document" />写故事</button><button type="button" onClick={() => addFromPalette('asset')}><Icon name="asset" />添加参考</button><button type="button" onClick={() => addFromPalette('video')}><Icon name="video" />创建镜头</button></div><span>自动保存草稿 · 确认后才会生成</span></div>}
        </div>
      </section>
      </div>
    </>
  );
}

function FlowInternalsSync({ nodes }: { nodes: FlowNode[] }) {
  const nodesInitialized = useNodesInitialized({ includeHiddenNodes: true });
  const updateNodeInternals = useUpdateNodeInternals();
  const handleSignature = nodes.map((node) => `${node.id}:${node.data.nodeType}:${node.data.mode || ''}`).join('|');
  const nodeIds = useMemo(() => nodes.map((node) => node.id), [handleSignature]);

  useEffect(() => {
    if (!nodesInitialized || !nodeIds.length) return;
    const frame = window.requestAnimationFrame(() => updateNodeInternals(nodeIds));
    return () => window.cancelAnimationFrame(frame);
  }, [handleSignature, nodeIds, nodesInitialized, updateNodeInternals]);

  return null;
}

function PreviewModal({ run, onClose }: { run: Run; onClose: () => void }) {
  const dialogRef = usePreviewDialog(onClose);
  const output = run.outputs?.[0];
  if (!output) return null;
  return (
    <div className="preview-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <div ref={dialogRef} className="preview-modal" role="dialog" aria-modal="true" aria-label="成品预览">
        <div className="preview-modal-head"><div><h2>{output.name || '最近生成的成品'}</h2></div><button type="button" className="icon-button" onClick={onClose} aria-label="关闭预览"><Icon name="close" /></button></div>
        <div className="preview-modal-content">{renderMedia(output, output.name || '生成媒体')}</div>
        <div className="preview-modal-foot"><span>本次成品</span><span>{run.snapshot.provider || '默认方式'} · {run.snapshot.model || '默认模型'}</span></div>
      </div>
    </div>
  );
}

function MediaModal({ output, onClose }: { output: RunOutput; onClose: () => void }) {
  const dialogRef = usePreviewDialog(onClose);
  return (
    <div className="preview-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <div ref={dialogRef} className="preview-modal" role="dialog" aria-modal="true" aria-label="素材预览">
        <div className="preview-modal-head"><div><h2>{output.name || '关联媒体'}</h2></div><button type="button" className="icon-button" onClick={onClose} aria-label="关闭预览"><Icon name="close" /></button></div>
        <div className="preview-modal-content">{renderMedia(output, output.name || '关联媒体')}</div>
        <div className="preview-modal-foot"><span>原始媒体 · 只读预览</span><span>{output.kind.startsWith('image') ? '图片' : output.kind.startsWith('video') ? '视频' : isAudioOutput(output) ? '音频' : '媒体'}</span></div>
      </div>
    </div>
  );
}

function usePreviewDialog(onClose: () => void) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    dialogRef.current?.querySelector<HTMLButtonElement>('button')?.focus();
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); closeRef.current(); }
      if (event.key === 'Tab') {
        const targets = dialogRef.current?.querySelectorAll<HTMLElement>('button, video[controls], audio[controls], a[href], [tabindex="0"]');
        if (!targets?.length) return;
        const first = targets[0];
        const last = targets[targets.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener('keydown', handleKey, true);
    return () => { document.removeEventListener('keydown', handleKey, true); if (previousFocus?.isConnected) previousFocus.focus(); };
  }, []);
  return dialogRef;
}

function renderMedia(output: RunOutput, label: string) {
  const kind = output.kind.toLowerCase();
  if (kind.startsWith('image') || /\.(png|jpe?g|webp|gif)$/i.test(output.path)) return <img src={mediaUrl(output.path)} alt={label} loading="lazy" />;
  if (isAudioOutput(output)) return <audio src={mediaUrl(output.path)} controls preload="metadata" />;
  return <video src={mediaUrl(output.path)} controls preload="metadata" />;
}

function isAudioOutput(output: RunOutput): boolean {
  return output.kind.toLowerCase().startsWith('audio') || /\.(mp3|wav|m4a|aac|ogg|flac)$/i.test(output.path);
}

export default App;
