import type { Edge } from '@xyflow/react';
import type { FlowNode } from './types';

export function resolveConnectionFocus(nodes: FlowNode[], edges: Edge[], edgeId?: string) {
  const edge = edges.find((item) => item.id === edgeId);
  const source = nodes.find((node) => node.id === edge?.source);
  const target = nodes.find((node) => node.id === edge?.target);
  if (!edge || !source || !target) return undefined;
  return { edge, source, target, related: edge.targetHandle === 'related' };
}

/** Presentation only: never set graph data, positions, inputs or run status. */
export function connectionPresentation(nodes: FlowNode[], edges: Edge[], edgeId?: string, pulse = 0, zoom = 1) {
  const focus = resolveConnectionFocus(nodes, edges, edgeId);
  return {
    focus,
    nodes: focus ? nodes.map((node) => {
      const role = node.id === focus.source.id ? 'source' : node.id === focus.target.id ? 'target' : undefined;
      return {
        ...node,
        selected: false,
        className: [node.className, role && `connection-endpoint connection-endpoint-${role} connection-pulse-${pulse % 2}`].filter(Boolean).join(' '),
        zIndex: role ? 5 : node.zIndex,
      };
    }) : nodes,
    edges: edges.map((edge) => {
      const source = nodes.find((node) => node.id === edge.source);
      const target = nodes.find((node) => node.id === edge.target);
      const active = focus?.edge.id === edge.id;
      return {
        ...edge,
        className: [edge.className, active && 'connection-focused-edge'].filter(Boolean).join(' '),
        selected: Boolean(active),
        interactionWidth: Math.max(24, 12 / Math.max(0.04, zoom)),
        ariaLabel: `${edge.targetHandle === 'related' ? '资料关联' : '实际输入'}：${source?.data.label || '起点'} → ${target?.data.label || '终点'}`,
        ...(active ? { zIndex: 4, style: { ...edge.style, stroke: '#b0d6c6', strokeWidth: 2.5 } } : {}),
      };
    }),
  };
}
