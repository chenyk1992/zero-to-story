import type { AssetRef, HistoryEntry } from './types';
import type { StoryNodeData, StoryNodePatch } from './workspace';

/** Source fields describe the asset currently displayed by a media card. */
const IMPORT_SOURCE_FIELDS = ['source_run_id', 'snapshot_provenance', 'source_path', 'prompt_source_path', 'prompt_provenance', 'import_source_path'] as const;

function comparablePath(value?: string): string {
  return (value || '').trim().replace(/\\/g, '/').replace(/\/+/g, '/').replace(/\/$/, '').toLocaleLowerCase();
}

export function sameImportRequest(data: StoryNodeData, requestedPath: string): boolean {
  const requested = comparablePath(requestedPath);
  if (!requested) return false;
  return [data.import_source_path, data.asset?.path].some((value) => Boolean(value) && comparablePath(value) === requested);
}

export function sameImportedAsset(data: StoryNodeData, asset: AssetRef): boolean {
  const current = comparablePath(data.asset?.path);
  return Boolean(current && asset.path && current === comparablePath(asset.path));
}

function previousAssetEntry(data: StoryNodeData, asset: AssetRef): HistoryEntry {
  const provenance = Object.fromEntries(
    IMPORT_SOURCE_FIELDS
      .filter((key) => data[key] !== undefined)
      .map((key) => [key, data[key]]),
  );
  return {
    id: `import-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    label: asset.name || '导入前成品',
    asset,
    // The server requires every history item to carry a snapshot object. An
    // empty object means the imported file had no recorded generation data.
    generation_snapshot: data.generation_snapshot || {},
    status: '旧当前成品',
    ...provenance,
  };
}

/**
 * Build the one canonical patch used by file uploads and local-path imports.
 * A repeated import returns undefined so it cannot erase a provenance snapshot
 * or create a duplicate history item.
 */
export function importedAssetPatch(data: StoryNodeData, asset: AssetRef, requestedPath?: string): StoryNodePatch | undefined {
  if (sameImportedAsset(data, asset)) return undefined;
  const previous = data.asset?.path ? previousAssetEntry(data, data.asset) : undefined;
  const history = previous ? [previous, ...(data.history || [])] : data.history;
  const patch: StoryNodePatch = {
    asset,
    import_path: requestedPath || asset.path,
    generation_snapshot: undefined,
    history,
  };
  for (const key of IMPORT_SOURCE_FIELDS) patch[key] = undefined;
  patch.import_source_path = requestedPath;
  return patch;
}
