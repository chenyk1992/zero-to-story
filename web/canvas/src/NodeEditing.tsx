import { createContext, useContext, type ReactNode } from 'react';
import type { StoryNodePatch } from './workspace';

export interface NodeEditingActions {
  updateNode: (id: string, patch: StoryNodePatch) => void;
  setComposing: (id: string, composing: boolean) => void;
  renderSettings: (id: string) => ReactNode;
  finishEditing?: (id: string) => void;
}

// UI callbacks never enter node.data or the serialized production graph.
const NodeEditingContext = createContext<NodeEditingActions | null>(null);
export const NodeEditingProvider = NodeEditingContext.Provider;
export const useNodeEditing = () => useContext(NodeEditingContext);
