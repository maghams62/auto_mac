"use client";

import { useState, KeyboardEvent, useRef, useEffect, useMemo } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { SLASH_COMMANDS, SlashCommandDefinition } from "@/lib/slashCommands";
import { duration, easing } from "@/lib/motion";
import logger from "@/lib/logger";

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
  initialValue = "",
  onValueChange,
  isProcessing = false,
  onStop,
  onVoiceRecord,
  isRecording = false,
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
    <div className="w-full">
      <div className="relative">
        {showSlashPalette && (
          <motion.div
            className="absolute bottom-full left-0 right-0 mb-2 z-20"
            initial={{ opacity: 0, y: 10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.95 }}
            transition={{ duration: 0.2, ease: [0.25, 0.1, 0.25, 1] }}
          >
            <div className="rounded-lg border border-glass bg-glass-elevated backdrop-blur-glass shadow-elevated p-2 max-h-80 overflow-y-auto shadow-inset-border">
              <div className="flex items-center justify-between px-2 pb-2 mb-1 border-b border-glass">
                <p className="text-xs uppercase tracking-wider text-text-subtle font-medium">
                  Commands
                </p>
                <p className="text-[11px] text-text-subtle font-medium">
                  ↑↓ · Enter · Press ? for help
                </p>
              </div>
              {filteredSlashCommands.length === 0 && (
                <div className="text-center text-xs text-text-muted py-4">
                  No commands match "{slashQuery}"
                </div>
              )}
              {filteredSlashCommands.map((command, index) => {
                const isSelected = index === selectedCommandIndex;
                return (
                  <motion.button
                    key={command.command}
                    onClick={() => applySlashCommand(command)}
                    onMouseEnter={() => setSelectedCommandIndex(index)}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    transition={{
                      duration: duration.fast,
                      ease: easing.default,
                    }}
                    className={cn(
                      "w-full text-left px-2.5 py-2 rounded transition-colors flex items-center gap-3",
                      isSelected
                        ? "bg-glass-hover text-text-primary shadow-inset-border"
                        : "hover:bg-glass-hover text-text-muted"
                    )}
                  >
                    {command.emoji && (
                      <motion.span
                        className="text-lg flex-shrink-0 w-5 h-5 flex items-center justify-center"
                        animate={isSelected ? { scale: 1.1 } : { scale: 1 }}
                        transition={{ duration: duration.fast }}
                      >
                        {command.emoji}
                      </motion.span>
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">
                        {command.label}
                      </p>
                      <p className="text-xs text-text-muted truncate">
                        {command.description}
                      </p>
                    </div>
                  </motion.button>
                );
              })}
            </div>
          </motion.div>
        )}

        <motion.div
          className="group relative rounded-2xl border border-glass bg-glass backdrop-blur-glass px-4 py-3 flex items-end gap-3 focus-within:border-accent-primary focus-within:shadow-glow-primary transition-all shadow-inset-border"
          whileFocus={{ scale: 1.01 }}
          transition={{ duration: 0.2, ease: "easeOut" }}
        >
          {/* Keyboard shortcut hint tooltip */}
          <div className="absolute -top-8 left-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity duration-150 pointer-events-none">
            <div className="bg-glass-elevated backdrop-blur-glass border border-glass rounded-lg px-2 py-1 text-xs text-text-muted shadow-elevated whitespace-nowrap">
              ⌘ Enter to send
            </div>
          </div>
          
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => {
              const newValue = e.target.value;
              setInput(newValue);
              onValueChange?.(newValue);
            }}
            onKeyDown={handleKeyDown}
            placeholder="Message Cerebro..."
            disabled={disabled}
            autoFocus
            className="flex-1 bg-transparent text-text-primary placeholder-text-subtle resize-none outline-none text-[15px] leading-[1.4] max-h-[200px] focus:outline-none focus:ring-2 focus:ring-accent-primary/50 focus:ring-offset-0 focus:ring-offset-transparent"
            rows={1}
            onInput={(e) => {
              const target = e.target as HTMLTextAreaElement;
              target.style.height = "auto";
              target.style.height = Math.min(target.scrollHeight, 200) + "px";
            }}
            aria-label="Message input"
          />

          <div className="flex items-center gap-2">
            {isProcessing && onStop && (
              <button
                onClick={onStop}
                className="rounded-lg p-2 text-xs font-medium transition-colors text-text-muted hover:text-text-primary hover:bg-glass-hover focus:outline-none focus:ring-2 focus:ring-accent-primary/50"
                title="Stop"
              >
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M6 6h12v12H6z" />
                </svg>
              </button>
            )}

            {onVoiceRecord && (
              <motion.button
                onClick={onVoiceRecord}
                disabled={disabled || isProcessing}
                className={cn(
                  "rounded-full p-3 transition-all relative focus:outline-none focus:ring-2 focus:ring-accent-primary/50",
                  isRecording
                    ? "bg-accent-danger/10 text-accent-danger cursor-pointer shadow-lg"
                    : disabled || isProcessing
                    ? "text-text-muted opacity-40 cursor-not-allowed"
                    : "text-text-muted hover:text-text-primary hover:bg-glass-hover cursor-pointer"
                )}
                title={isRecording ? "Stop recording" : "Start voice recording"}
                aria-label={isRecording ? "Stop voice recording" : "Start voice recording"}
                aria-pressed={isRecording}
                whileHover={!disabled && !isProcessing ? { scale: 1.05 } : {}}
                whileTap={!disabled && !isProcessing ? { scale: 0.95 } : {}}
                animate={isRecording ? {
                  scale: [1, 1.1, 1],
                  transition: {
                    duration: 1.5,
                    repeat: Infinity,
                    ease: "easeInOut"
                  }
                } : {}}
              >
                {/* Pulsing rings for recording state */}
                {isRecording && (
                  <>
                    <motion.span
                      className="absolute inset-0 rounded-full border-2 border-accent-danger"
                      animate={{
                        scale: [1, 1.3, 1],
                        opacity: [0.7, 0, 0.7],
                      }}
                      transition={{
                        duration: 1.5,
                        repeat: Infinity,
                        ease: "easeOut"
                      }}
                    />
                    <motion.span
                      className="absolute inset-0 rounded-full border-2 border-accent-danger"
                      animate={{
                        scale: [1, 1.5, 1],
                        opacity: [0.5, 0, 0.5],
                      }}
                      transition={{
                        duration: 1.5,
                        repeat: Infinity,
                        ease: "easeOut",
                        delay: 0.3
                      }}
                    />
                  </>
                )}

                <motion.svg
                  className="w-5 h-5 relative z-10"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  animate={isRecording ? { scale: [1, 1.1, 1] } : {}}
                  transition={{
                    duration: 0.5,
                    repeat: isRecording ? Infinity : 0,
                    ease: "easeInOut"
                  }}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
                  />
                  {/* Recording indicator dot */}
                  {isRecording && (
                    <motion.circle
                      cx="12"
                      cy="12"
                      r="2"
                      fill="currentColor"
                      initial={{ scale: 0 }}
                      animate={{ scale: [0, 1, 0] }}
                      transition={{
                        duration: 1,
                        repeat: Infinity,
                        ease: "easeInOut"
                      }}
                    />
                  )}
                </motion.svg>
              </motion.button>
            )}

            <button
              onClick={handleSend}
              disabled={!input.trim() || disabled || isProcessing}
              className={cn(
                "rounded-lg p-2 transition-colors focus:outline-none focus:ring-2 focus:ring-accent-primary/50",
                !input.trim() || disabled || isProcessing
                  ? "text-text-muted opacity-40 cursor-not-allowed"
                  : "text-text-primary hover:bg-glass-hover cursor-pointer"
              )}
              title="Send"
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
                  d="M5 12h14M12 5l7 7-7 7"
                />
              </svg>
            </button>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
