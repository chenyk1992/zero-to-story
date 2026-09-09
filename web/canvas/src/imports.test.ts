import { describe, expect, it } from 'vitest';
import { importedAssetPatch, sameImportRequest } from './imports';
import type { AssetRef, HistoryEntry } from './types';
import type { StoryNodeData } from './workspace';

const imported: AssetRef = { path: 'workspace/assets/current.mp4', kind: 'video', name: 'current.mp4' };

function data(overrides: Partial<StoryNodeData> = {}): StoryNodeData {
  return {
    nodeType: 'video', label: '镜头', prompt: '下一版提示词', provider: 'comfy', model: 'h3', mode: 't2v', options: {},
    ...overrides,
  };
}

describe('media import state', () => {
  it('treats the same local path as a no-op', () => {
    const node = data({ import_path: 'C:\\Media\\shot.mp4', import_source_path: 'C:\\Media\\shot.mp4', asset: imported });
    expect(sameImportRequest(node, 'c:/media/shot.mp4')).toBe(true);
    expect(sameImportRequest(node, 'workspace/assets/current.mp4')).toBe(true);
    expect(importedAssetPatch(node, imported, 'C:\\Media\\shot.mp4')).toBeUndefined();
  });

  it('allows a newly edited import path before recording it as the last source', () => {
    const node = data({ import_path: 'C:\\Media\\new.mp4', import_source_path: 'C:\\Media\\old.mp4', asset: imported });
    expect(sameImportRequest(node, 'C:\\Media\\new.mp4')).toBe(false);
    const patch = importedAssetPatch(node, { path: 'workspace/assets/new.mp4', kind: 'video', name: 'new.mp4' }, 'C:\\Media\\new.mp4');
    expect(patch?.import_source_path).toBe('C:\\Media\\new.mp4');
  });

  it('archives old provenance and clears it from a replacement asset', () => {
    const node = data({
      asset: imported,
      generation_snapshot: { provider: 'comfy', prompt: '原提示词' },
      source_run_id: 'run-internal',
      snapshot_provenance: { source: 'import' },
      source_path: 'old.mp4',
      prompt_source_path: 'old-prompt.md',
      prompt_provenance: 'old-prompt.md',
      import_source_path: 'C:\\Media\\old.mp4',
    });
    const next = { path: 'workspace/assets/new.mp4', kind: 'video', name: 'new.mp4' };
    const patch = importedAssetPatch(node, next, 'C:\\Media\\new.mp4');
    expect(patch?.import_path).toBe('C:\\Media\\new.mp4');
    expect(patch?.generation_snapshot).toBeUndefined();
    expect(patch?.source_run_id).toBeUndefined();
    expect(patch?.snapshot_provenance).toBeUndefined();
    expect(patch?.source_path).toBeUndefined();
    expect(patch?.prompt_source_path).toBeUndefined();
    expect(patch?.import_source_path).toBe('C:\\Media\\new.mp4');
    const history = patch?.history as HistoryEntry[];
    expect(history).toHaveLength(1);
    expect(history[0].generation_snapshot?.prompt).toBe('原提示词');
    expect(history[0].source_run_id).toBe('run-internal');
    expect(history[0].prompt_source_path).toBe('old-prompt.md');
    expect(history[0].prompt_provenance).toBe('old-prompt.md');
    expect(history[0].import_source_path).toBe('C:\\Media\\old.mp4');
  });
});
