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
import { getApiBaseUrl, getWebSocketUrl } from "@/lib/apiConfig";
import logger from "@/lib/logger";
import StartupOverlay from "./StartupOverlay";

const MAX_VISIBLE_MESSAGES = 200; // Limit to prevent performance issues

export default function ChatInterface() {
  const apiBaseUrl = useMemo(() => getApiBaseUrl(), []);
  const wsUrl = useMemo(() => getWebSocketUrl("/ws/chat"), []);
  const { messages: allMessages, isConnected, sendMessage, sendCommand } = useWebSocket(wsUrl);
  const [bootOverlayVisible, setBootOverlayVisible] = useState(true);
  const [minDelayComplete, setMinDelayComplete] = useState(false);
  
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
    } finally {
      setIsTranscribing(false);
    }
  }, [apiBaseUrl, createAbortController, sendMessage]);

  // Handle auto-stop transcription
  const handleAutoStopTranscription = useCallback(async (audioBlob: Blob) => {
    await transcribeAudio(audioBlob);
  }, [transcribeAudio]);

  const { isRecording, startRecording, stopRecording, error: voiceError } = useVoiceRecorder({
    onAutoStop: handleAutoStopTranscription,
  });
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const messageRefs = useRef<Map<number, HTMLDivElement>>(new Map());
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [inputValue, setInputValue] = useState("");
  const [showHelpOverlay, setShowHelpOverlay] = useState(false);
  const [showShortcutsOverlay, setShowShortcutsOverlay] = useState(false);

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

  // Handle help and shortcuts keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: globalThis.KeyboardEvent) => {
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
  }, []);

  // Handle /help command
  useEffect(() => {
    if (inputValue.trim() === "/help") {
      setShowHelpOverlay(true);
      setInputValue("");
    }
  }, [inputValue]);

  // Minimum display delay so the animation is visible but not lingering
  useEffect(() => {
    const delayTimer = window.setTimeout(() => setMinDelayComplete(true), 800);
    return () => window.clearTimeout(delayTimer);
  }, []);

  // Fallback: ensure overlay disappears even if backend connection fails
  useEffect(() => {
    const fallbackTimer = window.setTimeout(() => {
      setBootOverlayVisible(false);
    }, 5000);
    return () => window.clearTimeout(fallbackTimer);
  }, []);

  // Hide overlay shortly after connection is ready (respecting minimum delay)
  // Add a brief delay to show the "Ready" state before transitioning
  useEffect(() => {
    if (!isConnected || !minDelayComplete || !bootOverlayVisible) {
      return;
    }
    const readyTimer = window.setTimeout(() => setBootOverlayVisible(false), 600);
    return () => window.clearTimeout(readyTimer);
  }, [isConnected, minDelayComplete, bootOverlayVisible]);

  return (
    <>
      <StartupOverlay show={bootOverlayVisible} />
      <div className="flex-1 flex flex-col min-h-0" role="main">
      {/* Main chat area - centered, no sidebars */}
      <div className="flex-1 flex flex-col w-full max-w-3xl mx-auto px-4 sm:px-6" role="region" aria-label="Chat conversation">
        <div className="flex-1 overflow-hidden flex flex-col min-h-0 py-4">
          {!hasMessages ? (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center max-w-2xl glass rounded-2xl p-8 shadow-elevated backdrop-blur-glass">
                <h1 className="text-4xl font-semibold mb-4 text-text-primary">
                  Cerebro OS
                </h1>
                <p className="text-text-muted text-lg mb-8">
                  How can I help you today?
                </p>
              </div>
            </div>
          ) : (
            <div
              ref={messagesContainerRef}
              className="flex-1 overflow-y-auto space-y-4 min-h-0 relative"
              role="log"
              aria-live="polite"
              aria-label="Chat messages"
            >
              {messages.map((message, index) => (
                <div
                  key={index}
                  ref={(el) => {
                    if (el) {
                      messageRefs.current.set(index, el);
                    } else {
                      messageRefs.current.delete(index);
                    }
                  }}
                >
                  <MessageBubble message={message} index={index} />
                </div>
              ))}
              {(isProcessing || (lastMessage && lastMessage.type === "plan")) && <TypingIndicator />}
              <div ref={messagesEndRef} />
              {messagesContainerRef.current && (
                <ScrollToBottom containerRef={messagesContainerRef} />
              )}
            </div>
          )}
        </div>

        {/* Connection status banner */}
        {!isConnected && (
          <div className="rounded-lg border border-danger-border bg-danger-bg px-4 py-2 text-center mb-4" role="alert" aria-live="assertive">
            <p className="text-accent-danger text-sm">
              Disconnected from server. Attempting to reconnect...
            </p>
          </div>
        )}

        {/* Input area */}
        <div className="pb-6">
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

      {/* Recording Indicator */}
      <RecordingIndicator
        isRecording={isRecording}
        isTranscribing={isTranscribing}
        onStop={handleStopRecording}
      />

      {/* Help and Shortcuts Overlays */}
      <HelpOverlay isOpen={showHelpOverlay} onClose={() => setShowHelpOverlay(false)} />
      <KeyboardShortcutsOverlay
        isOpen={showShortcutsOverlay}
        onClose={() => setShowShortcutsOverlay(false)}
      />
      </div>
    </>
  );
}
