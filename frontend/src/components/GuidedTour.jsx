// Interactive, teacher-style product tour. It runs OVER the live cockpit: for each
// step it opens the real tab, spotlights that nav item, and explains what to do — the
// student follows along (click the highlighted tab, or press Next). Purely presentational.
import { useCallback, useEffect, useLayoutEffect, useState } from "react";
import Icon from "./icons";

const STEPS = [
  {
    view: "dashboard",
    center: true,
    title: "Welcome to RiskWise",
    body: "Let's take a quick tour together. I'll open each screen for you and explain it in one line — you can click the highlighted tab yourself, or just press Next to follow along.",
  },
  {
    view: "dashboard",
    title: "1 · Dashboard",
    body: "This is your control room — total value, P&L, allocation drift and every holding on one screen. Start your day here.",
  },
  {
    view: "holdings",
    title: "2 · My Holdings",
    body: "Add what you actually own here — stocks and F&O. Live prices fill in on their own. Build this first: every other screen reads from it.",
  },
  {
    view: "portfolios",
    title: "3 · Portfolios",
    body: "Your capital, split into buckets — F&O, Swing, Long-term — so you can hedge or analyse each one on its own.",
  },
  {
    view: "allocation",
    title: "4 · Allocation",
    body: "Set a target weight for each bucket. RiskWise warns you the moment one drifts off your plan.",
  },
  {
    view: "hedge",
    title: "5 · Hedge",
    body: "Compute your portfolio beta and the exact number of index lots to short to protect it when the market turns.",
  },
  {
    view: "options",
    title: "6 · Options",
    body: "Take a view on the market and get ranked strategies — with live payoff curves, breakevens and Greeks.",
  },
  {
    view: "basket",
    title: "7 · Basket Order",
    body: "Build a multi-leg trade from the live option chain and see its combined payoff and margin. Analysis only — you place the order at your broker.",
  },
  {
    view: "risk",
    title: "8 · Risk Analytics",
    body: "See concentration, correlation, VaR and drawdown — exactly where a bad day would hurt you most.",
  },
  {
    view: "journal",
    title: "9 · Journal",
    body: "Log every trade and track win-rate, R-multiple and expectancy — so you back your edge, not your luck. That's the tour, you're all set!",
  },
];

const PAD = 8;

function targetRect(view) {
  const els = document.querySelectorAll(`[data-tour="nav-${view}"]`);
  for (const el of els) {
    if (el.offsetParent !== null) return el.getBoundingClientRect(); // the visible one
  }
  return null;
}

export default function GuidedTour({ onNavigate, onDone }) {
  const [i, setI] = useState(0);
  const [rect, setRect] = useState(null);
  const step = STEPS[i];
  const last = i === STEPS.length - 1;

  const go = useCallback((n) => setI((v) => Math.min(STEPS.length - 1, Math.max(0, v + n))), []);
  const next = useCallback(() => (last ? onDone() : go(1)), [last, go, onDone]);

  // Open the step's tab as we arrive on it.
  useEffect(() => {
    onNavigate(step.view);
  }, [i, step.view, onNavigate]);

  // Measure the highlighted nav item (after navigation lays out), keep it fresh on resize.
  useLayoutEffect(() => {
    let raf;
    const measure = () => setRect(step.center ? null : targetRect(step.view));
    measure();
    const t = setTimeout(measure, 60); // let the tab switch settle
    raf = requestAnimationFrame(measure);
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", measure, true);
    return () => {
      clearTimeout(t);
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", measure);
      window.removeEventListener("scroll", measure, true);
    };
  }, [i, step.view, step.center]);

  // Let the student click the highlighted tab to advance.
  useEffect(() => {
    if (step.center) return;
    const els = document.querySelectorAll(`[data-tour="nav-${step.view}"]`);
    const onClick = () => setTimeout(next, 180);
    els.forEach((el) => el.addEventListener("click", onClick));
    return () => els.forEach((el) => el.removeEventListener("click", onClick));
  }, [i, step.view, step.center, next]);

  // Keyboard: Enter → next, ← / → to move, Esc → skip.
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "Escape") onDone();
      else if (e.key === "Enter" || e.key === "ArrowRight") next();
      else if (e.key === "ArrowLeft") go(-1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [next, go, onDone]);

  const spot = rect
    ? { top: rect.top - PAD, left: rect.left - PAD, width: rect.width + PAD * 2, height: rect.height + PAD * 2 }
    : null;

  // Coach card: beside the highlight if there's room, else below; centered when no target.
  let card;
  if (!spot) {
    card = { position: "fixed", top: "50%", left: "50%", transform: "translate(-50%, -50%)" };
  } else {
    const CARD_W = 320;
    const roomRight = window.innerWidth - (spot.left + spot.width);
    if (roomRight > CARD_W + 24) {
      card = { position: "fixed", top: Math.max(16, spot.top), left: spot.left + spot.width + 16 };
    } else {
      card = {
        position: "fixed",
        top: spot.top + spot.height + 12,
        left: Math.min(Math.max(16, spot.left), window.innerWidth - CARD_W - 16),
      };
    }
  }

  return (
    <div className="fixed inset-0 z-[60]" role="dialog" aria-modal="true" aria-label="Guided tour">
      {/* Spotlight — a dim everywhere except a soft-cornered hole around the tab. */}
      {spot ? (
        <div
          className="pointer-events-none absolute rounded-xl ring-2 ring-gold transition-all duration-300 ease-out"
          style={{
            top: spot.top,
            left: spot.left,
            width: spot.width,
            height: spot.height,
            boxShadow: "0 0 0 9999px rgba(2,3,5,0.72), 0 0 22px 2px rgba(230,200,110,0.45)",
          }}
        >
          <span className="absolute inset-0 rounded-xl ring-2 ring-gold/60 animate-pulse" />
        </div>
      ) : (
        <div className="pointer-events-none absolute inset-0" style={{ background: "rgba(2,3,5,0.72)" }} />
      )}

      {/* Coach card */}
      <div
        key={i}
        style={{ ...card, width: 320, maxWidth: "calc(100vw - 32px)" }}
        className="rw-scale-in pointer-events-auto rounded-2xl border border-hairline bg-card p-5 shadow-[var(--shadow-pop)]"
      >
        <div className="mb-3 flex items-center justify-between">
          <span className="inline-flex items-center gap-2 text-xs font-medium text-muted-strong">
            <Icon name="play" size={13} className="text-gold" />
            Guided tour
            <span className="tnum text-muted">· {i + 1}/{STEPS.length}</span>
          </span>
          <button onClick={onDone} className="text-xs font-medium text-muted-strong transition-colors hover:text-body">
            Skip
          </button>
        </div>

        <h3 className="text-lg font-bold text-headline">{step.title}</h3>
        <p className="mt-1.5 text-sm leading-relaxed text-body">{step.body}</p>

        {/* progress dots */}
        <div className="mt-4 flex items-center gap-1.5">
          {STEPS.map((_, k) => (
            <span
              key={k}
              className={`h-1.5 rounded-full transition-all ${k === i ? "w-5 bg-gold" : "w-1.5 bg-elevated"}`}
            />
          ))}
        </div>

        <div className="mt-4 flex items-center justify-between">
          <button
            onClick={() => go(-1)}
            disabled={i === 0}
            className="inline-flex items-center gap-1 rounded-full px-3 py-1.5 text-sm font-medium text-muted-strong transition-colors hover:text-body disabled:pointer-events-none disabled:opacity-0"
          >
            <Icon name="arrowLeft" size={16} />
            Back
          </button>
          <button
            onClick={next}
            className="group inline-flex items-center gap-2 rounded-full bg-gold px-5 py-2 text-sm font-semibold text-onprimary shadow-[var(--shadow-gold)] transition-all hover:bg-gold-bright active:scale-[0.98]"
          >
            {last ? "Finish" : "Next"}
            <Icon name={last ? "check" : "arrow"} size={16} className="transition-transform group-hover:translate-x-0.5" />
          </button>
        </div>
      </div>
    </div>
  );
}
