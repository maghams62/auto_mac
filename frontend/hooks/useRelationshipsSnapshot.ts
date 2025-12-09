"use client";

import { useEffect, useState } from "react";

import type { GraphExplorerResponse } from "@brain-graph-ui/types";

type SnapshotState =
  | { loading: true; data: null; error: null }
  | { loading: false; data: GraphExplorerResponse; error: null }
  | { loading: false; data: null; error: string };

export function useRelationshipsSnapshot(endpoint: string, options?: RequestInit) {
  const [{ loading, data, error }, setState] = useState<SnapshotState>({ loading: true, data: null, error: null });

  useEffect(() => {
    if (!endpoint) {
      setState({ loading: false, data: null, error: "Missing endpoint" });
      return;
    }

    const controller = new AbortController();
    setState({ loading: true, data: null, error: null });

    fetch(endpoint, {
      ...options,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...(options?.headers ?? {}),
      },
    })
      .then(async (response) => {
        if (!response.ok) {
          const message = await response.text();
          throw new Error(message || `Request failed with status ${response.status}`);
        }
        return response.json() as Promise<GraphExplorerResponse>;
      })
      .then((payload) => {
        setState({ loading: false, data: payload, error: null });
      })
      .catch((fetchError) => {
        if (controller.signal.aborted) {
          return;
        }
        setState({ loading: false, data: null, error: fetchError instanceof Error ? fetchError.message : String(fetchError) });
      });

    return () => {
      controller.abort();
    };
  }, [endpoint, options]);

  return { loading, data, error };
}

