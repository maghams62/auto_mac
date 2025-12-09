"use client";

type DesktopExpandAnimationProps = {
  isVisible: boolean;
  headline?: string;
  subhead?: string;
  statusSteps?: string[];
};

export default function DesktopExpandAnimation({
  isVisible,
  headline = "Opening Cerebros Desktop",
  subhead = "Linking live context…",
  statusSteps,
}: DesktopExpandAnimationProps) {
  const defaultSteps = [
    "Booting command router",
    "Priming slash commands",
    "Syncing Spotify + Slack state",
  ];
  const steps = statusSteps && statusSteps.length > 0 ? statusSteps : defaultSteps;

  if (!isVisible) {
    return null;
  }

  return (
    <div className="pointer-events-none absolute inset-0 z-40" aria-hidden="true">
      <div className="absolute inset-0 bg-gradient-to-b from-neutral-950/45 via-neutral-950/10 to-neutral-950/45 backdrop-blur-md" />

      <div className="absolute left-1/2 top-[22%] -translate-x-1/2 w-[260px] sm:w-[320px]">
        <div className="relative rounded-[22px] border border-white/10 bg-neutral-900/80 px-8 py-6 shadow-2xl shadow-black/50">
          <div className="absolute inset-x-8 -top-6 h-8 rounded-full bg-gradient-to-r from-accent-primary/40 via-white/30 to-purple-400/40 blur-3xl opacity-70" />

          <div className="flex items-center justify-between text-[11px] uppercase tracking-[0.3em] text-white/50 mb-4">
            <span className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-[#1DB954]" />
              Cerebros
            </span>
            <span>Desktop</span>
          </div>

          <h2 className="text-lg font-semibold text-white text-center">{headline}</h2>
          <p className="text-sm text-white/60 text-center mt-1">{subhead}</p>

          <div className="mt-4 space-y-2 text-xs text-white/60">
            {steps.map((step) => (
              <div key={step} className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-white/40" />
                <span className="truncate">{step}</span>
              </div>
            ))}
          </div>

          <div className="mt-5 h-1.5 rounded-full bg-white/10 overflow-hidden">
            <div className="h-full w-full rounded-full bg-gradient-to-r from-accent-primary via-purple-500 to-sky-400" />
          </div>
        </div>
      </div>
    </div>
  );
}


