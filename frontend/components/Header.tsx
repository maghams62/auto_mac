"use client";

import { motion } from "framer-motion";
import { useEffect, useState, useMemo } from "react";
import { getApiBaseUrl } from "@/lib/apiConfig";

interface HeaderProps {
  isConnected?: boolean;
}

export default function Header({ isConnected = true }: HeaderProps) {
  const apiBaseUrl = useMemo(() => getApiBaseUrl(), []);
  const [stats, setStats] = useState<{ agents?: number; tools?: number } | null>(null);

  useEffect(() => {
    // Fetch system stats
    const fetchStats = async () => {
      try {
        const response = await fetch(`${apiBaseUrl}/api/stats`);
        if (response.ok) {
          const data = await response.json();
          setStats({
            agents: data.available_agents?.length || 0,
            tools: 0, // Could be enhanced to show total tools
          });
        }
      } catch (err) {
        console.error("Failed to fetch stats:", err);
      }
    };

    fetchStats();
    // Refresh stats every 30 seconds
    const interval = setInterval(fetchStats, 30000);
    return () => clearInterval(interval);
  }, [apiBaseUrl]);

  return (
    <motion.header
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="sticky top-0 z-50 backdrop-blur-xl bg-black/20 border-b border-white/10"
    >
      <div className="container mx-auto px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 bg-gradient-to-br from-accent-cyan to-accent-purple rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-sm">M</span>
            </div>
            <h1 className="text-xl font-bold gradient-text">
              Mac Automation Assistant
            </h1>
            {stats && (
              <span className="text-xs text-white/40 ml-4">
                {stats.agents} agents available
              </span>
            )}
          </div>

          <div className="flex items-center space-x-4">
            <ConnectionStatus isConnected={isConnected} />
            <KeyboardShortcuts />
          </div>
        </div>
      </div>
    </motion.header>
  );
}

function ConnectionStatus({ isConnected }: { isConnected: boolean }) {
  return (
    <div className="flex items-center space-x-2 text-sm">
      <div
        className={`w-2 h-2 rounded-full ${
          isConnected ? "bg-accent-green animate-pulse" : "bg-red-400"
        }`}
      />
      <span className="text-white/60">{isConnected ? "Online" : "Offline"}</span>
    </div>
  );
}

function KeyboardShortcuts() {
  return (
    <div className="hidden md:flex items-center space-x-4 text-xs text-white/40">
      <div className="flex items-center space-x-1">
        <kbd className="px-2 py-1 bg-white/10 rounded">⌘K</kbd>
        <span>Focus</span>
      </div>
      <div className="flex items-center space-x-1">
        <kbd className="px-2 py-1 bg-white/10 rounded">⌘L</kbd>
        <span>Clear</span>
      </div>
    </div>
  );
}
