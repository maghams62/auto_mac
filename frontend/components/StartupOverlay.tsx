'use client';

import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { TypeAnimation } from "react-type-animation";
import { PulseLoader } from "react-spinners";

type StartupOverlayProps = {
  show: boolean;
};

export default function StartupOverlay({ show }: StartupOverlayProps) {
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);
  const [loadingPhase, setLoadingPhase] = useState<'connecting' | 'ready' | 'complete'>('connecting');

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    setPrefersReducedMotion(mediaQuery.matches);

    const handler = (event: MediaQueryListEvent) => {
      setPrefersReducedMotion(event.matches);
    };

    mediaQuery.addEventListener("change", handler);
    return () => {
      mediaQuery.removeEventListener("change", handler);
    };
  }, []);

  // Update loading phase based on show prop
  useEffect(() => {
    if (!show && loadingPhase === 'connecting') {
      setLoadingPhase('ready');
      // Brief moment to show ready state before transitioning to complete
      const timer = setTimeout(() => setLoadingPhase('complete'), 400);
      return () => clearTimeout(timer);
    }
  }, [show, loadingPhase]);

  const overlayTransition = useMemo(
    () => ({
      duration: prefersReducedMotion ? 0 : 0.6,
      ease: [0.43, 0.13, 0.23, 0.96] as const, // Custom easing for smooth exit
    }),
    [prefersReducedMotion]
  );

  const cardTransition = useMemo(
    () => ({
      duration: prefersReducedMotion ? 0 : 0.5,
      delay: prefersReducedMotion ? 0 : 0.15,
      ease: "easeOut" as const,
    }),
    [prefersReducedMotion]
  );

  const cardExitTransition = useMemo(
    () => ({
      duration: prefersReducedMotion ? 0 : 0.4,
      ease: [0.43, 0.13, 0.23, 0.96] as const,
    }),
    [prefersReducedMotion]
  );

  return (
    <AnimatePresence mode="wait">
      {show && (
        <motion.div
          key="startup-overlay"
          initial={{ opacity: 1 }}
          animate={{ opacity: 1 }}
          exit={{
            opacity: 0,
            transition: overlayTransition
          }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black"
        >
          <motion.div
            initial={{
              opacity: prefersReducedMotion ? 1 : 0,
              y: prefersReducedMotion ? 0 : 20,
              scale: prefersReducedMotion ? 1 : 0.95
            }}
            animate={{
              opacity: 1,
              y: 0,
              scale: 1
            }}
            exit={{
              opacity: 0,
              y: -10,
              scale: 0.98,
              transition: cardExitTransition
            }}
            transition={cardTransition}
            className="rounded-3xl border border-white/10 bg-neutral-900/70 px-12 py-14 text-center shadow-[0_0_80px_rgba(56,189,248,0.25)] backdrop-blur-md relative overflow-hidden"
          >
            {/* Animated background gradient */}
            <motion.div
              className="absolute inset-0 bg-gradient-to-br from-sky-500/5 via-transparent to-blue-500/5"
              animate={{
                opacity: [0.3, 0.6, 0.3],
              }}
              transition={{
                duration: 3,
                repeat: Infinity,
                ease: "easeInOut"
              }}
            />

            <div className="relative z-10">
              <div className="mb-8 font-mono text-lg text-neutral-200 min-h-[28px]">
                {loadingPhase === 'ready' ? (
                  <motion.span
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.3 }}
                    className="text-sky-400 font-semibold"
                  >
                    Ready.
                  </motion.span>
                ) : (
                  <TypeAnimation
                    sequence={[
                      "Initializing Cerebro OS…",
                      1000,
                      "Loading automation agents…",
                      900,
                      "Connecting to services…",
                      900,
                      "Establishing secure channels…",
                      900,
                      "Standing by…",
                      800,
                    ]}
                    speed={65}
                    deletionSpeed={45}
                    repeat={Infinity}
                    wrapper="span"
                    cursor
                    className="text-neutral-200"
                  />
                )}
              </div>

              <div className="flex items-center justify-center">
                {loadingPhase === 'ready' ? (
                  <motion.div
                    initial={{ scale: 0.8, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    transition={{ duration: 0.3 }}
                  >
                    <svg
                      className="w-8 h-8 text-sky-400"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <motion.path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2.5}
                        d="M5 13l4 4L19 7"
                        initial={{ pathLength: 0 }}
                        animate={{ pathLength: 1 }}
                        transition={{ duration: 0.4, ease: "easeOut" }}
                      />
                    </svg>
                  </motion.div>
                ) : (
                  <PulseLoader color="#38bdf8" size={12} speedMultiplier={0.7} />
                )}
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
