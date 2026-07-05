// First-run entrance, shown once per browser session before the cockpit:
//   splash (animated logo + slogan) → intro (why risk management) →
//   slogan gate (click to enter). Entering hands off to the live GuidedTour.
// Pure presentation; it touches no data and calls onDone() when finished or skipped.
import { useEffect, useState } from "react";
import { LogoMark, Wordmark } from "./Logo";
import Icon from "./icons";

const INTRO_POINTS = [
  {
    k: "01",
    title: "Separate your capital",
    body: "Keep long-term, swing and F&O money in their own buckets, so one bad trade can't drain the whole account.",
  },
  {
    k: "02",
    title: "Hedge before it hurts",
    body: "Know your portfolio beta and exactly what to short — or which put to buy — when the market turns against you.",
  },
  {
    k: "03",
    title: "Learn what actually works",
    body: "Every trade journaled, every strategy measured, so capital flows to the segment that genuinely earns it.",
  },
];

export default function Onboarding({ onDone, mode = "full" }) {
  // "full" = first-ever visit (splash -> intro -> gate -> tour); "splash" = returning
  // visit (just the logo entrance, then straight into the app).
  const splashOnly = mode === "splash";
  const [phase, setPhase] = useState("splash"); // splash | intro | gate

  // Splash auto-advances — to the app (returning) or to the intro (first time).
  useEffect(() => {
    if (phase !== "splash") return;
    const t = setTimeout(
      () => (splashOnly ? onDone(false) : setPhase("intro")),
      splashOnly ? 2600 : 4200
    );
    return () => clearTimeout(t);
  }, [phase, splashOnly, onDone]);

  // Enter advances the linear phases; Escape skips straight into the app.
  useEffect(() => {
    function onKey(e) {
      if (e.key === "Escape") onDone(false);
      if (e.key === "Enter") {
        if (phase === "splash") splashOnly ? onDone(false) : setPhase("intro");
        else if (phase === "intro") setPhase("gate");
        else if (phase === "gate") onDone(true);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [phase, splashOnly, onDone]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Welcome to RiskWise"
      className="fixed inset-0 z-50 overflow-hidden bg-canvas-deep text-body"
    >
      {/* Ambient light + faint grid so the void reads as a surface */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          backgroundImage:
            "radial-gradient(900px 520px at 18% -6%, rgba(230,200,110,0.12), transparent 60%)," +
            "radial-gradient(1000px 700px at 108% 8%, rgba(230,200,110,0.05), transparent 55%)",
        }}
      />
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.05]"
        style={{
          backgroundImage:
            "linear-gradient(to right, rgba(230,200,110,0.4) 1px, transparent 1px)," +
            "linear-gradient(to bottom, rgba(230,200,110,0.4) 1px, transparent 1px)",
          backgroundSize: "64px 64px",
          maskImage: "radial-gradient(circle at 50% 40%, black, transparent 75%)",
        }}
      />

      {/* Skip — only in the full first-time flow (the returning splash is quick). */}
      {!splashOnly && (
        <button
          onClick={() => onDone(false)}
          className="absolute right-5 top-5 z-10 rounded-full border border-hairline px-4 py-1.5 text-xs font-medium text-muted-strong transition-colors hover:border-hairline-strong hover:text-body"
        >
          Skip intro
        </button>
      )}

      <div className="relative z-[5] h-full overflow-y-auto">
        <div className="flex min-h-full flex-col items-center justify-center px-6 py-16 sm:py-20">
          {phase === "splash" && <Splash splashOnly={splashOnly} />}
          {phase === "intro" && <Intro onContinue={() => setPhase("gate")} onSkip={() => onDone(false)} />}
          {phase === "gate" && <Gate onEnter={() => onDone(true)} />}
        </div>
      </div>
    </div>
  );
}

function Splash({ splashOnly = false }) {
  return (
    <div key="splash" className="flex flex-col items-center text-center">
      <div className="relative rw-scale-in">
        <span
          className="absolute inset-0 -z-10 rounded-full blur-2xl"
          style={{ background: "radial-gradient(circle, rgba(230,200,110,0.35), transparent 70%)", animation: "rwHalo 5s ease-in-out infinite" }}
        />
        <LogoMark size={118} animated className="rw-float drop-shadow-[0_10px_30px_rgba(0,0,0,0.5)]" />
      </div>

      <div className="mt-8 rw-fade-up rw-d2">
        <Wordmark size={72} className="rw-shimmer" />
      </div>

      <h1 className="mt-7 max-w-2xl rw-fade-up rw-d3 text-3xl font-semibold text-headline sm:text-4xl">
        Know your risk. Own your edge.
      </h1>
      <p className="mt-3 max-w-md rw-fade-up rw-d4 text-base text-muted-strong">
        Allocation, hedging and analytics — in one cockpit.
      </p>

      {/* auto-advance progress */}
      <div className="mt-12 h-[3px] w-44 overflow-hidden rounded-full bg-elevated rw-fade-in rw-d5">
        <div
          className="h-full origin-left rounded-full bg-gold"
          style={{ animation: `rwProgress ${splashOnly ? "2.6s" : "4.2s"} linear forwards` }}
        />
      </div>
      <p className="mt-4 rw-fade-in rw-d6 text-xs uppercase tracking-[0.25em] text-muted">
        {splashOnly ? "welcome back" : "press enter to continue"}
      </p>
    </div>
  );
}

function Intro({ onContinue, onSkip }) {
  return (
    <div key="intro" className="w-full max-w-4xl">
      <p className="rw-fade-up text-xs font-semibold uppercase tracking-[0.3em] text-gold">
        Why risk management
      </p>
      <h2 className="mt-4 max-w-3xl rw-fade-up rw-d1 text-3xl font-bold leading-[1.1] text-headline sm:text-5xl">
        Most retail investors don't lose to the market.
        <br className="hidden sm:block" />
        <span className="text-muted-strong"> They lose to </span>
        <span className="text-gold">unmanaged risk.</span>
      </h2>
      <p className="mt-5 max-w-xl rw-fade-up rw-d2 text-base leading-relaxed text-body">
        The market decides returns. You decide how much you're willing to lose —
        position by position, day by day. RiskWise makes that decision visible.
      </p>

      <div className="mt-10 grid gap-4 sm:grid-cols-3">
        {INTRO_POINTS.map((p, i) => (
          <div
            key={p.k}
            className={`rw-fade-up rounded-2xl border border-hairline bg-card/60 p-5 ${["rw-d3", "rw-d4", "rw-d5"][i]}`}
          >
            <span className="font-mono text-sm font-semibold text-gold/80">{p.k}</span>
            <h3 className="mt-3 text-lg font-semibold text-headline">{p.title}</h3>
            <p className="mt-2 text-sm leading-relaxed text-muted-strong">{p.body}</p>
          </div>
        ))}
      </div>

      <div className="mt-10 flex items-center gap-5 rw-fade-up rw-d6">
        <button
          onClick={onContinue}
          className="group inline-flex items-center gap-2 rounded-full bg-gold px-6 py-3 text-sm font-semibold text-onprimary shadow-[var(--shadow-gold)] transition-all hover:bg-gold-bright active:scale-[0.98]"
        >
          Continue
          <Icon name="arrow" size={18} className="transition-transform group-hover:translate-x-0.5" />
        </button>
        <button onClick={onSkip} className="text-sm font-medium text-muted-strong transition-colors hover:text-body">
          Skip to app
        </button>
      </div>
    </div>
  );
}

function Gate({ onEnter }) {
  return (
    <div key="gate" className="flex flex-col items-center text-center">
      <LogoMark size={56} className="rw-fade-up rw-float" />
      <p className="mt-8 rw-fade-up rw-d1 text-sm font-semibold uppercase tracking-[0.3em] text-muted">
        One decision away
      </p>

      {/* the slogan itself is the door in */}
      <button
        onClick={onEnter}
        className="group mt-5 rw-fade-up rw-d2 max-w-3xl text-balance text-4xl font-bold leading-tight text-headline transition-colors hover:text-gold sm:text-6xl"
      >
        Trade with a plan,
        <br />
        <span className="text-gold group-hover:text-gold-bright">not a hope.</span>
      </button>

      <span className="mt-10 inline-flex items-center gap-2 rw-fade-up rw-d3 text-sm font-medium text-muted-strong">
        <span className="h-px w-8 bg-hairline-strong" />
        click the line to start your guided tour
        <span className="h-px w-8 bg-hairline-strong" />
      </span>

      <button
        onClick={onEnter}
        className="group mt-8 inline-flex items-center gap-2 rounded-full border border-gold/40 bg-gold/5 px-7 py-3 text-sm font-semibold text-gold rw-fade-up rw-d4 transition-all hover:bg-gold hover:text-onprimary active:scale-[0.98]"
      >
        Enter RiskWise
        <Icon name="arrow" size={18} className="transition-transform group-hover:translate-x-0.5" />
      </button>
    </div>
  );
}
