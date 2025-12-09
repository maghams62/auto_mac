"use client";

import React, { useMemo } from "react";

import { GraphExplorer } from "@brain-graph-ui/GraphExplorer";

import { getApiBaseDiagnostics } from "@/lib/apiConfig";

export default function BrainUniverseNeo4jPage() {
  const apiDiagnostics = useMemo(() => getApiBaseDiagnostics(), []);

  return (
    <div className="min-h-screen w-full bg-slate-950">
      <div className="mx-auto flex max-w-7xl flex-col gap-4 px-6 py-6">
        <GraphExplorer
          mode="neo4j_default"
          className="rounded-2xl border border-slate-800 bg-slate-900/80 p-4 shadow-xl shadow-slate-900/40"
          initialFilters={{ limit: 25 }}
          title="Neo4j Universe"
          apiBaseUrl={apiDiagnostics.baseUrl}
          apiDiagnostics={apiDiagnostics}
          lockViewport
          layoutStyle="neo4j"
          enableTimeControls={false}
          variant="neo4j"
        />
      </div>
    </div>
  );
}


