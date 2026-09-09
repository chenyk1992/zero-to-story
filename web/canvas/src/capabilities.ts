import type { CanvasNodeType, Capability } from './types';

/**
 * A capability is selectable when the browser can either run it itself or
 * hand it to an installed agent.  An unavailable script has no safe handoff
 * path, so it remains visible for explanation but cannot be selected.
 */
export function isCapabilitySelectable(capability: Capability, nodeType: CanvasNodeType): boolean {
  if (!capability.node_types.includes(nodeType)) return false;
  if (capability.execution === 'script') return capability.available;
  if (capability.execution === 'agent') return capability.available || Boolean(capability.installed);
  return false;
}

/**
 * New nodes only inherit a provider when exactly one capability is actually
 * available in this browser.  Agent handoff candidates still require an
 * explicit user choice because the current session cannot execute them.
 */
export function autoCapabilityForNode(capabilities: Capability[], nodeType: CanvasNodeType): Capability | undefined {
  const candidates = capabilities.filter((capability) => (
    capability.node_types.includes(nodeType)
    && capability.available
    && capability.execution !== 'unavailable'
  ));
  return candidates.length === 1 ? candidates[0] : undefined;
}

export function capabilityLabel(capability: Capability): string {
  if (capability.execution === 'agent' && !capability.available && capability.installed) {
    return `${capability.label}（需 Agent 接手）`;
  }
  if (capability.execution === 'unavailable'
    || (capability.execution === 'script' && !capability.available)
    || (capability.execution === 'agent' && !capability.available && !capability.installed)) {
    return `${capability.label}（不可用）`;
  }
  return capability.label;
}

export function hasExecutableSelection(
  provider: string,
  model: string,
  mode: string,
  nodeType: CanvasNodeType,
  capabilities: Capability[],
): boolean {
  if (!provider) return false;
  // If capability discovery is unavailable, preserve the existing explicit
  // selection and let the service perform its authoritative validation.
  if (!capabilities.length) return true;
  const capability = capabilities.find((item) => item.id === provider && item.node_types.includes(nodeType));
  if (!capability || !isCapabilitySelectable(capability, nodeType)) return false;
  if (capability.models.length > 0 && !model) return false;
  if (capability.modes.length > 0 && !mode) return false;
  return true;
}
