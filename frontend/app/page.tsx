"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import ChatInterface from "@/components/ChatInterface";

function AppLoader() {
  const [loadingProgress, setLoadingProgress] = useState(0);
  const [currentStep, setCurrentStep] = useState(0);
  const [particles, setParticles] = useState(() => {
    // Generate more sophisticated particles with physics
    return Array.from({ length: 25 }, (_, i) => ({
      id: i,
      x: Math.random() * 100,
      y: Math.random() * 100,
      size: Math.random() * 3 + 1,
      speed: Math.random() * 0.5 + 0.5,
      direction: Math.random() * Math.PI * 2,
      opacity: Math.random() * 0.4 + 0.2,
      color: ['blue-400', 'purple-400', 'cyan-400', 'indigo-400'][Math.floor(Math.random() * 4)],
    }));
  });

  const loadingSteps = [
    "Initializing Cerebro OS...",
    "Loading automation agents...",
    "Connecting to services...",
    "Preparing interface...",
    "Ready to assist!"
  ];

  useEffect(() => {
    // More realistic progress curve (starts fast, slows down)
    const progressInterval = setInterval(() => {
      setLoadingProgress(prev => {
        if (prev >= 100) {
          clearInterval(progressInterval);
          return 100;
        }
        // Sigmoid-like progress: fast start, slow finish
        const remaining = 100 - prev;
        const increment = Math.min(remaining * 0.15, Math.random() * 8 + 2);
        return Math.min(100, prev + increment);
      });
    }, 150);

    // Step through loading messages with varying timing
    const stepTimings = [400, 600, 500, 700, 300]; // Variable step durations
    let stepIndex = 0;

    const advanceStep = () => {
      if (stepIndex < loadingSteps.length - 1) {
        stepIndex++;
        setTimeout(advanceStep, stepTimings[stepIndex] || 500);
      }
    };

    setTimeout(advanceStep, stepTimings[0]);

    return () => {
      clearInterval(progressInterval);
    };
  }, []);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0, scale: 0.98 }}
      transition={{ duration: 0.5 }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950"
    >
      {/* Animated background */}
      <div className="absolute inset-0 overflow-hidden">
        <motion.div
          className="absolute inset-0 bg-gradient-to-r from-blue-600/10 via-purple-600/10 to-cyan-600/10"
          animate={{
            backgroundPosition: ["0% 50%", "100% 50%", "0% 50%"],
          }}
          transition={{
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
            className={`absolute rounded-full bg-${particle.color}/40`}
            style={{
              left: `${particle.x}%`,
              top: `${particle.y}%`,
              width: `${particle.size}px`,
              height: `${particle.size}px`,
            }}
            animate={{
              x: [0, Math.cos(particle.direction) * 50, 0],
              y: [0, Math.sin(particle.direction) * 50, 0],
              opacity: [particle.opacity, particle.opacity * 1.5, particle.opacity],
              scale: [1, 1.3, 1],
            }}
            transition={{
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
          animate={{
            rotate: [0, 360],
            scale: [1, 1.2, 1],
          }}
          transition={{
            duration: 20,
            repeat: Infinity,
            ease: "linear",
          }}
        />
        <motion.div
          className="absolute bottom-1/4 right-1/4 w-24 h-24 border border-purple-500/10 rounded-lg"
          animate={{
            rotate: [0, -360],
            scale: [1, 1.4, 1],
          }}
          transition={{
            duration: 15,
            repeat: Infinity,
            ease: "linear",
          }}
        />
      </div>

      <div className="relative z-10 text-center max-w-md mx-auto px-8">
        {/* Enhanced Logo */}
        <motion.div
          initial={{ scale: 0.5, opacity: 0, rotate: -180 }}
          animate={{ scale: 1, opacity: 1, rotate: 0 }}
          transition={{
            duration: 0.8,
            delay: 0.3,
            type: "spring",
            bounce: 0.4,
            stiffness: 100
          }}
          className="mb-8"
        >
          <motion.div
            className="relative mx-auto mb-4"
            whileHover={{ scale: 1.05 }}
            transition={{ duration: 0.2 }}
          >
            {/* Logo container with glow effect */}
            <motion.div
              className="w-24 h-24 rounded-3xl bg-gradient-to-br from-blue-500 via-purple-600 to-cyan-500 flex items-center justify-center shadow-2xl relative overflow-hidden"
              animate={{
                boxShadow: [
                  "0 0 20px rgba(59, 130, 246, 0.3)",
                  "0 0 40px rgba(147, 51, 234, 0.4)",
                  "0 0 20px rgba(59, 130, 246, 0.3)"
                ]
              }}
              transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
            >
              {/* Animated background gradient */}
              <motion.div
                className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent"
                animate={{
                  x: [-100, 100, -100],
                }}
                transition={{
                  duration: 3,
                  repeat: Infinity,
                  ease: "easeInOut",
                }}
              />

              {/* Logo letter with morphing */}
              <motion.span
                className="text-4xl font-bold text-white relative z-10"
                animate={{
                  scale: [1, 1.2, 1],
                  rotate: [0, 5, -5, 0]
                }}
                transition={{
                  duration: 4,
                  repeat: Infinity,
                  ease: "easeInOut"
                }}
              >
                C
              </motion.span>
            </motion.div>

            {/* Floating accent elements */}
            <motion.div
              className="absolute -top-2 -right-2 w-6 h-6 bg-cyan-400 rounded-full"
              animate={{
                y: [0, -10, 0],
                opacity: [0.7, 1, 0.7],
              }}
              transition={{
                duration: 2.5,
                repeat: Infinity,
                ease: "easeInOut",
              }}
            />
            <motion.div
              className="absolute -bottom-1 -left-1 w-4 h-4 bg-purple-400 rounded-full"
              animate={{
                y: [0, 8, 0],
                opacity: [0.5, 0.9, 0.5],
              }}
              transition={{
                duration: 3,
                repeat: Infinity,
                ease: "easeInOut",
                delay: 0.5,
              }}
            />
          </motion.div>

          <motion.h1
            className="text-3xl font-bold text-white mb-2 tracking-tight"
            initial={{ y: 30, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ duration: 0.6, delay: 0.6, type: "spring", bounce: 0.3 }}
          >
            Cerebro OS
          </motion.h1>

          <motion.p
            className="text-slate-400 text-lg"
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ duration: 0.6, delay: 0.8 }}
          >
            Your AI Assistant
          </motion.p>
        </motion.div>

        {/* Loading step */}
        <motion.div
          key={currentStep}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          transition={{ duration: 0.3 }}
          className="mb-8"
        >
          <p className="text-slate-300 text-sm font-mono">
            {loadingSteps[currentStep]}
          </p>
        </motion.div>

        {/* Enhanced Progress Section */}
        <div className="space-y-6">
          {/* Progress bar with glow */}
          <div className="relative">
            <div className="w-full bg-slate-800/50 rounded-full h-2 overflow-hidden backdrop-blur-sm">
              <motion.div
                className="h-full bg-gradient-to-r from-blue-500 via-purple-500 to-cyan-500 rounded-full relative overflow-hidden"
                style={{ width: `${loadingProgress}%` }}
                initial={{ width: "0%" }}
                animate={{ width: `${loadingProgress}%` }}
                transition={{ duration: 0.4, ease: [0.25, 0.1, 0.25, 1] }}
              >
                {/* Shimmer effect on progress bar */}
                <motion.div
                  className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent"
                  animate={{
                    x: [-200, 200, -200],
                  }}
                  transition={{
                    duration: 2,
                    repeat: Infinity,
                    ease: "easeInOut",
                  }}
                />
              </motion.div>
            </div>

            {/* Progress glow effect */}
            <motion.div
              className="absolute inset-0 rounded-full bg-gradient-to-r from-blue-500/20 to-purple-500/20 blur-md"
              style={{ width: `${loadingProgress}%` }}
              animate={{ width: `${loadingProgress}%` }}
              transition={{ duration: 0.4, ease: [0.25, 0.1, 0.25, 1] }}
            />
          </div>

          {/* Sophisticated loading indicator */}
          <div className="flex justify-center items-center space-x-2">
            <motion.div
              className="flex space-x-1"
              animate={{ rotate: [0, 5, -5, 0] }}
              transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
            >
              {[0, 1, 2, 3].map((i) => (
                <motion.div
                  key={i}
                  className="w-1.5 h-8 bg-gradient-to-t from-blue-400 to-cyan-400 rounded-full"
                  animate={{
                    scaleY: [0.3, 1, 0.3],
                    opacity: [0.4, 1, 0.4],
                  }}
                  transition={{
                    duration: 1.2,
                    repeat: Infinity,
                    delay: i * 0.1,
                    ease: "easeInOut",
                  }}
                  style={{
                    transformOrigin: 'bottom',
                  }}
                />
              ))}
            </motion.div>

            {/* Pulsing ring */}
            <motion.div
              className="w-8 h-8 border-2 border-blue-400/30 rounded-full"
              animate={{
                scale: [1, 1.3, 1],
                opacity: [0.3, 0.8, 0.3],
              }}
              transition={{
                duration: 2,
                repeat: Infinity,
                ease: "easeInOut",
              }}
            />
          </div>
        </div>
      </div>
    </motion.div>
  );
}

export default function Home() {
  const [isLoading, setIsLoading] = useState(true);
  const [showChat, setShowChat] = useState(false);

  useEffect(() => {
    // Simulate loading time
    const timer = setTimeout(() => {
      setIsLoading(false);
      setTimeout(() => setShowChat(true), 300); // Brief pause before showing chat
    }, 3000);

    return () => clearTimeout(timer);
  }, []);

  return (
    <main className="relative min-h-screen flex flex-col">
      <AnimatePresence mode="wait">
        {isLoading && (
          <AppLoader key="loader" />
        )}
      </AnimatePresence>

      <AnimatePresence mode="wait">
        {showChat && (
          <motion.div
            key="chat"
            initial={{
              opacity: 0,
              scale: 0.9,
              y: 20,
              filter: "blur(10px)"
            }}
            animate={{
              opacity: 1,
              scale: 1,
              y: 0,
              filter: "blur(0px)"
            }}
            exit={{
              opacity: 0,
              scale: 1.1,
              filter: "blur(5px)"
            }}
            transition={{
              duration: 1.2,
              ease: [0.25, 0.1, 0.25, 1],
              staggerChildren: 0.1,
            }}
            className="flex-1"
          >
            {/* Dramatic reveal effect */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.3, delay: 0.8 }}
              className="absolute inset-0 bg-gradient-to-br from-transparent via-blue-500/5 to-purple-500/5 pointer-events-none"
            />

            <ChatInterface />
          </motion.div>
        )}
      </AnimatePresence>
    </main>
  );
}
