import type { Edge } from '@xyflow/react';
import { describe, expect, it } from 'vitest';
import type { FlowNode } from './types';
import { connectionPresentation, resolveConnectionFocus } from './connectionFocus';

function node(id: string, label: string, x = 80): FlowNode {
  return {
    id,
    type: 'canvas',
    position: { x, y: 120 },
    data: {
      nodeType: 'video',
      label,
      prompt: `${label} prompt`,
      provider: 'comfy',
      model: '',
      mode: '',
      options: {},
    },
  };
}

function edge(id: string, source: string, target: string, targetHandle = 'first_frame'): Edge {
  return {
    id,
    source,
    target,
    sourceHandle: 'output',
    targetHandle,
    style: { stroke: '#71809a', strokeWidth: 1.4 },
  };
}

describe('connection focus presentation', () => {
  const nodes = [node('source', '起点镜头'), node('target', '终点镜头', 480), node('other', '无关镜头', 880)];
  const edges = [
    edge('actual', 'source', 'target'),
    edge('related', 'target', 'other', 'related'),
  ];

  it('highlights only the selected edge endpoints without mutating graph data', () => {
    const nodesBefore = JSON.stringify(nodes);
    const edgesBefore = JSON.stringify(edges);

    const presentation = connectionPresentation(nodes, edges, 'actual', 0);

    expect(presentation.focus?.edge.id).toBe('actual');
    expect(presentation.focus?.source.id).toBe('source');
    expect(presentation.focus?.target.id).toBe('target');
    expect(presentation.focus?.related).toBe(false);

    expect(presentation.nodes.find((item) => item.id === 'source')?.className)
      .toContain('connection-endpoint-source');
    expect(presentation.nodes.find((item) => item.id === 'target')?.className)
      .toContain('connection-endpoint-target');
    expect(presentation.nodes.find((item) => item.id === 'other')?.className).not
      .toContain('connection-endpoint');
    expect(presentation.nodes.find((item) => item.id === 'source')?.position)
      .toBe(nodes[0].position);
    expect(presentation.nodes.find((item) => item.id === 'source')?.data)
      .toBe(nodes[0].data);

    expect(presentation.edges.find((item) => item.id === 'actual')?.selected).toBe(true);
    expect(presentation.edges.find((item) => item.id === 'actual')?.className)
      .toContain('connection-focused-edge');
    expect(presentation.edges.find((item) => item.id === 'related')?.selected).toBe(false);
    expect(presentation.edges.find((item) => item.id === 'actual')?.ariaLabel)
      .toBe('实际输入：起点镜头 → 终点镜头');
    expect(presentation.edges.find((item) => item.id === 'actual')?.style)
      .toMatchObject({ stroke: '#b0d6c6', strokeWidth: 2.5 });

    expect(JSON.stringify(nodes)).toBe(nodesBefore);
    expect(JSON.stringify(edges)).toBe(edgesBefore);
  });

  it('distinguishes related references and clears invalid or missing focus safely', () => {
    const relatedPresentation = connectionPresentation(nodes, edges, 'related');

    expect(relatedPresentation.focus?.related).toBe(true);
    expect(relatedPresentation.focus?.source.data.label).toBe('终点镜头');
    expect(relatedPresentation.focus?.target.data.label).toBe('无关镜头');
    expect(relatedPresentation.edges.find((item) => item.id === 'related')?.ariaLabel)
      .toBe('资料关联：终点镜头 → 无关镜头');
    expect(relatedPresentation.edges.find((item) => item.id === 'actual')?.selected).toBe(false);
    expect(relatedPresentation.nodes.find((item) => item.id === 'source')?.className)
      .not.toContain('connection-endpoint');

    const missing = connectionPresentation(nodes, edges, 'does-not-exist');
    const invalid = connectionPresentation(nodes, [...edges, edge('invalid', 'gone', 'target')], 'invalid');

    expect(missing.focus).toBeUndefined();
    expect(missing.nodes).toBe(nodes);
    expect(invalid.focus).toBeUndefined();
    expect(invalid.nodes).toBe(nodes);
    expect(resolveConnectionFocus(nodes, edges, undefined)).toBeUndefined();
  });

  it('changes the pulse class when the same connection is selected again', () => {
    const first = connectionPresentation(nodes, edges, 'actual', 0);
    const repeated = connectionPresentation(nodes, edges, 'actual', 1);

    expect(first.nodes.find((item) => item.id === 'source')?.className)
      .toContain('connection-pulse-0');
    expect(repeated.nodes.find((item) => item.id === 'source')?.className)
      .toContain('connection-pulse-1');
    expect(repeated.nodes.find((item) => item.id === 'target')?.className)
      .toContain('connection-pulse-1');
  });

  it('keeps a usable connection hit area when zoomed out without thickening the visible line', () => {
    const overview = connectionPresentation(nodes, edges, undefined, 0, 0.12);
    expect(overview.edges[0].interactionWidth * 0.12).toBeGreaterThanOrEqual(12);
    expect(overview.edges[0].style).toEqual(edges[0].style);
  });
});
