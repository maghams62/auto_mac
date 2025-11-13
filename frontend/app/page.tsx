"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import ChatInterface from "@/components/ChatInterface";
import StartupOverlay from "@/components/StartupOverlay";


import { BootProvider, useBootContext } from "@/components/BootProvider";

export default function Home() {
  return (
    <BootProvider>
      <HomeContent />
    </BootProvider>
  );
}

function HomeContent() {
  const [isLoading, setIsLoading] = useState(true);
  const [showChat, setShowChat] = useState(false);
  const { bootPhase } = useBootContext();

  useEffect(() => {
    let hideLoaderTimer: number | undefined;
    let showChatTimer: number | undefined;

    if (bootPhase === "ready") {
      hideLoaderTimer = window.setTimeout(() => {
        setIsLoading(false);
        showChatTimer = window.setTimeout(() => setShowChat(true), 400);
      }, 800);
    } else if (bootPhase === "error") {
      setIsLoading(true);
      setShowChat(false);
    }

    return () => {
      if (hideLoaderTimer) {
        window.clearTimeout(hideLoaderTimer);
      }
      if (showChatTimer) {
        window.clearTimeout(showChatTimer);
      }
    };
  }, [bootPhase]);

  // Handle retry in error state
  const handleRetry = () => {
    // Reset UI state
    setIsLoading(true);
    setShowChat(false);
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
      {/* Startup Overlay */}
      <StartupOverlay
        phase={bootPhase}
        show={isLoading}
        error={bootPhase === "error" ? "Connection failed" : undefined}
        onRetry={handleRetry}
      />

      <motion.div
        variants={chatVariants}
        initial="hidden"
        animate={showChat ? "visible" : "hidden"}
        transition={{
          duration: 1.5,
          ease: [0.23, 1, 0.32, 1],
        }}
        className="flex-1 relative"
      >
        {/* Enhanced reveal effects */}
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: showChat ? 1 : 0, scale: showChat ? 1 : 0.9 }}
          transition={{ duration: 0.6, delay: showChat ? 0.3 : 0, ease: "easeOut" }}
          className="absolute inset-0 bg-gradient-to-br from-transparent via-blue-500/3 to-purple-500/3 pointer-events-none"
        />

        {/* Subtle glow overlay */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: showChat ? 1 : 0 }}
          transition={{ duration: 0.8, delay: showChat ? 0.5 : 0 }}
          className="absolute inset-0 bg-gradient-to-t from-transparent via-transparent to-white/2 pointer-events-none"
        />

        {/* Soft radial glow from center */}
        <motion.div
          initial={{
            opacity: 0,
            scale: 0,
            background: "radial-gradient(circle at center, rgba(59, 130, 246, 0.1) 0%, transparent 70%)"
          }}
          animate={{
            opacity: showChat ? 1 : 0,
            scale: showChat ? 1.2 : 0,
            background: "radial-gradient(circle at center, rgba(59, 130, 246, 0.05) 0%, transparent 70%)"
          }}
          transition={{ duration: 1.2, delay: showChat ? 0.2 : 0, ease: "easeOut" }}
          className="absolute inset-0 pointer-events-none"
        />

        <ChatInterface />
      </motion.div>
    </main>
  );
}
