// Inline SVG payoff diagram: profit zone green, loss zone red, breakeven + spot markers.
// Hover anywhere to read the exact P&L at that price (green profit / red loss).
// No chart library — keeps the bundle lean. Colors reference the theme tokens so the
// chart follows dark/light mode automatically.
import { useState } from "react";
import { inr } from "../api/client";

const UP = "var(--color-up)";
const DOWN = "var(--color-down)";
const GOLD = "var(--color-gold)";
const MUTED = "var(--color-muted)";
const BODY = "var(--color-body)";
const HAIR = "var(--color-hairline)";
const CARD = "var(--color-card)";

export default function PayoffChart({ curve, breakevens = [], spot, height = 300 }) {
  const [hover, setHover] = useState(null); // { x, spot, pnl }
  if (!curve || curve.length < 2) return null;

  const W = 640;
  const H = height;
  const padL = 64;
  const padR = 16;
  const padT = 16;
  const padB = 36;

  const xs = curve.map((p) => p.spot);
  const ys = curve.map((p) => p.pnl);
  const xMin = Math.min(...xs);
  const xMax = Math.max(...xs);
  let yMax = Math.max(...ys, 0);
  let yMin = Math.min(...ys, 0);
  const yPad = (yMax - yMin) * 0.08 || 1;
  yMax += yPad;
  yMin -= yPad;

  const sx = (v) => padL + ((v - xMin) / (xMax - xMin)) * (W - padL - padR);
  const sy = (v) => padT + ((yMax - v) / (yMax - yMin)) * (H - padT - padB);

  // P&L at any spot, linearly interpolated from the curve (sorted ascending by spot).
  const pnlAt = (s) => {
    if (s <= xs[0]) return ys[0];
    if (s >= xs[xs.length - 1]) return ys[ys.length - 1];
    for (let i = 1; i < xs.length; i++) {
      if (s <= xs[i]) {
        const t = (s - xs[i - 1]) / (xs[i] - xs[i - 1]);
        return ys[i - 1] + t * (ys[i] - ys[i - 1]);
      }
    }
    return ys[ys.length - 1];
  };

  function onMove(e) {
    const rect = e.currentTarget.getBoundingClientRect();
    if (!rect.width) return; // not laid out yet — avoid a NaN readout
    const px = ((e.clientX - rect.left) / rect.width) * W; // client -> viewBox x
    const clamped = Math.max(padL, Math.min(W - padR, px));
    const s = xMin + ((clamped - padL) / (W - padL - padR)) * (xMax - xMin);
    setHover({ x: clamped, spot: s, pnl: pnlAt(s) });
  }

  const zeroY = sy(0);
  const line = curve.map((p) => `${sx(p.spot)},${sy(p.pnl)}`).join(" ");
  // Area between the curve and the zero line (filled twice, clipped above/below zero).
  const area = `M ${sx(xs[0])},${zeroY} L ${line.replace(/ /g, " L ")} L ${sx(xs[xs.length - 1])},${zeroY} Z`;

  const id = `payoff-${Math.round(spot)}`;

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="w-full"
      role="img"
      aria-label="Payoff diagram"
      style={{ cursor: "crosshair" }}
      onMouseMove={onMove}
      onMouseLeave={() => setHover(null)}
    >
      <defs>
        <clipPath id={`${id}-above`}>
          <rect x="0" y="0" width={W} height={zeroY} />
        </clipPath>
        <clipPath id={`${id}-below`}>
          <rect x="0" y={zeroY} width={W} height={H - zeroY} />
        </clipPath>
      </defs>

      {/* profit (green) / loss (red) shaded zones */}
      <path d={area} fill={UP} opacity="0.16" clipPath={`url(#${id}-above)`} />
      <path d={area} fill={DOWN} opacity="0.16" clipPath={`url(#${id}-below)`} />

      {/* zero P&L line */}
      <line x1={padL} y1={zeroY} x2={W - padR} y2={zeroY} stroke={MUTED} strokeWidth="1" strokeDasharray="3 3" />

      {/* current spot marker */}
      {spot >= xMin && spot <= xMax && (
        <>
          <line x1={sx(spot)} y1={padT} x2={sx(spot)} y2={H - padB} stroke={MUTED} strokeWidth="1" opacity="0.5" />
          <text x={sx(spot)} y={padT + 10} fill={MUTED} fontSize="10" textAnchor="middle">
            spot {Math.round(spot)}
          </text>
        </>
      )}

      {/* breakeven markers on the zero line */}
      {breakevens.map((b, i) =>
        b >= xMin && b <= xMax ? (
          <g key={i}>
            <circle cx={sx(b)} cy={zeroY} r="3.5" fill={GOLD} />
            <text x={sx(b)} y={H - padB + 14} fill={GOLD} fontSize="10" textAnchor="middle">
              {Math.round(b)}
            </text>
          </g>
        ) : null,
      )}

      {/* payoff curve */}
      <polyline points={line} fill="none" stroke={BODY} strokeWidth="2" />

      {/* y-axis labels: max profit / 0 / max loss */}
      <text x={padL - 8} y={sy(yMax - yPad) + 4} fill={MUTED} fontSize="10" textAnchor="end">
        {inr(Math.max(...ys))}
      </text>
      <text x={padL - 8} y={zeroY + 4} fill={MUTED} fontSize="10" textAnchor="end">0</text>
      <text x={padL - 8} y={sy(yMin + yPad) + 4} fill={MUTED} fontSize="10" textAnchor="end">
        {inr(Math.min(...ys))}
      </text>

      {/* x-axis end labels */}
      <text x={padL} y={H - 8} fill={MUTED} fontSize="10" textAnchor="start">{Math.round(xMin)}</text>
      <text x={W - padR} y={H - 8} fill={MUTED} fontSize="10" textAnchor="end">{Math.round(xMax)}</text>

      {/* hover crosshair + P&L tooltip */}
      {hover && (
        <g pointerEvents="none">
          <line x1={hover.x} y1={padT} x2={hover.x} y2={H - padB} stroke={GOLD} strokeWidth="1" opacity="0.55" />
          <circle cx={hover.x} cy={sy(hover.pnl)} r="4" fill={hover.pnl >= 0 ? UP : DOWN} stroke={CARD} strokeWidth="1.5" />
          {(() => {
            const tw = 140, th = 40;
            const tx = hover.x + 10 + tw > W - padR ? hover.x - 10 - tw : hover.x + 10;
            return (
              <g transform={`translate(${tx}, ${padT + 4})`}>
                <rect width={tw} height={th} rx="6" fill={CARD} stroke={HAIR} />
                <text x="9" y="16" fill={MUTED} fontSize="10">Price {Math.round(hover.spot)}</text>
                <text x="9" y="31" fill={Math.abs(hover.pnl) < 1 ? MUTED : hover.pnl > 0 ? UP : DOWN} fontSize="12" fontWeight="bold">
                  {Math.abs(hover.pnl) < 1 ? "Breakeven " : hover.pnl > 0 ? "Profit " : "Loss "}
                  {inr(Math.round(Math.abs(hover.pnl)))}
                </text>
              </g>
            );
          })()}
        </g>
      )}
    </svg>
  );
}
