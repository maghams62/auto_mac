'use client';

import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { TypeAnimation } from "react-type-animation";
import { PulseLoader } from "react-spinners";
import { cn } from "@/lib/utils";

type StartupOverlayProps = {
  phase: "assets" | "websocket" | "ready" | "error";
  show: boolean;
  error?: string;
  onRetry?: () => void;
};

export default function StartupOverlay({ phase, show, error, onRetry }: StartupOverlayProps) {
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);
  const [loadingProgress, setLoadingProgress] = useState(0);
  const [currentStep, setCurrentStep] = useState(0);

  // Deterministic particle generation for SSR/CSR consistency
  const particles = useMemo(() => {
    // Use a simple seeded random for deterministic results
    let seed = 12345; // Fixed seed for consistency
    const seededRandom = () => {
      seed = (seed * 9301 + 49297) % 233280;
      return seed / 233280;
    };

    return Array.from({ length: 25 }, (_, i) => ({
      id: i,
      x: seededRandom() * 100,
      y: seededRandom() * 100,
      size: seededRandom() * 3 + 1,
      speed: seededRandom() * 0.5 + 0.5,
      direction: seededRandom() * Math.PI * 2,
      opacity: seededRandom() * 0.4 + 0.2,
      color: ['blue-400', 'purple-400', 'cyan-400', 'indigo-400'][Math.floor(seededRandom() * 4)],
    }));
  }, []);

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

  const loadingSteps = [
    "Initializing Cerebro OS...",
    "Loading automation agents...",
    "Connecting to services...",
    "Preparing interface...",
    "Ready to assist!"
  ];

  // Update loading progress and steps based on actual boot phase
  useEffect(() => {
    if (!show) return;

    // Progress based on actual boot phase for more realistic feedback
    const getProgressForPhase = (currentPhase: string) => {
      switch (currentPhase) {
        case "assets": return Math.min(60, loadingProgress + 2); // 0-60% during asset loading
        case "websocket": return Math.min(90, loadingProgress + 1); // 60-90% during websocket connection
        case "ready": return 100; // 100% when ready
        case "error": return loadingProgress; // Stay at current progress on error
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
          // Smooth progression towards target
          const increment = Math.min(targetProgress - prev, Math.random() * 3 + 1);
          return Math.min(100, prev + increment);
        });
      }, 100);

      return () => clearInterval(progressInterval);
    } else {
      // For reduced motion, set progress directly
      setLoadingProgress(getProgressForPhase(phase));
    }
  }, [show, phase, prefersReducedMotion, loadingProgress]);

  // Step through loading messages based on phase progression
  useEffect(() => {
    if (!show) return;

    const phaseToStepMap = {
      "assets": 0, // "Initializing Cerebro OS..."
      "websocket": 2, // "Connecting to services..."
      "ready": 4, // "Ready to assist!"
      "error": 4 // Stay on last step for error
    };

    const targetStep = phaseToStepMap[phase] || 0;
    if (targetStep !== currentStep) {
      // Smooth step advancement with delays
      const stepDelays = [400, 600, 500, 700, 300];
      let current = currentStep;

      const advanceToTarget = () => {
        if (current < targetStep) {
          current++;
          setCurrentStep(current);
          if (current < targetStep) {
            setTimeout(advanceToTarget, stepDelays[current] || 500);
          }
        }
      };

      if (current < targetStep) {
        setTimeout(advanceToTarget, stepDelays[current] || 500);
      }
    }
  }, [phase, currentStep, show]);

  // Map phase to internal loading phase for backward compatibility
  const loadingPhase = useMemo(() => {
    switch (phase) {
      case "assets":
        return "connecting"; // Show connecting during asset loading
      case "websocket":
        return "connecting"; // Show connecting during websocket connection
      case "ready":
        return "ready";
      case "error":
        return "complete"; // Error state handled separately
      default:
        return "connecting";
    }
  }, [phase]);

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
            scale: prefersReducedMotion ? 1 : 0.98,
            transition: overlayTransition
          }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black overflow-hidden"
        >
          {/* Animated background */}
          <div className="absolute inset-0 overflow-hidden">
            <motion.div
              className="absolute inset-0 bg-gradient-to-r from-blue-600/10 via-purple-600/10 to-cyan-600/10"
              animate={prefersReducedMotion ? {} : {
                backgroundPosition: ["0% 50%", "100% 50%", "0% 50%"],
              }}
              transition={prefersReducedMotion ? {} : {
                duration: 8,
                repeat: Infinity,
                ease: "linear",
              }}
              style={{ backgroundSize: "200% 200%" }}
            />

            {/* Advanced particle system */}
            {particles.map((particle) => (
              <motion.div
                key={particle.id}
                className={cn("absolute rounded-full", `bg-${particle.color}/40`)}
                style={{
                  left: `${particle.x}%`,
                  top: `${particle.y}%`,
                  width: `${particle.size}px`,
                  height: `${particle.size}px`,
                }}
                animate={prefersReducedMotion ? {} : {
                  x: [0, Math.cos(particle.direction) * 50, 0],
                  y: [0, Math.sin(particle.direction) * 50, 0],
                  opacity: [particle.opacity, particle.opacity * 1.5, particle.opacity],
                  scale: [1, 1.3, 1],
                }}
                transition={prefersReducedMotion ? {} : {
                  duration: 4 / particle.speed,
                  repeat: Infinity,
                  delay: particle.id * 0.1,
                  ease: "easeInOut",
                }}
              />
            ))}

            {/* Geometric shapes for depth */}
            <motion.div
              className="absolute top-1/4 left-1/4 w-32 h-32 border border-blue-500/10 rounded-full"
              animate={prefersReducedMotion ? {} : {
                rotate: [0, 360],
                scale: [1, 1.2, 1],
              }}
              transition={prefersReducedMotion ? {} : {
                duration: 20,
                repeat: Infinity,
                ease: "linear",
              }}
            />
            <motion.div
              className="absolute bottom-1/4 right-1/4 w-24 h-24 border border-purple-500/10 rounded-lg"
              animate={prefersReducedMotion ? {} : {
                rotate: [0, -360],
                scale: [1, 1.4, 1],
              }}
              transition={prefersReducedMotion ? {} : {
                duration: 15,
                repeat: Infinity,
                ease: "linear",
              }}
            />
          </div>

          <div className="relative z-10 text-center max-w-md mx-auto px-8">
            {/* Enhanced Logo with Cursor-like Embossed Effects */}
            <motion.div
              initial={prefersReducedMotion ? { scale: 1, opacity: 1, rotate: 0 } : { scale: 0.3, opacity: 0, rotate: -180 }}
              animate={{ scale: 1, opacity: 1, rotate: 0 }}
              transition={prefersReducedMotion ? { duration: 0 } : {
                duration: 1.2,
                delay: 0.2,
                type: "spring",
                bounce: 0.3,
                stiffness: 80
              }}
              className="mb-12"
            >
              <motion.div
                className="relative mx-auto mb-6"
                whileHover={{ scale: 1.02 }}
                transition={{ duration: 0.3 }}
              >
                {/* Logo container with advanced embossed effect */}
                <motion.div
                  className="w-28 h-28 rounded-2xl bg-gradient-to-br from-blue-500 via-purple-600 to-cyan-500 flex items-center justify-center relative overflow-hidden"
                  style={{
                    boxShadow: `
                      0 0 60px rgba(59, 130, 246, 0.4),
                      0 0 120px rgba(147, 51, 234, 0.3),
                      0 0 180px rgba(6, 182, 212, 0.2),
                      inset 0 2px 4px rgba(255, 255, 255, 0.1),
                      inset 0 -2px 4px rgba(0, 0, 0, 0.2)
                    `
                  }}
                  animate={prefersReducedMotion ? {} : {
                    boxShadow: [
                      "0 0 60px rgba(59, 130, 246, 0.4), 0 0 120px rgba(147, 51, 234, 0.3), 0 0 180px rgba(6, 182, 212, 0.2), inset 0 2px 4px rgba(255, 255, 255, 0.1), inset 0 -2px 4px rgba(0, 0, 0, 0.2)",
                      "0 0 80px rgba(59, 130, 246, 0.5), 0 0 140px rgba(147, 51, 234, 0.4), 0 0 200px rgba(6, 182, 212, 0.3), inset 0 3px 6px rgba(255, 255, 255, 0.15), inset 0 -3px 6px rgba(0, 0, 0, 0.25)",
                      "0 0 60px rgba(59, 130, 246, 0.4), 0 0 120px rgba(147, 51, 234, 0.3), 0 0 180px rgba(6, 182, 212, 0.2), inset 0 2px 4px rgba(255, 255, 255, 0.1), inset 0 -2px 4px rgba(0, 0, 0, 0.2)"
                    ]
                  }}
                  transition={prefersReducedMotion ? {} : { duration: 4, repeat: Infinity, ease: "easeInOut" }}
                >
                  {/* Animated background gradient */}
                  <motion.div
                    className="absolute inset-0 bg-gradient-to-r from-transparent via-white/15 to-transparent"
                    animate={prefersReducedMotion ? {} : {
                      x: [-150, 150, -150],
                    }}
                    transition={prefersReducedMotion ? {} : {
                      duration: 4,
                      repeat: Infinity,
                      ease: "easeInOut",
                    }}
                  />

                  {/* Inner glow ring */}
                  <motion.div
                    className="absolute inset-2 rounded-xl border border-white/20"
                    animate={prefersReducedMotion ? {} : {
                      borderColor: ["rgba(255, 255, 255, 0.2)", "rgba(255, 255, 255, 0.4)", "rgba(255, 255, 255, 0.2)"]
                    }}
                    transition={prefersReducedMotion ? {} : { duration: 3, repeat: Infinity, ease: "easeInOut" }}
                  />

                  {/* Logo letter with advanced morphing */}
                  <motion.span
                    className="text-5xl font-black text-white relative z-10"
                    style={{
                      textShadow: `
                        0 0 10px rgba(255, 255, 255, 0.8),
                        0 0 20px rgba(255, 255, 255, 0.6),
                        0 0 40px rgba(255, 255, 255, 0.4),
                        2px 2px 4px rgba(0, 0, 0, 0.3)
                      `
                    }}
                    animate={prefersReducedMotion ? {} : {
                      scale: [1, 1.1, 1],
                      rotate: [0, 2, -2, 0]
                    }}
                    transition={prefersReducedMotion ? {} : {
                      duration: 5,
                      repeat: Infinity,
                      ease: "easeInOut"
                    }}
                  >
                    C
                  </motion.span>
                </motion.div>

                {/* Enhanced floating accent elements with embossed effects */}
                <motion.div
                  className="absolute -top-3 -right-3 w-8 h-8 bg-cyan-400 rounded-full flex items-center justify-center"
                  style={{
                    boxShadow: `
                      0 0 20px rgba(6, 182, 212, 0.6),
                      inset 0 1px 2px rgba(255, 255, 255, 0.3),
                      inset 0 -1px 2px rgba(0, 0, 0, 0.2)
                    `
                  }}
                  animate={prefersReducedMotion ? {} : {
                    y: [0, -12, 0],
                    opacity: [0.8, 1, 0.8],
                    rotate: [0, 10, -10, 0]
                  }}
                  transition={prefersReducedMotion ? {} : {
                    duration: 3,
                    repeat: Infinity,
                    ease: "easeInOut",
                  }}
                >
                  <div className="w-2 h-2 bg-white/80 rounded-full"></div>
                </motion.div>

                <motion.div
                  className="absolute -bottom-2 -left-2 w-6 h-6 bg-purple-400 rounded-full flex items-center justify-center"
                  style={{
                    boxShadow: `
                      0 0 15px rgba(147, 51, 234, 0.6),
                      inset 0 1px 2px rgba(255, 255, 255, 0.3),
                      inset 0 -1px 2px rgba(0, 0, 0, 0.2)
                    `
                  }}
                  animate={prefersReducedMotion ? {} : {
                    y: [0, 10, 0],
                    opacity: [0.6, 1, 0.6],
                    rotate: [0, -15, 15, 0]
                  }}
                  transition={prefersReducedMotion ? {} : {
                    duration: 4,
                    repeat: Infinity,
                    ease: "easeInOut",
                    delay: 0.7,
                  }}
                >
                  <div className="w-1.5 h-1.5 bg-white/80 rounded-full"></div>
                </motion.div>

                {/* Additional floating particles for cursor-like feel */}
                <motion.div
                  className="absolute top-1/2 -right-8 w-2 h-2 bg-blue-400 rounded-full"
                  animate={prefersReducedMotion ? {} : {
                    x: [0, 15, 0],
                    opacity: [0, 1, 0],
                    scale: [0, 1, 0]
                  }}
                  transition={prefersReducedMotion ? {} : {
                    duration: 2,
                    repeat: Infinity,
                    ease: "easeInOut",
                    delay: 1.2,
                  }}
                />
                <motion.div
                  className="absolute top-1/3 -left-6 w-1.5 h-1.5 bg-indigo-400 rounded-full"
                  animate={prefersReducedMotion ? {} : {
                    x: [0, -12, 0],
                    opacity: [0, 0.8, 0],
                    scale: [0, 1.2, 0]
                  }}
                  transition={prefersReducedMotion ? {} : {
                    duration: 2.5,
                    repeat: Infinity,
                    ease: "easeInOut",
                    delay: 0.8,
                  }}
                />
              </motion.div>

              <motion.h1
                className="text-4xl font-black text-white mb-3 tracking-tight"
                style={{
                  textShadow: `
                    0 0 20px rgba(255, 255, 255, 0.3),
                    2px 2px 4px rgba(0, 0, 0, 0.5)
                  `
                }}
                initial={prefersReducedMotion ? { y: 0, opacity: 1 } : { y: 40, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                transition={prefersReducedMotion ? { duration: 0 } : { duration: 0.8, delay: 0.7, type: "spring", bounce: 0.2 }}
              >
                Cerebro OS
              </motion.h1>

              <motion.p
                className="text-slate-300 text-xl font-medium"
                style={{
                  textShadow: "0 1px 2px rgba(0, 0, 0, 0.3)"
                }}
                initial={prefersReducedMotion ? { y: 0, opacity: 1 } : { y: 25, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                transition={prefersReducedMotion ? { duration: 0 } : { duration: 0.8, delay: 0.9 }}
              >
                Your AI Assistant
              </motion.p>
            </motion.div>

            {/* Loading step */}
            <motion.div
              key={currentStep}
              initial={prefersReducedMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={prefersReducedMotion ? { opacity: 0, y: -10 } : { opacity: 0, y: -10 }}
              transition={prefersReducedMotion ? { duration: 0 } : { duration: 0.3 }}
              className="mb-8"
            >
              <p className="text-slate-300 text-sm font-mono">
                {loadingSteps[currentStep]}
              </p>
            </motion.div>

            {/* Enhanced Progress Section with Cursor-like Styling */}
            <div className="space-y-8">
              {/* Progress bar with advanced embossed effect */}
              <div className="relative">
                <div
                  className="w-full bg-slate-800/60 rounded-full h-3 overflow-hidden backdrop-blur-sm relative"
                  style={{
                    boxShadow: `
                      inset 0 2px 4px rgba(0, 0, 0, 0.3),
                      inset 0 -1px 2px rgba(255, 255, 255, 0.1),
                      0 1px 3px rgba(0, 0, 0, 0.2)
                    `
                  }}
                >
                  <motion.div
                    className="h-full bg-gradient-to-r from-blue-500 via-purple-500 to-cyan-500 rounded-full relative overflow-hidden"
                    style={{
                      width: `${loadingProgress}%`,
                      boxShadow: `
                        0 0 20px rgba(59, 130, 246, 0.6),
                        inset 0 1px 2px rgba(255, 255, 255, 0.2),
                        inset 0 -1px 2px rgba(0, 0, 0, 0.1)
                      `
                    }}
                    initial={prefersReducedMotion ? { width: `${loadingProgress}%` } : { width: "0%" }}
                    animate={{ width: `${loadingProgress}%` }}
                    transition={prefersReducedMotion ? { duration: 0 } : { duration: 0.6, ease: [0.25, 0.1, 0.25, 1] }}
                  >
                    {/* Enhanced shimmer effect */}
                    <motion.div
                      className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent"
                      animate={prefersReducedMotion ? {} : {
                        x: [-250, 250, -250],
                      }}
                      transition={prefersReducedMotion ? {} : {
                        duration: 2.5,
                        repeat: Infinity,
                        ease: "easeInOut",
                      }}
                    />
                    {/* Inner highlight */}
                    <motion.div
                      className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-transparent via-white/40 to-transparent rounded-full"
                      animate={prefersReducedMotion ? {} : {
                        opacity: [0.3, 0.8, 0.3],
                      }}
                      transition={prefersReducedMotion ? {} : {
                        duration: 1.5,
                        repeat: Infinity,
                        ease: "easeInOut",
                      }}
                    />
                  </motion.div>
                </div>

                {/* Enhanced progress glow effect */}
                <motion.div
                  className="absolute inset-0 rounded-full blur-lg"
                  style={{
                    width: `${loadingProgress}%`,
                    background: `linear-gradient(90deg,
                      rgba(59, 130, 246, 0.4) 0%,
                      rgba(147, 51, 234, 0.4) 50%,
                      rgba(6, 182, 212, 0.4) 100%
                    )`
                  }}
                  animate={{ width: `${loadingProgress}%` }}
                  transition={prefersReducedMotion ? { duration: 0 } : { duration: 0.6, ease: [0.25, 0.1, 0.25, 1] }}
                />

                {/* Outer glow ring */}
                <motion.div
                  className="absolute inset-0 rounded-full blur-xl opacity-50"
                  style={{
                    width: `${loadingProgress}%`,
                    background: `linear-gradient(90deg,
                      rgba(59, 130, 246, 0.2) 0%,
                      rgba(147, 51, 234, 0.2) 50%,
                      rgba(6, 182, 212, 0.2) 100%
                    )`
                  }}
                  animate={{ width: `${loadingProgress}%` }}
                  transition={prefersReducedMotion ? { duration: 0 } : { duration: 0.8, ease: [0.25, 0.1, 0.25, 1] }}
                />
              </div>

              {/* Connection Status */}
              <div className="mb-8 font-mono text-lg text-neutral-200 min-h-[28px]">
                {phase === 'error' ? (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3 }}
                    className="text-red-400"
                  >
                    <div className="mb-2">Connection failed</div>
                    <div className="text-sm text-red-300 mb-4">
                      {error || "Unable to connect to Cerebro. Please check your connection and try refreshing."}
                    </div>
                    {onRetry && (
                      <motion.button
                        onClick={onRetry}
                        className="px-4 py-2 bg-red-500/20 hover:bg-red-500/30 border border-red-400/30 rounded-lg text-red-300 hover:text-red-200 transition-all duration-200 font-medium"
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.2 }}
                      >
                        Try Again
                      </motion.button>
                    )}
                  </motion.div>
                ) : phase === 'ready' ? (
                  <motion.span
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.3 }}
                    className="text-sky-400 font-semibold"
                  >
                    Ready.
                  </motion.span>
                ) : (
                  <motion.span
                    key={phase}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.2 }}
                    className="text-neutral-200"
                  >
                    {phase === 'assets' ? "Loading assets..." : "Connecting to Cerebro..."}
                  </motion.span>
                )}
              </div>

              {/* Cursor-like Loading Indicator with Embossed Effects */}
              <div className="flex items-center justify-center space-x-4">
                <motion.div
                  className="flex space-x-2"
                  animate={prefersReducedMotion ? {} : { rotate: [0, 3, -3, 0] }}
                  transition={prefersReducedMotion ? {} : { duration: 3, repeat: Infinity, ease: "easeInOut" }}
                >
                  {[0, 1, 2, 3, 4].map((i) => (
                    <motion.div
                      key={i}
                      className="w-2 h-10 bg-gradient-to-t from-blue-400 via-purple-400 to-cyan-400 rounded-full"
                      style={{
                        boxShadow: `
                          0 0 8px rgba(59, 130, 246, 0.4),
                          inset 0 1px 2px rgba(255, 255, 255, 0.2),
                          inset 0 -1px 2px rgba(0, 0, 0, 0.1)
                        `,
                        transformOrigin: 'bottom center'
                      }}
                      animate={prefersReducedMotion ? {} : {
                        scaleY: [0.2, 1, 0.2],
                        opacity: [0.3, 1, 0.3],
                      }}
                      transition={prefersReducedMotion ? {} : {
                        duration: 1.5,
                        repeat: Infinity,
                        delay: i * 0.08,
                        ease: "easeInOut",
                      }}
                    />
                  ))}
                </motion.div>

                {/* Enhanced pulsing rings with embossed effect */}
                <div className="flex space-x-1">
                  <motion.div
                    className="w-6 h-6 border-2 border-blue-400/40 rounded-full"
                    style={{
                      boxShadow: `
                        0 0 12px rgba(59, 130, 246, 0.3),
                        inset 0 1px 2px rgba(255, 255, 255, 0.1)
                      `
                    }}
                    animate={prefersReducedMotion ? {} : {
                      scale: [1, 1.4, 1],
                      opacity: [0.4, 0.9, 0.4],
                      borderColor: ["rgba(59, 130, 246, 0.4)", "rgba(59, 130, 246, 0.7)", "rgba(59, 130, 246, 0.4)"],
                    }}
                    transition={prefersReducedMotion ? {} : {
                      duration: 2.5,
                      repeat: Infinity,
                      ease: "easeInOut",
                    }}
                  />
                  <motion.div
                    className="w-4 h-4 border-2 border-purple-400/30 rounded-full"
                    style={{
                      boxShadow: `
                        0 0 8px rgba(147, 51, 234, 0.3),
                        inset 0 1px 2px rgba(255, 255, 255, 0.1)
                      `
                    }}
                    animate={prefersReducedMotion ? {} : {
                      scale: [1, 1.6, 1],
                      opacity: [0.3, 0.8, 0.3],
                      borderColor: ["rgba(147, 51, 234, 0.3)", "rgba(147, 51, 234, 0.6)", "rgba(147, 51, 234, 0.3)"],
                    }}
                    transition={prefersReducedMotion ? {} : {
                      duration: 3,
                      repeat: Infinity,
                      ease: "easeInOut",
                      delay: 0.5,
                    }}
                  />
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
