// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Inspector } from './Inspector';
import { createFlowNode } from './graph';
import type { Capability, FlowNode, Run, RunOutput } from './types';

vi.mock('./api', () => ({
  mediaUrl: (path: string) => `/media/${path}`,
}));

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  container = document.createElement('div');
  document.body.append(container);
  root = createRoot(container);
});

afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
});

function capability(available = true): Capability {
  return {
    id: 'comfy',
    label: 'Comfy',
    node_types: ['video'],
    execution: available ? 'script' : 'unavailable',
    available,
    reason: available ? undefined : 'ComfyUI 当前不可用',
    models: [{ id: 'h3', label: 'H3' }],
    modes: [{ id: 't2v', label: '文生视频' }],
    fields: [
      { key: 'duration', label: '时长（秒）', type: 'number', group: 'specs', min: 1, max: 60, integer: true },
      { key: 'aspect_ratio', label: '画幅比例', type: 'select', group: 'specs', options: [{ value: '16:9', label: '16:9' }] },
    ],
  };
}

function ttsCapability(): Capability {
  return {
    id: 'comfy-qwen-tts', label: 'Qwen 语音合成', node_types: ['audio' as never],
    execution: 'script', available: true, installed: true,
    models: [{ id: 'qwen3-tts-1.7b-customvoice', label: 'Qwen3-TTS 1.7B CustomVoice' }],
    modes: [{ id: 'tts', label: '语音合成' }],
    fields: [
      { key: 'speaker', label: '声音角色', type: 'select', group: 'specs', required: true, default: 'Eric', options: ['Aiden', 'Dylan', 'Eric', 'Ono_anna', 'Ryan', 'Serena', 'Sohee', 'Uncle_fu', 'Vivian'].map((value) => ({ value, label: value })) },
      { key: 'language', label: '语言', type: 'select', group: 'specs', required: true, default: 'Chinese', options: [{ value: 'Chinese', label: '中文' }] },
      { key: 'tempo', label: '语速', type: 'number', group: 'specs', required: true, default: 1.2, min: 0.5, max: 2 },
      { key: 'instruct', label: '语音风格指令', type: 'text', group: 'advanced' },
      { key: 'seed', label: '随机种子', type: 'number', group: 'advanced', min: 0, max: 9007199254740991, integer: true },
      { key: 'max_new_tokens', label: '最大新 token 数', type: 'number', group: 'advanced', default: 2048, min: 512, max: 4096, integer: true },
    ],
  };
}

function musicCapability(): Capability {
  return {
    id: 'comfy-minimax-music', label: 'MiniMax Music 3', node_types: ['audio'],
    execution: 'script', available: true, installed: true,
    models: [{ id: 'minimax-music-3', label: 'Music 3' }],
    modes: [{ id: 'song', label: '歌曲' }, { id: 'instrumental', label: '纯器乐' }],
    fields: [
      { key: 'lyrics', label: '歌词', type: 'text', group: 'specs', modes: ['song'], required: true, multiline: true },
      { key: 'max_duration', label: '最长生成时长（秒）', type: 'number', group: 'specs', required: true, min: 0.04, max: 360 },
    ],
  };
}

function makeVideo(overrides: Partial<FlowNode['data']> = {}) {
  const node = createFlowNode('video', { x: 0, y: 0 }, 'video-test');
  node.data.label = '夜站镜头';
  node.data.prompt = '人物在雨夜站台回头';
  Object.assign(node.data, overrides);
  return node;
}

function makeAudio(overrides: Partial<FlowNode['data']> = {}) {
  const node = createFlowNode('audio' as never, { x: 0, y: 0 }, 'audio-test');
  node.data.label = '旁白';
  node.data.prompt = '请完整说出这句台词。';
  Object.assign(node.data, { provider: 'comfy-qwen-tts', model: 'qwen3-tts-1.7b-customvoice', mode: 'tts', ...overrides });
  return node;
}

function callbacks() {
  return {
    onUpdate: vi.fn(),
    onUpdateOptions: vi.fn(),
    onSelectNode: vi.fn(),
    onRemove: vi.fn(),
    onExecute: vi.fn(),
    onUploadAsset: vi.fn(async () => undefined),
    onImportAssetPath: vi.fn(async () => undefined),
    onCompositionChange: vi.fn(),
    onOpenPreview: vi.fn(),
    onOpenMedia: vi.fn<(output: RunOutput) => void>(),
  };
}

async function renderInspector(node: FlowNode, caps = [capability()], runs: Run[] = []) {
  const events = callbacks();
  await act(async () => root.render(
    <Inspector
      node={node}
      nodes={[node]}
      edges={[]}
      capabilities={caps}
      runs={runs}
      canExecute
      saveBlocked={false}
      {...events}
    />,
  ));
  return events;
}

function buttonWithText(text: string): HTMLButtonElement {
  const button = [...container.querySelectorAll<HTMLButtonElement>('button')].find((item) => item.textContent?.includes(text));
  if (!button) throw new Error(`未找到按钮：${text}`);
  return button;
}

async function setInputValue(input: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
  setter?.call(input, value);
  await act(async () => input.dispatchEvent(new Event('input', { bubbles: true })));
}

describe('Inspector editing behavior', () => {
  it('edits Music 3 caption and multiline lyrics separately without submitting', async () => {
    const node = makeAudio({ provider: 'comfy-minimax-music', model: 'minimax-music-3', mode: 'song', prompt: '温柔的钢琴流行', options: { 'comfy-minimax-music': { lyrics: '[Verse]\n雨停了。', max_duration: 60 } } });
    const events = await renderInspector(node, [musicCapability(), ttsCapability()]);
    const fields = [...container.querySelectorAll<HTMLLabelElement>('label.field')];
    const caption = fields.find((field) => field.textContent?.includes('音乐描述'))?.querySelector('textarea');
    const lyrics = fields.find((field) => field.textContent?.includes('歌词'))?.querySelector('textarea');
    expect(caption?.value).toBe('温柔的钢琴流行');
    expect(lyrics?.value).toBe('[Verse]\n雨停了。');
    expect(container.textContent).toContain('音乐规格');
    expect(container.textContent).not.toContain('语速倍率');
    const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')?.set;
    setter?.call(lyrics, '[Chorus]\n天亮了！');
    await act(async () => lyrics!.dispatchEvent(new Event('input', { bubbles: true })));
    expect(events.onUpdateOptions).toHaveBeenCalledWith('comfy-minimax-music', 'lyrics', '[Chorus]\n天亮了！');
    expect(events.onExecute).not.toHaveBeenCalled();
  });
  it('immediately marks reordered references as draft changes until a new run', async () => {
    const node = makeVideo({ provider: 'comfy', model: 'h3', mode: 't2v', duration: undefined, aspect_ratio: undefined });
    const run: Run = { id: 'queued', node_id: node.id, status: 'queued', outputs: [], created_at: '2026-09-22T00:00:00Z',
      snapshot: { node_id: node.id, node_type: 'video', provider: 'comfy', model: 'h3', mode: 't2v', prompt: node.data.prompt, parameters: {}, inputs: {} } };
    const events = callbacks();
    const onMoveReference = vi.fn();
    const edges = ['a', 'b'].map(id => ({ id, source: id, target: node.id, targetHandle: 'reference_image' }));
    const render = async (current: Run) => act(async () => root.render(<Inspector node={node} nodes={[node]} edges={edges} capabilities={[capability()]} runs={[current]} canExecute saveBlocked={false} {...events} onMoveReference={onMoveReference} />));
    await render(run);
    expect(container.querySelector('.stale-note')).toBeNull();
    await act(async () => container.querySelector<HTMLButtonElement>('[aria-label="图 1下移"]')!.click());
    expect(onMoveReference).toHaveBeenCalledWith('a', 1);
    expect(container.querySelector('.stale-note')).not.toBeNull();
    await render({ ...run, id: 'new-run' });
    expect(container.querySelector('.stale-note')).toBeNull();
  });
  it('lets users clear retained reference-only options after switching to text generation', async () => {
    const node = createFlowNode('image', { x: 0, y: 0 }, 'qwen');
    Object.assign(node.data, { provider: 'comfy-qwen-image', model: 'qwen-image-2.1', mode: 'create', options: { 'comfy-qwen-image': { reference_resolution: 1024 } } });
    const cap: Capability = { ...capability(), id: 'comfy-qwen-image', node_types: ['image'],
      models: [{ id: 'qwen-image-2.1', label: 'Qwen' }], modes: [{ id: 'create', label: '文生图' }],
      fields: [{ key: 'reference_resolution', label: '参考图预算边长', type: 'number', group: 'advanced', modes: ['reference', 'edit'] }] };
    const events = await renderInspector(node, [cap]);
    expect(container.textContent).toContain('当前模式不支持参考图预算边长');
    await act(async () => buttonWithText('清空').click());
    expect(events.onUpdateOptions).toHaveBeenCalledWith('comfy-qwen-image', 'reference_resolution', undefined);
  });
  it('exposes Qwen pixel budget and explains edit target ordering', async () => {
    const node = createFlowNode('image', { x: 0, y: 0 }, 'qwen');
    Object.assign(node.data, { provider: 'comfy-qwen-image', model: 'qwen-image-2.1', mode: 'reference' });
    const cap: Capability = { ...capability(), id: 'comfy-qwen-image', node_types: ['image'],
      models: [{ id: 'qwen-image-2.1', label: 'Qwen' }], modes: [{ id: 'reference', label: '图片参考生成' }],
      fields: [{ key: 'megapixels', label: '生成像素预算（MP）', type: 'number', group: 'specs', min: 0.25, max: 4, required: true }] };
    await renderInspector(node, [cap]);
    expect(container.textContent).toContain('生成像素预算');
    expect(container.textContent).toContain('10 张');
    expect(container.textContent).toContain('第 1 张');
  });
  it('opens audio in the media preview without nesting playback controls inside its button', async () => {
    const node = createFlowNode('asset', { x: 0, y: 0 }, 'audio-test');
    node.data.asset = { path: 'audio/voice.wav', kind: 'audio', name: '旁白.wav' };
    const events = await renderInspector(node);
    const preview = container.querySelector<HTMLButtonElement>('.preview-card');

    expect(preview?.textContent).toContain('播放音频');
    expect(preview?.querySelector('audio')).toBeNull();
    await act(async () => preview!.click());
    expect(events.onOpenMedia).toHaveBeenCalledWith(expect.objectContaining({ path: 'audio/voice.wav', kind: 'audio' }));
    expect(events.onUpdate).not.toHaveBeenCalled();
    expect(events.onExecute).not.toHaveBeenCalled();
  });

  it('shows TTS default hints for unsaved required fields and keeps confirmation disabled', async () => {
    const node = makeAudio();
    const events = await renderInspector(node, [ttsCapability()]);
    const fields = [...container.querySelectorAll<HTMLLabelElement>('label.field')];
    const fieldFor = (label: string) => fields.find((field) => field.textContent?.includes(label));

    expect(fieldFor('逐字台词')?.querySelector('textarea')?.value).toBe('请完整说出这句台词。');
    expect(fieldFor('声音角色')?.querySelector<HTMLSelectElement>('select')?.value).toBe('');
    expect(fieldFor('声音角色')?.querySelector('option[value=""]')?.textContent).toContain('默认值 Eric');
    expect(fieldFor('声音角色')?.querySelector('select')?.textContent).toContain('Uncle_fu');
    expect(fieldFor('语言')?.querySelector<HTMLSelectElement>('select')?.value).toBe('');
    expect(fieldFor('语言')?.querySelector('option[value=""]')?.textContent).toContain('默认值 Chinese');
    expect(fieldFor('语速')?.querySelector<HTMLInputElement>('input')?.value).toBe('');
    expect(fieldFor('语速')?.querySelector<HTMLInputElement>('input')?.placeholder).toContain('默认值 1.2');
    expect(container.textContent).not.toContain('画幅比例');
    expect(container.textContent).not.toContain('像素预算');
    expect(container.textContent).not.toContain('时长（秒）');
    expect(buttonWithText('确认执行').disabled).toBe(true);
    expect(events.onExecute).not.toHaveBeenCalled();

    await act(async () => buttonWithText('展开高级参数（3项）').click());
    const tokenField = [...container.querySelectorAll<HTMLLabelElement>('label.field')].find((field) => field.textContent?.includes('最大新 token 数'));
    const tokens = tokenField?.querySelector<HTMLInputElement>('input[type="number"]');
    expect(tokens?.value).toBe('2048');
    expect(tokens?.min).toBe('512');
    expect(tokens?.max).toBe('4096');
    const seedField = [...container.querySelectorAll<HTMLLabelElement>('label.field')].find((field) => field.textContent?.includes('随机种子'));
    expect(seedField?.querySelector<HTMLInputElement>('input[type="number"]')?.max).toBe('9007199254740991');
  });

  it('shows successful FLAC output duration and keeps the generated run preview action', async () => {
    const node = makeAudio();
    const run: Run = {
      id: 'tts-success', node_id: node.id, status: 'succeeded',
      snapshot: { node_id: node.id, node_type: 'audio' as never, provider: 'comfy-qwen-tts', model: 'qwen3-tts-1.7b-customvoice', mode: 'tts', prompt: node.data.prompt, parameters: {}, inputs: {} },
      outputs: [{ path: 'audio/voice.flac', kind: 'audio/flac', name: '旁白.flac', metadata: { duration_ms: 2450, sample_rate: 24000, channels: 1, tempo: 1.2, seed: 7, raw_duration_ms: 2410 } }],
    };
    const events = await renderInspector(node, [ttsCapability()], [run]);

    expect(container.querySelector('.preview-section')?.textContent).toContain('实际时长 2.45 秒');
    expect(container.querySelector('.preview-card')?.textContent).toContain('播放音频');
    await act(async () => container.querySelector<HTMLButtonElement>('.preview-card')?.click());
    expect(events.onOpenPreview).toHaveBeenCalledWith(run);
  });

  it('keeps history and derived outputs collapsed until opened, then opens the selected media read-only', async () => {
    const node = makeVideo({
      history: [{ id: 'history-1', label: '上一版夜站', status: '历史成功', asset: { path: 'history/old.mp4', kind: 'video', name: 'old.mp4' } }],
      derived_outputs: [{ id: 'tail-1', label: '真实末帧', asset: { path: 'derived/tail.png', kind: 'image', name: 'tail.png' } }],
    });
    const events = await renderInspector(node);

    expect(container.querySelector('.history-inspector-list')).toBeNull();
    expect(container.querySelector('.derived-section .history-inspector-list')).toBeNull();

    await act(async () => buttonWithText('展开历史版本').click());
    expect(container.querySelector('.history-section .history-inspector-list')).not.toBeNull();
    await act(async () => container.querySelector<HTMLButtonElement>('.history-section .preview-card')!.click());
    expect(events.onOpenMedia).toHaveBeenCalledWith(expect.objectContaining({ path: 'history/old.mp4', kind: 'video' }));
    expect(events.onUpdate).not.toHaveBeenCalled();
    expect(events.onExecute).not.toHaveBeenCalled();

    await act(async () => buttonWithText('展开派生输出').click());
    expect(container.querySelector('.derived-section .history-inspector-list')).not.toBeNull();
    await act(async () => container.querySelector<HTMLButtonElement>('.derived-section .preview-card')!.click());
    expect(events.onOpenMedia).toHaveBeenCalledWith(expect.objectContaining({ path: 'derived/tail.png', kind: 'image' }));
    expect(events.onUpdate).not.toHaveBeenCalled();
    expect(events.onExecute).not.toHaveBeenCalled();
  });

  it('saves a specification field edit without submitting generation', async () => {
    const node = makeVideo();
    const events = await renderInspector(node);
    const durationField = [...container.querySelectorAll<HTMLLabelElement>('label.field')]
      .find((field) => field.textContent?.includes('时长（秒）'));
    const duration = durationField?.querySelector<HTMLInputElement>('input[type="number"]');
    if (!duration) throw new Error('未找到时长字段');

    await setInputValue(duration, '8');

    expect(events.onUpdate).toHaveBeenCalledWith({ duration: 8 });
    expect(events.onExecute).not.toHaveBeenCalled();
  });

  it('keeps an unavailable provider option disabled in the route selector', async () => {
    const node = makeVideo();
    await renderInspector(node, [capability(false)]);
    const providerOption = container.querySelector<HTMLOptionElement>('select option[value="comfy"]');

    expect(providerOption).not.toBeNull();
    expect(providerOption?.disabled).toBe(true);
  });

  it('keeps an installed agent handoff selectable and labels it clearly', async () => {
    const node = makeVideo({ provider: '' });
    const agent: Capability = {
      ...capability(),
      id: 'agent-video',
      label: '远端视频 Agent',
      execution: 'agent',
      available: false,
      installed: true,
      reason: '需要接手会话核实工具',
    };
    await renderInspector(node, [agent]);

    const option = container.querySelector<HTMLOptionElement>('select option[value="agent-video"]');
    expect(option?.disabled).toBe(false);
    expect(option?.textContent).toContain('需 Agent 接手');
  });

  it('shows the selected node frozen input while queued and marks a changed draft', async () => {
    const node = makeVideo({ provider: 'comfy', model: 'h3', mode: 't2v', prompt: '当前草稿提示词' });
    const run: Run = {
      id: 'run-queued',
      node_id: node.id,
      status: 'queued',
      snapshot: {
        node_id: node.id,
        node_type: 'video',
        provider: 'comfy',
        model: 'h3',
        mode: 't2v',
        prompt: '确认时冻结的提示词',
        parameters: { duration: 5 },
        inputs: {},
      },
      outputs: [],
      created_at: '2026-09-09T10:00:00Z',
    };
    const newerOtherNode: Run = {
      ...run,
      id: 'run-other',
      node_id: 'other-node',
      status: 'running',
      snapshot: { ...run.snapshot, node_id: 'other-node', prompt: '其他节点输入' },
      created_at: '2026-09-09T10:01:00Z',
    };

    await renderInspector(node, [capability()], [run, newerOtherNode]);

    expect(container.querySelector('.run-summary')?.textContent).toContain('已确认');
    expect(container.querySelector('.snapshot-frozen-note')?.textContent).toContain('冻结输入');
    expect(container.querySelector('.snapshot-body')?.textContent).toContain('确认时冻结的提示词');
    expect(container.querySelector('.snapshot-body')?.textContent).not.toContain('其他节点输入');
    expect(container.querySelector('.stale-note')?.textContent).toContain('当前草稿已有修改');
    expect(buttonWithText('等待执行').disabled).toBe(true);
  });

  it('surfaces cancelled runs and inconclusive review without treating them as success', async () => {
    const node = makeVideo({ provider: 'comfy', model: 'h3', mode: 't2v' });
    const run: Run = {
      id: 'run-cancelled',
      node_id: node.id,
      status: 'cancelled',
      snapshot: { node_id: node.id, node_type: 'video', provider: 'comfy', model: 'h3', mode: 't2v', prompt: node.data.prompt, parameters: {}, inputs: {} },
      outputs: [],
      created_at: '2026-09-09T10:00:00Z',
      attention_state: 'paused',
      attention_reason: '等待核实',
      review: { decision: 'INCONCLUSIVE', evidence: [], end_state: {}, unverified: ['未提交'] },
    };
    await renderInspector(node, [capability()], [run]);

    expect(container.querySelector('.run-summary')?.textContent).toContain('已取消未提交任务');
    expect(container.querySelector('.run-summary')?.textContent).toContain('需要局部复核');
    expect(container.querySelector('.run-summary')?.textContent).toContain('已暂停：等待核实');
    expect(container.querySelector('.preview-section')).toBeNull();
  });
});
