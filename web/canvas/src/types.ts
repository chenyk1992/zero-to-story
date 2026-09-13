import type { Edge, Node, Viewport, XYPosition } from '@xyflow/react';

export const NODE_KINDS = ['asset', 'image', 'video'] as const;
export type CanvasNodeType = (typeof NODE_KINDS)[number];

export type RunStatus = 'queued' | 'pending_agent' | 'running' | 'succeeded' | 'failed' | 'unknown' | 'cancelled';

export interface AssetRef {
  path: string;
  kind: string;
  name: string;
  sha256?: string;
}

export interface GenerationSnapshot {
  provider?: string;
  model?: string;
  mode?: string;
  prompt?: string;
  parameters?: Record<string, unknown>;
  inputs?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface HistoryEntry {
  id: string;
  label: string;
  asset: AssetRef;
  generation_snapshot?: GenerationSnapshot;
  status?: string;
  source_path?: string;
  [key: string]: unknown;
}

export interface DerivedOutput {
  id: string;
  label: string;
  asset: AssetRef;
  source_version?: string | number;
  [key: string]: unknown;
}

export interface CanvasNodeData extends Record<string, unknown> {
  nodeType: CanvasNodeType;
  label: string;
  prompt: string;
  duration?: number;
  aspect_ratio?: string;
  megapixels?: number;
  provider: string;
  model: string;
  mode: string;
  options: Record<string, Record<string, string | number | boolean | undefined>>;
  asset?: AssetRef;
  import_path?: string;
  import_source_path?: string;
  content?: string;
  description?: string;
  source_path?: string;
  story_source_path?: string;
  generation_snapshot?: GenerationSnapshot;
  history?: HistoryEntry[];
  derived_outputs?: DerivedOutput[];
  runStatus?: RunStatus;
  runError?: string;
  resultChanged?: boolean;
  latestPreview?: PreviewInfo;
  latestSuccessfulRun?: Run;
  runHistory?: Run[];
  onPreview?: (output?: RunOutput) => void;
}

export type FlowNode = Node<CanvasNodeData, 'canvas'>;

export interface ApiNode {
  id: string;
  type: CanvasNodeType;
  position: XYPosition;
  data: Partial<CanvasNodeData> & { label?: string };
}

export interface ApiEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string;
  targetHandle?: string;
  source_run_id?: string;
  require_accept?: boolean;
}

export interface CanvasGraph {
  nodes: ApiNode[];
  edges: ApiEdge[];
  viewport: Viewport;
  selection: string[];
}

export interface Canvas {
  id: string;
  name: string;
  version: number;
  graph: CanvasGraph;
  created_at?: string;
  updated_at?: string;
}

export interface CapabilityOption {
  value: string;
  label: string;
}

export interface CapabilityChoice {
  id: string;
  label: string;
}

export interface CapabilityField {
  key: string;
  label: string;
  type: 'number' | 'select' | 'text' | 'boolean';
  group: 'specs' | 'advanced';
  options?: CapabilityOption[];
  min?: number;
  max?: number;
  integer?: boolean;
  values?: (string | number)[];
  modes?: string[];
  default?: string | number | boolean;
  required?: boolean;
}

export interface Capability {
  id: string;
  label: string;
  node_types: CanvasNodeType[];
  execution: 'script' | 'agent' | 'unavailable';
  available: boolean;
  installed?: boolean;
  reason?: string;
  models: CapabilityChoice[];
  modes: CapabilityChoice[];
  fields: CapabilityField[];
}

export interface RunOutput {
  path: string;
  kind: string;
  name?: string;
}

export interface PreviewInfo {
  runId: string;
  output: RunOutput;
}

export interface Run {
  id: string;
  node_id: string;
  status: RunStatus;
  snapshot: {
    node_id: string;
    node_type: CanvasNodeType;
    provider: string;
    model: string;
    mode: string;
    prompt: string;
    parameters: Record<string, unknown>;
    inputs: Record<string, unknown>;
  };
  outputs: RunOutput[];
  matches_current?: boolean;
  error?: string;
  created_at?: string;
  stage?: string;
  attention_state?: 'active' | 'paused' | 'abandoned' | string;
  attention_reason?: string | null;
  attention_updated_at?: string;
  review?: { decision: 'ACCEPT' | 'REJECT' | 'INCONCLUSIVE'; evidence: string[]; end_state: Record<string, unknown>; unverified: string[] } | null;
}

export type ContinuationPlanState = 'active' | 'paused';
export type ContinuationSummaryStatus = 'actionable' | 'waiting' | 'blocked' | 'complete' | 'paused';

export interface ContinuationAction {
  kind?: string;
  node_id?: string;
  unit_id?: string;
  reason: string;
}

export interface ContinuationBlockedItem {
  node_id?: string;
  unit_id?: string;
  reason: string;
}

export interface ContinuationNodeSummary {
  node_id: string;
  state: 'actionable' | 'waiting' | 'blocked' | 'complete' | string;
  reason?: string;
  run_status?: string;
  [key: string]: unknown;
}

export interface ContinuationPlanSummary {
  status: ContinuationSummaryStatus;
  actions: ContinuationAction[];
  blocked_items: ContinuationBlockedItem[];
  nodes: ContinuationNodeSummary[];
  allow_stop: boolean;
  reason: string;
  stalled?: boolean;
  stop_attempts?: number;
}

/** Public, read-only shape consumed by the canvas status widget. */
export interface ContinuationPlan {
  id: string;
  canvas_id: string;
  session_id?: string;
  node_ids: string[];
  state: ContinuationPlanState;
  revision: number;
  summary: ContinuationPlanSummary;
  updated_at?: string;
  [key: string]: unknown;
}

export interface ContinuationsResponse {
  plans: ContinuationPlan[];
}
