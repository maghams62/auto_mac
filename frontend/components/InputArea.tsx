"use client";

import { useState, KeyboardEvent, useRef, useEffect, useMemo } from "react";
import { cn } from "@/lib/utils";
import { SLASH_COMMANDS, SlashCommandDefinition } from "@/lib/slashCommands";
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
          <div className="absolute bottom-full left-0 right-0 mb-2 z-20">
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
                  <button
                    key={command.command}
                    onClick={() => applySlashCommand(command)}
                    onMouseEnter={() => setSelectedCommandIndex(index)}
                    className={cn(
                      "w-full text-left px-2.5 py-2 rounded transition-colors flex items-center justify-between gap-2",
                      isSelected
                        ? "bg-glass-hover text-text-primary shadow-inset-border"
                        : "hover:bg-glass-hover text-text-muted"
                    )}
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">
                        {command.label}
                      </p>
                      <p className="text-xs text-text-muted truncate">
                        {command.description}
                      </p>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        <div className="group relative rounded-2xl border border-glass bg-glass backdrop-blur-glass px-4 py-3 flex items-end gap-3 focus-within:border-accent-primary focus-within:shadow-glow-primary transition-all shadow-inset-border">
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
            className="flex-1 bg-transparent text-text-primary placeholder-text-subtle resize-none outline-none text-[15px] leading-[1.4] max-h-[200px]"
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
                className="rounded-lg p-2 text-xs font-medium transition-colors text-text-muted hover:text-text-primary hover:bg-glass-hover"
                title="Stop"
              >
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M6 6h12v12H6z" />
                </svg>
              </button>
            )}

            {onVoiceRecord && (
              <button
                onClick={onVoiceRecord}
                disabled={disabled || isProcessing}
                className={cn(
                  "rounded-lg p-2 transition-all relative",
                  isRecording
                    ? "text-accent-danger cursor-pointer"
                    : disabled || isProcessing
                    ? "text-text-muted opacity-40 cursor-not-allowed"
                    : "text-text-muted hover:text-text-primary hover:bg-glass-hover cursor-pointer"
                )}
                title={isRecording ? "Stop recording" : "Start voice recording"}
              >
                {isRecording && (
                  <span className="absolute inset-0 rounded-lg border-2 border-accent-danger animate-pulse opacity-75" />
                )}
                <svg
                  className="w-5 h-5 relative z-10"
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
              </button>
            )}

            <button
              onClick={handleSend}
              disabled={!input.trim() || disabled || isProcessing}
              className={cn(
                "rounded-lg p-2 transition-colors",
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
        </div>
      </div>
    </div>
  );
}
