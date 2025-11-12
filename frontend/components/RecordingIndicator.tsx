"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

interface RecordingIndicatorProps {
  isRecording: boolean;
  isTranscribing: boolean;
  onStop: () => void;
}

export default function RecordingIndicator({
  isRecording,
  isTranscribing,
  onStop,
}: RecordingIndicatorProps) {
  const [recordingTime, setRecordingTime] = useState(0);

  // Timer for recording duration
  useEffect(() => {
    let interval: NodeJS.Timeout | null = null;
    if (isRecording) {
      setRecordingTime(0);
      interval = setInterval(() => {
        setRecordingTime((prev) => prev + 1);
      }, 1000);
    } else {
      setRecordingTime(0);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isRecording]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  return (
    <AnimatePresence>
      {(isRecording || isTranscribing) && (
        <motion.div
          initial={{ opacity: 0, y: 20, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 20, scale: 0.95 }}
          transition={{ duration: 0.3, ease: "easeOut" }}
          className="fixed bottom-24 left-1/2 transform -translate-x-1/2 z-50"
        >
          {/* Pulsing rings effect - ChatGPT style */}
          {isRecording && (
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              {[0, 1, 2].map((i) => (
                <motion.div
                  key={i}
                  className="absolute rounded-full border-2 border-red-500/30"
                  initial={{ width: 0, height: 0, opacity: 0.8 }}
                  animate={{
                    width: 200 + i * 40,
                    height: 200 + i * 40,
                    opacity: [0.8, 0.4, 0],
                  }}
                  transition={{
                    duration: 2,
                    repeat: Infinity,
                    delay: i * 0.3,
                    ease: "easeOut",
                  }}
                />
              ))}
            </div>
          )}

          <div className="relative glass rounded-2xl p-6 shadow-2xl border border-white/20 min-w-[320px] backdrop-blur-xl">
            {/* Glow effect when recording */}
            {isRecording && (
              <motion.div
                className="absolute inset-0 rounded-2xl bg-red-500/10 blur-xl -z-10"
                animate={{
                  opacity: [0.3, 0.6, 0.3],
                }}
                transition={{
                  duration: 2,
                  repeat: Infinity,
                  ease: "easeInOut",
                }}
              />
            )}

            {isTranscribing ? (
              <div className="flex items-center justify-center space-x-4">
                <div className="flex space-x-1">
                  {[0, 1, 2].map((i) => (
                    <motion.div
                      key={i}
                      className="w-2 h-8 bg-accent-cyan rounded-full"
                      animate={{
                        height: [8, 24, 8],
                        opacity: [0.5, 1, 0.5],
                      }}
                      transition={{
                        duration: 0.6,
                        repeat: Infinity,
                        delay: i * 0.2,
                        ease: "easeInOut",
                      }}
                    />
                  ))}
                </div>
                <div className="text-white font-medium">Transcribing...</div>
              </div>
            ) : (
              <div className="flex flex-col items-center space-y-4">
                {/* Enhanced waveform animation */}
                <div className="flex items-center justify-center space-x-0.5 h-16 relative">
                  {Array.from({ length: 24 }).map((_, i) => {
                    // More dynamic animation with varying patterns
                    const pattern = i % 4;
                    const baseHeight = pattern === 0 ? 4 : pattern === 1 ? 8 : pattern === 2 ? 12 : 6;
                    const peakHeight = pattern === 0 ? 20 : pattern === 1 ? 32 : pattern === 2 ? 28 : 24;
                    const duration = 0.3 + (pattern * 0.1);
                    const delay = i * 0.03;
                    
                    return (
                      <motion.div
                        key={i}
                        className="w-1.5 bg-gradient-to-t from-red-500 to-red-400 rounded-full shadow-sm"
                        style={{
                          boxShadow: "0 0 4px rgba(239, 68, 68, 0.5)",
                        }}
                        animate={{
                          height: [baseHeight, peakHeight, baseHeight],
                          opacity: [0.4, 1, 0.4],
                        }}
                        transition={{
                          duration: duration,
                          repeat: Infinity,
                          delay: delay,
                          ease: "easeInOut",
                        }}
                      />
                    );
                  })}
                </div>

                {/* Recording status and timer */}
                <div className="flex items-center space-x-3">
                  <div className="flex items-center space-x-2">
                    <motion.div
                      className="w-3 h-3 bg-red-500 rounded-full relative"
                      animate={{ 
                        opacity: [1, 0.6, 1],
                        scale: [1, 1.2, 1],
                      }}
                      transition={{
                        duration: 1.5,
                        repeat: Infinity,
                        ease: "easeInOut",
                      }}
                    >
                      {/* Inner pulse */}
                      <motion.div
                        className="absolute inset-0 bg-red-500 rounded-full"
                        animate={{
                          scale: [1, 1.8],
                          opacity: [0.6, 0],
                        }}
                        transition={{
                          duration: 1.5,
                          repeat: Infinity,
                          ease: "easeOut",
                        }}
                      />
                    </motion.div>
                    <span className="text-white font-medium">Recording</span>
                  </div>
                  <span className="text-white/60 font-mono text-sm">
                    {formatTime(recordingTime)}
                  </span>
                </div>

                {/* Stop button with enhanced styling */}
                <motion.button
                  onClick={onStop}
                  className="flex items-center space-x-2 px-6 py-3 bg-red-500 hover:bg-red-600 text-white rounded-xl font-medium transition-all duration-200 shadow-lg relative overflow-hidden"
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                >
                  <motion.div
                    className="absolute inset-0 bg-white/20"
                    initial={{ x: "-100%" }}
                    whileHover={{ x: "100%" }}
                    transition={{ duration: 0.5 }}
                  />
                  <svg
                    className="w-5 h-5 relative z-10"
                    fill="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path d="M6 6h12v12H6z" />
                  </svg>
                  <span className="relative z-10">Stop Recording</span>
                </motion.button>
              </div>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

