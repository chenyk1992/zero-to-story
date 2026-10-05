// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Palette } from './Palette';
import { createFlowNode } from './graph';
import type { FlowNode } from './types';

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  container = document.createElement('div');
  document.body.append(container);
  root = createRoot(container);
});
afterEach(async () => { await act(async () => root.unmount()); container.remove(); });

function sectionNode(id: string, label: string): FlowNode {
  const node = createFlowNode('asset', { x: 64, y: 80 }, id);
  return { ...node, data: { ...node.data, nodeType: 'section', label } } as unknown as FlowNode;
}

async function setSearch(value: string) {
  const input = container.querySelector<HTMLInputElement>('.asset-search input')!;
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, value);
    input.dispatchEvent(new Event('input', { bubbles: true }));
  });
}

function viewButton(label: string) {
  return [...container.querySelectorAll<HTMLButtonElement>('.palette-view-button')].find((button) => button.textContent?.includes(label));
}

describe('asset navigation', () => {
  it('filters a chapter and focuses the original card without changing its contents', async () => {
    const image = createFlowNode('image', { x: 0, y: 0 }, 'character');
    image.data.label = '苏轼'; image.data.category = 'character';
    const video = createFlowNode('video', { x: 400, y: 0 }, 'shot');
    video.data.label = 'P001 · 问典'; video.data.category = 'video';
    const onSelect = vi.fn();
    await act(async () => root.render(<Palette nodes={[image, video]} onAdd={vi.fn()} onSelect={onSelect} />));
    const category = [...container.querySelectorAll<HTMLButtonElement>('.asset-filter')].find((button) => button.textContent?.includes('视频'))!;
    await act(async () => category.click());
    const cards = container.querySelectorAll<HTMLButtonElement>('.asset-list-item');
    expect(cards).toHaveLength(1);
    expect(category.getAttribute('aria-pressed')).toBe('true');
    await act(async () => cards[0].click());
    expect(onSelect).toHaveBeenCalledWith('shot');
    expect(video.data.prompt).toBe('');
    expect(video.position).toEqual({ x: 400, y: 0 });
  });

  it('keeps add tools and the asset toggle accessible in the narrow rail', async () => {
    const onAdd = vi.fn(); const onToggle = vi.fn();
    await act(async () => root.render(<Palette nodes={[]} collapsed onToggle={onToggle} onAdd={onAdd} onSelect={vi.fn()} />));
    await act(async () => container.querySelector<HTMLButtonElement>('[aria-label="添加视频"]')!.click());
    await act(async () => container.querySelector<HTMLButtonElement>('[aria-label="添加音频"]')!.click());
    await act(async () => container.querySelector<HTMLButtonElement>('[aria-label="展开资产栏"]')!.click());
    expect(onAdd).toHaveBeenCalledWith('video');
    expect(onAdd).toHaveBeenCalledWith('audio');
    expect(onToggle).toHaveBeenCalledOnce();
  });

  it('locates sections from the outline without changing the graph order or contents', async () => {
    const shot = createFlowNode('video', { x: 400, y: 0 }, 'shot');
    shot.data.label = 'P001 · 月台';
    const section = sectionNode('station', '车站场景');
    const image = createFlowNode('image', { x: 800, y: 0 }, 'reference');
    image.data.label = '人物参考';
    const nodes = [shot, section, image];
    const original = structuredClone(nodes);
    const onSelect = vi.fn();
    await act(async () => root.render(<Palette nodes={nodes} selectedId="station" onAdd={vi.fn()} onSelect={onSelect} />));
    expect(container.querySelector('.asset-list')?.textContent).not.toContain('车站场景');
    expect(viewButton('大纲')).toBeDefined();
    await act(async () => viewButton('大纲')!.click());
    const cards = container.querySelectorAll<HTMLButtonElement>('.asset-list-item');
    expect([...cards].map((card) => card.querySelector('strong')?.textContent)).toEqual(['车站场景', 'P001 · 月台', '人物参考']);
    expect(viewButton('大纲')?.getAttribute('aria-pressed')).toBe('true');
    expect(cards[0].getAttribute('aria-current')).toBe('true');
    expect(cards[1].hasAttribute('aria-current')).toBe(false);
    await act(async () => cards[0].click());
    expect(onSelect).toHaveBeenCalledWith('station');
    expect(nodes).toEqual(original);
  });

  it('finds a section in the outline and clears its search without changing views', async () => {
    const shot = createFlowNode('video', { x: 0, y: 0 }, 'shot');
    await act(async () => root.render(<Palette nodes={[shot, sectionNode('station', '车站场景')]} onAdd={vi.fn()} onSelect={vi.fn()} />));
    expect(viewButton('大纲')).toBeDefined();
    await act(async () => viewButton('大纲')!.click());
    await setSearch('车站');
    expect(container.querySelectorAll('.asset-list-item')).toHaveLength(1);
    expect(container.querySelector('.asset-list-item strong')?.textContent).toBe('车站场景');
    await act(async () => container.querySelector<HTMLButtonElement>('[aria-label="清除搜索"]')!.click());
    expect(container.querySelectorAll('.asset-list-item')).toHaveLength(2);
    expect(viewButton('大纲')?.getAttribute('aria-pressed')).toBe('true');
    expect(document.activeElement).toBe(container.querySelector('.asset-search input'));
  });

  it('restores assets from an empty result by resetting both search and category filters', async () => {
    const shot = createFlowNode('video', { x: 0, y: 0 }, 'shot');
    const image = createFlowNode('image', { x: 0, y: 0 }, 'image');
    await act(async () => root.render(<Palette nodes={[shot, image]} onAdd={vi.fn()} onSelect={vi.fn()} />));
    const category = [...container.querySelectorAll<HTMLButtonElement>('.asset-filter')].find((button) => button.textContent?.includes('视频'))!;
    await act(async () => category.click());
    await setSearch('不存在的镜头');
    expect(container.querySelectorAll('.asset-list-item')).toHaveLength(0);
    const reset = container.querySelector<HTMLButtonElement>('.asset-empty-reset');
    expect(reset).not.toBeNull();
    await act(async () => reset!.click());
    expect(container.querySelectorAll('.asset-list-item')).toHaveLength(2);
    expect(container.querySelector<HTMLInputElement>('.asset-search input')?.value).toBe('');
    expect(container.querySelector('.asset-filter[aria-pressed="true"]')?.textContent).toContain('全部');
  });

  it('keeps the material category when switching to an unfiltered outline and back', async () => {
    const shot = createFlowNode('video', { x: 0, y: 0 }, 'shot');
    const image = createFlowNode('image', { x: 0, y: 0 }, 'image');
    await act(async () => root.render(<Palette nodes={[shot, sectionNode('station', '车站场景'), image]} onAdd={vi.fn()} onSelect={vi.fn()} />));
    const category = [...container.querySelectorAll<HTMLButtonElement>('.asset-filter')].find((button) => button.textContent?.includes('视频'))!;
    await act(async () => category.click());
    expect(viewButton('大纲')).toBeDefined();
    await act(async () => viewButton('大纲')!.click());
    expect(container.querySelectorAll('.asset-list-item')).toHaveLength(3);
    await act(async () => viewButton('素材')!.click());
    expect(container.querySelectorAll('.asset-list-item')).toHaveLength(1);
    expect(container.querySelector('.asset-filter[aria-pressed="true"]')?.textContent).toContain('视频');
  });

  it('focuses search only for a new request, waiting until the rail expands', async () => {
    const props = { nodes: [], onAdd: vi.fn(), onSelect: vi.fn() };
    await act(async () => root.render(<Palette {...props} searchRequest={0} />));
    expect(document.activeElement).not.toBe(container.querySelector('.asset-search input'));
    const otherControl = document.createElement('button');
    container.append(otherControl);
    otherControl.focus();
    expect(document.activeElement).toBe(otherControl);
    await act(async () => root.render(<Palette {...props} searchRequest={1} />));
    expect(document.activeElement).toBe(container.querySelector('.asset-search input'));
    otherControl.focus();
    await act(async () => root.render(<Palette {...props} searchRequest={1} />));
    expect(document.activeElement).toBe(otherControl);
    await act(async () => root.render(<Palette {...props} collapsed searchRequest={2} />));
    expect(document.activeElement).toBe(otherControl);
    await act(async () => root.render(<Palette {...props} searchRequest={2} />));
    expect(document.activeElement).toBe(container.querySelector('.asset-search input'));
    otherControl.focus();
    await act(async () => root.render(<Palette {...props} collapsed searchRequest={2} />));
    await act(async () => root.render(<Palette {...props} searchRequest={2} />));
    expect(document.activeElement).toBe(otherControl);
  });
});
