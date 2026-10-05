// @vitest-environment jsdom
import { renderToStaticMarkup } from 'react-dom/server';
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, expect, it, vi } from 'vitest';
import type { NodeProps } from '@xyflow/react';
import type { FlowNode } from './types';
import { createFlowNode } from './graph';
import { CanvasNode } from './CanvasNode';
import { NodeEditingProvider } from './NodeEditing';
import type { StoryNodePatch } from './workspace';

vi.mock('@xyflow/react', () => ({
  Handle: ({ id, type }: { id: string; type: string }) => <span data-handle={id} data-handle-type={type} />,
  Position: { Left: 'left', Right: 'right' },
  useUpdateNodeInternals: () => () => undefined,
}));

function render(node: FlowNode) {
  const host = document.createElement('div');
  host.innerHTML = renderToStaticMarkup(<CanvasNode {...{ id: node.id, data: node.data, selected: false } as NodeProps<FlowNode>} />);
  return host;
}

async function mountEditable(node: FlowNode) {
  vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => { callback(0); return 1; });
  vi.stubGlobal('cancelAnimationFrame', vi.fn());
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  const host = document.createElement('div');
  document.body.append(host);
  const root = createRoot(host);
  const patches: StoryNodePatch[] = [];
  const composing: boolean[] = [];
  const canvasKey = vi.fn();
  const canvasPointer = vi.fn();
  let selected = true;
  const paint = () => root.render(<NodeEditingProvider value={{
    updateNode: (id, patch) => {
      expect(id).toBe(node.id);
      patches.push(patch);
      Object.assign(node.data, patch);
      paint();
    },
    setComposing: (id, value) => { expect(id).toBe(node.id); composing.push(value); },
    renderSettings: () => <div className="test-settings">生成设置</div>,
  }}><div onKeyDown={canvasKey} onPointerDown={canvasPointer}><CanvasNode {...{ id: node.id, data: node.data, selected } as NodeProps<FlowNode>} /></div></NodeEditingProvider>);
  await act(async () => paint());
  return {
    host, patches, composing, canvasKey, canvasPointer,
    select: async (value: boolean) => { selected = value; await act(async () => paint()); },
    cleanup: async () => { await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals(); },
  };
}

async function typeIn(field: HTMLTextAreaElement, value: string) {
  Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')!.set!.call(field, value);
  await act(async () => field.dispatchEvent(new Event('input', { bubbles: true })));
}

describe('media card controls', () => {
  it('edits complete selected-card text in place and keeps it after deselection', async () => {
    const node = createFlowNode('video', { x: 0, y: 0 });
    const original = 'subject_definitions:\n<Subject 1> is a traveler.\n\nsummary:\n旅人在月台等候。\n';
    Object.assign(node.data, { label: '旧名称', description: '  原始说明\n第二行  ', prompt: original });
    const view = await mountEditable(node);
    try {
      const title = view.host.querySelector<HTMLTextAreaElement>('textarea[aria-label="卡片名称"]')!;
      const prompt = view.host.querySelector<HTMLTextAreaElement>('textarea[aria-label="视频提示词"]')!;
      const description = view.host.querySelector<HTMLTextAreaElement>('textarea[aria-label="创作说明"]')!;
      expect(prompt?.value).toBe(original);
      expect(description?.value).toBe('  原始说明\n第二行  ');
      expect(view.host.querySelector('.node-prompt-summary')).toBeNull();
      expect(view.host.querySelector('.test-settings')).not.toBeNull();
      await typeIn(title, '新的卡片名称');
      await typeIn(prompt, `${original}  保留空格。\n`);
      expect(node.data.prompt).toBe(`${original}  保留空格。\n`);
      await view.select(false);
      expect(view.host.querySelector('textarea')).toBeNull();
      expect(view.host.querySelector('.node-kind')?.textContent).toBe('新的卡片名称');
      expect(view.host.querySelector('.test-settings')).toBeNull();
      await view.select(true);
      expect(view.host.querySelector<HTMLTextAreaElement>('textarea[aria-label="视频提示词"]')?.value).toBe(`${original}  保留空格。\n`);
    } finally { await view.cleanup(); }
  });

  it('keeps Chinese composition local until completion and blocks canvas shortcuts and dragging', async () => {
    const node = createFlowNode('video', { x: 0, y: 0 });
    const view = await mountEditable(node);
    try {
      const prompt = view.host.querySelector<HTMLTextAreaElement>('textarea[aria-label="视频提示词"]')!;
      expect(prompt).not.toBeNull();
      await act(async () => prompt.dispatchEvent(new CompositionEvent('compositionstart', { bubbles: true })));
      await typeIn(prompt, 'ni');
      expect(view.patches).toEqual([]);
      expect(prompt.value).toBe('ni');
      await typeIn(prompt, '  你好\n世界  ');
      await act(async () => prompt.dispatchEvent(new CompositionEvent('compositionend', { bubbles: true, data: '你好' })));
      expect(node.data.prompt).toBe('  你好\n世界  ');
      expect(view.composing).toEqual([true, false]);
      await act(async () => {
        prompt.dispatchEvent(new KeyboardEvent('keydown', { key: 'Delete', bubbles: true }));
        prompt.dispatchEvent(new Event('pointerdown', { bubbles: true }));
      });
      expect(view.canvasKey).not.toHaveBeenCalled();
      expect(view.canvasPointer).not.toHaveBeenCalled();
      expect(prompt.className).toContain('nodrag');
      expect(prompt.className).toContain('nowheel');
    } finally { await view.cleanup(); }
  });

  it('flushes unfinished composition on blur and grows text fields as content grows', async () => {
    const node = createFlowNode('image', { x: 0, y: 0 });
    const view = await mountEditable(node);
    try {
      const prompt = view.host.querySelector<HTMLTextAreaElement>('textarea[aria-label="图片提示词"]')!;
      expect(prompt).not.toBeNull();
      Object.defineProperty(prompt, 'scrollHeight', { value: 276 });
      await act(async () => {
        prompt.focus();
        prompt.dispatchEvent(new CompositionEvent('compositionstart', { bubbles: true }));
      });
      await typeIn(prompt, '正在写下\n新的画面');
      expect(prompt.style.height).toBe('276px');
      await act(async () => prompt.blur());
      expect(node.data.prompt).toBe('正在写下\n新的画面');
      expect(view.composing).toEqual([true, false]);
    } finally { await view.cleanup(); }
  });

  it('keeps focus when writing the first creative note and preserves composition on deselection', async () => {
    const node = createFlowNode('image', { x: 0, y: 0 });
    const view = await mountEditable(node);
    try {
      const details = view.host.querySelector<HTMLDetailsElement>('.node-description-details')!;
      await act(async () => details.querySelector('summary')?.click());
      const note = view.host.querySelector<HTMLTextAreaElement>('textarea[aria-label="创作说明"]')!;
      await act(async () => note.focus());
      await typeIn(note, '第');
      expect(document.activeElement).toBe(note);
      expect(note.isConnected).toBe(true);
      await act(async () => note.dispatchEvent(new CompositionEvent('compositionstart', { bubbles: true })));
      await typeIn(note, '第一次构思');
      await view.select(false);
      expect(node.data.description).toBe('第一次构思');
      expect(view.composing).toEqual([true, false]);
    } finally { await view.cleanup(); }
  });

  it('edits document originals and section notes without replacing them with display summaries', async () => {
    const node = createFlowNode('asset', { x: 0, y: 0 });
    Object.assign(node.data, { nodeType: 'document', content: '# 故事\n\n**雨停了**，她走向车站。' });
    const view = await mountEditable(node);
    try {
      const content = view.host.querySelector<HTMLTextAreaElement>('textarea[aria-label="文档正文"]')!;
      expect(content?.value).toBe('# 故事\n\n**雨停了**，她走向车站。');
      await typeIn(content, '# 新故事\n\n她停下了脚步。');
      expect(node.data.content).toBe('# 新故事\n\n她停下了脚步。');
    } finally { await view.cleanup(); }
    Object.assign(node.data, { nodeType: 'section', description: '车站段落', width: 720, height: 400 });
    const section = await mountEditable(node);
    try {
      const note = section.host.querySelector<HTMLTextAreaElement>('textarea[aria-label="创作说明"]')!;
      expect(note?.value).toBe('车站段落');
      await typeIn(note, '傍晚车站段落');
      expect(node.data.description).toBe('傍晚车站段落');
      expect(section.host.querySelector<HTMLElement>('.section-node')?.style.width).toBe('720px');
    } finally { await section.cleanup(); }
  });

  it.each([['comfy-qwen-tts', '逐字台词'], ['comfy-minimax-music', '音乐描述']])('labels %s audio for direct editing', async (provider, label) => {
    const node = createFlowNode('audio', { x: 0, y: 0 });
    Object.assign(node.data, { provider, prompt: '  第一行\n第二行。  ' });
    const view = await mountEditable(node);
    try {
      expect(view.host.querySelector<HTMLTextAreaElement>(`textarea[aria-label="${label}"]`)?.value).toBe('  第一行\n第二行。  ');
    } finally { await view.cleanup(); }
  });

  it('shows only valid mode inputs and keeps derived handles while previews are folded', () => {
    const node = createFlowNode('video', { x: 0, y: 0 });
    node.data.mode = 'r2v';
    node.data.derived_outputs = [{ id: 'tail', label: '真实末帧', asset: { path: 'tail.png', name: 'tail.png', kind: 'image' } }];
    const references = render(node);
    expect([...references.querySelectorAll('[data-handle-type="target"]')].map((port) => port.getAttribute('data-handle'))).toEqual(['reference_image', 'reference_video', 'reference_audio', 'related']);
    expect(references.querySelector('[data-handle="output:tail"]')).not.toBeNull();
    expect(references.querySelector('.node-output-list')).toBeNull();
    node.data.mode = 'i2v';
    expect([...render(node).querySelectorAll('[data-handle-type="target"]')].map((port) => port.getAttribute('data-handle'))).toEqual(['first_frame', 'related']);
  });

  it('exposes a first-frame guide only for Comfy R2V while keeping other modes and providers unchanged', () => {
    const node = createFlowNode('video', { x: 0, y: 0 });
    node.data.provider = 'comfy';
    node.data.mode = 'r2v';
    expect([...render(node).querySelectorAll('[data-handle-type="target"]')].map((port) => port.getAttribute('data-handle'))).toEqual(['first_frame', 'reference_image', 'reference_video', 'reference_audio', 'related']);

    node.data.provider = 'mmx';
    expect([...render(node).querySelectorAll('[data-handle-type="target"]')].map((port) => port.getAttribute('data-handle'))).toEqual(['reference_image', 'reference_video', 'reference_audio', 'related']);

    node.data.provider = 'comfy';
    node.data.mode = 'i2v';
    expect([...render(node).querySelectorAll('[data-handle-type="target"]')].map((port) => port.getAttribute('data-handle'))).toEqual(['first_frame', 'related']);
    node.data.mode = 'fl2v';
    expect([...render(node).querySelectorAll('[data-handle-type="target"]')].map((port) => port.getAttribute('data-handle'))).toEqual(['first_frame', 'last_frame', 'related']);
  });

  it('shows the configured provider instead of labeling every image as built-in generation', () => {
    const node = createFlowNode('image', { x: 0, y: 0 });
    expect(render(node).querySelector('.node-provider')?.textContent).toBe('待选生成方式');
    node.data.provider = 'custom-studio';
    expect(render(node).querySelector('.node-provider')?.textContent).toBe('custom-studio');
    node.data.provider = 'codex-imagegen';
    expect(render(node).querySelector('.node-provider')?.textContent).toBe('内置生图');
    node.data.provider = 'comfy-qwen-image';
    node.data.mode = 'reference';
    expect(render(node).querySelector('.node-provider')?.textContent).toBe('Qwen 2.1');
    expect(render(node).querySelector('.node-meta')?.getAttribute('title')).toContain('图片参考生成');
  });

  it('renders a speech card with a reference audio port and keeps FLAC results previewable', () => {
    const node = createFlowNode('audio' as never, { x: 0, y: 0 }, 'voice');
    Object.assign(node.data, { label: '语音', prompt: '我会按原文说完。', provider: 'comfy-qwen-tts', model: 'qwen3-tts-1.7b-customvoice', mode: 'tts', runStatus: 'succeeded' });
    node.data.latestSuccessfulRun = {
      id: 'voice-run', node_id: node.id, status: 'succeeded',
      snapshot: { node_id: node.id, node_type: 'audio' as never, provider: 'comfy-qwen-tts', model: 'qwen3-tts-1.7b-customvoice', mode: 'tts', prompt: node.data.prompt, parameters: {}, inputs: {} },
      outputs: [{ path: 'audio/voice.flac', kind: 'audio/flac' }],
    };

    const card = render(node);
    expect([...card.querySelectorAll('[data-handle-type="target"]')].map((port) => port.getAttribute('data-handle'))).toEqual(['reference_audio', 'related']);
    expect(card.querySelector('.node-preview')).not.toBeNull();
    expect(card.querySelector('.preview-audio-mark')).not.toBeNull();
    expect(card.textContent).toContain('我会按原文说完。');
    expect(card.querySelector('.node-meta')?.getAttribute('title')).toContain('语音合成');
  });

  it('does not offer an unsupported audio reference on Music 3 cards', () => {
    const node = createFlowNode('audio' as never, { x: 0, y: 0 }, 'music');
    node.data.provider = 'comfy-minimax-music';
    node.data.mode = 'song';
    expect([...render(node).querySelectorAll('[data-handle-type="target"]')].map((port) => port.getAttribute('data-handle'))).toEqual(['related']);
    node.data.mode = 'instrumental';
    expect([...render(node).querySelectorAll('[data-handle-type="target"]')].map((port) => port.getAttribute('data-handle'))).toEqual(['related']);
  });

  it('shows the creative description and one identity row instead of raw prompt scaffolding', () => {
    const node = createFlowNode('video', { x: 0, y: 0 });
    Object.assign(node.data, { label: '她在清晨的山间车站打开那封迟到的信', panel_id: 'P02', category: 'video', description: '她站在空站台，打开旧信。', prompt: 'subject_definitions:\nA woman.\nsummary:\nOpening a letter.', megapixels: 0.25 });
    const card = render(node);
    expect(card.querySelector('.node-creative-summary')?.textContent).toBe('她站在空站台，打开旧信。');
    expect(card.querySelector('.node-panel-id')?.textContent).toBe('P02');
    expect(card.querySelector('.node-kind')?.getAttribute('title')).toBe(node.data.label);
    expect(card.querySelector('.node-tags')).toBeNull();
    expect(card.textContent).not.toContain('subject_definitions');
    expect(card.querySelector('.node-prompt-summary')?.getAttribute('aria-expanded')).toBe('false');
    expect(card.querySelector('.node-meta')?.textContent).not.toContain('MP');
  });

  it('keeps a previous real result visible while a later attempt fails', () => {
    const node = createFlowNode('image', { x: 0, y: 0 });
    Object.assign(node.data, { runStatus: 'failed', resultChanged: true, latestSuccessfulRun: { id: 'old', status: 'succeeded', outputs: [{ path: 'old.png', kind: 'image' }] } });
    const card = render(node);
    expect(card.querySelector('img')?.getAttribute('src')).toContain('old.png');
    expect(card.textContent).toContain('生成失败');
    expect(card.textContent).toContain('上次成功成品');
    expect(card.querySelector('.node-preview-source')?.textContent).toBe('上次成功成品');
    expect(card.textContent).toContain('草稿已修改');
    expect(card.textContent).not.toContain('已采用');
  });

  it('gives empty media a state-specific placeholder without pretending it is an output', () => {
    const node = createFlowNode('video', { x: 0, y: 0 });
    expect(render(node).querySelector('.node-media-placeholder')?.textContent).toContain('等待第一版画面');
    node.data.runStatus = 'unknown';
    const card = render(node);
    expect(card.querySelector('.node-media-placeholder')?.textContent).toContain('等待核实原任务');
    expect(card.querySelector('.node-preview')).toBeNull();
    expect(card.textContent).not.toContain('已生成');
  });

  it('summarizes documents as readable text and displays only the asset filename', () => {
    const note = createFlowNode('asset', { x: 0, y: 0 });
    Object.assign(note.data, { nodeType: 'document', category: 'document', content: '# 故事\n\n**雨停了**，她走向车站。\n- 等待列车' });
    expect(render(note).querySelector('.document-copy')?.textContent).toBe('故事 雨停了，她走向车站。 等待列车');
    const asset = createFlowNode('asset', { x: 0, y: 0 });
    asset.data.asset = { path: 'C:\\private\\reference.png', kind: 'image', name: '' };
    const card = render(asset);
    expect(card.querySelector('.node-file-caption')?.textContent).toContain('reference.png');
    expect(card.textContent).not.toContain('C:\\private');
  });

  it('opens the exact original prompt and preview without turning a control click into a node edit', async () => {
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => { callback(0); return 1; });
    vi.stubGlobal('cancelAnimationFrame', vi.fn());
    Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
    const node = createFlowNode('video', { x: 0, y: 0 });
    const originalPrompt = 'subject_definitions:\n<Subject 1> is a traveler.\n\nsummary:\n旅人在月台等候。\n';
    const onPreview = vi.fn();
    Object.assign(node.data, { prompt: originalPrompt, asset: { path: 'clip.mp4', kind: 'video', name: 'clip.mp4' }, onPreview });
    const host = document.createElement('div');
    document.body.append(host);
    const root = createRoot(host);
    try {
      await act(async () => root.render(<CanvasNode {...{ id: node.id, data: node.data, selected: true } as NodeProps<FlowNode>} />));
      expect(host.querySelector('.node-prompt-full')).toBeNull();
      await act(async () => host.querySelector<HTMLButtonElement>('.node-prompt-summary')?.click());
      expect(host.querySelector('.node-prompt-full')?.textContent).toBe(originalPrompt);
      expect(host.querySelector('.node-prompt-full')?.className).toContain('nowheel');
      expect(node.data.prompt).toBe(originalPrompt);
      expect(onPreview).not.toHaveBeenCalled();
      await act(async () => host.querySelector<HTMLButtonElement>('.node-preview')?.click());
      expect(onPreview).toHaveBeenCalledOnce();
      expect(host.querySelector('.node-preview')?.className).toContain('nodrag');
    } finally {
      await act(async () => root.unmount());
      host.remove();
      vi.unstubAllGlobals();
    }
  });

  it('uses the real output dimensions before the planned frame ratio', () => {
    const node = createFlowNode('image', { x: 0, y: 0 });
    Object.assign(node.data, { aspect_ratio: '16:9', latestSuccessfulRun: { id: 'portrait', status: 'succeeded', outputs: [{ path: 'portrait.png', kind: 'image', metadata: { width: 720, height: 1280 } }] } });
    expect(render(node).querySelector<HTMLButtonElement>('.node-preview')?.style.aspectRatio).toBe('0.5625');
  });

  it('learns native media proportions and discards them when the output path changes', async () => {
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => { callback(0); return 1; });
    vi.stubGlobal('cancelAnimationFrame', vi.fn());
    Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
    const node = createFlowNode('image', { x: 0, y: 0 });
    Object.assign(node.data, { aspect_ratio: '16:9', asset: { path: 'portrait.png', kind: 'image' } });
    const host = document.createElement('div');
    document.body.append(host);
    const root = createRoot(host);
    const renderNode = () => root.render(<CanvasNode {...{ id: node.id, data: node.data, selected: false } as NodeProps<FlowNode>} />);
    try {
      await act(async () => renderNode());
      const image = host.querySelector('img')!;
      Object.defineProperties(image, { naturalWidth: { value: 600 }, naturalHeight: { value: 900 } });
      await act(async () => image.dispatchEvent(new Event('load', { bubbles: true })));
      expect(host.querySelector<HTMLButtonElement>('.node-preview')?.style.aspectRatio).toBe(String(600 / 900));
      node.data.asset = { path: 'new-wide.mp4', kind: 'video', name: 'new-wide.mp4' };
      await act(async () => renderNode());
      expect(host.querySelector<HTMLButtonElement>('.node-preview')?.style.aspectRatio).toBe(String(16 / 9));
      const video = host.querySelector('video')!;
      Object.defineProperties(video, { videoWidth: { value: 1920 }, videoHeight: { value: 800 } });
      await act(async () => video.dispatchEvent(new Event('loadedmetadata', { bubbles: true })));
      expect(host.querySelector<HTMLButtonElement>('.node-preview')?.style.aspectRatio).toBe('2.4');
    } finally {
      await act(async () => root.unmount());
      host.remove();
      vi.unstubAllGlobals();
    }
  });
});
