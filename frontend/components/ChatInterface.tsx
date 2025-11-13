"use client";

import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import { useWebSocket } from "@/lib/useWebSocket";
import { useVoiceRecorder } from "@/lib/useVoiceRecorder";
import MessageBubble from "./MessageBubble";
import TypingIndicator from "./TypingIndicator";
import InputArea from "./InputArea";
import ScrollToBottom from "./ScrollToBottom";
import HelpOverlay from "./HelpOverlay";
import KeyboardShortcutsOverlay from "./KeyboardShortcutsOverlay";
import RecordingIndicator from "./RecordingIndicator";
import SpotifyPlayer from "./SpotifyPlayer";
import { getApiBaseUrl, getWebSocketUrl } from "@/lib/apiConfig";
import logger from "@/lib/logger";
import { usePlanTelemetry } from "@/lib/usePlanTelemetry";
import Header from "./Header";
import PlanProgressRail from "./PlanProgressRail";
import ActiveStepChip from "./ActiveStepChip";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import { useBootContext } from "@/components/BootProvider";

const MAX_VISIBLE_MESSAGES = 200; // Limit to prevent performance issues

export default function ChatInterface() {
  const apiBaseUrl = useMemo(() => getApiBaseUrl(), []);
  const wsUrl = useMemo(() => getWebSocketUrl("/ws/chat"), []);
  const { messages: allMessages, isConnected, connectionState, lastError, planState, sendMessage, sendCommand } = useWebSocket(wsUrl);
  const { bootPhase, assetsLoaded, signalBootComplete, signalBootError } = useBootContext();
  const [planRailCollapsed, setPlanRailCollapsed] = useState(false);
  const [inputValue, setInputValue] = useState("");

  // Plan telemetry tracking
  const { getAnalytics } = usePlanTelemetry(planState);
  
  // Limit messages to prevent performance issues with very long conversations
  // Must be defined immediately after allMessages to avoid temporal dead zone issues
  const messages = useMemo(() => {
    if (allMessages.length <= MAX_VISIBLE_MESSAGES) {
      return allMessages;
    }
    return allMessages.slice(-MAX_VISIBLE_MESSAGES);
  }, [allMessages]);
  
  const createAbortController = useCallback((timeoutMs: number) => {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
    return { controller, timeoutId };
  }, []);

  const transcribeAudio = useCallback(async (audioBlob: Blob) => {
    setIsTranscribing(true);
    try {
      if (!audioBlob || audioBlob.size === 0) {
        throw new Error("No audio data recorded");
      }

      logger.info("Starting audio transcription", {
        audio_size_bytes: audioBlob.size,
        audio_type: audioBlob.type,
      });

      const formData = new FormData();
      formData.append("audio", audioBlob, "recording.webm");

      const { controller, timeoutId } = createAbortController(30000);
      let response: Response;

      try {
        logger.debug("Sending transcription request to API");
        response = await fetch(`${apiBaseUrl}/api/transcribe`, {
          method: "POST",
          body: formData,
          signal: controller.signal,
        });
      } finally {
        window.clearTimeout(timeoutId);
      }

      if (!response.ok) {
        let errorMessage = `Transcription failed (${response.status})`;
        try {
          const errorData = await response.json();
          errorMessage = errorData.detail || errorData.message || errorMessage;
        } catch {
          errorMessage = response.statusText || errorMessage;
        }
        logger.error("Transcription API error", new Error(errorMessage), {
          status: response.status,
          status_text: response.statusText,
        });
        throw new Error(errorMessage);
      }

      const data = await response.json();
      logger.info("Transcription successful", {
        transcript_length: data.text?.length || 0,
        transcript_preview: data.text?.substring(0, 50),
      });

      if (data.text && data.text.trim()) {
        sendMessage(data.text.trim());
        setVoiceError(null); // Clear any previous errors on success
        return;
      }

      throw new Error("No transcription text returned");
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      logger.error("Error transcribing audio", error, {
        error_name: error.name,
        error_message: error.message,
      });

      // Attempt a quick health check to provide clearer feedback
      let detailedMessage =
        error.name === "AbortError"
          ? "Transcription request timed out after 30 seconds"
          : error.message;
      try {
        const { controller: healthController, timeoutId: healthTimeout } = createAbortController(5000);
        try {
          const healthCheck = await fetch(`${apiBaseUrl}/api/stats`, {
            method: "GET",
            signal: healthController.signal,
          });

          if (healthCheck.ok) {
            detailedMessage += " (Server reachable, transcription endpoint returned an error)";
          } else {
            detailedMessage += ` (Server responded with status ${healthCheck.status})`;
          }
        } finally {
          window.clearTimeout(healthTimeout);
        }

      } catch (healthErr) {
        logger.error("Transcription health check failed", healthErr as Error, {
          api_base_url: apiBaseUrl,
        });
        detailedMessage += ` (Cannot reach API server at ${apiBaseUrl})`;
      }

      sendMessage(`❌ **Transcription Error:** ${detailedMessage}. Please try typing instead.`);
      setVoiceError(detailedMessage);
    } finally {
      setIsTranscribing(false);
    }
  }, [apiBaseUrl, createAbortController, sendMessage]);

  // Handle auto-stop transcription
  const handleAutoStopTranscription = useCallback(async (audioBlob: Blob) => {
    await transcribeAudio(audioBlob);
  }, [transcribeAudio]);

  const { isRecording, startRecording, stopRecording, error: voiceRecorderError } = useVoiceRecorder({
    onAutoStop: handleAutoStopTranscription,
  });
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const messageRefs = useRef<Map<number, HTMLDivElement>>(new Map());
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [showHelpOverlay, setShowHelpOverlay] = useState(false);
  const [showShortcutsOverlay, setShowShortcutsOverlay] = useState(false);
  const [voiceError, setVoiceError] = useState<string | null>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  // Check if assistant is currently processing
  const lastMessage = messages[messages.length - 1];
  const isProcessing = Boolean(
    lastMessage &&
    lastMessage.type === "status" &&
    ["processing", "cancelling"].includes(lastMessage.status || "")
  );

  // Handle voice recording
  const handleVoiceRecord = async () => {
    if (isRecording) {
      try {
        const audioBlob = await stopRecording();
        if (!audioBlob) return;
        await transcribeAudio(audioBlob);
      } catch (err) {
        console.error("[TRANSCRIBE] Error completing recording:", err);
      }
    } else {
      try {
        await startRecording();
      } catch (err) {
        console.error("[TRANSCRIBE] Error starting recording:", err);
      }
    }
  };

  // Handle stop recording from RecordingIndicator
  const handleStopRecording = useCallback(async () => {
    if (isRecording) {
      try {
        const audioBlob = await stopRecording();
        if (!audioBlob) return;
        await transcribeAudio(audioBlob);
      } catch (err) {
        console.error("[TRANSCRIBE] Error stopping recording:", err);
      }
    }
  }, [isRecording, stopRecording, transcribeAudio]);

  // Show voice error if any
  useEffect(() => {
    if (voiceError) {
      console.error("Voice recording error:", voiceError);
    }
  }, [voiceError]);

  const handleStopRequest = useCallback(() => {
    sendCommand("stop");
  }, [sendCommand]);

  const handleSend = useCallback((msg: string) => {
    sendMessage(msg);
    setInputValue("");
  }, [sendMessage]);

  const hasMessages = messages.length > 0;

  // Screen reader announcements for voice recording state changes
  const [screenReaderAnnouncement, setScreenReaderAnnouncement] = useState("");

  useEffect(() => {
    if (isRecording && !isTranscribing) {
      setScreenReaderAnnouncement("Voice recording started. Press Space or Escape to stop recording.");
    } else if (isTranscribing) {
      setScreenReaderAnnouncement("Recording stopped. Processing your voice...");
    } else if (!isRecording && !isTranscribing) {
      setScreenReaderAnnouncement("Voice recording ready.");
    }
  }, [isRecording, isTranscribing]);

  // Handle help, shortcuts, and voice recording keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: globalThis.KeyboardEvent) => {
      // Voice recording shortcuts (Space to toggle, Escape to stop)
      if (e.code === "Space" && !e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey) {
        // Only handle space if not in an input field and not composing
        const activeElement = document.activeElement as HTMLElement;
        const isInputField = activeElement?.tagName === "TEXTAREA" ||
                            activeElement?.tagName === "INPUT" ||
                            activeElement?.contentEditable === "true";

        if (!isInputField && !isProcessing && !isTranscribing) {
          e.preventDefault();
          handleVoiceRecord();
        }
      }

      // Escape to stop recording
      if (e.key === "Escape" && (isRecording || isTranscribing)) {
        e.preventDefault();
        if (isRecording) {
          handleStopRecording();
        }
      }

      // ⌘/ or ⌘? to show help
      if ((e.metaKey || e.ctrlKey) && (e.key === "/" || e.key === "?")) {
        e.preventDefault();
        setShowHelpOverlay(true);
      }
      // ? key when input not focused to show shortcuts
      if (e.key === "?" && !e.metaKey && !e.ctrlKey && document.activeElement?.tagName !== "TEXTAREA") {
        e.preventDefault();
        setShowShortcutsOverlay(true);
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isRecording, isTranscribing, isProcessing, handleVoiceRecord, handleStopRecording]);

  // Handle /help command
  useEffect(() => {
    if (inputValue.trim() === "/help") {
      setShowHelpOverlay(true);
      setInputValue("");
    }
  }, [inputValue]);

  // Signal boot completion when WebSocket is connected (assets are already loaded by this point)
  useEffect(() => {
    if (connectionState === "connected" && bootPhase !== "ready") {
      signalBootComplete();
    }
    // TEMPORARY: Force boot completion after 3 seconds for debugging
    else if (bootPhase === "websocket") {
      const timer = setTimeout(() => {
        console.log("🔧 TEMPORARY: Forcing boot completion");
        signalBootComplete();
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [connectionState, bootPhase, signalBootComplete]);

  // Signal boot error when WebSocket connection fails permanently
  useEffect(() => {
    if (connectionState === "error" && bootPhase !== "error") {
      signalBootError(lastError || "WebSocket connection failed");
    }
  }, [connectionState, bootPhase, lastError, signalBootError]);

  // Handle Bluesky notification actions
  useEffect(() => {
    const handleBlueskyAction = (event: CustomEvent) => {
      const { action, command } = event.detail;
      if (action === 'prefill-input' && command) {
        setInputValue(command);
      } else if (action === 'send-command' && command) {
        sendMessage(command);
      }
    };

    window.addEventListener('bluesky-action', handleBlueskyAction as EventListener);
    return () => {
      window.removeEventListener('bluesky-action', handleBlueskyAction as EventListener);
    };
  }, [sendMessage, setInputValue]);

  return (
    <>
      {/* Plan Progress Rail */}
      <PlanProgressRail
        planState={planState}
        isCollapsed={planRailCollapsed}
        onToggleCollapse={() => setPlanRailCollapsed(!planRailCollapsed)}
      />

      {/* Screen reader announcements */}
      <div
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
        role="status"
      >
        {screenReaderAnnouncement}
      </div>

      <div className="flex-1 flex flex-col min-h-0" role="main">
        <Header
          isConnected={isConnected}
          messageCount={messages.length}
          onClearSession={() => sendCommand("clear")}
          onShowHelp={() => setShowHelpOverlay(true)}
        />
        <div className="flex-1 flex flex-col">
          <div className="flex-1 w-full px-6 sm:px-8 lg:px-12" role="region" aria-label="Chat conversation">
            <div className="mx-auto flex h-full w-full max-w-4xl flex-col">
              <div className="flex-1 min-h-0 flex flex-col justify-end gap-6 py-6 sm:py-8 lg:py-10">
                <div
                  className={cn(
                    "flex-1 min-h-0",
                    hasMessages ? "overflow-hidden" : "flex items-center justify-center"
                  )}
                >
                  {!hasMessages ? (
                    <motion.div
                      className="w-full"
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.8, ease: [0.25, 0.1, 0.25, 1] }}
                    >
                      <motion.div
                        className="text-center max-w-3xl mx-auto space-y-8"
                        initial={{ scale: 0.95, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        transition={{ duration: 0.6, delay: 0.3, ease: [0.25, 0.1, 0.25, 1] }}
                      >
                        {/* Hero Section */}
                        <motion.div
                          className="glass-elevated rounded-3xl p-8 shadow-elevated backdrop-blur-glass"
                          whileHover={{ scale: 1.01 }}
                          transition={{ duration: 0.2, ease: "easeOut" }}
                        >
                          {/* Animated logo */}
                          <motion.div
                            className="mb-6 flex justify-center"
                            initial={{ scale: 0 }}
                            animate={{ scale: 1 }}
                            transition={{ duration: 0.5, delay: 0.6, type: "spring", bounce: 0.3 }}
                          >
                            <div className="w-20 h-20 rounded-3xl bg-gradient-to-br from-accent-primary to-accent-primary-hover flex items-center justify-center shadow-glow-primary">
                              <motion.span
                                className="text-3xl font-bold text-white"
                                animate={{ rotate: [0, -5, 5, 0] }}
                                transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
                              >
                                C
                              </motion.span>
                            </div>
                          </motion.div>

                          <motion.h1
                            className="text-5xl font-bold mb-4 text-text-primary"
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.6, delay: 0.8 }}
                          >
                            Welcome to Cerebro OS
                          </motion.h1>

                          <motion.p
                            className="text-text-muted text-xl mb-8 leading-relaxed"
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.6, delay: 1.0 }}
                          >
                            Your intelligent Mac assistant powered by AI. Ask me anything about your system,
                            automate tasks, or get help with your daily workflow.
                          </motion.p>
                        </motion.div>

                        {/* Suggestion Chips */}
                        <motion.div
                          className="flex flex-wrap justify-center gap-3"
                          initial={{ opacity: 0, y: 20 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ duration: 0.6, delay: 1.2 }}
                        >
                          {[
                            "Show me my system info",
                            "Check my email",
                            "Play some music",
                            "What's the weather like?",
                            "Help me organize files"
                          ].map((suggestion, index) => (
                            <motion.button
                              key={suggestion}
                              onClick={() => sendMessage(suggestion)}
                              className="px-4 py-3 bg-surface-elevated/80 hover:bg-surface-elevated/90 border border-surface-outline/30 rounded-xl text-text-primary font-medium transition-all duration-200 ease-out shadow-soft hover:shadow-medium"
                              whileHover={{ scale: 1.05, y: -2 }}
                              whileTap={{ scale: 0.95 }}
                              initial={{ opacity: 0, y: 20 }}
                              animate={{ opacity: 1, y: 0 }}
                              transition={{
                                duration: 0.4,
                                delay: 1.4 + index * 0.1,
                                ease: "easeOut"
                              }}
                            >
                              {suggestion}
                            </motion.button>
                          ))}
                        </motion.div>

                        {/* Keyboard hint */}
                        <motion.div
                          className="text-sm text-text-subtle"
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          transition={{ duration: 0.6, delay: 1.8 }}
                        >
                          <motion.span
                            animate={{ opacity: [0.6, 1, 0.6] }}
                            transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
                          >
                            Press ⌘K to start typing, or Space for voice commands
                          </motion.span>
                        </motion.div>
                      </motion.div>
                    </motion.div>
                  ) : (
                    <div
                      ref={messagesContainerRef}
                      className="flex-1 overflow-y-auto space-y-2 min-h-0 relative pb-6 sm:pb-8 lg:pb-10"
                      role="log"
                      aria-live="polite"
                      aria-label="Chat messages"
                    >
                      <AnimatePresence>
                        {messages.map((message, index) => (
                          <motion.div
                            key={index}
                            layout
                            ref={(el) => {
                              if (el) {
                                messageRefs.current.set(index, el);
                              } else {
                                messageRefs.current.delete(index);
                              }
                            }}
                            initial={{ opacity: 0, y: 12 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -12 }}
                            transition={{
                              duration: 0.18,
                              ease: [0, 0, 0.2, 1],
                              delay: Math.min(index * 0.08, 0.4) // Stagger up to 400ms max delay
                            }}
                          >
                            <MessageBubble message={message} index={index} planState={planState} />
                          </motion.div>
                        ))}
                      </AnimatePresence>
                      {(isProcessing || (lastMessage && lastMessage.type === "plan")) && <TypingIndicator />}
                      <div ref={messagesEndRef} />
                      {messagesContainerRef.current && (
                        <ScrollToBottom containerRef={messagesContainerRef} />
                      )}
                    </div>
                  )}
                </div>

                <AnimatePresence>
                  {connectionState === "error" && (
                    <motion.div
                      initial={{ opacity: 0, y: -10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -10 }}
                      transition={{ duration: 0.25, ease: "easeOut" }}
                      className="rounded-lg border border-danger-border bg-danger-bg px-4 py-2 text-center"
                      role="alert"
                      aria-live="assertive"
                    >
                      <p className="text-accent-danger text-sm">
                        {lastError || "Connection failed. Please refresh the page."}
                      </p>
                    </motion.div>
                  )}
                  {connectionState === "reconnecting" && (
                    <motion.div
                      initial={{ opacity: 0, y: -10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -10 }}
                      transition={{ duration: 0.25, ease: "easeOut" }}
                      className="rounded-lg border border-warning-border bg-warning-bg px-4 py-2 text-center"
                      role="alert"
                      aria-live="assertive"
                    >
                      <p className="text-warning text-sm">
                        Disconnected from server. Attempting to reconnect...
                      </p>
                    </motion.div>
                  )}
                </AnimatePresence>

                <div className="relative">
                  <div
                    className="pointer-events-none absolute inset-x-0 bottom-full h-20"
                    style={{
                      background:
                        "linear-gradient(to top, rgba(13, 13, 13, 0.95), rgba(13, 13, 13, 0.7), rgba(13, 13, 13, 0))",
                    }}
                    aria-hidden="true"
                  />
                  <div className="relative z-10 mx-auto w-full max-w-3xl pt-[clamp(1rem,2vh,2rem)] pb-[calc(env(safe-area-inset-bottom)+clamp(1.5rem,6vh,5rem))]">
                    {/* Active Step Chip */}
                    <div className="flex justify-center mb-3">
                      <ActiveStepChip planState={planState} />
                    </div>

                    <InputArea
                      onSend={handleSend}
                      disabled={!isConnected || isTranscribing}
                      onVoiceRecord={handleVoiceRecord}
                      isRecording={isRecording || isTranscribing}
                      initialValue={inputValue}
                      onValueChange={setInputValue}
                      isProcessing={isProcessing}
                      onStop={handleStopRequest}
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Recording Indicator */}
      <RecordingIndicator
        isRecording={isRecording}
        isTranscribing={isTranscribing}
        onStop={handleStopRecording}
        error={voiceError || voiceRecorderError}
        onRetry={() => {
          setVoiceError(null);
          handleVoiceRecord();
        }}
        onCancel={() => {
          setVoiceError(null);
        }}
      />

      {/* Help and Shortcuts Overlays */}
      <HelpOverlay isOpen={showHelpOverlay} onClose={() => setShowHelpOverlay(false)} />
      <KeyboardShortcutsOverlay
        isOpen={showShortcutsOverlay}
        onClose={() => setShowShortcutsOverlay(false)}
      />

      {/* Spotify Web Player */}
      <SpotifyPlayer />
    </>
  );
}
