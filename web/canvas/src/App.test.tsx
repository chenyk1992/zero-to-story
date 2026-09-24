// @vitest-environment jsdom
import { act, type ReactNode } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Canvas, Capability } from './types';

vi.mock('@xyflow/react', async () => {
  const { createElement, Fragment } = await import('react');
  const passthrough = ({ children }: { children?: ReactNode }) => createElement(Fragment, null, children);
  const panel = ({ children, ...props }: { children?: ReactNode; [key: string]: unknown }) => createElement('div', props, children);
  const fakeReactFlow = (props: any) => createElement('div', { className: props.className, 'data-testid': 'fake-react-flow' }, [
    createElement('div', { key: 'nodes', 'data-testid': 'fake-nodes' }, (props.nodes || []).map((node: any) => createElement('button', {
      key: node.id,
      type: 'button',
      'data-testid': `fake-node-${node.id}`,
      className: node.className,
      'data-position-x': node.position?.x,
      'data-position-y': node.position?.y,
      onClick: () => props.onNodeClick?.({}, node),
    }, node.data?.label || node.id))),
    createElement('div', { key: 'edges', 'data-testid': 'fake-edges' }, (props.edges || []).map((edge: any) => createElement('button', {
      key: edge.id,
      type: 'button',
      'data-testid': `fake-edge-${edge.id}`,
      className: edge.className,
      'aria-label': edge.ariaLabel,
      onClick: () => props.onEdgeClick?.({}, edge),
    }, edge.ariaLabel || edge.id))),
    createElement('button', { key: 'pane', type: 'button', 'data-testid': 'fake-pane', onClick: () => props.onPaneClick?.() }, '画布空白处'),
    props.children,
  ]);
  return {
    addEdge: (connection: unknown, edges: unknown[]) => [...edges, connection],
    applyEdgeChanges: (_changes: unknown, edges: unknown[]) => edges,
    applyNodeChanges: (_changes: unknown, nodes: unknown[]) => nodes,
    Background: () => null,
    ConnectionMode: { Strict: 'strict' },
    MiniMap: () => null,
    Panel: panel,
    ReactFlow: fakeReactFlow,
    ReactFlowProvider: passthrough,
    useNodesInitialized: () => false,
    useReactFlow: () => ({
      fitView: vi.fn(),
      screenToFlowPosition: (position: { x: number; y: number }) => position,
      zoomIn: vi.fn(),
      zoomOut: vi.fn(),
      zoomTo: vi.fn(),
    }),
    useUpdateNodeInternals: () => vi.fn(),
  };
});

vi.mock('./CanvasNode', () => ({
  CanvasNode: () => null,
  nodeTypes: { canvas: () => null },
}));

const api = vi.hoisted(() => ({
  createCanvas: vi.fn(),
  executeNode: vi.fn(),
  getCanvas: vi.fn(),
  getCanvases: vi.fn(),
  getCapabilities: vi.fn(),
  getContinuations: vi.fn(),
  getRuns: vi.fn(),
  importAssetPath: vi.fn(),
  mediaUrl: (path: string) => `/media/${path}`,
  updateCanvas: vi.fn(),
  uploadAsset: vi.fn(),
}));

vi.mock('./api', () => ({ ...api, ApiError: class ApiError extends Error {} }));

import App from './App';

let container: HTMLDivElement;
let root: Root;

const canvas: Canvas = {
  id: 'canvas-test',
  name: '测试章节',
  version: 1,
  graph: {
    nodes: [{
      id: 'shot-1',
      type: 'video',
      position: { x: 80, y: 80 },
      data: {
        nodeType: 'video',
        label: '夜站镜头',
        prompt: '人物在雨夜站台回头',
        provider: 'comfy',
        model: '',
        mode: '',
        options: {},
        category: 'video',
      },
    }],
    edges: [],
    viewport: { x: 0, y: 0, zoom: 1 },
    selection: ['shot-1'],
  },
};

const connectionCanvas: Canvas = {
  id: 'canvas-connections',
  name: '连线关系测试',
  version: 1,
  graph: {
    nodes: [
      {
        id: 'source-node',
        type: 'video',
        position: { x: 80, y: 80 },
        data: {
          nodeType: 'video',
          label: '起点镜头',
          prompt: '起点',
          provider: 'comfy',
          model: '',
          mode: '',
          options: {},
        },
      },
      {
        id: 'target-node',
        type: 'video',
        position: { x: 480, y: 80 },
        data: {
          nodeType: 'video',
          label: '终点镜头',
          prompt: '终点',
          provider: 'comfy',
          model: '',
          mode: '',
          options: {},
        },
      },
      {
        id: 'related-node',
        type: 'asset',
        position: { x: 880, y: 80 },
        data: {
          nodeType: 'asset',
          label: '资料镜头',
          prompt: '',
          provider: '',
          model: '',
          mode: '',
          options: {},
        },
      },
    ],
    edges: [
      { id: 'actual-edge', source: 'source-node', target: 'target-node', sourceHandle: 'output', targetHandle: 'first_frame' },
      { id: 'related-edge', source: 'target-node', target: 'related-node', sourceHandle: 'output', targetHandle: 'related' },
    ],
    viewport: { x: 0, y: 0, zoom: 1 },
    selection: ['source-node'],
  },
};

function ttsCapability(): Capability {
  return {
    id: 'comfy-qwen-tts', label: 'Qwen 语音合成', node_types: ['audio' as never],
    execution: 'script', available: true, installed: true,
    models: [{ id: 'qwen3-tts-1.7b-customvoice', label: 'Qwen3-TTS 1.7B CustomVoice' }],
    modes: [{ id: 'tts', label: '语音合成' }],
    fields: [
      { key: 'speaker', label: '声音角色', type: 'select', group: 'specs', required: true, default: 'Eric', options: [{ value: 'Eric', label: 'Eric' }] },
      { key: 'language', label: '语言', type: 'select', group: 'specs', required: true, default: 'Chinese', options: [{ value: 'Chinese', label: '中文' }] },
      { key: 'tempo', label: '语速', type: 'number', group: 'specs', required: true, default: 1.2, min: 0.5, max: 2 },
      { key: 'max_new_tokens', label: '最大新 token 数', type: 'number', group: 'advanced', default: 2048, min: 512, max: 4096, integer: true },
    ],
  };
}

function audioCanvas(provider: string, options: Record<string, Record<string, string | number | boolean | undefined>> = {}): Canvas {
  return {
    id: 'canvas-audio', name: '语音测试', version: 3,
    graph: {
      nodes: [{ id: 'voice-1', type: 'audio' as never, position: { x: 80, y: 80 }, data: {
        nodeType: 'audio' as never, label: '旁白', prompt: '请按原文读。', provider,
        model: provider === 'comfy-qwen-tts' ? 'qwen3-tts-1.7b-customvoice' : '',
        mode: provider === 'comfy-qwen-tts' ? 'tts' : '', options,
      } }],
      edges: [], viewport: { x: 0, y: 0, zoom: 1 }, selection: ['voice-1'],
    },
  };
}

beforeEach(() => {
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1440 });
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: () => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }),
  });
  window.requestAnimationFrame = ((callback: FrameRequestCallback) => { callback(0); return 1; }) as typeof window.requestAnimationFrame;
  window.cancelAnimationFrame = vi.fn();
  api.getCanvases.mockResolvedValue({ canvases: [canvas] });
  api.getCanvas.mockResolvedValue(canvas);
  api.getCapabilities.mockResolvedValue({ capabilities: [] });
  api.getContinuations.mockResolvedValue({ plans: [] });
  api.getRuns.mockResolvedValue({ runs: [] });
  api.updateCanvas.mockResolvedValue(canvas);
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  container = document.createElement('div');
  document.body.append(container);
  root = createRoot(container);
});

afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  vi.clearAllMocks();
});

async function settleApp() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
  });
}

async function renderConnectionCanvas() {
  api.getCanvases.mockResolvedValue({ canvases: [connectionCanvas] });
  api.getCanvas.mockResolvedValue(connectionCanvas);
  await act(async () => root.render(<App />));
  await settleApp();
}

describe('App inspector navigation', () => {
  it('reopens the inspector when the selected card is clicked from asset navigation', async () => {
    await act(async () => root.render(<App />));
    await settleApp();

    expect(container.querySelector('.inspector')).not.toBeNull();
    const closeButton = container.querySelector<HTMLButtonElement>('.inspector [aria-label="收起编辑栏"]');
    expect(closeButton).not.toBeNull();
    await act(async () => closeButton?.click());
    expect(container.querySelector('.inspector')).toBeNull();

    const assetCard = container.querySelector<HTMLButtonElement>('.asset-list-item');
    expect(assetCard?.textContent).toContain('夜站镜头');
    await act(async () => assetCard?.click());

    expect(container.querySelector('.inspector')).not.toBeNull();
    expect(container.querySelector('.inspector-node-label')?.textContent).toBe('夜站镜头');
  });
});

describe('App connection focus', () => {
  it('shows the selected endpoints and actual-input explanation, then closes the editor', async () => {
    await renderConnectionCanvas();

    expect(container.querySelector('.inspector')).not.toBeNull();
    const edgeButton = container.querySelector<HTMLButtonElement>('[data-testid="fake-edge-actual-edge"]');
    expect(edgeButton).not.toBeNull();

    await act(async () => edgeButton?.click());

    const panel = container.querySelector<HTMLElement>('.connection-focus-panel');
    expect(panel).not.toBeNull();
    expect(panel?.textContent).toContain('实际输入');
    expect(panel?.textContent).toContain('起点镜头');
    expect(panel?.textContent).toContain('终点镜头');
    expect(panel?.textContent).toContain('起点的输出作为终点的生成输入');
    expect(container.querySelector('[data-testid="fake-edge-actual-edge"]')?.className)
      .toContain('connection-focused-edge');
    expect(container.querySelector('[data-testid="fake-node-source-node"]')?.className)
      .toContain('connection-endpoint-source');
    expect(container.querySelector('[data-testid="fake-node-target-node"]')?.className)
      .toContain('connection-endpoint-target');
    expect(container.querySelector('[data-testid="fake-node-related-node"]')?.className)
      .not.toContain('connection-endpoint');
    expect(container.querySelector('.inspector')).toBeNull();
  });

  it('distinguishes related edges and supports repeated selection, Escape, pane and node exit', async () => {
    await renderConnectionCanvas();

    const actualEdge = () => container.querySelector<HTMLButtonElement>('[data-testid="fake-edge-actual-edge"]');
    const relatedEdge = () => container.querySelector<HTMLButtonElement>('[data-testid="fake-edge-related-edge"]');

    await act(async () => actualEdge()?.click());
    expect(container.querySelector('[data-testid="fake-node-source-node"]')?.className)
      .toContain('connection-pulse-1');
    await act(async () => actualEdge()?.click());
    expect(container.querySelector('[data-testid="fake-node-source-node"]')?.className)
      .toContain('connection-pulse-0');

    await act(async () => relatedEdge()?.click());
    const relatedPanel = container.querySelector<HTMLElement>('.connection-focus-panel');
    expect(relatedPanel?.textContent).toContain('资料关联');
    expect(relatedPanel?.textContent).toContain('仅作资料关联，不参与生成输入');
    expect(relatedPanel?.textContent).toContain('终点镜头');
    expect(relatedPanel?.textContent).toContain('资料镜头');
    expect(container.querySelector('[data-testid="fake-node-source-node"]')?.className)
      .not.toContain('connection-endpoint');
    expect(container.querySelector('[data-testid="fake-node-target-node"]')?.className)
      .toContain('connection-endpoint-source');
    expect(container.querySelector('[data-testid="fake-node-related-node"]')?.className)
      .toContain('connection-endpoint-target');

    await act(async () => window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' })));
    expect(container.querySelector('.connection-focus-panel')).toBeNull();
    expect(container.querySelector('[data-testid="fake-node-target-node"]')?.className)
      .not.toContain('connection-endpoint');

    await act(async () => actualEdge()?.click());
    await act(async () => container.querySelector<HTMLButtonElement>('[data-testid="fake-pane"]')?.click());
    expect(container.querySelector('.connection-focus-panel')).toBeNull();

    await act(async () => actualEdge()?.click());
    await act(async () => container.querySelector<HTMLButtonElement>('[data-testid="fake-node-source-node"]')?.click());
    expect(container.querySelector('.connection-focus-panel')).toBeNull();
    expect(container.querySelector('.inspector')).not.toBeNull();
  });
});

describe('App responsive workspace', () => {
  it('keeps the narrow palette and inspector mutually exclusive', async () => {
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 800 });
    Object.defineProperty(window, 'matchMedia', {
      configurable: true,
      value: (query: string) => ({
        matches: query.includes('max-width: 1050px'),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      }),
    });
    await renderConnectionCanvas();

    expect(container.querySelector('.palette')?.className).toContain('palette-collapsed');
    expect(container.querySelector('.inspector')).not.toBeNull();

    await act(async () => container.querySelector<HTMLButtonElement>('[aria-label="展开资产栏"]')?.click());
    expect(container.querySelector('.palette')?.className).not.toContain('palette-collapsed');
    expect(container.querySelector('.inspector')).toBeNull();

    await act(async () => container.querySelector<HTMLButtonElement>('.asset-list-item')?.click());
    expect(container.querySelector('.palette')?.className).toContain('palette-collapsed');
    expect(container.querySelector('.inspector')).not.toBeNull();

    await act(async () => container.querySelector<HTMLButtonElement>('[aria-label="收起编辑栏"]')?.click());
    await act(async () => container.querySelector<HTMLButtonElement>('[aria-label="展开资产栏"]')?.click());
    expect(container.querySelector('.palette')?.className).not.toContain('palette-collapsed');
    expect(container.querySelector('.inspector')).toBeNull();

    await act(async () => container.querySelector<HTMLButtonElement>('[aria-label="展开编辑栏"]')?.click());
    expect(container.querySelector('.inspector')).not.toBeNull();
    expect(container.querySelector('.palette')?.className).toContain('palette-collapsed');
  });

  it('places a palette-created node from the flow-shell bounds', async () => {
    await act(async () => root.render(<App />));
    await settleApp();

    const flowShell = container.querySelector<HTMLElement>('.flow-shell');
    expect(flowShell).not.toBeNull();
    vi.spyOn(flowShell as HTMLElement, 'getBoundingClientRect').mockReturnValue({
      left: 120,
      top: 80,
      right: 720,
      bottom: 480,
      width: 600,
      height: 400,
      x: 120,
      y: 80,
      toJSON: () => ({}),
    } as DOMRect);

    await act(async () => container.querySelector<HTMLButtonElement>('[aria-label="添加视频"]')?.click());

    const createdNode = Array.from(container.querySelectorAll<HTMLElement>('[data-testid^="fake-node-"]'))
      .find((item) => item.dataset.positionX === '260' && item.dataset.positionY === '200');
    expect(createdNode).not.toBeUndefined();
  });

  it('fills a new media node from the only available capability', async () => {
    const imageCapability: Capability = {
      id: 'image-local',
      label: '本机图片能力',
      node_types: ['image'],
      execution: 'script',
      available: true,
      installed: true,
      models: [{ id: 'image-model', label: '图片模型' }],
      modes: [{ id: 'create', label: '图像生成' }],
      fields: [],
    };
    api.getCapabilities.mockResolvedValue({ capabilities: [imageCapability] });
    await act(async () => root.render(<App />));
    await settleApp();

    await act(async () => container.querySelector<HTMLButtonElement>('[aria-label="添加图片"]')?.click());
    await settleApp();

    const routeSelects = container.querySelectorAll<HTMLSelectElement>('.route-section select');
    expect(routeSelects[0]?.value).toBe('image-local');
    expect(routeSelects[1]?.value).toBe('image-model');
    expect(routeSelects[2]?.value).toBe('create');
  });

  it('adds a speech card with the available Qwen TTS route and capability defaults', async () => {
    api.getCapabilities.mockResolvedValue({ capabilities: [ttsCapability()] });
    await act(async () => root.render(<App />));
    await settleApp();

    const addVoice = container.querySelector<HTMLButtonElement>('[aria-label="添加语音"]');
    expect(addVoice).not.toBeNull();
    await act(async () => addVoice?.click());

    const routeSelects = container.querySelectorAll<HTMLSelectElement>('.route-section select');
    expect(container.querySelector('.inspector h2')?.textContent).toContain('语音');
    expect(routeSelects[0]?.value).toBe('comfy-qwen-tts');
    expect(routeSelects[1]?.value).toBe('qwen3-tts-1.7b-customvoice');
    expect(routeSelects[2]?.value).toBe('tts');
    const speaker = [...container.querySelectorAll<HTMLLabelElement>('label.field')].find((field) => field.textContent?.includes('声音角色'));
    expect(speaker?.querySelector<HTMLSelectElement>('select')?.value).toBe('Eric');
    expect(container.querySelector('.execute-button')?.textContent).toContain('确认执行');
    expect(container.querySelector<HTMLButtonElement>('.execute-button')?.disabled).toBe(false);

    await act(async () => { await new Promise((resolve) => window.setTimeout(resolve, 850)); });
    const savedGraph = api.updateCanvas.mock.calls.at(-1)?.[2] as { nodes?: Array<{ type: string; data: { options?: Record<string, Record<string, unknown>> } }> } | undefined;
    const savedVoice = savedGraph?.nodes?.find((savedNode) => savedNode.type === 'audio');
    expect(savedVoice?.data.options?.['comfy-qwen-tts']).toMatchObject({ speaker: 'Eric', language: 'Chinese', tempo: 1.2, max_new_tokens: 2048 });
  });

  it('persists TTS defaults after the user explicitly changes the provider', async () => {
    const existing = audioCanvas('legacy-tts');
    api.getCanvases.mockResolvedValue({ canvases: [existing] });
    api.getCanvas.mockResolvedValue(existing);
    api.getCapabilities.mockResolvedValue({ capabilities: [ttsCapability()] });
    await act(async () => root.render(<App />));
    await settleApp();

    const provider = container.querySelector<HTMLSelectElement>('.route-section select');
    expect(provider?.value).toBe('legacy-tts');
    const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value')?.set;
    setter?.call(provider, 'comfy-qwen-tts');
    await act(async () => provider?.dispatchEvent(new Event('change', { bubbles: true })));

    const speaker = [...container.querySelectorAll<HTMLLabelElement>('label.field')].find((field) => field.textContent?.includes('声音角色'));
    expect(speaker?.querySelector<HTMLSelectElement>('select')?.value).toBe('Eric');
    await act(async () => { await new Promise((resolve) => window.setTimeout(resolve, 850)); });
    const savedGraph = api.updateCanvas.mock.calls.at(-1)?.[2] as { nodes?: Array<{ data: { options?: Record<string, Record<string, unknown>> } }> } | undefined;
    expect(savedGraph?.nodes?.[0]?.data.options?.['comfy-qwen-tts']).toMatchObject({ speaker: 'Eric', language: 'Chinese', tempo: 1.2, max_new_tokens: 2048 });
  });

  it('does not backfill capability defaults into an already loaded audio card', async () => {
    const existing = audioCanvas('comfy-qwen-tts');
    api.getCanvases.mockResolvedValue({ canvases: [existing] });
    api.getCanvas.mockResolvedValue(existing);
    api.getCapabilities.mockResolvedValue({ capabilities: [ttsCapability()] });
    await act(async () => root.render(<App />));
    await settleApp();

    const fields = [...container.querySelectorAll<HTMLLabelElement>('label.field')];
    const speaker = fields.find((field) => field.textContent?.includes('声音角色'));
    const language = fields.find((field) => field.textContent?.includes('语言'));
    const tempo = fields.find((field) => field.textContent?.includes('语速'));
    expect(speaker?.querySelector<HTMLSelectElement>('select')?.value).toBe('');
    expect(language?.querySelector<HTMLSelectElement>('select')?.value).toBe('');
    expect(tempo?.querySelector<HTMLInputElement>('input')?.value).toBe('');
    expect(container.querySelector<HTMLButtonElement>('.execute-button')?.disabled).toBe(true);
  });

  it('plays a generated FLAC audio run from its result preview', async () => {
    const currentAudioCanvas = audioCanvas('comfy-qwen-tts');
    const run = {
      id: 'tts-run', node_id: 'voice-1', status: 'succeeded' as const,
      snapshot: { node_id: 'voice-1', node_type: 'audio' as never, provider: 'comfy-qwen-tts', model: 'qwen3-tts-1.7b-customvoice', mode: 'tts', prompt: '请按原文读。', parameters: {}, inputs: {} },
      outputs: [{ path: 'audio/voice.flac', kind: 'audio/flac', name: '旁白.flac', metadata: { duration_ms: 2450 } }],
    };
    api.getCanvases.mockResolvedValue({ canvases: [currentAudioCanvas] });
    api.getCanvas.mockResolvedValue(currentAudioCanvas);
    api.getRuns.mockResolvedValue({ runs: [run] });
    await act(async () => root.render(<App />));
    await settleApp();

    const outputPreview = container.querySelector<HTMLButtonElement>('.preview-card');
    expect(outputPreview?.textContent).toContain('播放音频');
    await act(async () => outputPreview?.click());
    expect(container.querySelector<HTMLAudioElement>('.preview-modal audio')?.src).toContain('/media/audio/voice.flac');
  });
});

describe('App continuation status', () => {
  it('loads the read-only plan summary for the active canvas', async () => {
    api.getContinuations.mockResolvedValue({ plans: [{
      id: 'plan-1',
      canvas_id: 'canvas-test',
      node_ids: ['shot-1'],
      state: 'active',
      revision: 1,
      summary: {
        status: 'actionable',
        actions: [{ kind: 'handle_unit', reason: '先处理执行单元结果' }],
        blocked_items: [],
        nodes: [],
        allow_stop: false,
        reason: '有可交接的下一步',
      },
    }] });
    await act(async () => root.render(<App />));
    await settleApp();

    expect(api.getContinuations).toHaveBeenCalledWith('canvas-test');
    expect(container.querySelector('.continuation-trigger')?.textContent).toContain('待主会话处理');
    await act(async () => container.querySelector<HTMLButtonElement>('.continuation-trigger')?.click());
    expect(container.querySelector('.continuation-popover')?.textContent).toContain('待处理 1');
    expect(container.querySelector('.continuation-popover')?.textContent).toContain('接续计划 1');
  });

  it('keeps the canvas usable when the continuation endpoint is unavailable', async () => {
    api.getContinuations.mockRejectedValueOnce(new Error('offline'));
    await act(async () => root.render(<App />));
    await settleApp();

    expect(container.querySelector('[data-testid="fake-react-flow"]')).not.toBeNull();
    expect(container.querySelector('.connection-overlay')).toBeNull();
    expect(container.querySelector('.continuation-trigger')?.textContent).toContain('接续状态不可用');
  });
});
