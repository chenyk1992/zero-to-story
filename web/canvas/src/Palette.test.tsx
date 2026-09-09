// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Palette } from './Palette';
import { createFlowNode } from './graph';

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  container = document.createElement('div');
  document.body.append(container);
  root = createRoot(container);
});
afterEach(async () => { await act(async () => root.unmount()); container.remove(); });

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
    await act(async () => container.querySelector<HTMLButtonElement>('[aria-label="展开资产栏"]')!.click());
    expect(onAdd).toHaveBeenCalledWith('video');
    expect(onToggle).toHaveBeenCalledOnce();
  });
});
