import React from "react";
import { describe, it, expect, beforeEach, afterEach, beforeAll, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import BrainTraceView from "@/components/BrainTraceView";

vi.mock("react-force-graph-2d", () => {
  const Mock = () => <div data-testid="force-graph-2d" />;
  return { __esModule: true, default: Mock };
});

const createLocalStorageMock = () => {
  const store = new Map<string, string>();
  return {
    getItem: vi.fn((key: string) => (store.has(key) ? store.get(key)! : null)),
    setItem: vi.fn((key: string, value: string) => {
      store.set(key, value ?? "");
    }),
    removeItem: vi.fn((key: string) => {
      store.delete(key);
    }),
    clear: vi.fn(() => store.clear()),
  };
};

beforeAll(() => {
  Object.defineProperty(window, "localStorage", {
    value: createLocalStorageMock(),
    writable: true,
  });
});

const traceResponse = {
  query_id: "q-123",
  question: "What caused the billing regression?",
  created_at: "2025-01-01T00:00:00Z",
  modalities_used: ["slack", "git"],
  retrieved_chunks: [
    {
      chunk_id: "chunk:1",
      source_type: "slack",
      title: "Slack evidence",
      text: "Discussion about billing drift",
      url: "https://slack.com",
    },
  ],
  chosen_chunks: [],
  graph: {
    nodes: [
      { id: "query:q-123", type: "query" },
      { id: "chunk:1", type: "chunk", text_preview: "discussion" },
      { id: "source:slack:C1", type: "source", display_name: "#support" },
    ],
    edges: [
      { id: "edge:q->chunk", from: "query:q-123", to: "chunk:1", type: "RETRIEVED" },
      { id: "edge:chunk->source", from: "chunk:1", to: "source:slack:C1", type: "BELONGS_TO" },
    ],
  },
};

describe("BrainTraceView", () => {
  beforeEach(() => {
    global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve(traceResponse) })) as unknown as typeof fetch;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders question and graph when data loads", async () => {
    render(<BrainTraceView queryId="q-123" />);
    await waitFor(() => expect(screen.getByTestId("force-graph-2d")).toBeInTheDocument());
    expect(screen.getByText(traceResponse.question)).toBeInTheDocument();
    expect(screen.getAllByText(/Slack/)[0]).toBeInTheDocument();
    expect(screen.getAllByText(/Slack evidence/).length).toBeGreaterThan(0);
  });

  it("shows an error when the trace is missing", async () => {
    global.fetch = vi.fn(() => Promise.resolve({ ok: false, status: 404 })) as unknown as typeof fetch;
    render(<BrainTraceView queryId="missing" />);
    await waitFor(() => {
      expect(screen.getAllByText(/No trace found/i).length).toBeGreaterThan(0);
    });
  });
});

