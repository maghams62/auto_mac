"use client";

import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import { useWebSocket } from "@/lib/useWebSocket";
import { useVoiceRecorder } from "@/lib/useVoiceRecorder";
import MessageBubble from "./MessageBubble";
import TypingIndicator from "./TypingIndicator";
import InputArea from "./InputArea";
import Sidebar from "./Sidebar";
import { motion, AnimatePresence } from "framer-motion";

const WS_URL = "ws://localhost:8000/ws/chat";
const API_URL = "http://localhost:8000";
const MAX_VISIBLE_MESSAGES = 200; // Limit to prevent performance issues

export default function ChatInterface() {
  const { messages: allMessages, isConnected, sendMessage, sendCommand } = useWebSocket(WS_URL);
  const { isRecording, startRecording, stopRecording, error: voiceError } = useVoiceRecorder();
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
      // Stop recording and transcribe
      setIsTranscribing(true);
      try {
        const audioBlob = await stopRecording();
        if (!audioBlob) {
          setIsTranscribing(false);
          return;
        }

        // Send to backend for transcription
        const formData = new FormData();
        formData.append("audio", audioBlob, "recording.webm");

        const response = await fetch(`${API_URL}/api/transcribe`, {
          method: "POST",
          body: formData,
        });

        if (!response.ok) {
          throw new Error("Transcription failed");
        }

        const data = await response.json();
        if (data.text && data.text.trim()) {
          // Send transcribed text as a message
          sendMessage(data.text.trim());
        }
      } catch (err) {
        console.error("Error transcribing audio:", err);
        // Add error message to chat
        sendMessage("Error transcribing audio. Please try typing instead.");
      } finally {
        setIsTranscribing(false);
      }
    } else {
      // Start recording
      await startRecording();
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

      {/* Voice recording status */}
      {(isRecording || isTranscribing) && (
        <div className="px-6 py-2 bg-accent-cyan/10 border-t border-accent-cyan/20">
          <p className="text-center text-accent-cyan text-sm flex items-center justify-center space-x-2">
            {isTranscribing ? (
              <>
                <div className="w-2 h-2 bg-accent-cyan rounded-full animate-pulse" />
                <span>Transcribing audio...</span>
              </>
            ) : (
              <>
                <div className="w-2 h-2 bg-red-400 rounded-full animate-pulse" />
                <span>Recording... Click microphone to stop</span>
              </>
            )}
          </p>
        </div>
      )}

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
