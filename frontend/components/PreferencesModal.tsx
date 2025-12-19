"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Settings } from "@/types/electron";
import { useIsElectronRuntime } from "@/hooks/useIsElectron";
import { spotlightUi, clampMiniConversationDepth } from "@/config/ui";

interface PreferencesModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function PreferencesModal({ isOpen, onClose }: PreferencesModalProps) {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const isElectronRuntime = useIsElectronRuntime();

  // Load settings when modal opens
  useEffect(() => {
    if (isOpen && isElectronRuntime) {
      loadSettings();
    }
  }, [isOpen, isElectronRuntime]);

  const loadSettings = async () => {
    try {
      setLoading(true);
      const currentSettings = await window.electronAPI!.getSettings();
      setSettings({
        ...currentSettings,
        miniConversationDepth: clampMiniConversationDepth(
          currentSettings.miniConversationDepth ?? spotlightUi.miniConversation.defaultTurns
        ),
      });
    } catch (error) {
      console.error("Failed to load settings:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!settings) return;

    try {
      setSaving(true);
      const payload: Settings = {
        ...settings,
        miniConversationDepth: clampMiniConversationDepth(
          settings.miniConversationDepth ?? spotlightUi.miniConversation.defaultTurns
        ),
      };
      await window.electronAPI!.updateSettings(payload);
      console.log("Settings saved successfully");
      onClose();
    } catch (error) {
      console.error("Failed to save settings:", error);
    } finally {
      setSaving(false);
    }
  };

  const handleHotkeyChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!settings) return;
    setSettings({ ...settings, hotkey: e.target.value });
  };

  const handleHideOnBlurToggle = () => {
    if (!settings) return;
    setSettings({ ...settings, hideOnBlur: !settings.hideOnBlur });
  };

  const handleStartAtLoginToggle = () => {
    if (!settings) return;
    setSettings({ ...settings, startAtLogin: !settings.startAtLogin });
  };

  const handleThemeChange = (theme: 'dark' | 'light' | 'auto') => {
    if (!settings) return;
    setSettings({ ...settings, theme });
  };

  const handleMiniConversationDepthChange = (value: number) => {
    if (!settings) return;
    setSettings({
      ...settings,
      miniConversationDepth: clampMiniConversationDepth(value),
    });
  };

  if (!isElectronRuntime) {
    return null;
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50"
          />

          {/* Modal */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="bg-background border border-glass rounded-2xl shadow-2xl w-full max-w-md overflow-hidden">
              {/* Header */}
              <div className="px-6 py-4 border-b border-glass">
                <h2 className="text-xl font-semibold">Preferences</h2>
              </div>

              {/* Content */}
              <div className="px-6 py-4 space-y-6">
                {loading ? (
                  <div className="text-center text-muted py-8">Loading settings...</div>
                ) : settings ? (
                  <>
                    {/* Hotkey */}
                    <div>
                      <label className="block text-sm font-medium mb-2">
                        Global Hotkey
                      </label>
                      <input
                        type="text"
                        value={settings.hotkey}
                        onChange={handleHotkeyChange}
                        className="w-full px-3 py-2 bg-glass border border-glass-strong rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500"
                        placeholder="CommandOrControl+Alt+Space"
                      />
                      <p className="text-xs text-muted mt-1">
                        Use Electron accelerator format (e.g., CommandOrControl+Space)
                      </p>
                    </div>

                    {/* Hide on Blur */}
                    <div className="flex items-center justify-between">
                      <div>
                        <label className="block text-sm font-medium">
                          Hide on Blur
                        </label>
                        <p className="text-xs text-muted mt-1">
                          Hide launcher when it loses focus
                        </p>
                      </div>
                      <button
                        onClick={handleHideOnBlurToggle}
                        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                          settings.hideOnBlur ? "bg-purple-600" : "bg-glass-strong"
                        }`}
                      >
                        <span
                          className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                            settings.hideOnBlur ? "translate-x-6" : "translate-x-1"
                          }`}
                        />
                      </button>
                    </div>

                    {/* Start at Login */}
                    <div className="flex items-center justify-between">
                      <div>
                        <label className="block text-sm font-medium">
                          Start at Login
                        </label>
                        <p className="text-xs text-muted mt-1">
                          Launch Cerebros when you log in
                        </p>
                      </div>
                      <button
                        onClick={handleStartAtLoginToggle}
                        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                          settings.startAtLogin ? "bg-purple-600" : "bg-glass-strong"
                        }`}
                      >
                        <span
                          className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                            settings.startAtLogin ? "translate-x-6" : "translate-x-1"
                          }`}
                        />
                      </button>
                    </div>

                    {/* Theme */}
                    <div>
                      <label className="block text-sm font-medium mb-2">
                        Theme
                      </label>
                      <div className="flex gap-2">
                        {(['dark', 'light', 'auto'] as const).map((theme) => (
                          <button
                            key={theme}
                            onClick={() => handleThemeChange(theme)}
                            className={`flex-1 px-3 py-2 rounded-lg border transition-colors ${
                              settings.theme === theme
                                ? "bg-purple-600 border-purple-600 text-white"
                                : "bg-glass border-glass-strong hover:bg-glass-hover"
                            }`}
                          >
                            {theme.charAt(0).toUpperCase() + theme.slice(1)}
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Mini Conversation Depth */}
                    <div>
                      <label className="block text-sm font-medium mb-2">
                        Mini Conversation Turns
                      </label>
                      <input
                        type="number"
                        min={spotlightUi.miniConversation.minTurns}
                        max={spotlightUi.miniConversation.maxTurns}
                        value={
                          settings.miniConversationDepth ?? spotlightUi.miniConversation.defaultTurns
                        }
                        onChange={(e) => {
                          const value = Number(e.target.value);
                          handleMiniConversationDepthChange(
                            Number.isNaN(value)
                              ? spotlightUi.miniConversation.defaultTurns
                              : value
                          );
                        }}
                        className="w-full px-3 py-2 bg-glass border border-glass-strong rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500"
                      />
                      <p className="text-xs text-muted mt-1">
                        Controls how many recent user/assistant turns appear in the spotlight view before expanding.
                      </p>
                    </div>
                  </>
                ) : (
                  <div className="text-center text-muted py-8">
                    Failed to load settings
                  </div>
                )}
              </div>

              {/* Footer */}
              <div className="px-6 py-4 border-t border-glass flex justify-end gap-3">
                <button
                  onClick={onClose}
                  className="px-4 py-2 rounded-lg bg-glass hover:bg-glass-hover transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSave}
                  disabled={saving || loading || !settings}
                  className="px-4 py-2 rounded-lg bg-purple-600 hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {saving ? "Saving..." : "Save"}
                </button>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
