import { describe, expect, it } from 'vitest';
import type { Connection } from '@xyflow/react';
import { addCanvasEdge, createFlowNode, isValidConnection, moveReferenceEdge, normalizeEdges, outputForNode, outputForRun, resolveMediaOutput, serializeGraph, sortRuns, targetHandlesFor, toFlowNode } from './graph';
import type { FlowNode, Run } from './types';
import { normalizeWorkspace } from './workspace';

function imageAsset(path = 'assets/frame.png') {
  return { path, kind: 'image', name: path.split('/').pop() || 'frame.png' };
}

describe('canvas graph contract', () => {
  it('reorders only the selected node image inputs and preserves unrelated edges', () => {
    const edges = normalizeEdges([
      { id: 'one', source: 'a', target: 'image', targetHandle: 'reference_image' },
      { id: 'other', source: 'a', target: 'video', targetHandle: 'reference_image' },
      { id: 'two', source: 'b', target: 'image', targetHandle: 'reference_image' },
    ]);
    expect(moveReferenceEdge(edges, 'two', -1).map((edge) => edge.id)).toEqual(['two', 'other', 'one']);
    expect(moveReferenceEdge(edges, 'one', -1)).toEqual(edges);
    expect(edges.map((edge) => edge.id)).toEqual(['one', 'other', 'two']);
  });
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

  it('uses only an ACCEPTed review file inside its run folder for previews, without changing ordinary edge resolution', () => {
    const sourcePath = 'C:\\workspace\\outputs\\run-1\\generated.mp4';
    const adoptedPath = 'c:/workspace/outputs/run-1/P006-adopted-6s.mp4';
    const run: Run = {
      id: 'run-1', node_id: 'video-a', status: 'succeeded',
      snapshot: { node_id: 'video-a', node_type: 'video', provider: 'comfy', model: 'h3', mode: 'r2v', prompt: '', parameters: {}, inputs: {} },
      outputs: [{ path: sourcePath, kind: 'video/mp4', name: 'generated.mp4', metadata: { duration_ms: 8000, width: 608, height: 1056 } }],
      review: { decision: 'ACCEPT', evidence: [], end_state: {}, unverified: [], output_path: adoptedPath, output_sha256: 'sha256' },
    };

    expect(outputForRun(run)).toEqual({ path: adoptedPath, kind: 'video/mp4', name: 'P006-adopted-6s.mp4' });
    expect(outputForRun(run)?.metadata).toBeUndefined();

    const video = createFlowNode('video', { x: 0, y: 0 }, 'video-a');
    expect(outputForNode(video, 'output', [run])?.path).toBe(sourcePath);
  });

  it.each([
    ['REJECT', 'C:\\workspace\\outputs\\run-1\\fixed.mp4'],
    ['INCONCLUSIVE', 'C:\\workspace\\outputs\\run-1\\fixed.mp4'],
    ['ACCEPT', 'C:\\workspace\\outputs\\run-2\\outside.mp4'],
    ['ACCEPT', 'C:\\workspace\\outputs\\run-1\\..\\run-2\\outside.mp4'],
  ] as const)('keeps the generated preview for %s reviews with an unsafe or non-accepted path', (decision, outputPath) => {
    const original = { path: 'C:\\workspace\\outputs\\run-1\\generated.mp4', kind: 'video/mp4', name: 'generated.mp4', metadata: { duration_ms: 8000 } };
    const run: Run = {
      id: 'run-1', node_id: 'video-a', status: 'succeeded',
      snapshot: { node_id: 'video-a', node_type: 'video', provider: 'comfy', model: 'h3', mode: 'r2v', prompt: '', parameters: {}, inputs: {} },
      outputs: [original],
      review: { decision, evidence: [], end_state: {}, unverified: [], output_path: outputPath },
    };
    expect(outputForRun(run)).toBe(original);
  });

  it('keeps source metadata when ACCEPT points to the original output file', () => {
    const output = { path: '/workspace/outputs/run-1/generated.mp4', kind: 'video/mp4', name: 'generated.mp4', metadata: { duration_ms: 6000 } };
    const run: Run = {
      id: 'run-1', node_id: 'video-a', status: 'succeeded',
      snapshot: { node_id: 'video-a', node_type: 'video', provider: 'comfy', model: 'h3', mode: 'r2v', prompt: '', parameters: {}, inputs: {} },
      outputs: [output],
      review: { decision: 'ACCEPT', evidence: [], end_state: {}, unverified: [], output_path: '/workspace/outputs/run-1/./generated.mp4' },
    };
    expect(outputForRun(run)).toBe(output);
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

  it('round-trips a TTS node and lets its audio output feed video or clone audio references', () => {
    const voice = createFlowNode('audio' as never, { x: 32, y: 48 }, 'voice-1');
    Object.assign(voice.data, {
      label: '语音', prompt: '请沿用逐字台词', provider: 'comfy-qwen-tts',
      model: 'qwen3-tts-1.7b-customvoice', mode: 'tts',
      options: { 'comfy-qwen-tts': { speaker: 'Eric', language: 'Chinese', tempo: 1.2 } },
    });
    const video = createFlowNode('video', { x: 320, y: 48 }, 'shot-1');
    const image = createFlowNode('image', { x: 640, y: 48 }, 'image-1');
    const clone = createFlowNode('audio' as never, { x: 640, y: 120 }, 'clone-1');

    expect(targetHandlesFor('audio' as never)).toEqual(['reference_audio']);
    expect(voice.data.category).toBe('audio');
    expect(isValidConnection({ source: voice.id, sourceHandle: 'output', target: video.id, targetHandle: 'reference_audio' }, [voice, video])).toBe(true);
    expect(isValidConnection({ source: voice.id, sourceHandle: 'output', target: video.id, targetHandle: 'first_frame' }, [voice, video])).toBe(false);
    expect(isValidConnection({ source: voice.id, sourceHandle: 'output', target: image.id, targetHandle: 'reference_image' }, [voice, image])).toBe(false);
    expect(isValidConnection({ source: voice.id, sourceHandle: 'output', target: clone.id, targetHandle: 'reference_audio' }, [voice, clone])).toBe(true);
    expect(isValidConnection({ source: video.id, sourceHandle: 'output', target: clone.id, targetHandle: 'reference_audio' }, [video, clone])).toBe(false);
    expect(isValidConnection({ source: image.id, sourceHandle: 'output', target: voice.id, targetHandle: 'reference_audio' }, [image, voice])).toBe(false);

    const music = createFlowNode('audio' as never, { x: 640, y: 180 }, 'music');
    Object.assign(music.data, { provider: 'comfy-minimax-music', mode: 'song' });
    expect(isValidConnection({ source: voice.id, sourceHandle: 'output', target: music.id, targetHandle: 'reference_audio' }, [voice, music])).toBe(false);

    const graph = serializeGraph([voice, video], [], { x: 0, y: 0, zoom: 1 }, []);
    expect(graph.nodes[0]).toMatchObject({ type: 'audio', data: { prompt: '请沿用逐字台词', provider: 'comfy-qwen-tts', model: 'qwen3-tts-1.7b-customvoice', mode: 'tts' } });
    expect(toFlowNode(graph.nodes[0]).data.options).toEqual({ 'comfy-qwen-tts': { speaker: 'Eric', language: 'Chinese', tempo: 1.2 } });
  });

  it('resolves successful audio runs and recognizes FLAC files as audio references', () => {
    const voice = createFlowNode('audio' as never, { x: 0, y: 0 }, 'voice-1');
    const run = {
      id: 'run-voice', node_id: voice.id, status: 'succeeded' as const,
      snapshot: { node_id: voice.id, node_type: 'audio' as never, provider: 'comfy-qwen-tts', model: 'qwen3-tts-1.7b-customvoice', mode: 'tts', prompt: '逐字台词', parameters: {}, inputs: {} },
      outputs: [{ path: 'audio/voice.flac', kind: 'audio/flac', metadata: { duration_ms: 2450, sample_rate: 24000, channels: 1, tempo: 1.2, seed: 12, raw_duration_ms: 2430 } }],
    };
    expect(outputForNode(voice, 'output', [run])?.path).toBe('audio/voice.flac');

    const flacAsset = createFlowNode('asset', { x: 0, y: 0 }, 'flac');
    flacAsset.data.asset = { path: 'audio/reference.flac', name: 'reference.flac', kind: 'file' };
    const video = createFlowNode('video', { x: 320, y: 0 }, 'shot-1');
    expect(isValidConnection({ source: flacAsset.id, sourceHandle: 'output', target: video.id, targetHandle: 'reference_audio' }, [flacAsset, video])).toBe(true);
  });
});
