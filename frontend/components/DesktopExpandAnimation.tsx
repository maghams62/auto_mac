"use client";

import { motion } from "framer-motion";

type DesktopExpandAnimationProps = {
  isVisible: boolean;
  headline?: string;
  subhead?: string;
};

/**
 * Lightweight gradient sweep that mirrors Raycast-style window expansion.
 * Renders on top of the desktop view while the heavy chat bundle lazy-loads.
 */
export default function DesktopExpandAnimation({
  isVisible,
  headline = "Launching desktop mode",
  subhead = "Hydrating context…",
}: DesktopExpandAnimationProps) {
  return (
    <motion.div
      className="pointer-events-none absolute inset-0 z-40 flex items-center justify-center bg-neutral-950/70 backdrop-blur-3xl"
      initial={{ opacity: 0 }}
      animate={{ opacity: isVisible ? 1 : 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      aria-hidden="true"
    >
      <motion.div
        className="w-[360px] h-[360px] rounded-[32px] bg-gradient-to-br from-accent-primary/80 via-purple-500/70 to-transparent border border-white/20 shadow-2xl flex flex-col items-center justify-center text-center text-white p-10"
        initial={{ scale: 0.9, rotate: -2 }}
        animate={{
          scale: isVisible ? 1 : 0.96,
          rotate: isVisible ? 0 : 1,
        }}
        transition={{ duration: 0.45, ease: "easeOut" }}
      >
        <motion.div
          className="mb-4 rounded-full bg-white/20 px-4 py-1 text-xs uppercase tracking-[0.2em]"
          initial={{ opacity: 0, y: -12 }}
          animate={{ opacity: isVisible ? 1 : 0, y: isVisible ? 0 : -8 }}
          transition={{ delay: 0.05 }}
        >
          Cerebros
        </motion.div>
        <motion.h2
          className="text-lg font-semibold"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: isVisible ? 1 : 0, y: isVisible ? 0 : 8 }}
          transition={{ delay: 0.1 }}
        >
          {headline}
        </motion.h2>
        <motion.p
          className="text-sm text-white/70 mt-2"
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: isVisible ? 1 : 0, y: isVisible ? 0 : 6 }}
          transition={{ delay: 0.16 }}
        >
          {subhead}
        </motion.p>
      </motion.div>
    </motion.div>
  );
}


