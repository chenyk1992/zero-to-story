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

function makeVideo(overrides: Partial<FlowNode['data']> = {}) {
  const node = createFlowNode('video', { x: 0, y: 0 }, 'video-test');
  node.data.label = '夜站镜头';
  node.data.prompt = '人物在雨夜站台回头';
  Object.assign(node.data, overrides);
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

  it('shows the selected node frozen input while pending and marks a changed draft', async () => {
    const node = makeVideo({ provider: 'comfy', model: 'h3', mode: 't2v', prompt: '当前草稿提示词' });
    const run: Run = {
      id: 'run-pending',
      node_id: node.id,
      status: 'pending_agent',
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

    expect(container.querySelector('.run-summary')?.textContent).toContain('待 Agent 执行');
    expect(container.querySelector('.snapshot-frozen-note')?.textContent).toContain('冻结输入');
    expect(container.querySelector('.snapshot-body')?.textContent).toContain('确认时冻结的提示词');
    expect(container.querySelector('.snapshot-body')?.textContent).not.toContain('其他节点输入');
    expect(container.querySelector('.stale-note')?.textContent).toContain('当前草稿已有修改');
    expect(buttonWithText('待 Agent 接手').disabled).toBe(true);
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
