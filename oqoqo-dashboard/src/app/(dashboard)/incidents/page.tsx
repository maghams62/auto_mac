"use client";

import { type ReactNode, useEffect, useMemo, useState } from "react";

import { IncidentCard } from "@/components/incidents/IncidentCard";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { IncidentRecord } from "@/lib/types";

type LoadState = "loading" | "ready" | "error";

const severityFilters = [
  { value: "all", label: "All" },
  { value: "critical", label: "Critical" },
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low", label: "Low" },
];

export default function IncidentsIndexPage() {
  const [incidents, setIncidents] = useState<IncidentRecord[]>([]);
  const [state, setState] = useState<LoadState>("loading");
  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const [componentFilter, setComponentFilter] = useState<string>("");
  const [serviceFilter, setServiceFilter] = useState<string>("");

  const query = useMemo(() => {
    const params = new URLSearchParams({ limit: "50" });
    if (severityFilter !== "all") {
      params.set("severity", severityFilter);
    }
    if (componentFilter.trim()) {
      params.set("componentId", componentFilter.trim());
    }
    if (serviceFilter.trim()) {
      params.set("serviceId", serviceFilter.trim());
    }
    return params.toString();
  }, [severityFilter, componentFilter, serviceFilter]);

  useEffect(() => {
    const controller = new AbortController();
    const load = async () => {
      try {
        setState("loading");
        const response = await fetch(`/api/incidents?${query}`, {
          cache: "no-store",
          signal: controller.signal,
        });
        if (!response.ok) {
          throw new Error(`Request failed (${response.status})`);
        }
        const payload = await response.json();
        if (!controller.signal.aborted) {
          setIncidents(payload?.data?.incidents ?? []);
          setState("ready");
        }
      } catch (error) {
        if (controller.signal.aborted) return;
        console.error("Failed to load incidents", error);
        setState("error");
      }
    };
    load();
    return () => controller.abort();
  }, [query]);

  return (
    <div className="space-y-6">
      <div className="border-b border-border/40 pb-5">
        <p className="text-xs font-semibold uppercase tracking-[0.35em] text-muted-foreground">Incidents</p>
        <h1 className="text-3xl font-semibold text-foreground">All tracked incidents</h1>
        <p className="text-sm text-muted-foreground">
          Every promotion from Cerebros reasoning, summarized like Docs Impact Alerts. Filter to zero in on the work
          that matters, then open a card to dive into the full write-up.
        </p>
      </div>

      <Card className="border border-border/60 bg-background/50">
        <CardContent className="space-y-4 py-4">
          <div className="flex flex-wrap gap-3 text-xs">
            <FilterBlock label="Impact level">
              <Select value={severityFilter} onValueChange={setSeverityFilter}>
                <SelectTrigger className="w-36">
                  <SelectValue placeholder="All" />
                </SelectTrigger>
                <SelectContent>
                  {severityFilters.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FilterBlock>
            <FilterBlock label="Component ID">
              <Input
                value={componentFilter}
                onChange={(event) => setComponentFilter(event.target.value)}
                placeholder="comp:core-api"
                className="w-48"
              />
            </FilterBlock>
            <FilterBlock label="Service ID">
              <Input
                value={serviceFilter}
                onChange={(event) => setServiceFilter(event.target.value)}
                placeholder="svc:payments"
                className="w-48"
              />
            </FilterBlock>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
            <Badge variant="outline" className="rounded-full border-border/40">
              Showing {state === "ready" ? incidents.length : "…"} incidents
            </Badge>
            {severityFilter !== "all" ? (
              <span className="text-muted-foreground/80">Impact level · {severityFilter}</span>
            ) : null}
            {componentFilter.trim() ? <span>Component · {componentFilter.trim()}</span> : null}
            {serviceFilter.trim() ? <span>Service · {serviceFilter.trim()}</span> : null}
          </div>
        </CardContent>
      </Card>

      {state === "loading" ? (
        <LoadingState />
      ) : state === "error" ? (
        <p className="rounded-2xl border border-destructive/40 p-4 text-sm text-destructive">
          Unable to load incidents right now.
        </p>
      ) : incidents.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-border/40 p-4 text-sm text-muted-foreground">
          No incidents match those filters.
        </p>
      ) : (
        <div className="space-y-4">
          {incidents.map((incident) => (
            <IncidentCard key={incident.id} incident={incident} />
          ))}
        </div>
      )}
    </div>
  );
}

function FilterBlock({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">{label}</p>
      {children}
    </div>
  );
}

const LoadingState = () => (
  <div className="space-y-3">
    {Array.from({ length: 3 }).map((_, index) => (
      <div key={`incident-loading-${index}`} className="space-y-3 rounded-2xl border border-border/40 bg-muted/5 p-4">
        <div className="flex items-center justify-between">
          <div className="h-3 w-48 animate-pulse rounded-full bg-muted/30" />
          <div className="h-4 w-24 animate-pulse rounded-full bg-muted/30" />
        </div>
        <div className="h-3 w-full animate-pulse rounded-full bg-muted/20" />
        <div className="h-3 w-2/3 animate-pulse rounded-full bg-muted/20" />
        <div className="flex gap-2">
          <div className="h-6 w-24 animate-pulse rounded-full bg-muted/20" />
          <div className="h-6 w-20 animate-pulse rounded-full bg-muted/20" />
        </div>
      </div>
    ))}
  </div>
);

