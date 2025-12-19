'use client';

import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useTypewriter } from "./useTypewriter";

type StartupOverlayProps = {
  phase: "assets" | "websocket" | "ready" | "error";
  show: boolean;
  error?: string;
  onRetry?: () => void;
  onAnimationComplete?: () => void;
};

export default function StartupOverlay({ 
  phase, 
  show, 
  error, 
  onRetry,
  onAnimationComplete 
}: StartupOverlayProps) {
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);
  const [loadingProgress, setLoadingProgress] = useState(0);
  const [showLogo, setShowLogo] = useState(false);
  
  // Memoize speed object to prevent re-renders
  const typewriterSpeed = useMemo(() => ({ 
    start: 100, 
    middle: 120, 
    end: 150 
  }), []);
  
  // Typewriter animation for CEREBROS
  const { displayedText: cerebrosText, isComplete: typewriterComplete } = useTypewriter({
    text: "CEREBROS",
    speed: typewriterSpeed,
    jitter: 15,
    enabled: showLogo && !prefersReducedMotion,
  });

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

  // Animation: when phase is ready, start typewriter, then complete
  useEffect(() => {
    if (!show || phase !== 'ready') {
      setShowLogo(false);
      return;
    }

    // Start logo typewriter after 300ms
    const showTimer = setTimeout(() => {
      setShowLogo(true);
    }, 300);

    return () => {
      clearTimeout(showTimer);
    };
  }, [show, phase]);

  // Complete animation after typewriter finishes (with some delay for display)
  useEffect(() => {
    if (typewriterComplete && showLogo && phase === 'ready') {
      const completeTimer = setTimeout(() => {
        onAnimationComplete?.();
      }, 800); // Wait 800ms after typing completes before calling onAnimationComplete

      return () => clearTimeout(completeTimer);
    }
  }, [typewriterComplete, showLogo, phase, onAnimationComplete]);

  // Update loading progress based on actual boot phase
  useEffect(() => {
    if (!show) return;

    const getProgressForPhase = (currentPhase: string) => {
      switch (currentPhase) {
        case "assets": return Math.min(60, loadingProgress + 2);
        case "websocket": return Math.min(90, loadingProgress + 1);
        case "ready": return 100;
        case "error": return loadingProgress;
        default: return loadingProgress;
      }
    };

    if (!prefersReducedMotion) {
      const progressInterval = setInterval(() => {
        setLoadingProgress(prev => {
          const targetProgress = getProgressForPhase(phase);
          if (prev >= targetProgress) {
            return targetProgress;
          }
          const increment = Math.min(targetProgress - prev, Math.random() * 3 + 1);
          return Math.min(100, prev + increment);
        });
      }, 100);

      return () => clearInterval(progressInterval);
    } else {
      setLoadingProgress(getProgressForPhase(phase));
    }
  }, [show, phase, prefersReducedMotion, loadingProgress]);

  const overlayTransition = useMemo(
    () => ({
      duration: prefersReducedMotion ? 0 : 0.5,
      ease: [0.4, 0, 0.2, 1] as const,
    }),
    [prefersReducedMotion]
  );

  return (
    <AnimatePresence mode="wait">
      {show && (
        <motion.div
          key="startup-overlay"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{
            opacity: 0,
            transition: overlayTransition
          }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black overflow-hidden"
        >
          <div className="relative z-10 text-center max-w-2xl mx-auto px-8">
            {/* CEREBROS Logo with Typewriter Animation */}
            {phase === 'ready' && (
              <motion.h1
                initial={{ opacity: 0, y: 20 }}
                animate={showLogo ? { opacity: 1, y: 0 } : { opacity: 0, y: 20 }}
                transition={{ duration: 0.5, ease: [0.4, 0, 0.2, 1] }}
                className="text-6xl md:text-7xl font-bold text-white tracking-tight mb-2"
                style={{
                  fontFamily: 'var(--font-courier-prime), "Courier Prime", Courier, monospace',
                  fontWeight: 700,
                }}
              >
                {prefersReducedMotion ? (
                  "CEREBROS"
                ) : (
                  <>
                    {cerebrosText}
                    {!typewriterComplete && showLogo && (
                      <span
                        className="inline-block w-[3px] h-[1em] ml-[4px] align-middle"
                        style={{
                          backgroundColor: '#4FF3F8',
                          opacity: 0.8,
                          animation: 'bootCursorBlink 0.55s step-end infinite',
                        }}
                      />
                    )}
                  </>
                )}
              </motion.h1>
            )}

            {/* Loading states for non-ready phases */}
            {phase !== 'ready' && (
              <div className="space-y-6">
                {/* Progress Bar */}
                <div className="relative">
                  <div
                    className="w-full bg-gray-800/40 rounded-full h-1.5 overflow-hidden"
                    style={{
                      boxShadow: 'inset 0 1px 2px rgba(0, 0, 0, 0.5)'
                    }}
                  >
                    <motion.div
                      className="h-full bg-gray-500 rounded-full relative overflow-hidden"
                      style={{
                        width: `${loadingProgress}%`,
                        background: prefersReducedMotion 
                          ? '#64748b'
                          : 'linear-gradient(90deg, #4a5568 0%, #64748b 50%, #4a5568 100%)',
                      }}
                      initial={prefersReducedMotion ? { width: `${loadingProgress}%` } : { width: "0%" }}
                      animate={{ width: `${loadingProgress}%` }}
                      transition={prefersReducedMotion ? { duration: 0 } : { duration: 0.6, ease: [0.4, 0, 0.2, 1] }}
                    >
                      {!prefersReducedMotion && (
                        <motion.div
                          className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent"
                          animate={{
                            x: [-200, 200, -200],
                          }}
                          transition={{
                            duration: 2,
                            repeat: Infinity,
                            ease: "easeInOut",
                          }}
                        />
                      )}
                    </motion.div>
                  </div>
                </div>

                {/* Connection Status */}
                <div className="mb-6 font-mono text-sm text-gray-400 min-h-[20px]">
                  {phase === 'error' ? (
                    <motion.div
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.3 }}
                      className="text-red-400"
                    >
                      <div className="mb-2">Connection failed</div>
                      <div className="text-xs text-red-300/80 mb-4">
                        {error || "Unable to connect to Cerebro. Please check your connection and try refreshing."}
                      </div>
                      {onRetry && (
                        <motion.button
                          onClick={onRetry}
                          className="px-4 py-2 bg-gray-800/50 hover:bg-gray-700/50 border border-gray-600/50 rounded text-gray-300 hover:text-gray-200 transition-all duration-200 font-medium"
                          whileHover={{ scale: 1.02 }}
                          whileTap={{ scale: 0.98 }}
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ delay: 0.2 }}
                        >
                          Try Again
                        </motion.button>
                      )}
                    </motion.div>
                  ) : (
                    <motion.span
                      key={phase}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ duration: 0.2 }}
                      className="text-gray-400"
                    >
                      {phase === 'assets' ? "Loading assets..." : "Connecting to Cerebro..."}
                    </motion.span>
                  )}
                </div>

                {/* Loading Dots */}
                {phase !== 'error' && (
                  <div className="flex items-center justify-center space-x-1.5">
                    {[0, 1, 2].map((i) => (
                      <motion.div
                        key={i}
                        className="w-1.5 h-1.5 bg-gray-500 rounded-full"
                        animate={prefersReducedMotion ? {} : {
                          opacity: [0.3, 1, 0.3],
                          scale: [0.8, 1, 0.8],
                        }}
                        transition={prefersReducedMotion ? {} : {
                          duration: 1.2,
                          repeat: Infinity,
                          delay: i * 0.2,
                          ease: "easeInOut",
                        }}
                      />
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
