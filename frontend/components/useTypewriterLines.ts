import { useState, useEffect, useRef } from 'react';

type UseTypewriterLinesOptions = {
  lines: string[];
  baseDelayMs?: number;
  varianceMs?: number;
  pauseBetweenLinesMs?: number[];
  onComplete?: () => void;
  enabled?: boolean;
  prefersReducedMotion?: boolean;
};

export function useTypewriterLines({
  lines,
  baseDelayMs = 75,
  varianceMs = 10,
  pauseBetweenLinesMs = [],
  onComplete,
  enabled = true,
  prefersReducedMotion = false,
}: UseTypewriterLinesOptions) {
  const [displayedLines, setDisplayedLines] = useState<string[]>([]);
  const [currentLineIndex, setCurrentLineIndex] = useState(0);
  const [isComplete, setIsComplete] = useState(false);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const lineIndexRef = useRef(0);
  const charIndexRef = useRef(0);
  const wasEnabledRef = useRef(enabled);
  const previousLinesRef = useRef(lines);
  const isTypingRef = useRef(false);
  
  // Store callbacks and config in refs to avoid dependency issues
  const onCompleteRef = useRef(onComplete);
  const baseDelayMsRef = useRef(baseDelayMs);
  const varianceMsRef = useRef(varianceMs);
  const pauseBetweenLinesMsRef = useRef(pauseBetweenLinesMs);
  
  // Update refs when values change (but don't trigger effect)
  useEffect(() => {
    onCompleteRef.current = onComplete;
    baseDelayMsRef.current = baseDelayMs;
    varianceMsRef.current = varianceMs;
    pauseBetweenLinesMsRef.current = pauseBetweenLinesMs;
  }, [onComplete, baseDelayMs, varianceMs, pauseBetweenLinesMs]);

  useEffect(() => {
    // If reduced motion, show all text immediately
    if (prefersReducedMotion && enabled && lines.length > 0) {
      setDisplayedLines(lines);
      setCurrentLineIndex(lines.length - 1);
      setIsComplete(true);
      onCompleteRef.current?.();
      return;
    }

    // Reset when disabled or lines are empty
    if (!enabled || lines.length === 0) {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
      isTypingRef.current = false;
      if (!enabled) {
        return;
      }
      setDisplayedLines([]);
      setIsComplete(false);
      lineIndexRef.current = 0;
      charIndexRef.current = 0;
      previousLinesRef.current = lines;
      return;
    }

    // Check if lines actually changed
    const linesChanged = previousLinesRef.current.length !== lines.length || 
      previousLinesRef.current.some((line, idx) => line !== lines[idx]);
    
    // Reset when enabled changes from false to true OR when lines change
    if ((!wasEnabledRef.current && enabled) || linesChanged) {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
      isTypingRef.current = false;
      lineIndexRef.current = 0;
      charIndexRef.current = 0;
      setDisplayedLines([]);
      setIsComplete(false);
      previousLinesRef.current = lines;
    }
    wasEnabledRef.current = enabled;

    // Only start typing if we're not already typing and we should be
    if (!isTypingRef.current && enabled && lines.length > 0) {
      isTypingRef.current = true;
      
      const typeNextChar = () => {
        // Check if we're still enabled and lines haven't changed
        const currentLines = previousLinesRef.current;
        const linesStillMatch = currentLines.length === lines.length && 
          currentLines.every((line, idx) => line === lines[idx]);
        
        if (!enabled || !linesStillMatch || lineIndexRef.current >= lines.length) {
          if (lineIndexRef.current >= lines.length) {
            setIsComplete(true);
            isTypingRef.current = false;
            onCompleteRef.current?.();
          }
          return;
        }

        // Check if we've completed all lines
        if (lineIndexRef.current >= lines.length) {
          setIsComplete(true);
          isTypingRef.current = false;
          onCompleteRef.current?.();
          return;
        }

        const currentLine = currentLines[lineIndexRef.current];
        
        // Check if we've completed the current line
        if (charIndexRef.current >= currentLine.length) {
          // Ensure the current line is fully displayed
          setDisplayedLines(prev => {
            const newLines = [...prev];
            newLines[lineIndexRef.current] = currentLine;
            return newLines;
          });
          
          // Add pause between lines if specified
          const pauseMs = pauseBetweenLinesMsRef.current[lineIndexRef.current] || 0;
          
          if (pauseMs > 0) {
            timeoutRef.current = setTimeout(() => {
              // Double-check conditions
              const linesStillMatch = currentLines.length === lines.length && 
                currentLines.every((line, idx) => line === lines[idx]);
              if (enabled && linesStillMatch && lineIndexRef.current < lines.length) {
                // Move to next line
                lineIndexRef.current += 1;
                charIndexRef.current = 0;
                setCurrentLineIndex(lineIndexRef.current);
                
                if (lineIndexRef.current < lines.length) {
                  typeNextChar();
                } else {
                  setIsComplete(true);
                  isTypingRef.current = false;
                  onCompleteRef.current?.();
                }
              } else {
                isTypingRef.current = false;
              }
            }, pauseMs);
          } else {
            // Move to next line immediately
            lineIndexRef.current += 1;
            charIndexRef.current = 0;
            setCurrentLineIndex(lineIndexRef.current);
            
            if (lineIndexRef.current < lines.length) {
              typeNextChar();
            } else {
              setIsComplete(true);
              isTypingRef.current = false;
              onCompleteRef.current?.();
            }
          }
          return;
        }

        // Add random jitter
        const jitterAmount = (Math.random() * 2 - 1) * varianceMsRef.current; // -varianceMs to +varianceMs
        const delay = Math.max(50, baseDelayMsRef.current + jitterAmount); // Minimum 50ms

        timeoutRef.current = setTimeout(() => {
          // Double-check conditions before updating
          const linesStillMatch = currentLines.length === lines.length && 
            currentLines.every((line, idx) => line === lines[idx]);
          if (enabled && linesStillMatch && 
              lineIndexRef.current < lines.length && 
              charIndexRef.current < lines[lineIndexRef.current].length) {
            const newCharIndex = charIndexRef.current + 1;
            charIndexRef.current = newCharIndex;
            
            // Update displayed lines
            setDisplayedLines(prev => {
              const newLines = [...prev];
              if (newLines[lineIndexRef.current] === undefined) {
                newLines[lineIndexRef.current] = '';
              }
              newLines[lineIndexRef.current] = lines[lineIndexRef.current].slice(0, newCharIndex);
              return newLines;
            });
            
            typeNextChar();
          } else {
            isTypingRef.current = false;
            if (lineIndexRef.current >= lines.length) {
              setIsComplete(true);
              onCompleteRef.current?.();
            }
          }
        }, delay);
      };

      typeNextChar();
    }

    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
      isTypingRef.current = false;
    };
  }, [lines, enabled, prefersReducedMotion]); // Only depend on lines, enabled, and prefersReducedMotion

  return { displayedLines, currentLineIndex, isComplete };
}

