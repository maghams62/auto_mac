/**
 * Centralized UI tokens for the Raycast-style spotlight launcher.
 * Keep this file small and declarative so other surfaces (Electron, docs)
 * can reuse the same heuristics without duplicating literals.
 */
export const spotlightUi = {
  miniConversation: {
    minTurns: 1,
    maxTurns: 3,
    defaultTurns: 2,
  },
  historyPanel: {
    maxHeight: 192,
    timestampFormat: {
      hour: "2-digit" as const,
      minute: "2-digit" as const,
    },
  },
  motion: {
    fade: {
      duration: 0.18,
      ease: [0.4, 0, 0.2, 1],
    },
    spring: {
      type: "spring",
      stiffness: 320,
      damping: 32,
      mass: 0.6,
    },
    overlay: {
      duration: 0.24,
      ease: [0.33, 1, 0.68, 1],
    },
    card: {
      type: "spring",
      stiffness: 280,
      damping: 28,
      mass: 0.75,
    },
    progress: {
      duration: 1.4,
      ease: "easeInOut",
    },
  },
};

export const clampMiniConversationDepth = (value: number) => {
  const { minTurns, maxTurns } = spotlightUi.miniConversation;
  return Math.min(Math.max(value, minTurns), maxTurns);
};

