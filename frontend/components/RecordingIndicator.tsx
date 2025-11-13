"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";

interface RecordingIndicatorProps {
  isRecording: boolean;
  isTranscribing: boolean;
  onStop: () => void;
  error?: string | null;
  onRetry?: () => void;
  onCancel?: () => void;
}

export default function RecordingIndicator({
  isRecording,
  isTranscribing,
  onStop,
  error,
  onRetry,
  onCancel,
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

  // Prevent body scroll when modal is open
  useEffect(() => {
    if (isRecording || isTranscribing || error) {
      const originalStyle = window.getComputedStyle(document.body).overflow;
      document.body.style.overflow = 'hidden';
      return () => {
        document.body.style.overflow = originalStyle;
      };
    }
  }, [isRecording, isTranscribing, error]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  return (
    <AnimatePresence>
      {(isRecording || isTranscribing || error) && (
        <>
          {/* Backdrop - Fixed to viewport */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 bg-black/40 backdrop-blur-sm z-40"
            onClick={onStop}
          />

          {/* Modal - Fixed to viewport, always centered */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 20 }}
            transition={{ duration: 0.3, ease: [0.25, 0.1, 0.25, 1] }}
            className="fixed inset-0 flex items-center justify-center z-50 p-4 pointer-events-none"
          >
            <div className="relative w-full max-w-sm pointer-events-auto">
              {/* Pulsing background rings */}
              {isRecording && (
                <>
                  <motion.div
                    className="absolute inset-0 rounded-3xl border-2 border-accent-danger/30"
                    animate={{
                      scale: [1, 1.2, 1],
                      opacity: [0.3, 0, 0.3],
                    }}
                    transition={{
                      duration: 1.5,
                      repeat: Infinity,
                      ease: "easeInOut",
                    }}
                  />
                  <motion.div
                    className="absolute inset-0 rounded-3xl border-2 border-accent-danger/20"
                    animate={{
                      scale: [1, 1.4, 1],
                      opacity: [0.2, 0, 0.2],
                    }}
                    transition={{
                      duration: 1.5,
                      repeat: Infinity,
                      ease: "easeInOut",
                      delay: 0.5,
                    }}
                  />
                </>
              )}

              {/* Main modal */}
              <motion.div
                className={cn(
                  "relative rounded-3xl p-8 shadow-elevated backdrop-blur-glass border min-h-[300px] flex flex-col items-center justify-center",
                  isRecording
                    ? "bg-glass-elevated border-accent-danger/20"
                    : "bg-glass-elevated border-accent-cyan/20"
                )}
                animate={isRecording ? {
                  boxShadow: [
                    "0 20px 60px rgba(0, 0, 0, 0.35)",
                    "0 20px 60px rgba(239, 68, 68, 0.15)",
                    "0 20px 60px rgba(0, 0, 0, 0.35)"
                  ]
                } : {}}
                transition={{
                  duration: 1.5,
                  repeat: isRecording ? Infinity : 0,
                  ease: "easeInOut"
                }}
              >
                {error ? (
                  /* Error State */
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex flex-col items-center space-y-6 text-center"
                  >
                    {/* Error icon */}
                    <motion.div
                      className="w-16 h-16 rounded-full bg-accent-danger/10 flex items-center justify-center"
                      animate={{
                        scale: [1, 1.1, 1],
                      }}
                      transition={{
                        duration: 1.5,
                        repeat: Infinity,
                        ease: "easeInOut",
                      }}
                    >
                      <svg
                        className="w-8 h-8 text-accent-danger"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"
                        />
                      </svg>
                    </motion.div>

                    {/* Error message */}
                    <div className="space-y-3">
                      <h3 className="text-xl font-semibold text-text-primary">
                        Recording Failed
                      </h3>
                      <p className="text-sm text-text-muted max-w-xs">
                        {error || "An unexpected error occurred while recording."}
                      </p>
                    </div>

                    {/* Action buttons */}
                    <div className="flex items-center space-x-3">
                      {onRetry && (
                        <motion.button
                          onClick={onRetry}
                          className="flex items-center space-x-2 px-6 py-3 bg-accent-primary hover:bg-accent-primary-hover text-white rounded-xl font-medium transition-all"
                          whileHover={{ scale: 1.02 }}
                          whileTap={{ scale: 0.98 }}
                          aria-label="Retry voice recording"
                        >
                          <svg
                            className="w-5 h-5"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                            />
                          </svg>
                          <span>Try Again</span>
                        </motion.button>
                      )}

                      <motion.button
                        onClick={onCancel || onStop}
                        className="flex items-center space-x-2 px-6 py-3 bg-glass-hover hover:bg-glass-elevated text-text-primary rounded-xl font-medium transition-all border border-glass"
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                        aria-label="Cancel and close"
                      >
                        <span>Cancel</span>
                      </motion.button>
                    </div>
                  </motion.div>
                ) : isTranscribing ? (
                  /* Transcribing State */
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex flex-col items-center space-y-6 text-center"
                  >
                    {/* Processing animation */}
                    <motion.div
                      className="flex items-end justify-center space-x-1 h-12"
                      animate={{
                        scale: [1, 1.05, 1],
                      }}
                      transition={{
                        duration: 1.5,
                        repeat: Infinity,
                        ease: "easeInOut",
                      }}
                    >
                      {[0, 1, 2, 3].map((i) => (
                        <motion.div
                          key={i}
                          className="w-2 bg-accent-cyan rounded-full"
                          animate={{
                            height: [8, 24, 8],
                            opacity: [0.4, 1, 0.4],
                          }}
                          transition={{
                            duration: 0.8,
                            repeat: Infinity,
                            ease: "easeInOut",
                            delay: i * 0.1,
                          }}
                        />
                      ))}
                    </motion.div>

                    {/* Status text */}
                    <div className="space-y-2">
                      <motion.h3
                        className="text-xl font-semibold text-text-primary"
                        animate={{ opacity: [0.7, 1, 0.7] }}
                        transition={{
                          duration: 1.5,
                          repeat: Infinity,
                          ease: "easeInOut"
                        }}
                      >
                        Processing your voice...
                      </motion.h3>
                      <p className="text-sm text-text-muted">
                        Converting speech to text
                      </p>
                    </div>
                  </motion.div>
                ) : (
                  /* Recording State */
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex flex-col items-center space-y-6 text-center"
                  >
                    {/* Enhanced waveform */}
                    <motion.div
                      className="flex items-center justify-center space-x-1 h-16 relative"
                      animate={{
                        scale: [1, 1.02, 1],
                      }}
                      transition={{
                        duration: 1,
                        repeat: Infinity,
                        ease: "easeInOut",
                      }}
                    >
                      {Array.from({ length: 15 }).map((_, i) => (
                        <motion.div
                          key={i}
                          className="w-1 bg-gradient-to-t from-accent-danger to-accent-danger/60 rounded-full"
                          animate={{
                            height: [
                              8 + Math.sin(i * 0.3) * 4,
                              16 + Math.sin(i * 0.3) * 8,
                              8 + Math.sin(i * 0.3) * 4
                            ],
                            opacity: [
                              0.4 + Math.cos(i * 0.2) * 0.3,
                              0.8 + Math.cos(i * 0.2) * 0.2,
                              0.4 + Math.cos(i * 0.2) * 0.3
                            ],
                          }}
                          transition={{
                            duration: 0.8,
                            repeat: Infinity,
                            ease: "easeInOut",
                            delay: i * 0.06,
                          }}
                        />
                      ))}
                    </motion.div>

                    {/* Recording status */}
                    <div className="space-y-3">
                      <div className="flex items-center justify-center space-x-3">
                        <motion.div
                          className="w-3 h-3 bg-accent-danger rounded-full"
                          animate={{
                            scale: [1, 1.2, 1],
                            opacity: [1, 0.7, 1],
                          }}
                          transition={{
                            duration: 1,
                            repeat: Infinity,
                            ease: "easeInOut",
                          }}
                        />
                        <span className="text-lg font-medium text-text-primary">
                          Listening...
                        </span>
                      </div>

                      <div className="text-sm text-text-muted font-mono">
                        {formatTime(recordingTime)}
                      </div>
                    </div>

                    {/* Stop button */}
                    <motion.button
                      onClick={onStop}
                      className="flex items-center space-x-3 px-8 py-4 bg-accent-danger hover:bg-accent-danger/90 text-white rounded-2xl font-medium transition-all shadow-lg"
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                      aria-label="Stop voice recording"
                    >
                      <motion.svg
                        className="w-6 h-6"
                        fill="currentColor"
                        viewBox="0 0 24 24"
                        animate={{ scale: [1, 1.1, 1] }}
                        transition={{
                          duration: 0.5,
                          repeat: Infinity,
                          ease: "easeInOut",
                        }}
                      >
                        <path d="M6 6h12v12H6z" />
                      </motion.svg>
                      <span>Stop Recording</span>
                    </motion.button>

                    {/* Hint text */}
                    <p className="text-xs text-text-subtle">
                      Recording stops automatically after 5 seconds of silence
                    </p>
                  </motion.div>
                )}
              </motion.div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

