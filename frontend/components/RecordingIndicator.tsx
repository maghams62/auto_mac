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
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 20 }}
          transition={{ duration: 0.3 }}
          className="fixed bottom-24 left-1/2 transform -translate-x-1/2 z-50"
        >
          <div className="glass rounded-2xl p-6 shadow-2xl border border-white/20 min-w-[320px]">
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
                {/* Waveform animation */}
                <div className="flex items-center justify-center space-x-1 h-12">
                  {Array.from({ length: 20 }).map((_, i) => {
                    // Use deterministic values based on index for consistent animation
                    const baseHeight = 8 + (i % 3) * 4;
                    const peakHeight = 16 + (i % 5) * 3;
                    const duration = 0.4 + (i % 3) * 0.15;
                    return (
                      <motion.div
                        key={i}
                        className="w-1 bg-red-400 rounded-full"
                        animate={{
                          height: [baseHeight, peakHeight, baseHeight],
                          opacity: [0.6, 1, 0.6],
                        }}
                        transition={{
                          duration: duration,
                          repeat: Infinity,
                          delay: i * 0.05,
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
                      className="w-3 h-3 bg-red-500 rounded-full"
                      animate={{ opacity: [1, 0.5, 1] }}
                      transition={{
                        duration: 1,
                        repeat: Infinity,
                        ease: "easeInOut",
                      }}
                    />
                    <span className="text-white font-medium">Recording</span>
                  </div>
                  <span className="text-white/60 font-mono text-sm">
                    {formatTime(recordingTime)}
                  </span>
                </div>

                {/* Stop button */}
                <button
                  onClick={onStop}
                  className="flex items-center space-x-2 px-6 py-3 bg-red-500 hover:bg-red-600 text-white rounded-xl font-medium transition-all duration-200 hover:scale-105 active:scale-95 shadow-lg"
                >
                  <svg
                    className="w-5 h-5"
                    fill="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path d="M6 6h12v12H6z" />
                  </svg>
                  <span>Stop Recording</span>
                </button>
              </div>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

