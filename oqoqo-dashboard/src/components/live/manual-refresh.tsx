"use client";

import { useState } from "react";
import { AlertTriangle, Check, RefreshCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { fetchApiEnvelope } from "@/lib/http/api-response";
import { useDashboardStore } from "@/lib/state/dashboard-store";
import { logClientEvent } from "@/lib/logging";
import { shortDate } from "@/lib/utils";
import type { LiveActivitySnapshot, LiveMode, Project } from "@/lib/types";

type RefreshState = "idle" | "refreshing" | "success" | "error";

export function ManualRefreshButton() {
  const applyLiveProjects = useDashboardStore((state) => state.applyLiveProjects);
  const setLiveStatus = useDashboardStore((state) => state.setLiveStatus);
  const liveStatus = useDashboardStore((state) => state.liveStatus);
  const [state, setState] = useState<RefreshState>("idle");
  const [lastManualRefresh, setLastManualRefresh] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleRefresh = async () => {
    if (state === "refreshing") return;
    setState("refreshing");
    setErrorMessage(null);

    try {
      const payload = await fetchApiEnvelope<{ snapshot?: LiveActivitySnapshot; projects?: Project[] }>(
        "/api/activity?manual=1",
        { cache: "no-store" },
      );
      const data = payload.data;
      if (!data?.snapshot || !Array.isArray(data.projects)) {
        throw new Error("Live payload missing data");
      }

      applyLiveProjects(data.projects as Project[], data.snapshot as LiveActivitySnapshot, payload.mode);
      const message = describeLiveFallback(payload.status, payload.fallbackReason, payload.error?.message);
      if (message) {
        setLiveStatus({
          mode: payload.mode ?? liveStatus.mode,
          lastUpdated: data.snapshot.generatedAt,
          message,
        });
      }
      logClientEvent("live.manual-refresh.success", {
        mode: payload.mode ?? "unknown",
        generatedAt: data.snapshot.generatedAt,
      });
      setState("success");
      const timestamp = data.snapshot.generatedAt ?? new Date().toISOString();
      setLastManualRefresh(timestamp);
      setTimeout(() => setState("idle"), 2500);
    } catch (error) {
      console.warn("Manual refresh failed", error);
      const message = error instanceof Error ? error.message : "Unexpected error refreshing live data";
      setState("error");
      setErrorMessage(message);
      setLiveStatus({
        ...liveStatus,
        mode: "error",
        message,
      });
      logClientEvent("live.manual-refresh.error", { message });
      setTimeout(() => setState("idle"), 4000);
    }
  };

  const renderStatus = () => {
    if (state === "refreshing") {
      return (
        <span className="flex items-center gap-1 text-xs text-muted-foreground">
          <RefreshCcw className="h-3 w-3 animate-spin" />
          Refreshing…
        </span>
      );
    }
    if (state === "success") {
      return (
        <span className="flex items-center gap-1 text-xs text-emerald-300">
          <Check className="h-3 w-3" />
          Snapshot updated
        </span>
      );
    }
    if (state === "error" && errorMessage) {
      return (
        <span className="flex items-center gap-1 text-xs text-amber-200">
          <AlertTriangle className="h-3 w-3" />
          {errorMessage}
        </span>
      );
    }
    const last = lastManualRefresh ?? liveStatus.lastUpdated;
    return (
      <span className="text-xs text-muted-foreground">
        Last refresh {last ? shortDate(last) : "not yet"}
      </span>
    );
  };

  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button
        variant="outline"
        size="sm"
        className="rounded-full border-border/60"
        onClick={handleRefresh}
        disabled={state === "refreshing"}
      >
        <RefreshCcw className={`mr-2 h-4 w-4 ${state === "refreshing" ? "animate-spin" : ""}`} />
        {state === "refreshing" ? "Refreshing…" : "Refresh live data"}
      </Button>
      {renderStatus()}
    </div>
  );
}

function describeLiveFallback(status: string, fallbackReason?: string, errorMessage?: string) {
  if (status === "OK") {
    return undefined;
  }
  if (fallbackReason === "cerebros_unavailable") {
    return "Cerebros unavailable, showing fallback snapshot";
  }
  if (fallbackReason === "synthetic_fallback") {
    return "Synthetic fixtures in use";
  }
  return errorMessage ?? "Live ingest degraded";
}

