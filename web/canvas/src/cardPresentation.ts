import type { StoryNodeData } from './workspace';

/** Display-only text cleanup; the stored document and generation prompt stay intact. */
export function plainCardText(value: string): string {
  return value
    .split(/\r?\n/)
    .filter((line) => !/^\s*(```|~~~)/.test(line) && !/^\s*[-_*]{3,}\s*$/.test(line) && !/^\s*\|?[\s:|-]+\|\s*$/.test(line))
    .map((line) => line.replace(/^\s{0,3}#{1,6}\s+/, '').replace(/^\s*>\s?/, '').replace(/^\s*(?:[-*+] |\d+[.)] )/, '').replace(/^\s*\|\s*|\s*\|\s*$/g, '').replace(/\s+\|\s+/g, ' '))
    .join(' ')
    .replace(/!?\[([^\]]+)\]\([^\n)]*\)/g, '$1')
    .replace(/\*\*(.+?)\*\*|__(.+?)__|`([^`]+)`/g, (_, bold, emphasis, code) => bold || emphasis || code)
    .replace(/\s+/g, ' ')
    .trim();
}

/** Prefer explicit creative notes; structured provider setup is not a story synopsis. */
export function cardDescription(data: Partial<StoryNodeData>): string {
  const note = data.description?.trim() || data.content?.trim();
  if (note) return plainCardText(note);
  const prompt = data.prompt?.trim() || '';
  const summary = prompt.match(/^summary:\s*([\s\S]*?)(?=^(?:subject_definitions|retention_analysis|detailed_description|overall_soundscape|non_diegetic_music):|(?![\s\S]))/im)?.[1];
  if (summary) return plainCardText(summary);
  if (/^(?:subject_definitions|retention_analysis|detailed_description|overall_soundscape|non_diegetic_music):/im.test(prompt)) return '';
  return plainCardText(prompt);
}
