// RiskWise logo — a shield of protection over a managed-risk trendline (dips once,
// then recovers) + the RISK·WISE wordmark. Rebuilt from the brand SVGs as components
// so they scale crisply, theme with the app, and can animate on the splash screen.
import { useId } from "react";

// The shield mark on its own. `animated` draws the trendline on mount.
export function LogoMark({ size = 40, animated = false, className = "" }) {
  const id = useId().replace(/:/g, "");
  const gold = `g-${id}`;
  const navy = `n-${id}`;
  return (
    <svg
      width={size}
      height={size * (216 / 188)}
      viewBox="8 -6 188 216"
      fill="none"
      className={className}
      role="img"
      aria-label="RiskWise"
    >
      <defs>
        <linearGradient id={gold} x1="0" y1="1" x2="1" y2="0">
          <stop offset="0" stopColor="#C9A544" />
          <stop offset="1" stopColor="#F0D683" />
        </linearGradient>
        <linearGradient id={navy} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#123456" />
          <stop offset="1" stopColor="#0A1F38" />
        </linearGradient>
      </defs>
      {/* shield body */}
      <path
        d="M102 4 L184 32 V104 C184 156 150 190 102 204 C54 190 20 156 20 104 V32 Z"
        fill={`url(#${navy})`}
        stroke="#E6C86E"
        strokeOpacity="0.28"
        strokeWidth="2"
      />
      {/* inner keyline for a crafted feel */}
      <path
        d="M102 22 L168 45 V104 C168 146 141 174 102 186 C63 174 36 146 36 104 V45 Z"
        fill="none"
        stroke="#E6C86E"
        strokeOpacity="0.22"
        strokeWidth="2"
      />
      {/* trendline: risk down, then managed recovery */}
      <path
        d="M52 138 L86 104 L106 122 L146 74"
        fill="none"
        stroke={`url(#${gold})`}
        strokeWidth="12"
        strokeLinecap="round"
        strokeLinejoin="round"
        className={animated ? "rw-draw" : ""}
        style={animated ? { "--len": 150 } : undefined}
      />
      {/* arrowhead */}
      <path
        d="M132 66 L152 62 L150 84 Z"
        fill="#F0D683"
        stroke={`url(#${gold})`}
        strokeWidth="4"
        strokeLinejoin="round"
      />
      {/* recovery node */}
      <circle cx="86" cy="104" r="7" fill="#0A1F38" stroke="#F0D683" strokeWidth="4" />
    </svg>
  );
}

// RISK·WISE wordmark. `size` controls the font-size (px).
export function Wordmark({ size = 22, className = "" }) {
  return (
    <span
      className={`font-display font-bold leading-none tracking-tight ${className}`}
      style={{ fontSize: size }}
    >
      <span className="text-headline">RISK</span>
      <span className="text-gold">WISE</span>
    </span>
  );
}

// Mark + wordmark lock-up, used in the sidebar / top bar.
export function Logo({ markSize = 30, wordSize = 20, animated = false, className = "" }) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <LogoMark size={markSize} animated={animated} />
      <Wordmark size={wordSize} />
    </span>
  );
}
