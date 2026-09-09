import { describe, expect, it } from 'vitest';
import type { Connection } from '@xyflow/react';
import { addCanvasEdge, createFlowNode, isValidConnection, normalizeEdges, outputForNode, resolveMediaOutput, serializeGraph, sortRuns, toFlowNode } from './graph';
import type { FlowNode, Run } from './types';
import { normalizeWorkspace } from './workspace';

function imageAsset(path = 'assets/frame.png') {
  return { path, kind: 'image', name: path.split('/').pop() || 'frame.png' };
}

describe('canvas graph contract', () => {
  it('creates direct-prompt media nodes without assuming a provider or model', () => {
    const video = createFlowNode('video', { x: 16, y: 24 });
    const image = createFlowNode('image', { x: 320, y: 24 });

    expect(video.data.provider).toBe('');
    expect(video.data.prompt).toBe('');
    expect(video.data.duration).toBeUndefined();
    expect(image.data.provider).toBe('');
    expect(image.data.model).toBe('');
    expect(image.data.mode).toBe('');
  });

  it('accepts explicit media input handles and derived output handles', () => {
    const reference = createFlowNode('asset', { x: 0, y: 0 }, 'reference-a');
    reference.data.asset = imageAsset();
    const image = createFlowNode('image', { x: 280, y: 0 }, 'image-a');
    const video = createFlowNode('video', { x: 560, y: 0 }, 'video-a');
    const nodes = [reference, image, video];

    const imageConnection: Connection = { source: reference.id, sourceHandle: 'output', target: image.id, targetHandle: 'reference_image' };
    const videoConnection: Connection = { source: image.id, sourceHandle: 'output', target: video.id, targetHandle: 'first_frame' };
    const invalidPromptConnection: Connection = { source: reference.id, sourceHandle: 'output', target: video.id, targetHandle: 'prompt' };
    const invalidGenericConnection: Connection = { source: reference.id, sourceHandle: 'output', target: image.id, targetHandle: 'media' };

    expect(isValidConnection(imageConnection, nodes)).toBe(true);
    expect(isValidConnection(videoConnection, nodes)).toBe(true);
    expect(isValidConnection(invalidPromptConnection, nodes)).toBe(false);
    expect(isValidConnection(invalidGenericConnection, nodes)).toBe(false);

    video.data.derived_outputs = [{ id: 'tail', label: '真实末帧', asset: imageAsset('assets/tail.png') }];
    const derivedConnection: Connection = { source: video.id, sourceHandle: 'output:tail', target: video.id, targetHandle: 'first_frame' };
    expect(isValidConnection(derivedConnection, nodes)).toBe(false);
    expect(outputForNode(video, 'output:tail')?.path).toBe('assets/tail.png');
  });

  it('keeps the newest successful run ahead of imported current media and ignores history', () => {
    const video = createFlowNode('video', { x: 0, y: 0 }, 'video-a');
    video.data.asset = { path: 'assets/imported.mp4', kind: 'video', name: 'imported.mp4' };
    video.data.history = [{ id: 'old', label: '旧版本', asset: { path: 'assets/old.mp4', kind: 'video', name: 'old.mp4' } }];
    const failed: Run = { id: 'run-failed', node_id: video.id, status: 'failed', snapshot: { node_id: video.id, node_type: 'video', provider: 'comfy', model: 'h3', mode: 't2v', prompt: 'failed', parameters: {}, inputs: {} }, outputs: [], created_at: '2026-09-08T10:03:00Z' };
    const success: Run = { id: 'run-success', node_id: video.id, status: 'succeeded', snapshot: { node_id: video.id, node_type: 'video', provider: 'comfy', model: 'h3', mode: 't2v', prompt: 'new', parameters: {}, inputs: {} }, outputs: [{ path: 'outputs/new.mp4', kind: 'video', name: 'new.mp4' }], created_at: '2026-09-08T10:02:00Z' };

    expect(resolveMediaOutput(video.id, [video], [], [failed, success])?.path).toBe('outputs/new.mp4');
    expect(resolveMediaOutput(video.id, [video], [], [failed])?.path).toBe('assets/imported.mp4');
    expect(resolveMediaOutput(video.id, [video], [], [])?.path).toBe('assets/imported.mp4');
    expect(resolveMediaOutput(video.id, [video], [], [])?.path).not.toBe('assets/old.mp4');
  });

  it('serializes direct prompt, snapshots, history and derived outputs while stripping local callbacks', () => {
    const video = createFlowNode('video', { x: 111, y: 222 }, 'video-a');
    video.data.prompt = '雨夜里的人物回头';
    video.data.generation_snapshot = { provider: 'comfy', model: 'h3', mode: 't2v', prompt: '原提示词', parameters: { duration: 5 } };
    video.data.history = [{ id: 'old', label: '旧版本', asset: { path: 'assets/old.mp4', kind: 'video', name: 'old.mp4' }, status: 'accepted' }];
    video.data.derived_outputs = [{ id: 'tail', label: '真实末帧', asset: imageAsset('assets/tail.png'), source_version: 'run-1' }];
    video.data.latestPreview = { runId: 'run-1', output: { path: 'outputs/a.mp4', kind: 'video' } };
    expect(outputForNode(video)?.path).toBeUndefined();
    video.data.onPreview = () => undefined;
    const graph = serializeGraph([video], [], { x: 0, y: 0, zoom: 1 }, [video.id]);

    expect(graph.nodes[0].data.prompt).toBe('雨夜里的人物回头');
    expect(graph.nodes[0].data.generation_snapshot).toBeDefined();
    expect(graph.nodes[0].data.history).toHaveLength(1);
    expect(graph.nodes[0].data.derived_outputs).toHaveLength(1);
    expect(graph.nodes[0].data.latestPreview).toBeUndefined();
    expect(graph.nodes[0].data.onPreview).toBeUndefined();
    expect(toFlowNode(graph.nodes[0]).data.nodeType).toBe('video');
  });

  it('restores positions and explicit output handles without reintroducing generic media edges', () => {
    const video = createFlowNode('video', { x: 111, y: 222 }, 'video-a');
    const image = createFlowNode('image', { x: 444, y: 222 }, 'image-a');
    const edges = addCanvasEdge([], { source: video.id, sourceHandle: 'output:tail', target: image.id, targetHandle: 'reference_image' });
    const graph = serializeGraph([video, image], edges, { x: -20, y: 8, zoom: 0.8 }, []);
    const restored = graph.nodes.map(toFlowNode);
    expect(restored[0].position).toEqual({ x: 111, y: 222 });
    expect(graph.edges[0].sourceHandle).toBe('output:tail');
    expect(graph.edges[0].targetHandle).toBe('reference_image');
    expect(graph.edges[0].targetHandle).not.toBe('media');
    expect(graph.viewport.zoom).toBe(0.8);
  });

  it('round-trips accepted upstream run metadata through browser edge state', () => {
    const video = createFlowNode('video', { x: 0, y: 0 }, 'video-a');
    const image = createFlowNode('image', { x: 320, y: 0 }, 'image-a');
    const edge = addCanvasEdge([], { source: video.id, sourceHandle: 'output', target: image.id, targetHandle: 'reference_image' })[0];
    edge.data = { source_run_id: 'run-accepted', require_accept: true };

    const graph = serializeGraph([video, image], [edge], { x: 0, y: 0, zoom: 1 }, []);
    expect(graph.edges[0].source_run_id).toBe('run-accepted');
    expect(graph.edges[0].require_accept).toBe(true);

    const restored = normalizeEdges(graph.edges)[0];
    expect(restored.data).toMatchObject({ source_run_id: 'run-accepted', require_accept: true });
  });

  it('uses ID as a deterministic tie-breaker when run timestamps match', () => {
    const base = (id: string): Run => ({ id, node_id: 'video-a', status: 'succeeded', snapshot: { node_id: 'video-a', node_type: 'video', provider: 'comfy', model: 'h3', mode: 't2v', prompt: '', parameters: {}, inputs: {} }, outputs: [{ path: `${id}.mp4`, kind: 'video' }], created_at: '2026-09-08T10:00:00Z' });
    expect(sortRuns([base('run-a'), base('run-z')])[0].id).toBe('run-z');
  });

  it('keeps workspace metadata extensions when normalizing story fields', () => {
    const workspace = normalizeWorkspace({ story: '第六章', chapter: '车站', summary: '夜里重逢', imported_at: '2026-09-08T00:00:00Z' });
    expect(workspace.story).toBe('第六章');
    expect(workspace.imported_at).toBe('2026-09-08T00:00:00Z');
  });
});
