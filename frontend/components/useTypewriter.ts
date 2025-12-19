import { useState, useEffect, useRef } from 'react';

type UseTypewriterOptions = {
  text: string;
  speed?: {
    start: number;      // First 3 chars
    middle: number;     // Middle chars
    end: number;        // Last 2 chars
  };
  jitter?: number;      // Random jitter in ms (±jitter)
  onComplete?: () => void;
  enabled?: boolean;
};

export function useTypewriter({
  text,
  speed = { start: 110, middle: 130, end: 165 },
  jitter = 10,
  onComplete,
  enabled = true,
}: UseTypewriterOptions) {
  const [displayedText, setDisplayedText] = useState('');
  const [isComplete, setIsComplete] = useState(false);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const indexRef = useRef(0);
  const wasEnabledRef = useRef(enabled);
  const previousTextRef = useRef(text);
  const isTypingRef = useRef(false);
  
  // Store callbacks and config in refs to avoid dependency issues
  const onCompleteRef = useRef(onComplete);
  const speedRef = useRef(speed);
  const jitterRef = useRef(jitter);
  
  // Update refs when values change (but don't trigger effect)
  useEffect(() => {
    onCompleteRef.current = onComplete;
    speedRef.current = speed;
    jitterRef.current = jitter;
  }, [onComplete, speed, jitter]);

  useEffect(() => {
    // Reset when disabled or text is empty
    if (!enabled || text.length === 0) {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
      isTypingRef.current = false;
      if (!enabled) {
        // Don't reset state when just disabled, keep progress
        return;
      }
      // Reset state when text is empty
      setDisplayedText('');
      setIsComplete(false);
      indexRef.current = 0;
      previousTextRef.current = text;
      return;
    }

    // Check if text actually changed
    const textChanged = previousTextRef.current !== text;
    
    // Reset when enabled changes from false to true OR when text changes
    if ((!wasEnabledRef.current && enabled) || textChanged) {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
      isTypingRef.current = false;
      indexRef.current = 0;
      setDisplayedText('');
      setIsComplete(false);
      previousTextRef.current = text;
    }
    wasEnabledRef.current = enabled;

    // Only start typing if we're not already typing and we should be
    if (!isTypingRef.current && enabled && text.length > 0) {
      isTypingRef.current = true;
      
      const typeNextChar = () => {
        // Check if we're still enabled and text hasn't changed
        if (!enabled || previousTextRef.current !== text || indexRef.current >= text.length) {
          if (indexRef.current >= text.length) {
            setIsComplete(true);
            isTypingRef.current = false;
            onCompleteRef.current?.();
          }
          return;
        }

        const currentIndex = indexRef.current;
        const currentSpeed = speedRef.current;
        const currentJitter = jitterRef.current;
        
        // Determine speed based on position
        let baseSpeed: number;
        if (currentIndex < 3) {
          baseSpeed = currentSpeed.start;
        } else if (currentIndex >= text.length - 2) {
          baseSpeed = currentSpeed.end;
        } else {
          baseSpeed = currentSpeed.middle;
        }

        // Add random jitter
        const jitterAmount = (Math.random() * 2 - 1) * currentJitter; // -jitter to +jitter
        const delay = Math.max(50, baseSpeed + jitterAmount); // Minimum 50ms

        timeoutRef.current = setTimeout(() => {
          // Double-check conditions before updating
          if (enabled && previousTextRef.current === text && indexRef.current < text.length) {
            setDisplayedText(text.slice(0, indexRef.current + 1));
            indexRef.current = indexRef.current + 1;
            typeNextChar();
          } else {
            isTypingRef.current = false;
            if (indexRef.current >= text.length) {
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
  }, [text, enabled]); // Only depend on text and enabled, not speed/jitter/onComplete

  return { displayedText, isComplete };
}

