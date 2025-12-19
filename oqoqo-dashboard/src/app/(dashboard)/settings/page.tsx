"use client";

import { useEffect, useMemo, useState } from "react";
import { Loader2, RefreshCcw, Save } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { ENABLE_PROTOTYPE_ADMIN } from "@/lib/feature-flags";

const PRIORITY_OPTIONS = ["code", "api_spec", "docs", "config", "slack", "activity_graph", "issues"];
const HINT_OPTIONS = ["slack", "tickets", "support"];
const AUTOMATION_MODES = [
  { value: "off", label: "No automation" },
  { value: "suggest_only", label: "Suggest fixes" },
  { value: "pr_only", label: "Open PRs" },
  { value: "pr_and_auto_merge", label: "Open + auto-merge" },
];

type DomainPolicy = {
  priority: string[];
  hints: string[];
};

type SettingsPayload = {
  sourceOfTruth: { domains: Record<string, DomainPolicy> };
  gitMonitor: {
    defaultBranch?: string;
    projects: Record<string, Array<{ repoId: string; branch: string }>>;
  };
  automation: { docUpdates: Record<string, { mode: string }> };
};

const createEmptySettings = (): SettingsPayload => ({
  sourceOfTruth: { domains: {} },
  gitMonitor: { defaultBranch: "", projects: {} },
  automation: { docUpdates: {} },
});

const deepClone = <T,>(value: T): T => JSON.parse(JSON.stringify(value));
const isObject = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null;

const computeDiff = (base: unknown, current: unknown): unknown => {
  if (Array.isArray(base) && Array.isArray(current)) {
    if (JSON.stringify(base) === JSON.stringify(current)) {
      return undefined;
    }
    return current;
  }
  if (isObject(base) && isObject(current)) {
    const diff: Record<string, unknown> = {};
    const keys = new Set([...Object.keys(base), ...Object.keys(current)]);
    keys.forEach((key) => {
      const value = computeDiff(base[key], current[key]);
      if (value !== undefined) {
        diff[key] = value;
      }
    });
    return Object.keys(diff).length ? diff : undefined;
  }
  if (base !== current) {
    return current;
  }
  return undefined;
};

export default function SettingsPage() {
  const [defaults, setDefaults] = useState<SettingsPayload | null>(null);
  const [draft, setDraft] = useState<SettingsPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  const fetchSettings = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/settings");
      if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`);
      }
      const payload = await response.json();
      setDefaults(payload.defaults || createEmptySettings());
      setDraft(payload.effective || createEmptySettings());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load settings");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!ENABLE_PROTOTYPE_ADMIN) {
      return;
    }
    fetchSettings();
  }, []);

  const diffPayload = useMemo(() => {
    if (!defaults || !draft) {
      return {};
    }
    return computeDiff(defaults, draft) || {};
  }, [defaults, draft]);

  const handleSave = async () => {
    if (!ENABLE_PROTOTYPE_ADMIN || !draft || !defaults) return;
    setSaving(true);
    setStatus(null);
    setError(null);
    try {
      const response = await fetch("/api/settings", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(diffPayload),
      });
      if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`);
      }
      await fetchSettings();
      setStatus("Settings saved");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  const handlePriorityChange = (domain: string, index: number, value: string) => {
    if (!draft) return;
    setDraft((prev) => {
      if (!prev) return prev;
      const domains = { ...prev.sourceOfTruth.domains };
      const policy = deepClone(domains[domain] || { priority: [], hints: [] });
      const nextPriority = [...policy.priority];
      nextPriority[index] = value;
      const filtered = nextPriority.filter((item, idx) => item && nextPriority.indexOf(item) === idx);
      policy.priority = filtered;
      domains[domain] = policy;
      return {
        ...prev,
        sourceOfTruth: { ...prev.sourceOfTruth, domains },
      };
    });
  };

  const handleHintToggle = (domain: string, hint: string, enabled: boolean) => {
    if (!draft) return;
    setDraft((prev) => {
      if (!prev) return prev;
      const domains = { ...prev.sourceOfTruth.domains };
      const policy = deepClone(domains[domain] || { priority: [], hints: [] });
      const hints = new Set(policy.hints || []);
      if (enabled) {
        hints.add(hint);
      } else {
        hints.delete(hint);
      }
      policy.hints = Array.from(hints);
      domains[domain] = policy;
      return {
        ...prev,
        sourceOfTruth: { ...prev.sourceOfTruth, domains },
      };
    });
  };

  const handleBranchChange = (projectId: string, index: number, key: "repoId" | "branch", value: string) => {
    if (!draft) return;
    setDraft((prev) => {
      if (!prev) return prev;
      const projects = { ...prev.gitMonitor.projects };
      const overrides = [...(projects[projectId] || [])];
      overrides[index] = { ...overrides[index], [key]: value };
      projects[projectId] = overrides;
      return {
        ...prev,
        gitMonitor: { ...prev.gitMonitor, projects },
      };
    });
  };

  const addRepoOverride = (projectId: string) => {
    if (!draft) return;
    setDraft((prev) => {
      if (!prev) return prev;
      const projects = { ...prev.gitMonitor.projects };
      const overrides = [...(projects[projectId] || [])];
      overrides.push({ repoId: "", branch: prev.gitMonitor.defaultBranch || "" });
      projects[projectId] = overrides;
      return {
        ...prev,
        gitMonitor: { ...prev.gitMonitor, projects },
      };
    });
  };

  const handleAutomationChange = (domain: string, mode: string) => {
    if (!draft) return;
    setDraft((prev) => {
      if (!prev) return prev;
      const docUpdates = { ...prev.automation.docUpdates };
      docUpdates[domain] = { mode };
      return {
        ...prev,
        automation: { docUpdates },
      };
    });
  };

  if (!ENABLE_PROTOTYPE_ADMIN) {
    return (
      <div className="rounded-2xl border border-dashed border-border/60 bg-muted/5 p-6 text-sm text-muted-foreground">
        System settings are hidden in this demo. Set{" "}
        <code className="rounded bg-muted/30 px-1 py-0.5 text-xs">NEXT_PUBLIC_ENABLE_PROTOTYPE_ADMIN=true</code> to enable the control surface.
      </div>
    );
  }

  if (loading || !draft || !defaults) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        {error ? error : <Loader2 className="h-4 w-4 animate-spin" />}
      </div>
    );
  }

  const projectEntries = Object.entries(draft.gitMonitor.projects || {});

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.4em] text-muted-foreground">Settings</p>
          <h1 className="text-3xl font-semibold text-foreground">Cerebros control surface</h1>
          <p className="text-sm text-muted-foreground">Tune source-of-truth policy, git monitoring, and automation without editing YAML.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" className="rounded-full" onClick={fetchSettings} disabled={saving}>
            <RefreshCcw className="mr-2 h-4 w-4" />
            Reload
          </Button>
          <Button className="rounded-full" onClick={handleSave} disabled={saving || !Object.keys(diffPayload).length}>
            {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
            Save
          </Button>
        </div>
      </div>

      {status ? <p className="text-sm text-emerald-400">{status}</p> : null}
      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      <Card>
        <CardHeader>
          <CardTitle>Source of truth</CardTitle>
          <CardDescription>Define which signals win when code, docs, and Slack disagree.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {Object.entries(draft.sourceOfTruth.domains || {}).map(([domain, policy]) => (
            <div key={domain} className="rounded-2xl border border-border/40 p-4">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-sm font-semibold capitalize text-foreground">{domain.replace(/_/g, " ")}</p>
                  <p className="text-xs text-muted-foreground">Select the trust order for this domain.</p>
                </div>
              </div>
              <div className="mt-3 grid gap-2 md:grid-cols-3">
                {policy.priority.map((entry, index) => (
                  <div key={`${domain}-priority-${index}`} className="flex flex-col gap-1">
                    <Label className="text-xs uppercase tracking-wide text-muted-foreground">Rank {index + 1}</Label>
                    <select
                      className="rounded-md border border-border/60 bg-background p-2 text-sm"
                      value={entry}
                      onChange={(event) => handlePriorityChange(domain, index, event.target.value)}
                    >
                      {PRIORITY_OPTIONS.map((option) => (
                        <option key={option} value={option}>
                          {option}
                        </option>
                      ))}
                    </select>
                  </div>
                ))}
              </div>
              <div className="mt-4 space-y-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Hint sources</p>
                <div className="flex flex-wrap gap-3">
                  {HINT_OPTIONS.map((hint) => (
                    <label key={hint} className="flex items-center gap-2 text-sm">
                      <Switch
                        checked={(policy.hints || []).includes(hint)}
                        onCheckedChange={(checked) => handleHintToggle(domain, hint, checked)}
                      />
                      {hint}
                    </label>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Git monitoring</CardTitle>
          <CardDescription>Override branches per project without restarting ingest.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-col gap-2">
            <Label className="text-xs uppercase tracking-wide text-muted-foreground">Default branch</Label>
            <Input
              value={draft.gitMonitor.defaultBranch || ""}
              onChange={(event) =>
                setDraft((prev) =>
                  prev
                    ? {
                        ...prev,
                        gitMonitor: { ...prev.gitMonitor, defaultBranch: event.target.value },
                      }
                    : prev,
                )
              }
            />
          </div>
          {projectEntries.map(([projectId, overrides]) => (
            <div key={projectId} className="rounded-2xl border border-border/40 p-4">
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold text-foreground">Project {projectId}</p>
                <Button variant="ghost" size="sm" onClick={() => addRepoOverride(projectId)}>
                  Add repo override
                </Button>
              </div>
              <div className="mt-3 divide-y divide-border/40">
                {overrides.map((entry, index) => (
                  <div key={`${projectId}-${index}`} className="grid gap-3 py-3 md:grid-cols-2">
                    <div>
                      <Label className="text-xs uppercase tracking-wide text-muted-foreground">Repo</Label>
                      <Input
                        value={entry.repoId}
                        placeholder="owner/repo"
                        onChange={(event) => handleBranchChange(projectId, index, "repoId", event.target.value)}
                      />
                    </div>
                    <div>
                      <Label className="text-xs uppercase tracking-wide text-muted-foreground">Branch</Label>
                      <Input value={entry.branch} onChange={(event) => handleBranchChange(projectId, index, "branch", event.target.value)} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
          {!projectEntries.length ? <p className="text-sm text-muted-foreground">No git overrides configured.</p> : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Automation & safety</CardTitle>
          <CardDescription>Choose how aggressively Cerebros heals doc drift by domain.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {Object.entries(draft.automation.docUpdates || {}).map(([domain, settings]) => (
            <div key={domain} className="rounded-2xl border border-border/40 p-4">
              <p className="text-sm font-semibold text-foreground">{domain.replace(/_/g, " ")}</p>
              <div className="mt-3 grid gap-2 md:grid-cols-2 lg:grid-cols-4">
                {AUTOMATION_MODES.map((mode) => (
                  <label key={mode.value} className="flex items-center gap-2 rounded-xl border border-border/40 px-3 py-2 text-sm">
                    <input
                      type="radio"
                      name={`${domain}-automation`}
                      value={mode.value}
                      checked={settings.mode === mode.value}
                      onChange={() => handleAutomationChange(domain, mode.value)}
                    />
                    {mode.label}
                  </label>
                ))}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Data sources</CardTitle>
          <CardDescription>Read-only view of the repos and branches currently wired into Cerebros.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {projectEntries.length ? (
            projectEntries.map(([projectId, overrides]) => (
              <div key={`sources-${projectId}`} className="rounded-2xl border border-border/40 p-4 text-sm">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Project {projectId}</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {overrides.map((entry) => (
                    <Badge key={`${projectId}-${entry.repoId}-${entry.branch}`} variant="outline" className="rounded-full border-border/60">
                      {entry.repoId || "repo"} · {entry.branch || "branch"}
                    </Badge>
                  ))}
                </div>
              </div>
            ))
          ) : (
            <p className="text-sm text-muted-foreground">Git monitoring is not configured yet.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
