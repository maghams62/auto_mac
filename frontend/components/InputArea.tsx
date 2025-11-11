"use client";

import { useState, KeyboardEvent, useRef, useEffect, useMemo } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { SLASH_COMMANDS, SlashCommandDefinition } from "@/lib/slashCommands";

interface InputAreaProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  onVoiceRecord?: () => void;
  isRecording?: boolean;
  initialValue?: string;
  onValueChange?: (value: string) => void;
  isProcessing?: boolean;
  onStop?: () => void;
}

export default function InputArea({ 
  onSend, 
  disabled, 
  onVoiceRecord, 
  isRecording,
  initialValue = "",
  onValueChange,
  isProcessing = false,
  onStop
}: InputAreaProps) {
  const [input, setInput] = useState(initialValue);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [selectedCommandIndex, setSelectedCommandIndex] = useState(0);

  const slashInput = input.startsWith("/") ? input.slice(1) : "";
  const slashQuery = slashInput.split(/[\s\n]/)[0] ?? "";
  const showSlashPalette =
    input.startsWith("/") && !input.includes(" ") && !input.includes("\n");

  const filteredSlashCommands = useMemo(() => {
    if (!showSlashPalette) {
      return [];
    }

    if (!slashQuery.trim()) {
      return SLASH_COMMANDS;
    }

    const query = slashQuery.toLowerCase();
    return SLASH_COMMANDS.filter((cmd) =>
      [cmd.command, cmd.label, cmd.description]
        .join(" ")
        .toLowerCase()
        .includes(query)
    );
  }, [showSlashPalette, slashQuery]);

  useEffect(() => {
    if (showSlashPalette) {
      setSelectedCommandIndex(0);
    }
  }, [showSlashPalette, filteredSlashCommands.length]);

  // Sync with external value changes
  // Use a ref to track if the change is from external source
  const isExternalChangeRef = useRef(false);

  useEffect(() => {
    // Only update if the external value is different and not empty
    // This prevents unnecessary re-renders and sync loops
    if (initialValue && initialValue !== input && !isExternalChangeRef.current) {
      isExternalChangeRef.current = true;
      setInput(initialValue);
      // Reset the flag after state update
      requestAnimationFrame(() => {
        isExternalChangeRef.current = false;
      });
    }
  }, [initialValue, input]);

  // Keyboard shortcuts (Raycast-style)
  useEffect(() => {
    const handleKeyDown = (e: globalThis.KeyboardEvent) => {
      // Cmd+K or Ctrl+K to focus input
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        textareaRef.current?.focus();
      }
      // Cmd+L or Ctrl+L to clear input
      if ((e.metaKey || e.ctrlKey) && e.key === "l") {
        e.preventDefault();
        setInput("");
        textareaRef.current?.focus();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  const applySlashCommand = (command: SlashCommandDefinition) => {
    const newValue = `${command.command} `;
    setInput(newValue);
    onValueChange?.(newValue);
    requestAnimationFrame(() => {
      textareaRef.current?.focus();
      const target = textareaRef.current;
      if (target) {
        const cursorPos = newValue.length;
        target.setSelectionRange(cursorPos, cursorPos);
      }
    });
  };

  const handleSend = () => {
    if (isProcessing) {
      return;
    }
    if (input.trim() && !disabled) {
      onSend(input.trim());
      setInput("");
      onValueChange?.("");
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (showSlashPalette && filteredSlashCommands.length > 0) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedCommandIndex((prev) =>
          prev === filteredSlashCommands.length - 1 ? 0 : prev + 1
        );
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedCommandIndex((prev) =>
          prev === 0 ? filteredSlashCommands.length - 1 : prev - 1
        );
        return;
      }
      if (e.key === "Tab") {
        e.preventDefault();
        const cmd = filteredSlashCommands[selectedCommandIndex];
        applySlashCommand(cmd);
        return;
      }
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        const cmd = filteredSlashCommands[selectedCommandIndex];
        applySlashCommand(cmd);
        return;
      }
    }

    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="sticky bottom-0 backdrop-blur-xl bg-black/20 border-t border-white/10">
      <div className="container mx-auto px-6 py-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="max-w-4xl mx-auto"
        >
          <div className="glass-input rounded-2xl p-4 flex items-end space-x-3 relative">
            {showSlashPalette && (
              <div className="absolute bottom-full left-0 right-0 mb-3 z-20">
                <div className="rounded-2xl border border-white/10 bg-black/70 backdrop-blur-xl shadow-2xl p-3 max-h-96 overflow-y-auto">
                  <div className="flex items-center justify-between px-2 pb-2">
                    <p className="text-xs uppercase tracking-widest text-white/50">
                      Slash Commands
                    </p>
                    <p className="text-[11px] text-white/40">
                      ↑↓ navigate · Enter to select
                    </p>
                  </div>
                  {filteredSlashCommands.length === 0 && (
                    <div className="text-center text-xs text-white/50 py-4">
                      No commands match "{slashQuery}"
                    </div>
                  )}
                  {filteredSlashCommands.map((command, index) => {
                    const isSelected = index === selectedCommandIndex;
                    return (
                      <button
                        key={command.command}
                        onClick={() => applySlashCommand(command)}
                        onMouseEnter={() => setSelectedCommandIndex(index)}
                        className={cn(
                          "w-full text-left px-3 py-2.5 rounded-xl transition-all duration-200 flex items-center justify-between gap-3",
                          isSelected
                            ? "bg-white/10 text-white"
                            : "hover:bg-white/5 text-white/80"
                        )}
                      >
                        <div>
                          <p className="text-sm font-semibold">
                            {command.label}
                          </p>
                          <p className="text-xs text-white/60">
                            {command.description}
                          </p>
                        </div>
                        <span className="text-xs font-mono text-white/70">
                          {command.command}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
            {/* Voice recording button */}
            {onVoiceRecord && (
              <button
                onClick={onVoiceRecord}
                disabled={disabled || isProcessing || isRecording}
                className={cn(
                  "rounded-xl p-3 transition-all duration-300 flex-shrink-0 relative",
                  isRecording
                    ? "bg-red-500/20 text-red-400 cursor-not-allowed"
                    : "bg-white/5 hover:bg-white/10 text-white/60 hover:text-white/90",
                  (disabled || isProcessing) && "opacity-50 cursor-not-allowed"
                )}
                title={isRecording ? "Recording in progress - use stop button above" : "Start voice recording"}
              >
                {isRecording ? (
                  <>
                    <svg
                      className="w-5 h-5"
                      fill="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path d="M12 14c1.66 0 2.99-1.34 2.99-3L15 5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm5.3-3c0 3-2.54 5.1-5.3 5.1S6.7 14 6.7 11H5c0 3.41 2.72 6.23 6 6.72V21h2v-3.28c3.28-.48 6-3.3 6-6.72h-1.7z" />
                    </svg>
                    <motion.div
                      className="absolute inset-0 rounded-xl border-2 border-red-400"
                      animate={{
                        scale: [1, 1.1, 1],
                        opacity: [0.5, 0.8, 0.5],
                      }}
                      transition={{
                        duration: 1.5,
                        repeat: Infinity,
                        ease: "easeInOut",
                      }}
                    />
                  </>
                ) : (
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
                      d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
                    />
                  </svg>
                )}
              </button>
            )}

            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => {
                const newValue = e.target.value;
                setInput(newValue);
                onValueChange?.(newValue);
              }}
              onKeyDown={handleKeyDown}
              placeholder="Type your request here... (⌘K focus, ⌘L clear, / for commands)"
              disabled={disabled}
              autoFocus
              className="flex-1 bg-transparent text-white placeholder-white/40 resize-none outline-none min-h-[24px] max-h-[200px]"
              rows={1}
              style={{
                height: "auto",
                minHeight: "24px",
              }}
              onInput={(e) => {
                const target = e.target as HTMLTextAreaElement;
                target.style.height = "auto";
                target.style.height = target.scrollHeight + "px";
              }}
              aria-label="Message input"
              aria-describedby="input-help-text"
            />

            {isProcessing && onStop && (
              <button
                onClick={onStop}
                className="glass-button rounded-xl px-4 py-3 font-medium transition-all duration-300 flex-shrink-0 bg-red-500/20 text-red-200 hover:bg-red-500/30 hover:text-white"
                title="Stop current task"
              >
                <div className="flex items-center space-x-2">
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M6 6h12v12H6z" />
                  </svg>
                  <span>Stop</span>
                </div>
              </button>
            )}

            <button
              onClick={handleSend}
              disabled={!input.trim() || disabled || isProcessing}
              className={cn(
                "glass-button rounded-xl px-6 py-3 font-medium transition-all duration-300 flex-shrink-0",
                !input.trim() || disabled || isProcessing
                  ? "opacity-50 cursor-not-allowed"
                  : "hover:scale-105 active:scale-95 cursor-pointer"
              )}
              title="Send (Enter)"
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
                  d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
                />
              </svg>
            </button>
          </div>

          {/* Example prompts */}
          <div className="mt-4 flex flex-wrap gap-2">
            {[
              "Search my documents for Tesla",
              "Create a stock report for AAPL",
              "Plan a trip from LA to San Diego",
            ].map((example) => (
              <button
                key={example}
                onClick={() => setInput(example)}
                disabled={disabled || isProcessing}
                className="text-xs px-3 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-white/60 hover:text-white/90 transition-all duration-200 border border-white/10 cursor-pointer disabled:cursor-not-allowed"
              >
                {example}
              </button>
            ))}
          </div>
        </motion.div>
      </div>
    </div>
  );
}
