'use client';

import { useState, useEffect, useCallback } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { useBootContext } from './BootProvider';
import TypewriterIntro from './TypewriterIntro';
import CMonogram from './CMonogram';

export default function BootScreen() {
  const { bootPhase } = useBootContext();
  const [hasSkipped, setHasSkipped] = useState(false);
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);
  const [showContent, setShowContent] = useState(false);
  const [typewriterComplete, setTypewriterComplete] = useState(false);
  const [cLogoStartDelay, setCLogoStartDelay] = useState(0);

  // Detect reduced motion preference
  useEffect(() => {
    if (typeof window === 'undefined') return;

    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    setPrefersReducedMotion(mediaQuery.matches);

    const handler = (event: MediaQueryListEvent) => {
      setPrefersReducedMotion(event.matches);
    };

    mediaQuery.addEventListener('change', handler);
    return () => mediaQuery.removeEventListener('change', handler);
  }, []);

  // Show content after black screen fade-in
  useEffect(() => {
    const timer = setTimeout(() => {
      setShowContent(true);
    }, prefersReducedMotion ? 0 : 200);

    return () => clearTimeout(timer);
  }, [prefersReducedMotion]);

  // Start C logo animation after first typewriter line completes
  // First line is ~24 chars × 75ms = ~1.8s, so start C logo around 1.8s
  useEffect(() => {
    if (showContent && !prefersReducedMotion) {
      const delay = 1800; // Start C logo after first line completes
      setCLogoStartDelay(delay);
    } else if (showContent && prefersReducedMotion) {
      setCLogoStartDelay(0);
    }
  }, [showContent, prefersReducedMotion]);

  // Handle skip functionality
  const handleSkip = useCallback(() => {
    setHasSkipped(true);
  }, []);

  // Keyboard skip handlers
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' || e.key === 'Enter' || e.key === ' ') {
        // Don't skip if user is typing in an input
        const activeElement = document.activeElement as HTMLElement;
        const isInputField = activeElement?.tagName === 'TEXTAREA' ||
                            activeElement?.tagName === 'INPUT' ||
                            activeElement?.contentEditable === 'true';
        
        if (!isInputField) {
          e.preventDefault();
          handleSkip();
        }
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleSkip]);

  // Determine if we should show the boot screen
  const isErrorState = bootPhase === 'error';
  const shouldShow = bootPhase !== 'ready' && !isErrorState && !hasSkipped;

  // Fade out when boot is ready or skipped
  const shouldFadeOut = bootPhase === 'ready' || hasSkipped;

  if (isErrorState) {
    return (
      <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-black">
        <div className="text-center space-y-4 max-w-sm px-6">
          <h2 className="text-lg font-mono text-white">Unable to connect to Cerebro</h2>
          <p className="text-sm text-white/60 font-mono leading-relaxed">
            The automation service did not finish booting. Please make sure the backend is running, then retry.
          </p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-gray-800/60 hover:bg-gray-700/60 border border-gray-600/60 rounded text-gray-200 font-mono text-sm transition"
          >
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  if (!shouldShow && !shouldFadeOut) {
    return null;
  }

  return (
    <AnimatePresence mode="wait">
      {shouldShow && (
        <motion.div
          key="boot-screen"
          initial={{ opacity: 0 }}
          animate={{ opacity: shouldFadeOut ? 0 : 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: prefersReducedMotion ? 0 : 0.25, ease: [0.4, 0, 0.2, 1] }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black cursor-pointer"
          onClick={handleSkip}
          role="dialog"
          aria-label="Boot screen"
        >
          {/* Skip hint */}
          <div className="absolute top-4 right-4 text-xs text-white/40 font-mono pointer-events-none">
            Press Esc to skip
          </div>

          {/* Content */}
          {showContent && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: prefersReducedMotion ? 0 : 0.2 }}
              className="flex flex-col items-center justify-center space-y-8"
            >
              {/* Typewriter Intro */}
              <TypewriterIntro
                onComplete={() => setTypewriterComplete(true)}
                prefersReducedMotion={prefersReducedMotion}
              />

              {/* C Monogram */}
              <CMonogram
                size={80}
                strokeWidth={3}
                color="#8E8E8E"
                prefersReducedMotion={prefersReducedMotion}
                startDelay={cLogoStartDelay}
              />
            </motion.div>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
