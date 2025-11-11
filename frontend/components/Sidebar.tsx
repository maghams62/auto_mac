"use client";

import { useState, useEffect, useMemo } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { SLASH_COMMANDS, SlashCommandDefinition } from "@/lib/slashCommands";
import Profile from "./Profile";

interface SidebarProps {
  messages: Array<{ type: string; message: string; timestamp: string }>;
  onSelectCommand?: (command: string) => void;
  isConnected: boolean;
}

export default function Sidebar({ messages, onSelectCommand, isConnected }: SidebarProps) {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [activeTab, setActiveTab] = useState<"history" | "quick" | "help" | "profile">("history");
  
  // Check if /help command was sent and switch to help tab
  useEffect(() => {
    const lastMessage = messages[messages.length - 1];
    const normalizedMessage = lastMessage?.message?.toLowerCase().trim();

    if (!normalizedMessage) {
      return;
    }

    if (lastMessage.type === "user" && normalizedMessage.startsWith("/help")) {
      setActiveTab("help");
      setIsCollapsed(false);
      return;
    }

    if (lastMessage.type === "system" && normalizedMessage.includes("help panel opened")) {
      setActiveTab("help");
      setIsCollapsed(false);
    }
  }, [messages]);

  // Extract user commands from messages
  const userCommands = messages
    .filter((msg) => msg.type === "user")
    .map((msg) => msg.message)
    .slice(-10) // Last 10 commands
    .reverse();

  const quickActions = [
    { label: "Search Documents", command: "Search my documents for", icon: "📄" },
    { label: "Create Presentation", command: "Create a Keynote presentation about", icon: "📊" },
    { label: "Stock Analysis", command: "Get stock analysis for", icon: "📈" },
    { label: "Plan Trip", command: "Plan a trip from", icon: "🗺️" },
    { label: "Organize Files", command: "Organize my files", icon: "📁" },
    { label: "Send Email", command: "Send an email to", icon: "✉️" },
  ];

  const groupedCommands = useMemo<Record<string, SlashCommandDefinition[]>>(() => {
    return SLASH_COMMANDS.reduce((acc, cmd) => {
      const category = cmd.category || "Other";
      if (!acc[category]) {
        acc[category] = [];
      }
      acc[category].push(cmd);
      return acc;
    }, {} as Record<string, SlashCommandDefinition[]>);
  }, []);

  return (
    <motion.div
      initial={{ x: -300 }}
      animate={{ x: isCollapsed ? -280 : 0 }}
      transition={{ duration: 0.3 }}
      className={cn(
        "fixed left-0 top-0 h-full w-[280px] bg-black/40 backdrop-blur-xl border-r border-white/10 z-40 flex flex-col",
        isCollapsed && "w-[20px]",
        "hidden md:flex" // Hide on mobile, show on desktop
      )}
      role="navigation"
      aria-label="Sidebar navigation"
    >
      {/* Toggle button */}
      <button
        onClick={() => setIsCollapsed(!isCollapsed)}
        className="absolute -right-3 top-4 w-6 h-6 bg-white/10 hover:bg-white/20 rounded-full flex items-center justify-center text-white/60 hover:text-white transition-all"
        aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
        aria-expanded={!isCollapsed}
      >
        {isCollapsed ? "→" : "←"}
      </button>

      {!isCollapsed && (
        <>
          {/* Header */}
          <div className="p-4 border-b border-white/10">
            <h2 className="text-sm font-semibold text-white/90 uppercase tracking-wider">
              Quick Access
            </h2>
          </div>

          {/* Tabs */}
          <div className="flex border-b border-white/10">
            <button
              onClick={() => setActiveTab("history")}
              className={cn(
                "flex-1 px-3 py-2 text-xs font-medium transition-colors",
                activeTab === "history"
                  ? "text-white bg-white/10"
                  : "text-white/60 hover:text-white/90"
              )}
            >
              History
            </button>
            <button
              onClick={() => setActiveTab("quick")}
              className={cn(
                "flex-1 px-3 py-2 text-xs font-medium transition-colors",
                activeTab === "quick"
                  ? "text-white bg-white/10"
                  : "text-white/60 hover:text-white/90"
              )}
            >
              Quick
            </button>
            <button
              onClick={() => setActiveTab("help")}
              className={cn(
                "flex-1 px-3 py-2 text-xs font-medium transition-colors",
                activeTab === "help"
                  ? "text-white bg-white/10"
                  : "text-white/60 hover:text-white/90"
              )}
            >
              Help
            </button>
            <button
              onClick={() => setActiveTab("profile")}
              className={cn(
                "flex-1 px-3 py-2 text-xs font-medium transition-colors",
                activeTab === "profile"
                  ? "text-white bg-white/10"
                  : "text-white/60 hover:text-white/90"
              )}
            >
              Profile
            </button>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto">
            {activeTab === "history" ? (
              <div className="p-4 space-y-2">
                {userCommands.length === 0 ? (
                  <p className="text-white/40 text-sm text-center py-8">
                    No command history yet
                  </p>
                ) : (
                  userCommands.map((command, index) => (
                    <button
                      key={index}
                      onClick={() => onSelectCommand?.(command)}
                      className="w-full text-left px-3 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-white/80 hover:text-white text-sm transition-all cursor-pointer"
                    >
                      <div className="truncate">{command}</div>
                    </button>
                  ))
                )}
              </div>
            ) : activeTab === "quick" ? (
              <div className="p-4 space-y-2">
                {quickActions.map((action, index) => (
                  <button
                    key={index}
                    onClick={() => onSelectCommand?.(action.command)}
                    className="w-full text-left px-3 py-3 rounded-lg bg-white/5 hover:bg-white/10 text-white/80 hover:text-white transition-all cursor-pointer flex items-center space-x-3"
                  >
                    <span className="text-lg">{action.icon}</span>
                    <div>
                      <div className="font-medium text-sm">{action.label}</div>
                      <div className="text-xs text-white/50 truncate">{action.command}</div>
                    </div>
                  </button>
                ))}
              </div>
            ) : activeTab === "profile" ? (
              <Profile />
            ) : (
              <div className="p-4 space-y-4">
                <div className="px-3 py-2 rounded-xl bg-white/5 text-xs text-white/60">
                  View every slash command along with a quick tooltip. Click any entry to pre-fill the chat box.
                </div>
                {Object.entries(groupedCommands).map(([category, commands]) => (
                  <div key={category} className="mb-4">
                    <h3 className="text-xs font-semibold text-white/50 uppercase tracking-wider mb-2 px-2">
                      {category}
                    </h3>
                    <div className="space-y-1">
                      {commands.map((cmd) => (
                        <button
                          key={cmd.command}
                          onClick={() => onSelectCommand?.(cmd.command)}
                          className="w-full text-left px-3 py-2.5 rounded-lg bg-white/5 hover:bg-white/10 text-white/80 hover:text-white transition-all cursor-pointer group"
                          title={`${cmd.label} • ${cmd.description}`}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <span className="font-mono text-sm text-white group-hover:text-white">
                                  {cmd.command}
                                </span>
                                <span className="text-[10px] uppercase tracking-wider text-white/60 bg-white/10 px-2 py-0.5 rounded-full">
                                  {cmd.label}
                                </span>
                              </div>
                              <div className="text-xs text-white/50 mt-1">
                                {cmd.description}
                              </div>
                            </div>
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Status footer */}
          <div className="p-4 border-t border-white/10">
            <div className="flex items-center justify-between">
              <span className="text-xs text-white/60">Status</span>
              <div className="flex items-center space-x-2">
                <div
                  className={cn(
                    "w-2 h-2 rounded-full",
                    isConnected ? "bg-green-400 animate-pulse" : "bg-red-400"
                  )}
                />
                <span className="text-xs text-white/60">
                  {isConnected ? "Online" : "Offline"}
                </span>
              </div>
            </div>
          </div>
        </>
      )}
    </motion.div>
  );
}
