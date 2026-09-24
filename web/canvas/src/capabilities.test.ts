import { describe, expect, it } from 'vitest';
import { autoCapabilityForNode, capabilityLabel, hasExecutableSelection, isCapabilitySelectable } from './capabilities';
import type { Capability } from './types';

function makeCapability(overrides: Partial<Capability> = {}): Capability {
  return {
    id: 'provider-a',
    label: 'Provider A',
    node_types: ['image'],
    execution: 'script',
    available: true,
    installed: true,
    models: [{ id: 'model-a', label: 'Model A' }],
    modes: [{ id: 'create', label: '生成' }],
    fields: [],
    ...overrides,
  };
}

describe('canvas capability selection', () => {
  it('auto-selects only one capability that is actually available', () => {
    const available = makeCapability();
    const unavailableAgent = makeCapability({ id: 'agent-b', label: 'Agent B', execution: 'agent', available: false, installed: true });
    const unavailableScript = makeCapability({ id: 'script-c', label: 'Script C', available: false, installed: false });

    expect(autoCapabilityForNode([available, unavailableAgent, unavailableScript], 'image')).toEqual(available);
    expect(autoCapabilityForNode([available, makeCapability({ id: 'provider-b' })], 'image')).toBeUndefined();
  });

  it('keeps an installed unavailable agent selectable while blocking an unavailable script', () => {
    const agent = makeCapability({ id: 'agent-b', label: 'Agent B', execution: 'agent', available: false, installed: true });
    const script = makeCapability({ id: 'script-c', label: 'Script C', available: false, installed: false });

    expect(isCapabilitySelectable(agent, 'image')).toBe(true);
    expect(capabilityLabel(agent)).toContain('需 Agent 接手');
    expect(isCapabilitySelectable(script, 'image')).toBe(false);
    expect(capabilityLabel(script)).toContain('不可用');
  });

  it('requires a complete known selection before enabling a new execution', () => {
    const capability = makeCapability();
    expect(hasExecutableSelection('', 'model-a', 'create', 'image', [capability])).toBe(false);
    expect(hasExecutableSelection('provider-a', '', 'create', 'image', [capability])).toBe(false);
    expect(hasExecutableSelection('provider-a', 'model-a', 'create', 'image', [capability])).toBe(true);
    expect(hasExecutableSelection('legacy-provider', '', '', 'image', [])).toBe(true);
  });

  it('requires persisted values for custom required fields even when the capability advertises defaults', () => {
    const tts = makeCapability({
      id: 'comfy-qwen-tts',
      node_types: ['audio' as never],
      models: [{ id: 'qwen3-tts-1.7b-customvoice', label: 'Qwen3-TTS' }],
      modes: [{ id: 'tts', label: '语音合成' }],
      fields: [
        { key: 'speaker', label: '声音角色', type: 'select', group: 'specs', required: true, options: [{ value: 'Eric', label: 'Eric' }] },
        { key: 'language', label: '语言', type: 'select', group: 'specs', required: true, default: 'Chinese', options: [{ value: 'Chinese', label: '中文' }] },
      ],
    });

    expect(hasExecutableSelection('comfy-qwen-tts', 'qwen3-tts-1.7b-customvoice', 'tts', 'audio' as never, [tts])).toBe(false);
    expect(hasExecutableSelection('comfy-qwen-tts', 'qwen3-tts-1.7b-customvoice', 'tts', 'audio' as never, [tts], { speaker: 'Eric' })).toBe(false);
    expect(hasExecutableSelection('comfy-qwen-tts', 'qwen3-tts-1.7b-customvoice', 'tts', 'audio' as never, [tts], { speaker: 'Eric', language: 'Chinese' })).toBe(true);
  });
});
