// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Edge } from '@xyflow/react';
import { createFlowNode } from './graph';
import { ShotOverview, type ShotOverviewProps } from './ShotOverview';
import type { FlowNode, Run, RunOutput } from './types';

let container: HTMLDivElement;
let root: Root;

function node(id: string, data: Record<string, unknown> = {}): FlowNode {
  const result = createFlowNode('video', { x: 20, y: 40 }, id);
  return { ...result, data: { ...result.data, label: id, ...data } };
}

function run(id: string, nodeId: string, status: Run['status'], outputs: RunOutput[] = [], extra: Partial<Run> = {}): Run {
  return {
    id, node_id: nodeId, status, outputs,
    snapshot: { node_id: nodeId, node_type: 'video', provider: 'comfy', model: 'h3', mode: 't2v', prompt: '', parameters: {}, inputs: {} },
    ...extra,
  };
}

async function renderOverview(props: Partial<ShotOverviewProps> = {}) {
  const resolved: ShotOverviewProps = {
    nodes: [], edges: [], runs: [], onSelect: vi.fn(), onLocate: vi.fn(), onPreview: vi.fn(), onAdd: vi.fn(), ...props,
  };
  await act(async () => root.render(<ShotOverview {...resolved} />));
  return resolved;
}

function cardIds() {
  return Array.from(container.querySelectorAll<HTMLElement>('article[data-node-id]')).map((card) => card.dataset.nodeId);
}

function button(text: string, scope: ParentNode = container) {
  const match = Array.from(scope.querySelectorAll<HTMLButtonElement>('button')).find((element) => element.textContent?.trim() === text);
  expect(match, `Expected button: ${text}`).toBeDefined();
  return match!;
}

async function click(text: string, scope: ParentNode = container) {
  await act(async () => button(text, scope).click());
}

async function search(value: string) {
  const input = container.querySelector<HTMLInputElement>('input[type="search"]');
  expect(input).not.toBeNull();
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, value);
    input!.dispatchEvent(new Event('input', { bubbles: true }));
  });
}

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

describe('ShotOverview', () => {
  it('includes shot generators and boards while excluding characters, documents, sections and ordinary assets', async () => {
    await renderOverview({ nodes: [
      node('video'), node('image', { nodeType: 'image' }),
      node('board', { nodeType: 'asset', category: 'board' }),
      node('storyboard', { nodeType: 'asset', category: 'storyboard' }),
      node('character', { nodeType: 'image', category: 'character' }),
      node('document', { nodeType: 'document' }), node('section', { nodeType: 'section' }),
      node('reference', { nodeType: 'asset', asset: { path: 'reference.png', kind: 'image', name: 'reference' } }),
      node('audio', { nodeType: 'audio' }),
    ] });
    expect(cardIds()).toEqual(['video', 'image', 'board', 'storyboard']);
  });

  it('naturally sorts explicit panel IDs, keeps unnumbered order and never rearranges the graph', async () => {
    const nodes = [node('unlisted-b'), node('ten', { panel_id: 'P10' }), node('two', { panel_id: 'P2' }), node('unlisted-a')];
    const edges: Edge[] = [{ id: 'link', source: 'unlisted-a', target: 'two' }];
    const before = JSON.stringify({ nodes, edges });
    Object.freeze(nodes);
    Object.freeze(edges);
    await renderOverview({ nodes, edges });
    expect(cardIds()).toEqual(['two', 'ten', 'unlisted-b', 'unlisted-a']);
    expect(JSON.stringify({ nodes, edges })).toBe(before);
  });

  it('combines title or panel search with filters based on actual current media', async () => {
    await renderOverview({
      nodes: [node('done', { label: '夜雨', panel_id: 'P02' }), node('draft', { label: '日落', panel_id: 'P10' }), node('history-only', {
        history: [{ id: 'old', label: '旧产物', asset: { path: 'old.mp4', kind: 'video', name: 'old' } }],
      })],
      runs: [run('r1', 'done', 'succeeded', [{ path: 'rain.mp4', kind: 'video' }])],
    });
    await click('有成品');
    expect(cardIds()).toEqual(['done']);
    await search('p02');
    expect(cardIds()).toEqual(['done']);
    await search('日落');
    expect(cardIds()).toEqual([]);
    await click('待生成');
    expect(cardIds()).toEqual(['draft']);
    await search('');
    expect(cardIds()).toEqual(['draft', 'history-only']);
    await click('全部');
    await search('夜雨');
    expect(cardIds()).toEqual(['done']);
  });

  it('shows the newest run state while keeping an older real output available', async () => {
    await renderOverview({ nodes: [node('shot')], runs: [
      run('older', 'shot', 'succeeded', [{ path: 'earlier.mp4', kind: 'video' }], { created_at: '2026-10-01T00:00:00Z' }),
      run('newer', 'shot', 'failed', [], { created_at: '2026-10-02T00:00:00Z' }),
    ] });
    expect(container.querySelector('article')?.textContent).toContain('生成失败');
    expect(container.querySelector('article')?.textContent).not.toContain('已生成');
    expect(container.querySelector('.shot-overview-stale')?.textContent || '').toContain('保留上次成品');
    expect(container.querySelector('video')?.getAttribute('src')).toContain('earlier.mp4');
    expect(button('预览').disabled).toBe(false);
  });

  it('uses the readable H3 summary instead of exposing generation instructions', async () => {
    await renderOverview({ nodes: [node('shot', {
      prompt: 'subject_definitions:\n<Subject 1> is the traveler.\n\nsummary:\n旅人在月台等候末班车。\n\nretention_analysis:\n<Subject 1>: fully_preserved\n\ndetailed_description:\n[Shot 1] The camera tracks the traveler.',
    })] });
    const description = container.querySelector('.shot-overview-description');
    expect(description?.textContent).toBe('旅人在月台等候末班车。');
    expect(container.querySelector('article')?.textContent).not.toContain('subject_definitions');
    expect(container.querySelector('article')?.textContent).not.toContain('fully_preserved');
  });

  it('prefers the authored description and presents its text without Markdown syntax', async () => {
    await renderOverview({ nodes: [node('shot', {
      description: '## 夜站\n\n旅人在**月台**等候末班车。',
      content: '过期的故事板内容。',
      prompt: 'The traveler runs through the station.',
    })] });
    const description = container.querySelector('.shot-overview-description')?.textContent || '';
    expect(description).toContain('旅人在月台等候末班车。');
    expect(description).not.toContain('##');
    expect(description).not.toContain('**');
    expect(description).not.toContain('过期的故事板内容');
    expect(description).not.toContain('The traveler');
  });

  it('omits empty descriptions without adding a request to fill them in', async () => {
    await renderOverview({ nodes: [node('shot', { description: '', content: '', prompt: '' })] });
    expect(container.querySelector('.shot-overview-description')).toBeNull();
    expect(container.querySelector('article')?.textContent).not.toContain('补充画面描述');
  });

  it('identifies an edited draft while keeping the saved output previewable', async () => {
    const output: RunOutput = { path: 'saved.mp4', kind: 'video' };
    const props = await renderOverview({ nodes: [node('shot')], runs: [
      run('saved', 'shot', 'succeeded', [output], { matches_current: false }),
    ] });
    expect(container.querySelector('.shot-overview-stale')?.textContent || '').toContain('草稿已修改');
    expect(container.querySelector('.shot-overview-stale')?.textContent || '').toContain('已保存成品');
    expect(container.querySelector('video')?.getAttribute('src')).toContain('saved.mp4');
    await click('预览');
    expect(props.onPreview).toHaveBeenCalledWith('shot', output);
  });

  it('does not imply a saved output exists for a failed draft without media', async () => {
    await renderOverview({ nodes: [node('shot')], runs: [
      run('failed', 'shot', 'failed', [], { matches_current: false }),
    ] });
    expect(container.querySelector('.shot-overview-stale')).toBeNull();
    expect(button('预览').disabled).toBe(true);
  });

  it('does not equate generation success with adoption and binds adoption to the displayed output', async () => {
    await renderOverview({ nodes: [node('generated'), node('accepted'), node('replaced')], runs: [
      run('generated-run', 'generated', 'succeeded', [{ path: 'generated.mp4', kind: 'video' }]),
      run('accepted-run', 'accepted', 'succeeded', [{ path: 'accepted.mp4', kind: 'video' }], {
        review: { decision: 'ACCEPT', evidence: [], end_state: {}, unverified: [] },
      }),
      run('old', 'replaced', 'succeeded', [{ path: 'old.mp4', kind: 'video' }], {
        created_at: '2026-10-01T00:00:00Z', review: { decision: 'ACCEPT', evidence: [], end_state: {}, unverified: [] },
      }),
      run('new', 'replaced', 'succeeded', [{ path: 'new.mp4', kind: 'video' }], { created_at: '2026-10-02T00:00:00Z' }),
    ] });
    expect(container.querySelector('[data-node-id="generated"]')?.textContent).toContain('已生成');
    expect(container.querySelector('[data-node-id="generated"]')?.textContent).not.toContain('已采用');
    expect(container.querySelector('[data-node-id="accepted"]')?.textContent).toContain('已采用');
    expect(container.querySelector('[data-node-id="replaced"]')?.textContent).not.toContain('已采用');
  });

  it('previews the resolved media and keeps video thumbnails muted without autoplay', async () => {
    const output: RunOutput = { path: 'actual.mp4', kind: 'video', metadata: { duration_ms: 4200 } };
    const props = await renderOverview({ nodes: [node('shot', { asset: { path: 'outdated.png', kind: 'image', name: 'outdated' } })], runs: [run('run', 'shot', 'succeeded', [output])] });
    const thumbnail = container.querySelector('video');
    expect(thumbnail?.getAttribute('src')).toContain('actual.mp4');
    expect(thumbnail?.muted).toBe(true);
    expect(thumbnail?.getAttribute('preload')).toBe('metadata');
    expect(thumbnail?.autoplay).toBe(false);
    await click('预览');
    expect(props.onPreview).toHaveBeenCalledWith('shot', output);
  });

  it('renders board images and never substitutes an upstream reference or history for a missing result', async () => {
    await renderOverview({
      nodes: [node('board', { nodeType: 'asset', category: 'board', asset: { path: 'board.png', kind: 'image', name: '分镜板' } }), node('draft')],
      edges: [{ id: 'ref', source: 'board', target: 'draft', targetHandle: 'first_frame' }],
    });
    expect(container.querySelector('[data-node-id="board"] img')?.getAttribute('src')).toContain('board.png');
    const draft = container.querySelector('[data-node-id="draft"]')!;
    expect(draft.querySelector('img, video')).toBeNull();
    expect(button('预览', draft).disabled).toBe(true);
  });

  it('routes editing and canvas location to the correct selected node without previewing or generating', async () => {
    const props = await renderOverview({ nodes: [node('shot', { label: '远山' })], selectedId: 'shot' });
    const card = container.querySelector('[data-node-id="shot"]')!;
    expect(card.classList.contains('is-selected')).toBe(true);
    await click('编辑', card);
    await act(async () => container.querySelector<HTMLButtonElement>('[aria-label="在画布中定位 远山"]')!.click());
    expect(props.onSelect).toHaveBeenCalledWith('shot');
    expect(props.onLocate).toHaveBeenCalledWith('shot');
    expect(props.onPreview).not.toHaveBeenCalled();
    expect(props.onAdd).not.toHaveBeenCalled();
  });

  it('offers adding a video draft when the canvas has no shots', async () => {
    const props = await renderOverview({ nodes: [node('notes', { nodeType: 'document' })] });
    expect(container.querySelector('.shot-overview')).not.toBeNull();
    await click('添加视频草稿');
    expect(props.onAdd).toHaveBeenCalledOnce();
    expect(props.onPreview).not.toHaveBeenCalled();
  });
});
