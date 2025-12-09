"use client";

import React from "react";

import type { GraphExplorerNode } from "./types";
import { formatTimestamp } from "./utils";

type NodeDetailsPanelProps = {
  node: GraphExplorerNode | null;
};

const LINK_KEYS = [
  { key: "url", label: "Open link" },
  { key: "html_url", label: "Open in GitHub" },
  { key: "github_url", label: "Open in GitHub" },
  { key: "doc_url", label: "Open document" },
  { key: "slack_url", label: "Open in Slack" },
  { key: "ticket_url", label: "Open ticket" },
];

export function NodeDetailsPanel({ node }: NodeDetailsPanelProps) {
  if (!node) {
    return (
      <aside
        className="w-full rounded-2xl border border-slate-800 bg-slate-900/70 p-4 text-sm text-slate-400"
        data-testid="node-details-panel"
      >
        Select a node to inspect metadata and deep links.
      </aside>
    );
  }

  const linkEntries = LINK_KEYS.map(({ key, label }) => {
    const value = node.props?.[key];
    if (typeof value === "string" && value.startsWith("http")) {
      return { key, label, href: value };
    }
    return null;
  }).filter(Boolean) as { key: string; label: string; href: string }[];

  const propsEntries = Object.entries(node.props || {}).filter(
    ([key, value]) => !LINK_KEYS.find((entry) => entry.key === key) && value !== undefined && value !== null,
  );

  return (
    <aside
      className="flex w-full max-w-xs flex-col gap-3 rounded-2xl border border-slate-800 bg-slate-900/70 p-4 text-slate-100"
      data-testid="node-details-panel"
    >
      <div>
        <p className="text-xs uppercase tracking-wide text-slate-500">{node.label}</p>
        <h3 className="text-lg font-semibold text-white">{node.title ?? node.id}</h3>
        {node.modality && <p className="text-xs text-slate-400">{node.modality}</p>}
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs text-slate-300">
        <div>
          <p className="text-[10px] uppercase text-slate-500">Created</p>
          <p>{formatTimestamp(node.createdAt)}</p>
        </div>
        <div>
          <p className="text-[10px] uppercase text-slate-500">Updated</p>
          <p>{formatTimestamp(node.updatedAt)}</p>
        </div>
      </div>

      {linkEntries.length ? (
        <div className="flex flex-col gap-2">
          {linkEntries.map((entry) => (
            <a
              key={entry.key}
              href={entry.href}
              target="_blank"
              rel="noreferrer"
              className="rounded-md border border-slate-700 px-2 py-1 text-center text-xs font-medium text-slate-200 hover:border-slate-500 hover:text-white"
            >
              {entry.label}
            </a>
          ))}
        </div>
      ) : null}

      <div className="max-h-64 overflow-y-auto rounded-lg border border-slate-800 bg-slate-950/60 p-2 text-xs">
        <p className="mb-1 font-semibold text-slate-400">Properties</p>
        {propsEntries.length ? (
          <dl className="space-y-1">
            {propsEntries.map(([key, value]) => (
              <div key={key} className="flex flex-col rounded-md bg-slate-900/60 px-2 py-1">
                <dt className="text-[10px] uppercase text-slate-500">{key}</dt>
                <dd className="font-mono text-slate-200">{String(value)}</dd>
              </div>
            ))}
          </dl>
        ) : (
          <p className="text-slate-500">No additional metadata.</p>
        )}
      </div>
    </aside>
  );
}


