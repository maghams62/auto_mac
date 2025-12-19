"use client";

import { useEffect, useRef, useState, useCallback, useMemo, lazy, Suspense } from "react";
import { useWebSocket, PlanState } from "@/lib/useWebSocket";
import { useVoiceRecorder } from "@/lib/useVoiceRecorder";
import MessageBubble from "./MessageBubble";
import TypingIndicator from "./TypingIndicator";
import InputArea from "./InputArea";
import ScrollToBottom from "./ScrollToBottom";
import RecordingIndicator from "./RecordingIndicator";
import { getApiBaseUrl, getWebSocketUrl } from "@/lib/apiConfig";
import logger from "@/lib/logger";
import { usePlanTelemetry } from "@/lib/usePlanTelemetry";
import Header from "./Header";
import FeedbackBar, { FeedbackChoice } from "./FeedbackBar";
import ActiveStepChip from "./ActiveStepChip";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import { useBootContext } from "@/components/BootProvider";
import { useGlobalEventBus } from "@/lib/telemetry";
import { useToast } from "@/lib/useToast";
import { useSharedSessionId } from "@/lib/useSharedSessionId";

// Lazy load non-critical components to improve initial load time
const HelpOverlay = lazy(() => import("./HelpOverlay"));
const KeyboardShortcutsOverlay = lazy(() => import("./KeyboardShortcutsOverlay"));
const SpotifyPlayer = lazy(() => import("./SpotifyPlayer"));
const ReasoningTrace = lazy(() => import("./ReasoningTrace"));

const MAX_VISIBLE_MESSAGES = 200; // Limit to prevent performance issues

type FinalPlanStatus = PlanState["status"];

interface PendingFeedbackState {
  planId: string;
  goal: string;
  planStatus: FinalPlanStatus;
  startedAt?: string;
  completedAt?: string;
}

type SlashCommandTelemetryPayload = {
  command: string;
  invocation_source?: string;
  query?: string;
};

const isSlashCommandTelemetryPayload = (
  payload?: Record<string, any>
): payload is SlashCommandTelemetryPayload => {
  return typeof payload?.command === "string";
};

const FINAL_PLAN_STATUSES = new Set<FinalPlanStatus>(["completed", "failed", "cancelled"]);

export default function ChatInterface() {
  const apiBaseUrl = useMemo(() => getApiBaseUrl(), []);
  const sessionId = useSharedSessionId();
  const wsUrl = useMemo(() => {
    if (!sessionId) {
      return "";
    }
    const resolved = new URL(getWebSocketUrl("/ws/chat"));
    resolved.searchParams.set("session_id", sessionId);
    return resolved.toString();
  }, [sessionId]);
  const { messages: allMessages, isConnected, connectionState, lastError, planState, sendMessage, sendCommand } = useWebSocket(wsUrl);
  const { bootPhase, assetsLoaded, signalBootComplete, signalBootError } = useBootContext();
  const [showReasoningTrace, setShowReasoningTrace] = useState(false);
  const [inputValue, setInputValue] = useState("");
  const { addToast } = useToast();
  const [pendingFeedback, setPendingFeedback] = useState<PendingFeedbackState | null>(null);
  const [isFeedbackSubmitting, setIsFeedbackSubmitting] = useState(false);
  const submittedPlanIdsRef = useRef<Set<string>>(new Set());

  // Plan telemetry tracking
  const { currentTelemetry, getAnalytics } = usePlanTelemetry(planState);
  
  // Limit messages to prevent performance issues with very long conversations
  // Must be defined immediately after allMessages to avoid temporal dead zone issues
  const messages = useMemo(() => {
    if (allMessages.length <= MAX_VISIBLE_MESSAGES) {
      return allMessages;
    }
    return allMessages.slice(-MAX_VISIBLE_MESSAGES);
  }, [allMessages]);

  const isPlanActive = Boolean(planState && (planState.status === "planning" || planState.status === "executing"));

  useEffect(() => {
    if (!isPlanActive && showReasoningTrace) {
      setShowReasoningTrace(false);
    }
  }, [isPlanActive, showReasoningTrace]);
  
  useEffect(() => {
    if (!planState || !currentTelemetry) {
      return;
    }

    const planStatus = planState.status as FinalPlanStatus;
    if (!FINAL_PLAN_STATUSES.has(planStatus)) {
      return;
    }

    const planId = currentTelemetry.planId;
    if (!planId || submittedPlanIdsRef.current.has(planId)) {
      return;
    }

    setPendingFeedback((prev) => {
      if (prev && prev.planId === planId) {
        return prev;
      }

      return {
        planId,
        goal: planState.goal || "Unnamed task",
        planStatus,
        startedAt: planState.started_at,
        completedAt: planState.completed_at,
      };
    });
  }, [planState, currentTelemetry]);
  
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

  const handleFeedbackSubmit = useCallback(
    async (choice: FeedbackChoice, notes?: string) => {
      if (!pendingFeedback || !planState) {
        return;
      }

      setIsFeedbackSubmitting(true);
      try {
        const analytics = getAnalytics();
        const stepSnapshots = planState.steps.map((step) => ({
          id: step.id,
          action: step.action,
          status: step.status,
          started_at: step.started_at,
          completed_at: step.completed_at,
          sequence_number: step.sequence_number,
          output_preview: step.output_preview
            ? step.output_preview.slice(0, 400)
            : undefined,
          error: step.error,
        }));

        const payload: Record<string, unknown> = {
          plan_id: pendingFeedback.planId,
          goal: pendingFeedback.goal,
          feedback_type: choice,
          plan_status: planState.status,
          duration_ms: analytics?.duration,
          analytics,
          plan_started_at: pendingFeedback.startedAt,
          plan_completed_at: pendingFeedback.completedAt,
          step_statuses: stepSnapshots,
          metadata: {
            message_count: messages.length,
          },
        };

        if (notes) {
          payload.notes = notes;
        }

        const response = await fetch(`${apiBaseUrl}/api/feedback`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        });

        if (!response.ok) {
          let detail = "Server returned an error";
          try {
            const errorData = await response.json();
            detail = errorData.detail || errorData.message || detail;
          } catch {
            // ignore parse errors
          }
          throw new Error(detail);
        }

        submittedPlanIdsRef.current.add(pendingFeedback.planId);
        setPendingFeedback(null);
        addToast(
          choice === "positive"
            ? "Thanks for the feedback! Logged for quality tracking."
            : "Issue flagged for critique follow-up.",
          choice === "positive" ? "success" : "warning",
          3500
        );
      } catch (error) {
        console.error("[FEEDBACK] Failed to record feedback", error);
        addToast("Couldn't record feedback. Please try again.", "error", 4000);
      } finally {
        setIsFeedbackSubmitting(false);
      }
    },
    [pendingFeedback, planState, getAnalytics, messages.length, apiBaseUrl, addToast]
  );

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

  // Handle slash command telemetry
  const eventBus = useGlobalEventBus();
  useEffect(() => {
    if (!eventBus) return;

    const handleSlashCommandTelemetry = async (payload?: Record<string, any>) => {
      if (!isSlashCommandTelemetryPayload(payload)) {
        return;
      }

      try {
        // Send telemetry to backend
        const response = await fetch(`${apiBaseUrl}/api/telemetry/slash-command`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            command_name: payload.command,
            invocation_source: payload.invocation_source || "unknown",
            timestamp: new Date().toISOString(),
            query: payload.query,
          }),
        });

        if (!response.ok) {
          logger.warn("[TELEMETRY] Failed to record slash command usage", {
            command: payload.command,
            status: response.status,
          });
        }
      } catch (error) {
        // Don't break user flow if telemetry fails
        logger.warn("[TELEMETRY] Error recording slash command usage", {
          error: error instanceof Error ? error.message : String(error),
        });
      }
    };

    const unsubscribe = eventBus.subscribe("slash-command-used", handleSlashCommandTelemetry);

    return () => {
      unsubscribe();
    };
  }, [eventBus, apiBaseUrl]);

  return (
    <>
      {/* Screen reader announcements */}
      <div
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
        role="status"
      >
        {screenReaderAnnouncement}
      </div>

      <div className="flex-1 flex flex-row min-h-0" role="main">
        {/* Main chat area */}
        <div className="flex-1 flex flex-col min-h-0">
          <div className="flex-shrink-0">
            <Header
              isConnected={isConnected}
              messageCount={messages.length}
              onClearSession={() => sendCommand("clear")}
              onShowHelp={() => setShowHelpOverlay(true)}
              planActive={isPlanActive}
              onTogglePlanTrace={() => setShowReasoningTrace((prev) => !prev)}
              isTraceOpen={showReasoningTrace}
            />
          </div>
          <AnimatePresence>
            {planState && showReasoningTrace && (
              <motion.div
                key="reasoning-trace"
                initial={{ opacity: 0, y: -16 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -16 }}
                transition={{ duration: 0.25 }}
                className="px-6 pt-4 sm:px-8 lg:px-12"
              >
                <div className="relative mx-auto max-w-4xl">
                  <button
                    onClick={() => setShowReasoningTrace(false)}
                    className="absolute -top-3 -right-3 z-10 rounded-full bg-surface/90 text-text-primary border border-surface-outline/60 shadow-lg w-8 h-8 flex items-center justify-center hover:bg-surface/80 transition-colors"
                    aria-label="Close plan trace"
                  >
                    ✕
                  </button>
                  <Suspense fallback={<div className="w-full h-64 bg-background-secondary/80 rounded-2xl border border-surface-outline/40" />}>
                    <ReasoningTrace planState={planState} className="shadow-2xl border border-surface-outline/60" />
                  </Suspense>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
          <div className="flex-1 flex flex-col min-h-0">
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
                    <div className="flex h-full items-center justify-center">
                      <div className="text-center space-y-3 text-text-muted">
                        <p className="text-sm">Start typing or press Space to issue a voice command.</p>
                        <p className="text-xs text-text-subtle">The expanded desktop is ready whenever you are.</p>
                      </div>
                    </div>
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

                <div className="relative flex-shrink-0">
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

                    {pendingFeedback && (
                      <div className="mb-4">
                        <FeedbackBar
                          goal={pendingFeedback.goal}
                          planStatus={pendingFeedback.planStatus}
                          analytics={getAnalytics()}
                          isSubmitting={isFeedbackSubmitting}
                          onSubmit={handleFeedbackSubmit}
                        />
                      </div>
                    )}

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

        {/* Sidebar with description */}
        <div className="hidden lg:flex w-80 flex-col justify-center items-start px-12 py-16 border-l border-glass/20">
          <div className="max-w-xs space-y-2">
            <p className="text-text-primary text-base leading-[1.7] font-normal tracking-normal">
              It&apos;s an LLM orchestration engine for the Mac
            </p>
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

      {/* Help and Shortcuts Overlays - Lazy loaded */}
      {showHelpOverlay && (
        <Suspense fallback={null}>
          <HelpOverlay isOpen={showHelpOverlay} onClose={() => setShowHelpOverlay(false)} />
        </Suspense>
      )}
      {showShortcutsOverlay && (
        <Suspense fallback={null}>
          <KeyboardShortcutsOverlay
            isOpen={showShortcutsOverlay}
            onClose={() => setShowShortcutsOverlay(false)}
          />
        </Suspense>
      )}

      {/* Spotify Web Player - Lazy loaded */}
      <Suspense fallback={null}>
        <SpotifyPlayer />
      </Suspense>
    </>
  );
}
