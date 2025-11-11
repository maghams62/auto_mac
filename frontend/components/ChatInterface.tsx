"use client";

import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import { useWebSocket } from "@/lib/useWebSocket";
import { useVoiceRecorder } from "@/lib/useVoiceRecorder";
import MessageBubble from "./MessageBubble";
import TypingIndicator from "./TypingIndicator";
import InputArea from "./InputArea";
import Sidebar from "./Sidebar";
import RecordingIndicator from "./RecordingIndicator";
import { motion, AnimatePresence } from "framer-motion";
import { getApiBaseUrl, getWebSocketUrl } from "@/lib/apiConfig";
import logger from "@/lib/logger";

const MAX_VISIBLE_MESSAGES = 200; // Limit to prevent performance issues

export default function ChatInterface() {
  const apiBaseUrl = useMemo(() => getApiBaseUrl(), []);
  const wsUrl = useMemo(() => getWebSocketUrl("/ws/chat"), []);
  const { messages: allMessages, isConnected, sendMessage, sendCommand } = useWebSocket(wsUrl);
  
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
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [inputValue, setInputValue] = useState("");

  // Limit messages to prevent performance issues with very long conversations
  const messages = useMemo(() => {
    if (allMessages.length <= MAX_VISIBLE_MESSAGES) {
      return allMessages;
    }
    return allMessages.slice(-MAX_VISIBLE_MESSAGES);
  }, [allMessages]);

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

  // Show voice error if any
  useEffect(() => {
    if (voiceError) {
      console.error("Voice recording error:", voiceError);
    }
  }, [voiceError]);

  const handleSelectCommand = useCallback((command: string) => {
    // Set input value so user can edit before sending
    setInputValue(command);
    // Focus the input area
    setTimeout(() => {
      const textarea = document.querySelector("textarea");
      textarea?.focus();
    }, 100);
  }, []);

  const handleStopRequest = useCallback(() => {
    sendCommand("stop");
  }, [sendCommand]);

  const handleSend = useCallback((msg: string) => {
    sendMessage(msg);
    setInputValue("");
  }, [sendMessage]);

  return (
    <div className="flex h-[calc(100vh-180px)]" role="main">
      {/* Sidebar */}
      <Sidebar
        messages={messages}
        onSelectCommand={handleSelectCommand}
        isConnected={isConnected}
      />

      {/* Main chat area */}
      <div className="flex-1 max-w-5xl mx-auto flex flex-col ml-0 md:ml-[280px]" role="region" aria-label="Chat conversation">
      {/* Welcome message when no messages */}
      {messages.length === 0 && (
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5 }}
          className="flex-1 flex items-center justify-center"
        >
          <div className="text-center max-w-2xl px-6">
            <h2 className="text-4xl font-bold mb-4 gradient-text">
              Welcome to Mac Automation Assistant
            </h2>
            <p className="text-white/60 text-lg mb-8">
              I can help you automate tasks on your Mac, search documents, create presentations,
              analyze stocks, plan trips, and much more.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-8">
              {[
                {
                  title: "Document Search",
                  description: "Search and extract content from your documents",
                  icon: "📄",
                },
                {
                  title: "Presentations",
                  description: "Create Keynote presentations automatically",
                  icon: "📊",
                },
                {
                  title: "Stock Analysis",
                  description: "Get real-time stock data and charts",
                  icon: "📈",
                },
                {
                  title: "Trip Planning",
                  description: "Plan routes with stops using Maps",
                  icon: "🗺️",
                },
              ].map((feature) => (
                <div
                  key={feature.title}
                  className="glass rounded-xl p-6 text-left hover:bg-white/10 transition-all duration-300"
                >
                  <div className="text-3xl mb-3">{feature.icon}</div>
                  <h3 className="text-white font-semibold mb-2">{feature.title}</h3>
                  <p className="text-white/60 text-sm">{feature.description}</p>
                </div>
              ))}
            </div>
          </div>
        </motion.div>
      )}

      {/* Messages area */}
      {messages.length > 0 && (
        <div
          ref={messagesContainerRef}
          className="flex-1 overflow-y-auto px-6 py-8 space-y-4"
          role="log"
          aria-live="polite"
          aria-label="Chat messages"
        >
          <AnimatePresence>
            {messages.map((message, index) => (
              <MessageBubble key={index} message={message} index={index} />
            ))}
            {isProcessing && <TypingIndicator />}
          </AnimatePresence>
          <div ref={messagesEndRef} />
        </div>
      )}

      {/* Connection status banner */}
      {!isConnected && (
        <div
          className="px-6 py-3 bg-red-500/10 border-t border-red-500/20"
          role="alert"
          aria-live="assertive"
        >
          <p className="text-center text-red-400 text-sm">
            Disconnected from server. Attempting to reconnect...
          </p>
        </div>
      )}

      {/* ChatGPT-style Recording Indicator */}
      <RecordingIndicator
        isRecording={isRecording}
        isTranscribing={isTranscribing}
        onStop={handleVoiceRecord}
      />

      {/* Input area */}
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
  );
}
