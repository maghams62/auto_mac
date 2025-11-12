"use client";

import { useState, useEffect, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { overlayFade, modalSlideDown, staggerContainer } from "@/lib/motion";
import { SLASH_COMMANDS, SlashCommandDefinition } from "@/lib/slashCommands";
import { cn } from "@/lib/utils";
import HelpCard from "./HelpCard";

interface HelpOverlayProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function HelpOverlay({ isOpen, onClose }: HelpOverlayProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  // Get unique categories
  const categories = useMemo(() => {
    const cats = Array.from(
      new Set(SLASH_COMMANDS.map((cmd) => cmd.category || "Other"))
    );
    return cats.sort();
  }, []);

  // Filter commands based on search and category
  const filteredCommands = useMemo(() => {
    let filtered = SLASH_COMMANDS;

    // Filter by category
    if (selectedCategory) {
      filtered = filtered.filter(
        (cmd) => (cmd.category || "Other") === selectedCategory
      );
    }

    // Filter by search query
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (cmd) =>
          cmd.command.toLowerCase().includes(query) ||
          cmd.label.toLowerCase().includes(query) ||
          cmd.description.toLowerCase().includes(query) ||
          (cmd.category || "").toLowerCase().includes(query)
      );
    }

    return filtered;
  }, [searchQuery, selectedCategory]);

  // Group commands by category for display
  const groupedCommands = useMemo(() => {
    const groups: Record<string, SlashCommandDefinition[]> = {};
    filteredCommands.forEach((cmd) => {
      const category = cmd.category || "Other";
      if (!groups[category]) {
        groups[category] = [];
      }
      groups[category].push(cmd);
    });
    return groups;
  }, [filteredCommands]);

  // Keyboard navigation
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) =>
          prev < filteredCommands.length - 1 ? prev + 1 : 0
        );
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) =>
          prev > 0 ? prev - 1 : filteredCommands.length - 1
        );
      } else if (e.key === "Enter" && filteredCommands[selectedIndex]) {
        e.preventDefault();
        // Could trigger command selection here
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose, filteredCommands, selectedIndex]);

  // Reset selection when filter changes
  useEffect(() => {
    setSelectedIndex(0);
  }, [searchQuery, selectedCategory]);

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial="hidden"
        animate="visible"
        exit="hidden"
        variants={overlayFade}
        className="fixed inset-0 z-50 flex items-start justify-center p-4 pt-20 overflow-y-auto"
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
            "relative w-full max-w-4xl max-h-[85vh] overflow-y-auto",
            "bg-glass-elevated backdrop-blur-glass rounded-2xl",
            "border border-glass shadow-elevated shadow-inset-border",
            "p-6"
          )}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-semibold text-text-primary">
              Help & Commands
            </h2>
            <button
              onClick={onClose}
              className="text-text-muted hover:text-text-primary transition-colors"
              aria-label="Close"
            >
              <svg
                className="w-6 h-6"
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

          {/* Search */}
          <div className="mb-6">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search commands..."
              autoFocus
              className={cn(
                "w-full px-4 py-3 rounded-lg",
                "bg-glass backdrop-blur-glass border border-glass",
                "text-text-primary placeholder-text-subtle",
                "focus:outline-none focus:border-accent-primary focus:shadow-glow-primary",
                "transition-all"
              )}
            />
          </div>

          {/* Category filters */}
          <div className="flex flex-wrap gap-2 mb-6">
            <button
              onClick={() => setSelectedCategory(null)}
              className={cn(
                "px-3 py-1.5 rounded-full text-xs font-medium transition-colors",
                selectedCategory === null
                  ? "bg-accent-primary text-white"
                  : "bg-glass border border-glass text-text-muted hover:text-text-primary"
              )}
            >
              All
            </button>
            {categories.map((category) => (
              <button
                key={category}
                onClick={() => setSelectedCategory(category)}
                className={cn(
                  "px-3 py-1.5 rounded-full text-xs font-medium transition-colors",
                  selectedCategory === category
                    ? "bg-accent-primary text-white"
                    : "bg-glass border border-glass text-text-muted hover:text-text-primary"
                )}
              >
                {category}
              </button>
            ))}
          </div>

          {/* Commands list */}
          <motion.div
            initial="hidden"
            animate="visible"
            variants={staggerContainer}
            className="space-y-6"
          >
            {Object.keys(groupedCommands).length === 0 ? (
              <div className="text-center py-12 text-text-muted">
                No commands found matching "{searchQuery}"
              </div>
            ) : (
              Object.entries(groupedCommands).map(([category, commands]) => (
                <div key={category}>
                  <h3 className="text-sm font-semibold text-text-muted uppercase tracking-wider mb-3">
                    {category}
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {commands.map((command, idx) => {
                      const globalIndex = filteredCommands.indexOf(command);
                      const isSelected = globalIndex === selectedIndex;
                      return (
                        <motion.div
                          key={command.command}
                          initial="hidden"
                          animate="visible"
                          variants={staggerContainer}
                        >
                          <HelpCard
                            title={command.label}
                            description={command.description}
                            examples={[command.command]}
                            icon={command.category === "Files" ? "📁" : command.category === "Web" ? "🌐" : command.category === "Communication" ? "💬" : "⚡"}
                            className={cn(
                              isSelected && "ring-2 ring-accent-primary"
                            )}
                          />
                        </motion.div>
                      );
                    })}
                  </div>
                </div>
              ))
            )}
          </motion.div>

          {/* Footer hint */}
          <div className="mt-6 pt-4 border-t border-glass text-center text-xs text-text-subtle">
            Use ↑↓ to navigate, Enter to select, Esc to close
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

