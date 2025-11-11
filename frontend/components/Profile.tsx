"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";

const API_URL = "http://localhost:8000";

interface Config {
  email?: {
    default_recipient?: string;
    default_subject_prefix?: string;
    signature?: string;
  };
  documents?: {
    folders?: string[];
    supported_types?: string[];
  };
  imessage?: {
    default_phone_number?: string;
  };
  twitter?: {
    default_list?: string;
    lists?: Record<string, string>;
  };
  discord?: {
    default_server?: string;
    default_channel?: string;
    credentials?: {
      email?: string;
      password?: string;
      mfa_code?: string;
    };
  };
  maps?: {
    default_maps_service?: string;
    max_stops?: number;
  };
  browser?: {
    headless?: boolean;
    timeout?: number;
    allowed_domains?: string[];
  };
}

export default function Profile() {
  const [config, setConfig] = useState<Config>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [newFolder, setNewFolder] = useState("");
  const [newDomain, setNewDomain] = useState("");
  const [newTwitterList, setNewTwitterList] = useState({ name: "", id: "" });

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      const response = await fetch(`${API_URL}/api/config`);
      if (!response.ok) throw new Error("Failed to load config");
      const data = await response.json();
      setConfig(data);
    } catch (error) {
      setMessage({ type: "error", text: `Failed to load config: ${error}` });
    } finally {
      setLoading(false);
    }
  };

  const saveConfig = async () => {
    setSaving(true);
    setMessage(null);
    
    try {
      const response = await fetch(`${API_URL}/api/config`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ updates: config }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Failed to save config");
      }

      const result = await response.json();
      setMessage({ type: "success", text: result.message || "Config saved successfully!" });
      
      // Reload config to get sanitized version
      await loadConfig();
    } catch (error: any) {
      setMessage({ type: "error", text: error.message || "Failed to save config" });
    } finally {
      setSaving(false);
    }
  };

  const updateConfig = (path: string[], value: any) => {
    setConfig((prev) => {
      // Deep clone to avoid mutating state directly
      const newConfig = JSON.parse(JSON.stringify(prev));
      let current: any = newConfig;
      
      for (let i = 0; i < path.length - 1; i++) {
        if (!current[path[i]]) {
          current[path[i]] = {};
        }
        current = current[path[i]];
      }
      
      current[path[path.length - 1]] = value;
      return newConfig;
    });
  };

  const addFolder = () => {
    if (newFolder.trim()) {
      const folders = config.documents?.folders || [];
      updateConfig(["documents", "folders"], [...folders, newFolder.trim()]);
      setNewFolder("");
    }
  };

  const removeFolder = (index: number) => {
    const folders = config.documents?.folders || [];
    updateConfig(["documents", "folders"], folders.filter((_, i) => i !== index));
  };

  const addDomain = () => {
    if (newDomain.trim()) {
      const domains = config.browser?.allowed_domains || [];
      updateConfig(["browser", "allowed_domains"], [...domains, newDomain.trim()]);
      setNewDomain("");
    }
  };

  const removeDomain = (index: number) => {
    const domains = config.browser?.allowed_domains || [];
    updateConfig(["browser", "allowed_domains"], domains.filter((_, i) => i !== index));
  };

  const addTwitterList = () => {
    if (newTwitterList.name.trim() && newTwitterList.id.trim()) {
      const lists = config.twitter?.lists || {};
      updateConfig(["twitter", "lists"], { ...lists, [newTwitterList.name]: newTwitterList.id });
      setNewTwitterList({ name: "", id: "" });
    }
  };

  const removeTwitterList = (name: string) => {
    const lists = { ...(config.twitter?.lists || {}) };
    delete lists[name];
    updateConfig(["twitter", "lists"], lists);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-white/60">Loading profile...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-4">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-white">Profile Settings</h2>
        <button
          onClick={saveConfig}
          disabled={saving}
          className="glass-button px-4 py-2 rounded-lg font-medium transition-all duration-300 bg-accent-cyan/20 text-accent-cyan hover:bg-accent-cyan/30 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {saving ? "Saving..." : "Save"}
        </button>
      </div>

      {message && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className={`p-3 rounded-lg ${
            message.type === "success"
              ? "bg-green-500/20 text-green-300"
              : "bg-red-500/20 text-red-300"
          }`}
        >
          {message.text}
        </motion.div>
      )}

      {/* Email Settings */}
      <section className="glass rounded-xl p-6">
        <h3 className="text-lg font-semibold text-white mb-4">Email Settings</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-white/80 mb-2">
              Default Email (for "email to me")
            </label>
            <input
              type="email"
              value={config.email?.default_recipient || ""}
              onChange={(e) => updateConfig(["email", "default_recipient"], e.target.value)}
              className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-white/40 focus:outline-none focus:border-accent-cyan/50"
              placeholder="your@email.com"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-white/80 mb-2">
              Default Subject Prefix
            </label>
            <input
              type="text"
              value={config.email?.default_subject_prefix || ""}
              onChange={(e) => updateConfig(["email", "default_subject_prefix"], e.target.value)}
              className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-white/40 focus:outline-none focus:border-accent-cyan/50"
              placeholder="[Auto-generated]"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-white/80 mb-2">Signature</label>
            <textarea
              value={config.email?.signature || ""}
              onChange={(e) => updateConfig(["email", "signature"], e.target.value)}
              rows={3}
              className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-white/40 focus:outline-none focus:border-accent-cyan/50 resize-none"
              placeholder="Email signature"
            />
          </div>
        </div>
      </section>

      {/* Document Folders */}
      <section className="glass rounded-xl p-6">
        <h3 className="text-lg font-semibold text-white mb-4">Document Folders</h3>
        <div className="space-y-4">
          <div className="flex gap-2">
            <input
              type="text"
              value={newFolder}
              onChange={(e) => setNewFolder(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addFolder()}
              className="flex-1 px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-white/40 focus:outline-none focus:border-accent-cyan/50"
              placeholder="/path/to/folder"
            />
            <button
              onClick={addFolder}
              className="px-4 py-2 bg-accent-cyan/20 text-accent-cyan rounded-lg hover:bg-accent-cyan/30 transition-colors"
            >
              Add
            </button>
          </div>
          <div className="space-y-2">
            {config.documents?.folders?.map((folder, index) => (
              <div key={index} className="flex items-center justify-between p-2 bg-white/5 rounded-lg">
                <span className="text-white/80 text-sm">{folder}</span>
                <button
                  onClick={() => removeFolder(index)}
                  className="text-red-400 hover:text-red-300 text-sm"
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
          <div>
            <label className="block text-sm font-medium text-white/80 mb-2">File Types</label>
            <div className="flex gap-2 flex-wrap">
              {config.documents?.supported_types?.map((type, index) => (
                <span key={index} className="px-3 py-1 bg-white/10 rounded-lg text-white/80 text-sm">
                  {type}
                </span>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* iMessage Settings */}
      <section className="glass rounded-xl p-6">
        <h3 className="text-lg font-semibold text-white mb-4">iMessage Settings</h3>
        <div>
          <label className="block text-sm font-medium text-white/80 mb-2">
            Default Phone Number
          </label>
          <input
            type="tel"
            value={config.imessage?.default_phone_number || ""}
            onChange={(e) => updateConfig(["imessage", "default_phone_number"], e.target.value)}
            className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-white/40 focus:outline-none focus:border-accent-cyan/50"
            placeholder="+1234567890"
          />
        </div>
      </section>

      {/* Twitter Settings */}
      <section className="glass rounded-xl p-6">
        <h3 className="text-lg font-semibold text-white mb-4">Twitter Settings</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-white/80 mb-2">Default List</label>
            <input
              type="text"
              value={config.twitter?.default_list || ""}
              onChange={(e) => updateConfig(["twitter", "default_list"], e.target.value)}
              className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-white/40 focus:outline-none focus:border-accent-cyan/50"
              placeholder="product_watch"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-white/80 mb-2">List Mappings</label>
            <div className="flex gap-2 mb-2">
              <input
                type="text"
                value={newTwitterList.name}
                onChange={(e) => setNewTwitterList({ ...newTwitterList, name: e.target.value })}
                className="flex-1 px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-white/40 focus:outline-none focus:border-accent-cyan/50"
                placeholder="List name"
              />
              <input
                type="text"
                value={newTwitterList.id}
                onChange={(e) => setNewTwitterList({ ...newTwitterList, id: e.target.value })}
                className="flex-1 px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-white/40 focus:outline-none focus:border-accent-cyan/50"
                placeholder="List ID"
              />
              <button
                onClick={addTwitterList}
                className="px-4 py-2 bg-accent-cyan/20 text-accent-cyan rounded-lg hover:bg-accent-cyan/30 transition-colors"
              >
                Add
              </button>
            </div>
            <div className="space-y-2">
              {Object.entries(config.twitter?.lists || {}).map(([name, id]) => (
                <div key={name} className="flex items-center justify-between p-2 bg-white/5 rounded-lg">
                  <span className="text-white/80 text-sm">
                    <span className="font-medium">{name}</span>: {id}
                  </span>
                  <button
                    onClick={() => removeTwitterList(name)}
                    className="text-red-400 hover:text-red-300 text-sm"
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Discord Settings */}
      <section className="glass rounded-xl p-6">
        <h3 className="text-lg font-semibold text-white mb-4">Discord Settings</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-white/80 mb-2">Default Server</label>
            <input
              type="text"
              value={config.discord?.default_server || ""}
              onChange={(e) => updateConfig(["discord", "default_server"], e.target.value)}
              className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-white/40 focus:outline-none focus:border-accent-cyan/50"
              placeholder="Personal"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-white/80 mb-2">Default Channel</label>
            <input
              type="text"
              value={config.discord?.default_channel || ""}
              onChange={(e) => updateConfig(["discord", "default_channel"], e.target.value)}
              className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-white/40 focus:outline-none focus:border-accent-cyan/50"
              placeholder="general"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-white/80 mb-2">Email</label>
            <input
              type="email"
              value={config.discord?.credentials?.email || ""}
              onChange={(e) => {
                updateConfig(["discord", "credentials"], {
                  ...config.discord?.credentials,
                  email: e.target.value,
                });
              }}
              className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-white/40 focus:outline-none focus:border-accent-cyan/50"
              placeholder="discord@email.com"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-white/80 mb-2">Password</label>
            <input
              type="password"
              value={config.discord?.credentials?.password === "***REDACTED***" ? "" : (config.discord?.credentials?.password || "")}
              onChange={(e) => {
                updateConfig(["discord", "credentials"], {
                  ...config.discord?.credentials,
                  password: e.target.value,
                });
              }}
              className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-white/40 focus:outline-none focus:border-accent-cyan/50"
              placeholder="••••••••"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-white/80 mb-2">MFA Code</label>
            <input
              type="text"
              value={config.discord?.credentials?.mfa_code === "***REDACTED***" ? "" : (config.discord?.credentials?.mfa_code || "")}
              onChange={(e) => {
                updateConfig(["discord", "credentials"], {
                  ...config.discord?.credentials,
                  mfa_code: e.target.value,
                });
              }}
              className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-white/40 focus:outline-none focus:border-accent-cyan/50"
              placeholder="123456"
            />
          </div>
        </div>
      </section>

      {/* Maps Settings */}
      <section className="glass rounded-xl p-6">
        <h3 className="text-lg font-semibold text-white mb-4">Maps Settings</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-white/80 mb-2">Default Maps Service</label>
            <select
              value={config.maps?.default_maps_service || "apple"}
              onChange={(e) => updateConfig(["maps", "default_maps_service"], e.target.value)}
              className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:border-accent-cyan/50"
            >
              <option value="apple">Apple Maps</option>
              <option value="google">Google Maps</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-white/80 mb-2">Max Stops</label>
            <input
              type="number"
              value={config.maps?.max_stops || 20}
              onChange={(e) => updateConfig(["maps", "max_stops"], parseInt(e.target.value) || 20)}
              className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-white/40 focus:outline-none focus:border-accent-cyan/50"
              min="1"
              max="50"
            />
          </div>
        </div>
      </section>

      {/* Browser Settings */}
      <section className="glass rounded-xl p-6">
        <h3 className="text-lg font-semibold text-white mb-4">Browser Settings</h3>
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="headless"
              checked={config.browser?.headless || false}
              onChange={(e) => updateConfig(["browser", "headless"], e.target.checked)}
              className="w-4 h-4 rounded bg-white/5 border-white/10 text-accent-cyan focus:ring-accent-cyan"
            />
            <label htmlFor="headless" className="text-white/80 text-sm">
              Run browser in headless mode
            </label>
          </div>
          <div>
            <label className="block text-sm font-medium text-white/80 mb-2">Timeout (ms)</label>
            <input
              type="number"
              value={config.browser?.timeout || 30000}
              onChange={(e) => updateConfig(["browser", "timeout"], parseInt(e.target.value) || 30000)}
              className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-white/40 focus:outline-none focus:border-accent-cyan/50"
              min="1000"
              max="120000"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-white/80 mb-2">Allowed Domains</label>
            <div className="flex gap-2 mb-2">
              <input
                type="text"
                value={newDomain}
                onChange={(e) => setNewDomain(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addDomain()}
                className="flex-1 px-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-white/40 focus:outline-none focus:border-accent-cyan/50"
                placeholder="example.com"
              />
              <button
                onClick={addDomain}
                className="px-4 py-2 bg-accent-cyan/20 text-accent-cyan rounded-lg hover:bg-accent-cyan/30 transition-colors"
              >
                Add
              </button>
            </div>
            <div className="space-y-2">
              {config.browser?.allowed_domains?.map((domain, index) => (
                <div key={index} className="flex items-center justify-between p-2 bg-white/5 rounded-lg">
                  <span className="text-white/80 text-sm">{domain}</span>
                  <button
                    onClick={() => removeDomain(index)}
                    className="text-red-400 hover:text-red-300 text-sm"
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

