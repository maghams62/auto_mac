'use client';

import { motion } from "framer-motion";
import { useEffect, useState } from "react";

type CMonogramProps = {
  size?: number;
  strokeWidth?: number;
  color?: string;
  prefersReducedMotion?: boolean;
  onComplete?: () => void;
  startDelay?: number;
};

export default function CMonogram({ 
  size = 80, 
  strokeWidth = 3,
  color = "#8E8E8E",
  prefersReducedMotion = false,
  onComplete,
  startDelay = 0,
}: CMonogramProps) {
  const [animationPhase, setAnimationPhase] = useState<'idle' | 'draw' | 'glow' | 'scale' | 'complete'>('idle');
  
  // SVG path for a clean "C" monogram
  // This creates a stylized C that looks like it's drawn by a plotter
  // Starting from top-right, curving around to bottom-right
  const pathData = "M 55 25 Q 60 20, 60 15 Q 60 10, 55 10 Q 45 10, 35 15 Q 25 20, 25 30 Q 25 40, 25 50 Q 25 60, 25 65 Q 25 70, 30 70 Q 35 70, 40 68 Q 45 66, 50 63";
  
  // Calculate path length for stroke-dasharray animation
  const pathLength = 140; // Approximate path length

  useEffect(() => {
    if (prefersReducedMotion) {
      setAnimationPhase('complete');
      onComplete?.();
      return;
    }

    // Start delay
    const startTimer = setTimeout(() => {
      setAnimationPhase('draw');
      
      // Phase 1: Draw (0-500ms)
      const drawTimer = setTimeout(() => {
        setAnimationPhase('glow');
        
        // Phase 2: Glow/Pulse (500-900ms)
        const glowTimer = setTimeout(() => {
          setAnimationPhase('scale');
          
          // Phase 3: Scale pulse (900-1200ms)
          const scaleTimer = setTimeout(() => {
            setAnimationPhase('complete');
            onComplete?.();
          }, 300);
          
          return () => clearTimeout(scaleTimer);
        }, 400);
        
        return () => clearTimeout(glowTimer);
      }, 500);
      
      return () => clearTimeout(drawTimer);
    }, startDelay);

    return () => clearTimeout(startTimer);
  }, [prefersReducedMotion, onComplete, startDelay]);

  // Glow filter with cyan/purple mix
  const glowFilterId = `glow-${Math.random().toString(36).slice(2, 11)}`;

  return (
    <motion.svg
      width={size}
      height={size}
      viewBox="0 0 80 80"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.2 }}
      className="relative"
    >
      <defs>
        {/* Glow filter with cyan/purple mix */}
        <filter id={glowFilterId} x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="1.5" result="coloredBlur"/>
          <feOffset in="coloredBlur" dx="0" dy="0" result="offsetBlur"/>
          <feFlood floodColor="#4FF3F8" floodOpacity={animationPhase === 'glow' || animationPhase === 'scale' ? 0.4 : 0.2} result="cyan"/>
          <feFlood floodColor="#C874FF" floodOpacity={animationPhase === 'glow' || animationPhase === 'scale' ? 0.3 : 0.15} result="purple"/>
          <feComposite in="cyan" in2="offsetBlur" operator="in" result="cyanGlow"/>
          <feComposite in="purple" in2="offsetBlur" operator="in" result="purpleGlow"/>
          <feMerge>
            <feMergeNode in="cyanGlow"/>
            <feMergeNode in="purpleGlow"/>
            <feMergeNode in="SourceGraphic"/>
          </feMerge>
        </filter>
      </defs>
      
      {/* The C path with stroke animation */}
      <motion.path
        d={pathData}
        fill="none"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
        filter={`url(#${glowFilterId})`}
        initial={prefersReducedMotion ? { pathLength: 1, scale: 1 } : { pathLength: 0, scale: 1 }}
        animate={
          prefersReducedMotion 
            ? { pathLength: 1, scale: 1 }
            : {
                pathLength: animationPhase === 'idle' ? 0 : 1,
                scale: animationPhase === 'scale' ? [1, 1.03, 1] : 1,
              }
        }
        transition={
          prefersReducedMotion
            ? {}
            : {
                pathLength: {
                  duration: animationPhase === 'draw' ? 0.5 : 0,
                  ease: [0.43, 0.13, 0.23, 0.96],
                },
                scale: {
                  duration: 0.3,
                  times: [0, 0.5, 1],
                  ease: "easeInOut",
                },
              }
        }
        style={{
          strokeDasharray: pathLength,
          strokeDashoffset: 0,
          transformOrigin: 'center',
        }}
      />
    </motion.svg>
  );
}

