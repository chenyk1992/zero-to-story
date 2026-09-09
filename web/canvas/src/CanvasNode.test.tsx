// @vitest-environment jsdom
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import type { NodeProps } from '@xyflow/react';
import type { FlowNode } from './types';
import { createFlowNode } from './graph';
import { CanvasNode } from './CanvasNode';

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

describe('media card controls', () => {
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

  it('shows the configured provider instead of labeling every image as built-in generation', () => {
    const node = createFlowNode('image', { x: 0, y: 0 });
    expect(render(node).querySelector('.node-provider')?.textContent).toBe('请选择生成方式');
    node.data.provider = 'custom-studio';
    expect(render(node).querySelector('.node-provider')?.textContent).toBe('custom-studio');
    node.data.provider = 'codex-imagegen';
    expect(render(node).querySelector('.node-provider')?.textContent).toBe('内置生图');
  });
});
