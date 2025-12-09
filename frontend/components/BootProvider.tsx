"use client";

import { createContext, useContext, ReactNode, useState, useEffect } from "react";

interface BootContextType {
  bootPhase: "assets" | "websocket" | "ready" | "error";
  assetsLoaded: boolean;
  bootError: string | null;
  signalBootComplete: () => void;
  signalBootError: (error: string) => void;
}

const BootContext = createContext<BootContextType | null>(null);

export const useBootContext = () => {
  const context = useContext(BootContext);
  if (!context) {
    throw new Error("useBootContext must be used within a BootProvider");
  }
  return context;
};

interface BootProviderProps {
  children: ReactNode;
}

export function BootProvider({ children }: BootProviderProps) {
  const [bootPhase, setBootPhase] = useState<"assets" | "websocket" | "ready" | "error">("assets");
  const [assetsLoaded, setAssetsLoaded] = useState(false);
  const [bootError, setBootError] = useState<string | null>(null);

  // Boot sequence using promise-based gates
  useEffect(() => {
    const initializeBoot = async () => {
      setBootPhase("assets");
      try {
        // Wait for critical assets: fonts and basic DOM readiness
        await Promise.all([
          document.fonts.ready,
          // Small delay to ensure component mounting is stable
          new Promise(resolve => setTimeout(resolve, 100))
        ]);

        setAssetsLoaded(true);
        setBootPhase("websocket");
      } catch (error) {
        console.warn("Asset loading failed, continuing anyway:", error);
        setAssetsLoaded(true);
        setBootPhase("websocket");
      }
    };

    initializeBoot();
  }, []);

  // Fail gracefully if websocket boot takes too long
  useEffect(() => {
    if (bootPhase !== "websocket") {
      return;
    }
    const timeout = setTimeout(() => {
      setBootError("Timed out connecting to Cerebros. Ensure api_server.py and npm run dev are running.");
      setBootPhase("error");
    }, 15000);
    return () => clearTimeout(timeout);
  }, [bootPhase]);

  // Signal when boot is complete (called by ChatInterface when WebSocket connects)
  const signalBootComplete = () => {
    setBootError(null);
    setBootPhase("ready");
  };

  // Signal boot error (called by ChatInterface when WebSocket fails permanently)
  const signalBootError = (error: string) => {
    console.error("Boot error:", error);
    setBootError(error);
    setBootPhase("error");
  };

  const value = {
    bootPhase,
    assetsLoaded,
    bootError,
    signalBootComplete,
    signalBootError,
  };

  return (
    <BootContext.Provider value={value}>
      {children}
    </BootContext.Provider>
  );
}
