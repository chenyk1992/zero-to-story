import type { Canvas, Capability, CanvasGraph, Run, AssetRef, ContinuationsResponse } from './types';

const API_BASE = (import.meta.env.VITE_API_BASE || '/api').replace(/\/$/, '');

export class ApiError extends Error {
  status: number;
  code?: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...(init?.method && init.method !== 'GET' ? { 'X-Canvas-Request': '1' } : {}),
      ...init?.headers,
    },
  });
  const text = await response.text();
  let payload: unknown = undefined;
  if (text) {
    try {
      payload = JSON.parse(text) as unknown;
    } catch {
      payload = text;
    }
  }
  if (!response.ok) {
    const record = payload && typeof payload === 'object' ? payload as { error?: { code?: string; message?: string } } : {};
    throw new ApiError(record.error?.message || `请求失败（${response.status}）`, response.status, record.error?.code);
  }
  return payload as T;
}

export function getCapabilities(): Promise<{ capabilities: Capability[] }> {
  return request('/capabilities');
}

export function getCanvases(): Promise<{ canvases: Canvas[] }> {
  return request('/canvases');
}

export function createCanvas(name: string): Promise<Canvas> {
  return request('/canvases', { method: 'POST', body: JSON.stringify({ name }) });
}

export function getCanvas(id: string): Promise<Canvas> {
  return request(`/canvases/${encodeURIComponent(id)}`);
}

export function updateCanvas(id: string, version: number, graph: CanvasGraph, name?: string): Promise<Canvas> {
  return request(`/canvases/${encodeURIComponent(id)}`, {
    method: 'PUT',
    body: JSON.stringify({ version, graph, ...(name === undefined ? {} : { name }) }),
  });
}

export function getRuns(id: string): Promise<{ runs: Run[] }> {
  return request(`/canvases/${encodeURIComponent(id)}/runs`);
}

export function getContinuations(id: string): Promise<ContinuationsResponse> {
  return request(`/continuations?canvas_id=${encodeURIComponent(id)}`);
}

export function executeNode(id: string, nodeId: string, version: number, requestId: string): Promise<Run> {
  return request(`/canvases/${encodeURIComponent(id)}/runs`, {
    method: 'POST',
    body: JSON.stringify({ node_id: nodeId, version, request_id: requestId }),
  });
}

export async function uploadAsset(file: File): Promise<AssetRef> {
  return request(`/assets?name=${encodeURIComponent(file.name)}`, {
    method: 'POST',
    body: file,
    headers: { 'Content-Type': 'application/octet-stream' },
  });
}

export function importAssetPath(path: string): Promise<AssetRef> {
  return request('/assets/import', { method: 'POST', body: JSON.stringify({ path }) });
}

export function mediaUrl(path: string): string {
  return `${API_BASE}/media?path=${encodeURIComponent(path)}`;
}

export function apiBase(): string {
  return API_BASE;
}
