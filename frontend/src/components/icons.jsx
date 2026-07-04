// One consistent stroke-based icon set (1.6px, 24×24, currentColor) so the whole
// cockpit shares a single visual language instead of mismatched emoji glyphs.
const PATHS = {
  dashboard: <><rect x="3" y="3" width="7" height="9" rx="1.5" /><rect x="14" y="3" width="7" height="5" rx="1.5" /><rect x="14" y="12" width="7" height="9" rx="1.5" /><rect x="3" y="16" width="7" height="5" rx="1.5" /></>,
  holdings: <><rect x="3" y="6" width="18" height="13" rx="2" /><path d="M3 10h18" /><path d="M16 14h2" /></>,
  portfolios: <><path d="M12 3 3 8l9 5 9-5-9-5Z" /><path d="M3 13l9 5 9-5" /><path d="M3 8v5" /><path d="M21 8v5" /></>,
  allocation: <><path d="M12 3a9 9 0 1 0 9 9" /><path d="M12 3v9h9" /></>,
  hedge: <><path d="M12 3 5 6v5c0 4.5 3 7.5 7 9 4-1.5 7-4.5 7-9V6l-7-3Z" /><path d="m9 11 2 2 4-4" /></>,
  options: <><path d="M4 18 10 11l3.5 3.5L20 6" /><path d="M15 6h5v5" /></>,
  basket: <><path d="M4 8h16l-1.5 10.5A2 2 0 0 1 16.5 20h-9a2 2 0 0 1-2-1.5L4 8Z" /><path d="M8.5 8 12 3l3.5 5" /><path d="M9 12v4M15 12v4" /></>,
  risk: <><path d="M3 12h4l2.5 6L14 5l2.5 7H21" /></>,
  journal: <><path d="M5 4h11a2 2 0 0 1 2 2v14l-4-2-4 2-4-2V6a2 2 0 0 1 2-2Z" /><path d="M9 8h6M9 12h4" /></>,
  arrow: <path d="M5 12h14M13 6l6 6-6 6" />,
  arrowLeft: <path d="M19 12H5M11 18l-6-6 6-6" />,
  check: <path d="m5 13 4 4L19 7" />,
  close: <path d="M6 6l12 12M18 6 6 18" />,
  chevronDown: <path d="m6 9 6 6 6-6" />,
  spark: <path d="M12 3v4M12 17v4M3 12h4M17 12h4M6.3 6.3l2.4 2.4M15.3 15.3l2.4 2.4M17.7 6.3l-2.4 2.4M8.7 15.3l-2.4 2.4" />,
  book: <><path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2V5Z" /><path d="M4 19a2 2 0 0 0 2 2h13" /></>,
  play: <path d="M8 5v14l11-7-11-7Z" />,
  help: <><circle cx="12" cy="12" r="9" /><path d="M9.5 9.5a2.5 2.5 0 0 1 4.5 1.5c0 1.5-2 2-2 3.5" /><path d="M12 17.5h.01" /></>,
  sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M19.1 4.9l-1.4 1.4M6.3 17.7l-1.4 1.4" /></>,
  moon: <path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8Z" />,
  menu: <path d="M4 6h16M4 12h16M4 18h16" />,
  logout: <><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><path d="M16 17l5-5-5-5" /><path d="M21 12H9" /></>,
  user: <><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></>,
};

export default function Icon({ name, size = 20, className = "", strokeWidth = 1.6 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      {PATHS[name] || null}
    </svg>
  );
}
