"use client";

import { AnimatePresence, motion } from "framer-motion";
import { spotlightUi } from "@/config/ui";

type DesktopExpandAnimationProps = {
  isVisible: boolean;
  headline?: string;
  subhead?: string;
};

/**
 * Lightweight, Raycast-inspired expand animation that feels instant while
 * the desktop bundle hydrates. Keeps overlays translucent so the user still
 * perceives motion from the underlying window.
 */
export default function DesktopExpandAnimation({
  isVisible,
  headline = "Opening Cerebros Desktop",
  subhead = "Linking live context…",
}: DesktopExpandAnimationProps) {
  return (
    <AnimatePresence>
      {isVisible && (
        <motion.div
          className="pointer-events-none absolute inset-0 z-40"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={spotlightUi.motion.fade}
          aria-hidden="true"
        >
          {/* Soft vignette */}
          <motion.div
            className="absolute inset-0 bg-gradient-to-b from-neutral-950/45 via-neutral-950/10 to-neutral-950/45 backdrop-blur-md"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
          />

          {/* Glass card */}
          <motion.div
            className="absolute left-1/2 top-[22%] -translate-x-1/2 w-[260px] sm:w-[320px]"
            initial={{ opacity: 0, y: -20, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -20, scale: 0.9 }}
            transition={spotlightUi.motion.spring}
          >
            <div className="relative rounded-[22px] border border-white/10 bg-neutral-900/80 px-8 py-6 shadow-2xl shadow-black/50">
              {/* Top glow */}
              <div className="absolute inset-x-8 -top-6 h-8 rounded-full bg-gradient-to-r from-accent-primary/40 via-white/30 to-purple-400/40 blur-3xl opacity-70" />

              <div className="flex items-center justify-between text-[11px] uppercase tracking-[0.3em] text-white/50 mb-4">
                <span className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#1DB954] animate-pulse" />
                  Cerebros
                </span>
                <span>Desktop</span>
              </div>

              <motion.h2
                className="text-lg font-semibold text-white text-center"
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.05, duration: 0.2 }}
              >
                {headline}
              </motion.h2>
              <motion.p
                className="text-sm text-white/60 text-center mt-1"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.08, duration: 0.2 }}
              >
                {subhead}
              </motion.p>

              <div className="mt-4 space-y-2 text-xs text-white/60">
                {[
                  "Booting command router",
                  "Priming slash commands",
                  "Syncing Spotify + Slack state",
                ].map((step, index) => (
                  <motion.div
                    key={step}
                    className="flex items-center gap-2"
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.12 + index * 0.04 }}
                  >
                    <span className="w-1.5 h-1.5 rounded-full bg-white/40" />
                    <span className="truncate">{step}</span>
                  </motion.div>
                ))}
              </div>

              <motion.div
                className="mt-5 h-1.5 rounded-full bg-white/10 overflow-hidden"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.15, duration: 0.2 }}
              >
                <motion.div
                  className="h-full rounded-full bg-gradient-to-r from-accent-primary via-purple-500 to-sky-400"
                  initial={{ width: "10%" }}
                  animate={{ width: ["15%", "70%", "100%"] }}
                  transition={{ duration: 1.6, ease: "easeInOut" }}
                />
              </motion.div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}


