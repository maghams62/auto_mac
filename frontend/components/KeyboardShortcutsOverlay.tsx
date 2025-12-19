"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { overlayFade, modalSlideDown } from "@/lib/motion";
import { cn } from "@/lib/utils";

interface Shortcut {
  keys: string[];
  description: string;
  category: string;
}

const shortcuts: Shortcut[] = [
  { keys: ["⌘", "K"], description: "Focus input", category: "Navigation" },
  { keys: ["⌘", "L"], description: "Clear input", category: "Navigation" },
  { keys: ["⌘", "Enter"], description: "Send message", category: "Input" },
  { keys: ["Shift", "Enter"], description: "New line", category: "Input" },
  { keys: ["⌘", "/"], description: "Show help", category: "Commands" },
  { keys: ["⌘", "?"], description: "Show shortcuts", category: "Commands" },
  { keys: ["↑", "↓"], description: "Navigate commands", category: "Commands" },
  { keys: ["Enter"], description: "Select command", category: "Commands" },
  { keys: ["Esc"], description: "Close overlay", category: "Navigation" },
];

interface KeyboardShortcutsOverlayProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function KeyboardShortcutsOverlay({
  isOpen,
  onClose,
}: KeyboardShortcutsOverlayProps) {
  const [categories, setCategories] = useState<string[]>([]);

  useEffect(() => {
    const uniqueCategories = Array.from(
      new Set(shortcuts.map((s) => s.category))
    );
    setCategories(uniqueCategories);
  }, []);

  useEffect(() => {
    if (!isOpen) return;

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };

    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial="hidden"
        animate="visible"
        exit="hidden"
        variants={overlayFade}
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
        onClick={onClose}
      >
        {/* Backdrop */}
        <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />

        {/* Modal */}
        <motion.div
          initial="hidden"
          animate="visible"
          exit="hidden"
          variants={modalSlideDown}
          className={cn(
            "relative w-full max-w-2xl max-h-[80vh] overflow-y-auto",
            "bg-glass-elevated backdrop-blur-glass rounded-2xl",
            "border border-glass shadow-elevated shadow-inset-border",
            "p-6"
          )}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold text-text-primary">
              Keyboard Shortcuts
            </h2>
            <button
              onClick={onClose}
              className="text-text-muted hover:text-text-primary transition-colors"
              aria-label="Close"
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
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>

          <div className="space-y-6">
            {categories.map((category) => {
              const categoryShortcuts = shortcuts.filter(
                (s) => s.category === category
              );
              return (
                <div key={category}>
                  <h3 className="text-sm font-semibold text-text-muted uppercase tracking-wider mb-3">
                    {category}
                  </h3>
                  <div className="space-y-2">
                    {categoryShortcuts.map((shortcut, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-glass-hover transition-colors"
                      >
                        <span className="text-sm text-text-primary">
                          {shortcut.description}
                        </span>
                        <div className="flex items-center gap-1">
                          {shortcut.keys.map((key, keyIdx) => (
                            <span
                              key={keyIdx}
                              className="px-2 py-1 text-xs font-mono bg-glass border border-glass rounded text-text-primary"
                            >
                              {key}
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

