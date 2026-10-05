import { describe, expect, it } from 'vitest';
import { cardDescription, plainCardText } from './cardPresentation';

describe('card content presentation', () => {
  it('prefers the creative note over a provider prompt without changing either', () => {
    const data = { description: '雨停之后，她走向车站。', prompt: 'subject_definitions:\nPerson A\nsummary:\nA station.' };
    expect(cardDescription(data)).toBe('雨停之后，她走向车站。');
    expect(data.prompt).toContain('subject_definitions:');
  });
  it('extracts the explicit summary from structured prompts, never subject setup', () => {
    expect(cardDescription({ prompt: 'subject_definitions:\nA woman.\n\nsummary:\nShe arrives at the station.\n\nretention_analysis:\nKeep her coat.\n\ndetailed_description:\n[Shot 1] ...' })).toBe('She arrives at the station.');
    expect(cardDescription({ prompt: 'subject_definitions:\nA woman.\ndetailed_description:\nTechnical setup.' })).toBe('');
    expect(cardDescription({ prompt: 'summary:\nShe arrives.\nShe opens the letter.\n\ndetailed_description:\nCamera setup.' })).toBe('She arrives. She opens the letter.');
  });
  it('cleans display markdown while preserving its readable words', () => {
    expect(plainCardText('# 场景一\n\n1. **雨后**，走到[车站](https://example.com)。\n---\n> 等待列车')).toBe('场景一 雨后，走到车站。 等待列车');
    expect(plainCardText('```text\n拍摄说明\n```\n| 镜头 | 动作 |\n| --- | --- |\n| P01 | 回头 |')).toBe('拍摄说明 镜头 动作 P01 回头');
  });
  it('keeps plain dialogue, heading-only notes and empty drafts honest', () => {
    expect(cardDescription({ prompt: '大家好，我叫陈先森。' })).toBe('大家好，我叫陈先森。');
    expect(cardDescription({ content: '## 只有标题' })).toBe('只有标题');
    expect(cardDescription({ description: ' ', prompt: '' })).toBe('');
  });
});
