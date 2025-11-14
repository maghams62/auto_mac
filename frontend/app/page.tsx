"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import ChatInterface from "@/components/ChatInterface";
import BootScreen from "@/components/BootScreen";

import { BootProvider, useBootContext } from "@/components/BootProvider";

export default function Home() {
  return (
    <BootProvider>
      <HomeContent />
    </BootProvider>
  );
}

function HomeContent() {
  const [showChat, setShowChat] = useState(false);
  const { bootPhase } = useBootContext();

  // Show chat when boot is ready
  useEffect(() => {
    if (bootPhase === "ready") {
      // Small delay before chat fade-in for smooth handoff
      setTimeout(() => {
        setShowChat(true);
      }, 100);
    } else if (bootPhase === "error") {
      setShowChat(false);
    }
  }, [bootPhase]);

  // Handle retry in error state
  const handleRetry = () => {
    // The BootProvider will handle resetting the boot phase
    window.location.reload(); // Simple retry for now
  };

  const chatVariants = {
    hidden: {
      opacity: 0,
      scale: 0.85,
      y: 40,
      filter: "blur(20px) brightness(0.8)",
      pointerEvents: "none" as const,
    },
    visible: {
      opacity: 1,
      scale: 1,
      y: 0,
      filter: "blur(0px) brightness(1)",
      pointerEvents: "auto" as const,
    },
  };

  return (
    <main className="relative min-h-screen flex flex-col">
      {/* Boot Screen - shows during boot, auto-fades when ready */}
      <BootScreen />

      {/* Error state overlay */}
      {bootPhase === "error" && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black">
          <div className="text-center space-y-4">
            <div className="text-red-400 font-mono text-sm mb-2">Connection failed</div>
            <div className="text-white/60 font-mono text-xs mb-4">
              Unable to connect to Cerebro. Please check your connection and try refreshing.
            </div>
            <button
              onClick={handleRetry}
              className="px-4 py-2 bg-gray-800/50 hover:bg-gray-700/50 border border-gray-600/50 rounded text-gray-300 hover:text-gray-200 transition-all duration-200 font-medium font-mono text-sm"
            >
              Try Again
            </button>
          </div>
        </div>
      )}

      {/* Chat Interface - always mounted, visually hidden during boot */}
      <motion.div
        variants={chatVariants}
        initial="hidden"
        animate={showChat ? "visible" : "hidden"}
        transition={{
          duration: 0.4,
          ease: [0.4, 0, 0.2, 1],
        }}
        className="flex-1 relative"
      >
        {/* Simplified reveal effects - reduced animation complexity for better performance */}
        {showChat && (
          <div className="absolute inset-0 bg-gradient-to-br from-transparent via-blue-500/3 to-purple-500/3 pointer-events-none" />
        )}

        <ChatInterface />
      </motion.div>
    </main>
  );
}
