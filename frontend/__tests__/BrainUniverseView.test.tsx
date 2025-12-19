import React from "react";
import { describe, it, expect, beforeEach, afterEach, beforeAll, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import BrainUniverseView from "@/components/BrainUniverseView";

vi.mock("react-force-graph-2d", () => {
  const React = require("react");
  const Mock = React.forwardRef((props: any, ref: any) => {
    React.useImperativeHandle(ref, () => ({
    }));
    return <div data-testid="force-graph-2d" />;
  });
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
  if (!("ResizeObserver" in window)) {
    class ResizeObserverMock {
      callback: ResizeObserverCallback;
      constructor(callback: ResizeObserverCallback) {
        this.callback = callback;
      }
      observe() {
        this.callback([], this);
      }
      unobserve() {}
      disconnect() {}
    }
    Object.defineProperty(window, "ResizeObserver", {
      value: ResizeObserverMock,
      writable: true,
    });
  }
});

const mockResponse = {
  nodes: [{ id: "component:1", label: "Component", title: "Billing", props: {} }],
  edges: [],
  generatedAt: "2025-01-01T00:00:00Z",
  filters: {},
  meta: {
    nodeLabelCounts: { Component: 1 },
    relTypeCounts: {},
    propertyKeys: [],
    modalityCounts: { component: 1 },
  },
};

describe("BrainUniverseView", () => {
  beforeEach(() => {
    global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve(mockResponse) })) as unknown as typeof fetch;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the graph once data loads", async () => {
    render(<BrainUniverseView />);

    await waitFor(() => expect(screen.getByTestId("force-graph-2d")).toBeInTheDocument());
    expect(screen.getByText(/Brain Universe/i)).toBeInTheDocument();
    expect(screen.getByText(/Snapshot generated/i)).toBeInTheDocument();
  });

  it("refetches when a modality is toggled", async () => {
    render(<BrainUniverseView />);
    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));

    const modalityButton = screen.getAllByRole("button", { name: /component/i })[0];
    fireEvent.click(modalityButton);

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(2));
  });
});

