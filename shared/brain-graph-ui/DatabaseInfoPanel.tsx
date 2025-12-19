"use client";

import React from "react";

import type { GraphExplorerMeta } from "./types";
import { formatTimestamp, getColorForNode } from "./utils";

type DatabaseInfoPanelProps = {
  meta?: GraphExplorerMeta;
  activeLabel: string | null;
  onSelectLabel: (label: string | null) => void;
};

export function DatabaseInfoPanel({ meta, activeLabel, onSelectLabel }: DatabaseInfoPanelProps) {
  const labelEntries = Object.entries(meta?.nodeLabelCounts ?? {}).sort((a, b) => b[1] - a[1]);
  const relationshipEntries = Object.entries(meta?.relTypeCounts ?? {}).sort((a, b) => b[1] - a[1]);
  const propertyKeys = (meta?.propertyKeys ?? []).slice(0, 40);

  return (
    <aside className="flex w-full max-w-xs flex-col gap-4 rounded-2xl border border-slate-800 bg-slate-900/80 p-4 text-slate-200 shadow-inner shadow-slate-900/40">
      <div>
        <p className="text-xs uppercase text-slate-500">Snapshot range</p>
        <p className="text-sm font-medium">
          {formatTimestamp(meta?.minTimestamp ?? undefined)} → {formatTimestamp(meta?.maxTimestamp ?? undefined)}
        </p>
      </div>

      <section>
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Node labels</h3>
          <span className="text-xs text-slate-500">{labelEntries.length}</span>
        </div>
        <div className="mt-2 flex flex-wrap gap-2">
          {labelEntries.map(([label, count]) => {
            const isActive = activeLabel === label;
            return (
              <button
                type="button"
                key={label}
                onClick={() => onSelectLabel(isActive ? null : label)}
                className={`flex items-center gap-2 rounded-full border px-3 py-1 text-sm transition ${
                  isActive
                    ? "border-slate-200 bg-slate-200 text-slate-900"
                    : "border-slate-700 bg-slate-800/70 text-slate-100 hover:border-slate-500"
                }`}
              >
                <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: getColorForNode(label, label.toLowerCase()) }} />
                <span className="font-semibold">{label}</span>
                <span className="text-xs text-slate-400">{count}</span>
              </button>
            );
          })}
          {labelEntries.length === 0 && <p className="text-xs text-slate-500">No labels available.</p>}
        </div>
      </section>

      <section>
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Relationships</h3>
          <span className="text-xs text-slate-500">{relationshipEntries.length}</span>
        </div>
        <div className="mt-2 flex flex-wrap gap-2">
          {relationshipEntries.map(([rel, count]) => (
            <span
              key={rel}
              className="rounded-full border border-slate-700 bg-slate-800/70 px-3 py-1 text-[11px] font-medium text-slate-100"
            >
              {rel} ({count})
            </span>
          ))}
          {relationshipEntries.length === 0 && <p className="text-xs text-slate-500">No relationships captured.</p>}
        </div>
      </section>

      <section>
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Property keys</h3>
          <span className="text-xs text-slate-500">{propertyKeys.length}</span>
        </div>
        <div className="mt-2 flex flex-wrap gap-2">
          {propertyKeys.length ? (
            propertyKeys.map((key) => (
              <span key={key} className="rounded-full border border-slate-700 px-2 py-0.5 text-xs text-slate-400">
                {key}
              </span>
            ))
          ) : (
            <p className="text-xs text-slate-500">No properties reported.</p>
          )}
        </div>
      </section>
    </aside>
  );
}


