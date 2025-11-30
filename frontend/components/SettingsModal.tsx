"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useIsElectronRuntime } from "@/hooks/useIsElectron";
import type { Settings } from "@/types/electron";
import { spotlightUi, clampMiniConversationDepth } from "@/config/ui";

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
  const [settings, setSettings] = useState<Settings>({
    hotkey: "CommandOrControl+Option+K",
    hideOnBlur: true,
    startAtLogin: false,
    theme: "dark",
    miniConversationDepth: spotlightUi.miniConversation.defaultTurns,
  });
  const [isSaving, setIsSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<"idle" | "success" | "error">("idle");
  const isElectronRuntime = useIsElectronRuntime();

  // Load settings when modal opens
  useEffect(() => {
    if (isOpen && isElectronRuntime) {
      window.electronAPI?.getSettings().then((loaded) => {
        if (loaded) {
          setSettings(prev => ({
            ...prev,
            ...loaded,
            miniConversationDepth: clampMiniConversationDepth(
              loaded.miniConversationDepth ?? spotlightUi.miniConversation.defaultTurns
            ),
          }));
        }
      });
    }
  }, [isOpen, isElectronRuntime]);

  // Handle escape key
  useEffect(() => {
    if (!isOpen) return;
    
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  const handleSave = async () => {
    if (!isElectronRuntime) return;
    
    setIsSaving(true);
    setSaveStatus("idle");
    
    try {
      const payload: Settings = {
        ...settings,
        miniConversationDepth: clampMiniConversationDepth(
          settings.miniConversationDepth ?? spotlightUi.miniConversation.defaultTurns
        ),
      };
      await window.electronAPI?.updateSettings(payload);
      setSaveStatus("success");
      setTimeout(() => {
        onClose();
        setSaveStatus("idle");
      }, 500);
    } catch (error) {
      console.error("Failed to save settings:", error);
      setSaveStatus("error");
    } finally {
      setIsSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      >
        <motion.div
          initial={{ scale: 0.95, opacity: 0, y: 10 }}
          animate={{ scale: 1, opacity: 1, y: 0 }}
          exit={{ scale: 0.95, opacity: 0, y: 10 }}
          transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
          className="bg-neutral-900 border border-white/10 rounded-2xl p-6 w-[440px] shadow-2xl"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2 bg-white/5 rounded-xl">
              <span className="text-2xl">⚙️</span>
            </div>
            <div>
              <h2 className="text-xl font-semibold text-white">Preferences</h2>
              <p className="text-sm text-white/50">Customize Cerebros behavior</p>
            </div>
          </div>

          <div className="space-y-5">
            {/* Hotkey */}
            <div className="space-y-2">
              <label className="block text-sm font-medium text-white/70">
                Global Hotkey
              </label>
              <input
                type="text"
                value={settings.hotkey}
                onChange={(e) => setSettings({ ...settings, hotkey: e.target.value })}
                className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white placeholder-white/30 focus:border-blue-500/50 focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all"
                placeholder="CommandOrControl+Option+K"
              />
              <p className="text-xs text-white/40">
                Use &quot;CommandOrControl&quot; for cross-platform, &quot;Command&quot; for Mac only
              </p>
            </div>

            {/* Divider */}
            <div className="border-t border-white/10" />

            {/* Checkboxes */}
            <div className="space-y-3">
              <label className="flex items-center gap-3 cursor-pointer group">
                <div className="relative">
                  <input
                    type="checkbox"
                    checked={settings.startAtLogin}
                    onChange={(e) => setSettings({ ...settings, startAtLogin: e.target.checked })}
                    className="sr-only peer"
                  />
                  <div className="w-5 h-5 rounded-md border border-white/20 bg-white/5 peer-checked:bg-blue-500 peer-checked:border-blue-500 transition-all flex items-center justify-center">
                    <motion.svg
                      initial={false}
                      animate={{ scale: settings.startAtLogin ? 1 : 0 }}
                      className="w-3 h-3 text-white"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </motion.svg>
                  </div>
                </div>
                <div>
                  <span className="text-white group-hover:text-white/90 transition-colors">Start Cerebros at login</span>
                  <p className="text-xs text-white/40">Launch automatically when you log in</p>
                </div>
              </label>

              <label className="flex items-center gap-3 cursor-pointer group">
                <div className="relative">
                  <input
                    type="checkbox"
                    checked={settings.hideOnBlur}
                    onChange={(e) => setSettings({ ...settings, hideOnBlur: e.target.checked })}
                    className="sr-only peer"
                  />
                  <div className="w-5 h-5 rounded-md border border-white/20 bg-white/5 peer-checked:bg-blue-500 peer-checked:border-blue-500 transition-all flex items-center justify-center">
                    <motion.svg
                      initial={false}
                      animate={{ scale: settings.hideOnBlur ? 1 : 0 }}
                      className="w-3 h-3 text-white"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </motion.svg>
                  </div>
                </div>
                <div>
                  <span className="text-white group-hover:text-white/90 transition-colors">Hide when clicking outside</span>
                  <p className="text-xs text-white/40">Spotlight-style behavior</p>
                </div>
              </label>
            </div>

            {/* Mini conversation depth */}
            <div className="space-y-2">
              <label className="block text-sm font-medium text-white/70">
                Mini Conversation Turns
              </label>
              <input
                type="number"
                min={spotlightUi.miniConversation.minTurns}
                max={spotlightUi.miniConversation.maxTurns}
                value={settings.miniConversationDepth}
                onChange={(e) => {
                  const value = Number(e.target.value);
                  setSettings({
                    ...settings,
                    miniConversationDepth: clampMiniConversationDepth(
                      Number.isNaN(value)
                        ? spotlightUi.miniConversation.defaultTurns
                        : value
                    ),
                  });
                }}
                className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white placeholder-white/30 focus:border-blue-500/50 focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all"
              />
              <p className="text-xs text-white/40">
                Number of user/assistant turns to show in the spotlight history before expanding the desktop view.
              </p>
            </div>
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between mt-8 pt-4 border-t border-white/10">
            <div className="text-xs text-white/30">
              {!isElectronRuntime && "Settings only work in the desktop app"}
            </div>
            <div className="flex gap-3">
              <button
                onClick={onClose}
                className="px-4 py-2 text-white/60 hover:text-white transition-colors rounded-lg hover:bg-white/5"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={isSaving || !isElectronRuntime}
                className={`px-5 py-2 rounded-xl font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed ${
                  saveStatus === "success"
                    ? "bg-green-500 text-white"
                    : saveStatus === "error"
                    ? "bg-red-500 text-white"
                    : "bg-blue-600 hover:bg-blue-500 text-white"
                }`}
              >
                {isSaving ? (
                  <motion.span
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                    className="inline-block"
                  >
                    ⏳
                  </motion.span>
                ) : saveStatus === "success" ? (
                  "✓ Saved"
                ) : saveStatus === "error" ? (
                  "Failed"
                ) : (
                  "Save"
                )}
              </button>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

