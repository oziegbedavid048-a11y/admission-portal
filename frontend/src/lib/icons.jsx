import { Children, Fragment, cloneElement, isValidElement } from 'react';

// One drawn icon set for the whole product.
//
// Every icon is a stroked 24x24 SVG on the same grid at the same weight, so a
// row of them lines up without nudging. There are no emoji and no characters
// pressed into service as icons: an arrow, a tick and a cross are all drawn
// here too.

const BASE = {
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.8,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  'aria-hidden': 'true',
};

export const PATHS = {
  grid: (
    <>
      <rect x="3" y="3" width="7.5" height="7.5" rx="2" />
      <rect x="13.5" y="3" width="7.5" height="7.5" rx="2" />
      <rect x="3" y="13.5" width="7.5" height="7.5" rx="2" />
      <rect x="13.5" y="13.5" width="7.5" height="7.5" rx="2" />
    </>
  ),
  dashboard: (
    <>
      <rect x="3" y="3" width="7" height="9" rx="1.5" />
      <rect x="14" y="3" width="7" height="5" rx="1.5" />
      <rect x="14" y="12" width="7" height="9" rx="1.5" />
      <rect x="3" y="16" width="7" height="5" rx="1.5" />
    </>
  ),
  layoutDashboard: (
    <>
      <rect x="3" y="3" width="7" height="9" rx="1.5" />
      <rect x="14" y="3" width="7" height="5" rx="1.5" />
      <rect x="14" y="12" width="7" height="9" rx="1.5" />
      <rect x="3" y="16" width="7" height="5" rx="1.5" />
    </>
  ),
  cap: (
    <>
      <path d="M22 10 12 5 2 10l10 5 10-5Z" />
      <path d="M6 12.5V17c0 2.8 6 3.8 6 3.8s6-1 6-3.8v-4.5" />
      <path d="M22 10v6" />
    </>
  ),
  // Ads funding: a screen with a rising line, money put into advertising.
  adsFunding: (
    <>
      <rect x="3" y="4" width="18" height="12" rx="2" />
      <path d="M8 20h8" />
      <path d="M12 16v4" />
      <path d="M7 12.5l3-3 2.5 2.5L17 7.5" />
      <path d="M14.5 7.5H17V10" />
    </>
  ),
  adsLoan: (
    <>
      <path d="M3 11v3a1 1 0 0 0 1 1h2l4 3V6L6 9H4a1 1 0 0 0-1 1v1Z" />
      <path d="M13 8.5a4.5 4.5 0 0 1 0 7" />
      <circle cx="18" cy="12" r="3.5" />
      <path d="M18 10.2v3.6" />
      <path d="M16.5 12h3" />
    </>
  ),
  mail: (
    <>
      <rect x="2.5" y="4.5" width="19" height="15" rx="2" />
      <path d="m2.5 6 9.5 6.5 9.5-6.5" />
    </>
  ),
  envelope: (
    <>
      <rect x="2.5" y="4.5" width="19" height="15" rx="2" />
      <path d="m2.5 6 9.5 6.5 9.5-6.5" />
    </>
  ),
  fileText: (
    <>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
      <line x1="10" y1="9" x2="8" y2="9" />
    </>
  ),
  file: (
    <>
      <path d="M14 2.5H6.5A2 2 0 0 0 4.5 4.5v15a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2.5 14 8 19.5 8" />
    </>
  ),
  user: (
    <>
      <path d="M19 20.5v-1.75a4.25 4.25 0 0 0-4.25-4.25h-5.5A4.25 4.25 0 0 0 5 18.75v1.75" />
      <circle cx="12" cy="7.5" r="4" />
    </>
  ),
  users: (
    <>
      <path d="M16 20v-1.5a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4V20" />
      <circle cx="9" cy="7" r="3.5" />
      <path d="M22 20v-1.5a4 4 0 0 0-3-3.87" />
      <path d="M16 3.63a4 4 0 0 1 0 7.75" />
    </>
  ),
  userPlus: (
    <>
      <path d="M15 20v-1.5a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4V20" />
      <circle cx="8.5" cy="7" r="3.5" />
      <path d="M19 8v6M22 11h-6" />
    </>
  ),
  wallet: (
    <>
      <path d="M3 8.5A2.5 2.5 0 0 1 5.5 6H19a2 2 0 0 1 2 2v9a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 17z" />
      <path d="M3 8.5V7a2 2 0 0 1 2-2h11" />
      <circle cx="17" cy="12.5" r="1.25" />
    </>
  ),
  tag: (
    <>
      <path d="m3 11 6.5-6.5a2 2 0 0 1 2.83 0l8.17 8.17a2 2 0 0 1 0 2.83L14 22" />
      <path d="M3 11v8a2 2 0 0 0 2 2h8" />
      <circle cx="8" cy="16" r="1.4" />
    </>
  ),
  megaphone: (
    <>
      <path d="M3 11v2a1 1 0 0 0 1 1h2l5 4V6L6 10H4a1 1 0 0 0-1 1z" />
      <path d="M15.5 9.5a3.5 3.5 0 0 1 0 5" />
      <path d="M18.5 7a7 7 0 0 1 0 10" />
    </>
  ),
  home: (
    <>
      <path d="m3 11 9-7 9 7" />
      <path d="M5 10v9a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-9" />
    </>
  ),
  signOut: (
    <>
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <polyline points="16 17 21 12 16 7" />
      <line x1="21" y1="12" x2="9" y2="12" />
    </>
  ),
  signIn: (
    <>
      <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" />
      <polyline points="10 17 15 12 10 7" />
      <line x1="15" y1="12" x2="3" y2="12" />
    </>
  ),
  menu: (
    <>
      <line x1="3" y1="12" x2="21" y2="12" />
      <line x1="3" y1="6" x2="21" y2="6" />
      <line x1="3" y1="18" x2="21" y2="18" />
    </>
  ),
  bell: (
    <>
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </>
  ),
  check: <polyline points="20 6 9 17 4 12" />,
  close: (
    <>
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </>
  ),
  arrowRight: (
    <>
      <line x1="5" y1="12" x2="19" y2="12" />
      <polyline points="12 5 19 12 12 19" />
    </>
  ),
  arrowLeft: (
    <>
      <line x1="19" y1="12" x2="5" y2="12" />
      <polyline points="12 19 5 12 12 5" />
    </>
  ),
  chevronLeft: <polyline points="15 5 8 12 15 19" />,
  chevronRight: <polyline points="9 5 16 12 9 19" />,
  chevronDown: <polyline points="6 9 12 15 18 9" />,
  info: (
    <>
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="16" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12.01" y2="8" />
    </>
  ),
  alert: (
    <>
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
    </>
  ),
  checkCircle: (
    <>
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
      <polyline points="22 4 12 14.01 9 11.01" />
    </>
  ),
  closeCircle: (
    <>
      <circle cx="12" cy="12" r="10" />
      <line x1="15" y1="9" x2="9" y2="15" />
      <line x1="9" y1="9" x2="15" y2="15" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="9.5" />
      <polyline points="12 6.5 12 12 15.5 14" />
    </>
  ),
  sunrise: (
    <>
      <path d="M12 2v4M4.93 10.93l2.83 2.83M19.07 10.93l-2.83 2.83M2 18h20M7 18a5 5 0 0 1 10 0" />
    </>
  ),
  sun: (
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" />
    </>
  ),
  moon: (
    <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" />
  ),
  pin: (
    <>
      <path d="M12 2a8 8 0 0 0-8 8c0 5.25 8 12 8 12s8-6.75 8-12a8 8 0 0 0-8-8z" />
      <circle cx="12" cy="10" r="3" />
    </>
  ),
  passport: (
    <>
      <rect x="4" y="2.5" width="16" height="19" rx="2.5" />
      <circle cx="12" cy="10" r="3" />
      <path d="M8.5 17.5h7" />
    </>
  ),
  calendar: (
    <>
      <rect x="3" y="4" width="18" height="18" rx="2" />
      <line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8" y1="2" x2="8" y2="6" />
      <line x1="3" y1="10" x2="21" y2="10" />
    </>
  ),
  document: (
    <>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
    </>
  ),
  resume: (
    <>
      <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
      <circle cx="8.5" cy="7" r="4" />
      <polyline points="17 11 19 13 23 9" />
    </>
  ),
  save: (
    <>
      <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
      <polyline points="17 21 17 13 7 13 7 21" />
      <polyline points="7 3 7 8 15 8" />
    </>
  ),
  card: (
    <>
      <rect x="2" y="5" width="20" height="14" rx="2.5" />
      <line x1="2" y1="10" x2="22" y2="10" />
    </>
  ),
  currency: <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />,
  // Two sheets, the front one offset: the shape people read as "copy".
  copy: (
    <>
      <rect x="9" y="9" width="11" height="11" rx="2" />
      <path d="M6 15H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v1" />
    </>
  ),
  // Money leaving the wallet, for a payout. Distinct from `download`, which is
  // a file coming to you.
  payout: (
    <>
      <path d="M3 9.5A2.5 2.5 0 0 1 5.5 7H18a2 2 0 0 1 2 2v7.5A2.5 2.5 0 0 1 17.5 19h-12A2.5 2.5 0 0 1 3 16.5z" />
      <path d="M16 13h2" />
      <path d="M12 2.5v5" />
      <polyline points="9.5 5 12 2.5 14.5 5" />
    </>
  ),
  download: (
    <>
      <path d="M12 3v12" />
      <polyline points="7 11 12 16 17 11" />
      <path d="M4 21h16" />
    </>
  ),
  upload: (
    <>
      <path d="M12 16V4" />
      <polyline points="7 9 12 4 17 9" />
      <path d="M4 21h16" />
    </>
  ),
  printer: (
    <>
      <polyline points="6 9 6 2 18 2 18 9" />
      <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" />
      <rect x="6" y="14" width="12" height="8" />
    </>
  ),
  search: (
    <>
      <circle cx="11" cy="11" r="7.5" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </>
  ),
  camera: (
    <>
      <path d="M3 8.5A2 2 0 0 1 5 6.5h2l1.4-2h7.2L17 6.5h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
      <circle cx="12" cy="12.5" r="3.4" />
    </>
  ),
  lock: (
    <>
      <rect x="4" y="10.5" width="16" height="10" rx="2.5" />
      <path d="M8 10.5V7a4 4 0 0 1 8 0v3.5" />
    </>
  ),
  pencil: (
    <>
      <path d="M11 4.5H5a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h13a2 2 0 0 0 2-2v-6" />
      <path d="M18.5 2.5a2.12 2.12 0 0 1 3 3L12 15l-4 1z" />
    </>
  ),
  chart: (
    <>
      <line x1="18" y1="20" x2="18" y2="10" />
      <line x1="12" y1="20" x2="12" y2="4" />
      <line x1="6" y1="20" x2="6" y2="14" />
    </>
  ),
  trend: (
    <>
      <polyline points="3 16.5 9 10.5 13 14.5 21 6.5" />
      <polyline points="15 6.5 21 6.5 21 12.5" />
    </>
  ),
  badgeCheck: (
    <>
      <path d="M12 2.5 14.4 5l3.4-.3.3 3.4L20.5 12l-2.4 3.9-.3 3.4-3.4-.3L12 21.5 9.6 19l-3.4.3-.3-3.4L3.5 12l2.4-3.9.3-3.4L9.6 5z" />
      <polyline points="9 12 11 14 15 10" />
    </>
  ),
  building: (
    <>
      <path d="M3 21h18M5 21V7l7-4 7 4v14" />
      <path d="M10 21v-6h4v6" />
      <path d="M9 10h.01M15 10h.01" />
    </>
  ),
  globe: (
    <>
      <circle cx="12" cy="12" r="9.5" />
      <path d="M2.5 12h19" />
      <path d="M12 2.5a15 15 0 0 1 0 19 15 15 0 0 1 0-19z" />
    </>
  ),
  shield: (
    <>
      <path d="M12 2.5 4.5 5.5v6c0 4.6 3.2 8.6 7.5 10 4.3-1.4 7.5-5.4 7.5-10v-6z" />
      <polyline points="9 12 11 14 15 10" />
    </>
  ),
  sunrise: (
    <>
      <path d="M12 3v4M5.6 9.6 8.4 12.4M2 17h4M18 17h4M15.6 12.4l2.8-2.8" />
      <path d="M8 17a4 4 0 0 1 8 0" />
      <line x1="2" y1="21" x2="22" y2="21" />
    </>
  ),
  sun: (
    <>
      <circle cx="12" cy="12" r="4.2" />
      <path d="M12 2.5v2.5M12 19v2.5M4.6 4.6l1.8 1.8M17.6 17.6l1.8 1.8M2.5 12H5M19 12h2.5M4.6 19.4l1.8-1.8M17.6 6.4l1.8-1.8" />
    </>
  ),
  moon: <path d="M20.5 14.5A8.5 8.5 0 1 1 9.5 3.5a6.8 6.8 0 0 0 11 11z" />,
  book: (
    <>
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
      <line x1="8" y1="7" x2="16" y2="7" />
      <line x1="8" y1="11" x2="14" y2="11" />
    </>
  ),
  medal: (
    <>
      <circle cx="12" cy="8" r="6" />
      <path d="M15.477 12.89 17 22l-5-3-5 3 1.523-9.11" />
    </>
  ),
  flask: (
    <>
      <path d="M10 2v7.31M14 2v7.31M8.5 2h7M14 9.3a6.5 6.5 0 1 1-4 0" />
      <circle cx="12" cy="15" r="1.5" />
    </>
  ),
  plane: (
    <path d="M17.8 19.8 16 14l4.3-4.3a2 2 0 0 0-2.8-2.8L13.2 11 7.4 9.2a1 1 0 0 0-1 .3L5 10.9l5.2 2.6-2.1 2.1-2.4-.4-1 1L7.5 18l1.6 2.8 1-1-.4-2.4 2.1-2.1 2.6 5.2 1.4-1.4a1 1 0 0 0 .3-1z" />
  ),
  // Support: a headset, the one shape everyone reads as "talk to a person".
  headset: (
    <>
      <path d="M4 14v-2a8 8 0 0 1 16 0v2" />
      <rect x="3" y="14" width="4" height="6" rx="1.5" />
      <rect x="17" y="14" width="4" height="6" rx="1.5" />
      <path d="M19 20a3 3 0 0 1-3 2h-3" />
    </>
  ),
  chat: (
    <>
      <path d="M21 12a8 8 0 0 1-11.6 7.1L4 20.5l1.4-4.6A8 8 0 1 1 21 12z" />
      <path d="M8.5 12h.01M12 12h.01M15.5 12h.01" />
    </>
  ),
  send: (
    <>
      <path d="M22 2 11 13" />
      <path d="M22 2 15 22l-4-9-9-4 20-7z" />
    </>
  ),
  paperclip: (
    <path d="m21 11.5-8.6 8.6a5.5 5.5 0 0 1-7.8-7.8l8.6-8.6a3.7 3.7 0 0 1 5.2 5.2l-8.6 8.6a1.8 1.8 0 0 1-2.6-2.6l8-8" />
  ),
  userCircle: (
    <>
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="10" r="3" />
      <path d="M6.2 18.4a6.5 6.5 0 0 1 11.6 0" />
    </>
  ),
};

/**
 * @param {{name: keyof typeof PATHS, size?: number, className?: string, strokeWidth?: number}} props
 */
/**
 * Give every shape the same nominal length so one animation can draw any icon.
 *
 * `pathLength="1"` rescales a shape's stroke units, so a long passport outline
 * and a short tick both run from dash-offset 1 to 0 over the same duration.
 * Without it each icon would draw at a different speed and a row of them would
 * finish raggedly.
 */
function normalise(node, keyPrefix = 'p') {
  return Children.map(node, (child, index) => {
    if (!isValidElement(child)) return child;
    if (child.type === Fragment) {
      return normalise(child.props.children, `${keyPrefix}-${index}`);
    }
    return cloneElement(child, { pathLength: 1, key: `${keyPrefix}-${index}` });
  });
}

/**
 * One drawn icon, on a 24px grid at a consistent stroke weight.
 *
 * `animate` draws the icon in when it mounts; `interactive` lets it respond to
 * a hover on whatever contains it. Both are CSS, both respect a reduced-motion
 * preference, and neither changes what the icon means.
 *
 * @param {object} props
 * @param {keyof typeof PATHS} props.name
 * @param {number} [props.size]
 * @param {boolean} [props.animate]   Draw the stroke in on mount.
 * @param {boolean} [props.interactive] React to hover on the parent control.
 */
export default function Icon({
  name,
  size = 18,
  className,
  strokeWidth,
  style,
  title,
  animate = false,
  interactive = true,
}) {
  const path = PATHS[name];
  if (!path) return null;

  const classes = [
    'icon',
    `icon-${name}`,
    animate ? 'icon-draw' : null,
    interactive ? 'icon-live' : null,
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <svg
      {...BASE}
      strokeWidth={strokeWidth || BASE.strokeWidth}
      width={size}
      height={size}
      className={classes}
      style={style}
      role={title ? 'img' : undefined}
      aria-hidden={title ? undefined : 'true'}
    >
      {title ? <title>{title}</title> : null}
      {animate ? normalise(path) : path}
    </svg>
  );
}
