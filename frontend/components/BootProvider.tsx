"use client";

import { createContext, useContext, ReactNode, useState, useEffect } from "react";

interface BootContextType {
  bootPhase: "assets" | "websocket" | "ready" | "error";
  assetsLoaded: boolean;
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

  // Signal when boot is complete (called by ChatInterface when WebSocket connects)
  const signalBootComplete = () => {
    setBootPhase("ready");
  };

  // Signal boot error (called by ChatInterface when WebSocket fails permanently)
  const signalBootError = (error: string) => {
    console.error("Boot error:", error);
    setBootPhase("error");
  };

  const value = {
    bootPhase,
    assetsLoaded,
    signalBootComplete,
    signalBootError,
  };

  return (
    <BootContext.Provider value={value}>
      {children}
    </BootContext.Provider>
  );
}
