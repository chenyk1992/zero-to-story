import type { SVGProps } from 'react';

/** Small, stroke based icons shared by the canvas chrome and node cards. */
export type IconName =
  | 'image'
  | 'video'
  | 'document'
  | 'section'
  | 'asset'
  | 'character'
  | 'storyboard'
  | 'board'
  | 'grid'
  | 'search'
  | 'plus'
  | 'close'
  | 'chevronLeft'
  | 'chevronRight'
  | 'chevronDown'
  | 'chevronUp'
  | 'panelLeft'
  | 'panelRight'
  | 'settings'
  | 'check'
  | 'alert'
  | 'play'
  | 'pause'
  | 'expand'
  | 'fit'
  | 'zoomIn'
  | 'zoomOut'
  | 'history'
  | 'layers'
  | 'link'
  | 'arrowUpRight'
  | 'upload'
  | 'trash'
  | 'audio'
  | 'film'
  | 'info';

export interface IconProps extends Omit<SVGProps<SVGSVGElement>, 'name' | 'title'> {
  name: IconName;
  size?: number | string;
  title?: string;
}

const PATHS: Record<IconName, string[]> = {
  image: [
    'M4 4.5A1.5 1.5 0 0 1 5.5 3h13A1.5 1.5 0 0 1 20 4.5v15a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 19.5v-15Z',
    'm5 17 4.2-4.2a1.2 1.2 0 0 1 1.7 0l2.3 2.3 1.6-1.6a1.2 1.2 0 0 1 1.7 0L19 16.2',
    'M8.2 8.2h.01',
  ],
  video: [
    'M4 6.5A1.5 1.5 0 0 1 5.5 5h8A1.5 1.5 0 0 1 15 6.5v11a1.5 1.5 0 0 1-1.5 1.5h-8A1.5 1.5 0 0 1 4 17.5v-11Z',
    'm15 9 4.2-2.1a.55.55 0 0 1 .8.5v9.2a.55.55 0 0 1-.8.5L15 15',
  ],
  document: [
    'M6 3.5h8l4 4v13H6a1 1 0 0 1-1-1v-15a1 1 0 0 1 1-1Z',
    'M14 3.5v4h4',
    'M8 12h8M8 15.5h6',
  ],
  section: [
    'M4 6.5A1.5 1.5 0 0 1 5.5 5h5l1.6 1.8H18.5A1.5 1.5 0 0 1 20 8.3v9.2a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 17.5v-11Z',
    'M4 9h16',
  ],
  asset: [
    'M12 3.5 20 8v8l-8 4.5L4 16V8l8-4.5Z',
    'M4 8 12 12.5 20 8M12 12.5V20.5',
  ],
  character: [
    'M12 12a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z',
    'M5 20a7 7 0 0 1 14 0',
  ],
  storyboard: [
    'M4 5.5A1.5 1.5 0 0 1 5.5 4h13A1.5 1.5 0 0 1 20 5.5v13a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 18.5v-13Z',
    'M4 10h16M10 4v16',
  ],
  board: [
    'M4 4.5A1.5 1.5 0 0 1 5.5 3h13A1.5 1.5 0 0 1 20 4.5v15a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 19.5v-15Z',
    'm7 16 3.4-3.4 2.3 2.3 2.8-3.5 1.5 1.7',
  ],
  grid: [
    'M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z',
  ],
  search: [
    'm20 20-4.4-4.4',
    'M10.8 17.2a6.4 6.4 0 1 0 0-12.8 6.4 6.4 0 0 0 0 12.8Z',
  ],
  plus: ['M12 5v14M5 12h14'],
  close: ['m6 6 12 12M18 6 6 18'],
  chevronLeft: ['m14.5 5-7 7 7 7'],
  chevronRight: ['m9.5 5 7 7-7 7'],
  chevronDown: ['m5 9.5 7 7 7-7'],
  chevronUp: ['m5 14.5 7-7 7 7'],
  panelLeft: [
    'M5 4h14a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1Z',
    'M9 4v16',
  ],
  panelRight: [
    'M5 4h14a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1Z',
    'M15 4v16',
  ],
  settings: [
    'M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z',
    'm19.4 15 .1.1a1.8 1.8 0 0 1-2.5 2.5l-.1-.1a1.8 1.8 0 0 0-3.1 1.3v.2a1.8 1.8 0 0 1-3.6 0v-.2a1.8 1.8 0 0 0-3.1-1.3l-.1.1a1.8 1.8 0 0 1-2.5-2.5l.1-.1a1.8 1.8 0 0 0-1.3-3.1h-.2a1.8 1.8 0 0 1 0-3.6h.2A1.8 1.8 0 0 0 4.6 5l-.1-.1A1.8 1.8 0 0 1 7 2.4l.1.1a1.8 1.8 0 0 0 3.1-1.3V1a1.8 1.8 0 0 1 3.6 0v.2a1.8 1.8 0 0 0 3.1 1.3l.1-.1a1.8 1.8 0 0 1 2.5 2.5l-.1.1a1.8 1.8 0 0 0 1.3 3.1h.2a1.8 1.8 0 0 1 0 3.6h-.2a1.8 1.8 0 0 0-1.3 3.1Z',
  ],
  check: ['m5 12.5 4.2 4.2L19 7'],
  alert: [
    'M10.3 4.1 3.8 17a1.7 1.7 0 0 0 1.5 2.5h13.4a1.7 1.7 0 0 0 1.5-2.5L13.7 4.1a1.9 1.9 0 0 0-3.4 0Z',
    'M12 9v4.2M12 16.4h.01',
  ],
  play: ['m8 5 11 7-11 7V5Z'],
  pause: ['M8 5v14M16 5v14'],
  expand: ['M8 4H4v4M16 4h4v4M20 16v4h-4M4 16v4h4'],
  fit: ['M8 4H5a1 1 0 0 0-1 1v3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3'],
  zoomIn: ['M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14Z', 'M20 20l-4-4', 'M11 8v6M8 11h6'],
  zoomOut: ['M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14Z', 'M20 20l-4-4', 'M8 11h6'],
  history: ['M4 12a8 8 0 1 0 2.3-5.6', 'M4 5v5h5', 'M12 7v5l3 2'],
  layers: ['m12 3 8 4.5-8 4.5-8-4.5L12 3Z', 'm4 12 8 4.5 8-4.5', 'm4 16.5 8 4.5 8-4.5'],
  link: ['M9.5 14.5 14.5 9.5', 'M7.2 17.8H6a4 4 0 0 1 0-8h3', 'M16.8 6.2H18a4 4 0 0 1 0 8h-3'],
  arrowUpRight: ['M6 18 18 6M9 6h9v9'],
  upload: ['M12 15V4', 'm8 8 4-4 4 4', 'M5 14v4a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-4'],
  trash: ['M5 7h14M10 11v6M14 11v6', 'm9 7 .7-2.2A1.2 1.2 0 0 1 10.8 4h2.4a1.2 1.2 0 0 1 1.1.8L15 7', 'm7 7 .7 13h8.6L17 7'],
  audio: ['M8 18V6a1 1 0 0 1 1.4-.9L18 8.7v7.6l-8.6 3.6A1 1 0 0 1 8 19V18Z', 'M5 11v2M3 10v4'],
  film: ['M4 5.5A1.5 1.5 0 0 1 5.5 4h13A1.5 1.5 0 0 1 20 5.5v13a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 18.5v-13Z', 'M8 4v16M16 4v16M4 9h4M16 9h4M4 15h4M16 15h4'],
  info: ['M12 10v6M12 7.2h.01', 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z'],
};

export function Icon({ name, size = 18, strokeWidth = 1.7, title, 'aria-hidden': ariaHidden, ...props }: IconProps) {
  const labelled = Boolean(props['aria-label'] || title);
  return (
    <svg
      {...props}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden={ariaHidden ?? !labelled}
      focusable="false"
      data-icon={name}
    >
      {title && <title>{title}</title>}
      {PATHS[name].map((path, index) => <path key={`${name}-${index}`} d={path} />)}
    </svg>
  );
}
