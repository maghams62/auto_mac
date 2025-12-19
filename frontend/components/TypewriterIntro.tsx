'use client';

import { useState, useMemo, useCallback } from 'react';
import { useTypewriterLines } from './useTypewriterLines';
import { cn } from '@/lib/utils';

type TypewriterIntroProps = {
  onComplete?: () => void;
  prefersReducedMotion?: boolean;
};

export default function TypewriterIntro({ 
  onComplete,
  prefersReducedMotion = false 
}: TypewriterIntroProps) {
  const [showCursor, setShowCursor] = useState(true);
  const [cursorOpacity, setCursorOpacity] = useState(0.6);

  // Memoize lines array to prevent re-renders
  const lines = useMemo(() => [
    "Launching Cerebro OS…",
    "Initializing Mac automations…"
  ], []);

  // Memoize pause array to prevent re-renders
  const pauseBetweenLinesMs = useMemo(() => [500, 350], []);

  // Memoize onComplete callback
  const handleComplete = useCallback(() => {
    // Fade out cursor after completion
    setTimeout(() => {
      setCursorOpacity(0);
      setTimeout(() => {
        setShowCursor(false);
      }, 200);
    }, 200);
    onComplete?.();
  }, [onComplete]);

  const { displayedLines, currentLineIndex, isComplete } = useTypewriterLines({
    lines,
    baseDelayMs: 75,
    varianceMs: 10,
    pauseBetweenLinesMs,
    onComplete: handleComplete,
    enabled: true,
    prefersReducedMotion,
  });

  return (
    <div className="text-center space-y-4">
      <div 
        className={cn(
          "font-mono text-white text-sm md:text-base",
          "font-[family-name:var(--font-ibm-plex-mono),'IBM Plex Mono','SF Mono',Menlo,Monaco,Consolas,'Liberation Mono','Courier New',monospace]"
        )}
      >
        {displayedLines.map((line, index) => (
          <div key={index} className="min-h-[1.5em]">
            {line}
            {index === currentLineIndex && showCursor && (
              <span
                className="inline-block w-[2px] h-[1em] ml-[2px] align-middle"
                style={{
                  backgroundColor: '#4FF3F8',
                  opacity: prefersReducedMotion ? 0.6 : cursorOpacity,
                  animation: prefersReducedMotion ? 'none' : 'bootCursorBlink 0.55s step-end infinite',
                }}
              />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

