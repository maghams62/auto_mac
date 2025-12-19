import React from "react";
import { describe, expect, it, beforeAll, afterAll, beforeEach, vi } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import { mapServerPayloadToMessage, useWebSocket } from "../lib/useWebSocket";

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  public onopen: ((event: any) => void) | null = null;
  public onmessage: ((event: any) => void) | null = null;
  public onerror: ((event: any) => void) | null = null;
  public onclose: ((event: any) => void) | null = null;
  public readyState = MockWebSocket.OPEN;
  public sent: any[] = [];

  constructor(public url: string) {
    MockWebSocket.instances.push(this);
    setTimeout(() => this.onopen?.({}), 0);
  }

  send(payload: any) {
    this.sent.push(payload);
  }

  close() {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.({ code: 1000, reason: "closed" });
  }

  simulateMessage(payload: Record<string, any>) {
    this.onmessage?.({ data: JSON.stringify(payload) });
  }
}

type HarnessProps = {
  socketUrl?: string;
};

function WebSocketHarness({ socketUrl = "ws://test" }: HarnessProps) {
  const { planState, messages } = useWebSocket(socketUrl);
  const lastMessage = messages[messages.length - 1];
  return (
    <>
      <span data-testid="plan-status">{planState?.status ?? "none"}</span>
      <span data-testid="active-step">{planState?.activeStepId ?? "none"}</span>
      <span data-testid="last-message">{lastMessage?.message ?? ""}</span>
    </>
  );
}

describe("mapServerPayloadToMessage", () => {
  it("preserves slash_slack payloads even when server message text is empty", () => {
    const payload = {
      type: "assistant",
      timestamp: "2024-01-01T00:00:00.000Z",
      result: {
        type: "slash_slack_summary",
        message: "Summary of #core-api",
        sections: { topics: [{ topic: "core-api", mentions: 3 }] },
        context: { channel_label: "#core-api" },
      },
    };

    const mapped = mapServerPayloadToMessage(payload);
    expect(mapped).not.toBeNull();
    expect(mapped?.slash_slack?.sections?.topics?.[0]?.topic).toBe("core-api");
    expect(mapped?.message).toContain("Summary of #core-api");
  });

  it("returns null for empty payloads without attachments", () => {
    const mapped = mapServerPayloadToMessage({
      type: "assistant",
      timestamp: "2024-01-01T00:00:00.000Z",
      message: "",
    });
    expect(mapped).toBeNull();
  });

  it("maps slash git summary payloads and exposes sources", () => {
    const payload = {
      type: "assistant",
      timestamp: "2025-01-02T00:00:00.000Z",
      result: {
        type: "slash_git_summary",
        message: "Core API saw 2 commits recently.",
        sources: [
          {
            id: "c1",
            type: "commit",
            short_sha: "abc1234",
            author: "alice",
            timestamp: "2025-01-01T01:00:00Z",
            message: "feat: add billing hooks",
            url: "https://github.com/acme/core-api/commit/abc1234",
          },
        ],
        context: { repo_label: "core-api", scope_label: "Core API" },
        data: {
          snapshot: {
            commits: [{ sha: "abc1234" }],
            prs: [],
          },
        },
      },
    };

    const mapped = mapServerPayloadToMessage(payload);
    expect(mapped).not.toBeNull();
    expect(mapped?.slash_git?.sources?.[0]?.short_sha).toBe("abc1234");
    expect(mapped?.message).toContain("Core API saw 2 commits");
  });

  it("maps slash cerebros summary payloads with sources", () => {
    const payload = {
      type: "assistant",
      timestamp: "2025-01-03T00:00:00.000Z",
      result: {
        type: "slash_cerebros_summary",
        message: "Cross-source insights for billing checkout.",
        context: { modalities_used: ["slack", "git"], total_results: 4 },
        sources: [
          {
            type: "slack",
            label: "#incidents thread",
            url: "https://workspace.slack.com/archives/C123/p1111",
            channel: "#incidents",
            snippet: "Urgent checkout issues raised by ops.",
          },
        ],
        cerebros_answer: { answer: "Checkout issues driven by recent Git changes.", option: "activity_graph" },
        data: {
          query_plan: { intent: "summarize" },
        },
      },
    };

    const mapped = mapServerPayloadToMessage(payload);
    expect(mapped).not.toBeNull();
    expect(mapped?.slash_cerebros?.sources?.[0]?.label).toBe("#incidents thread");
    expect(mapped?.slash_cerebros?.cerebros_answer?.option).toBe("activity_graph");
  });
});

describe("useWebSocket plan + slash flows", () => {
  beforeAll(() => {
    vi.stubGlobal("WebSocket", MockWebSocket as any);
  });

  afterAll(() => {
    vi.unstubAllGlobals();
  });

  beforeEach(() => {
    MockWebSocket.instances.length = 0;
  });

  it("does not open a socket when url is empty", async () => {
    render(<WebSocketHarness socketUrl="" />);
    await waitFor(() => expect(MockWebSocket.instances.length).toBe(0));
  });

  it("reconnects when the url changes", async () => {
    function UrlHarness({ url }: { url: string }) {
      useWebSocket(url);
      return null;
    }

    const { rerender } = render(<UrlHarness url="ws://first" />);
    await waitFor(() => expect(MockWebSocket.instances.length).toBe(1));
    const firstSocket = MockWebSocket.instances[0];

    rerender(<UrlHarness url="ws://second" />);
    await waitFor(() => expect(MockWebSocket.instances.length).toBe(2));
    await waitFor(() => expect(firstSocket.readyState).toBe(MockWebSocket.CLOSED));
  });

  it("advances plan steps until completion", async () => {
    render(<WebSocketHarness />);
    const ws = MockWebSocket.instances[0];
    await act(async () => {
      ws.simulateMessage({
      type: "plan",
      goal: "/git what changed recently in billing-service?",
      timestamp: "2025-01-01T00:00:00.000Z",
      steps: [
        { id: 1, action: "interpret slash command" },
        { id: 2, action: "execute slash assistant" },
      ],
    });
    });

    await waitFor(() => expect(screen.getByTestId("plan-status").textContent).toBe("executing"));

    await act(async () => {
      ws.simulateMessage({
      type: "plan_update",
      step_id: 1,
      status: "running",
      sequence_number: 1,
      timestamp: "2025-01-01T00:00:01.000Z",
    });
    });
    await waitFor(() => expect(screen.getByTestId("active-step").textContent).toBe("1"));

    await act(async () => {
      ws.simulateMessage({
      type: "plan_update",
      step_id: 1,
      status: "completed",
      sequence_number: 2,
      timestamp: "2025-01-01T00:00:02.000Z",
    });
    });

    await act(async () => {
      ws.simulateMessage({
      type: "plan_finalize",
      status: "completed",
      timestamp: "2025-01-01T00:00:03.000Z",
    });
    });

    await waitFor(() => {
      expect(screen.getByTestId("plan-status").textContent).toBe("completed");
      expect(screen.getByTestId("active-step").textContent).toBe("none");
    });
  });

  it("renders slash results after plan completion", async () => {
    render(<WebSocketHarness />);
    const ws = MockWebSocket.instances[0];
    await act(async () => {
      ws.simulateMessage({
      type: "plan",
      goal: "/slack summarize incidents",
      steps: [{ id: 1, action: "interpret" }],
      timestamp: "2025-01-01T00:00:00.000Z",
    });
    });
    await waitFor(() => expect(screen.getByTestId("plan-status").textContent).toBe("executing"));

    await act(async () => {
      ws.simulateMessage({
      type: "plan_finalize",
      status: "completed",
      timestamp: "2025-01-01T00:00:01.000Z",
    });
    });

    await act(async () => {
      ws.simulateMessage({
      type: "assistant",
      timestamp: "2025-01-01T00:00:02.000Z",
      result: {
        type: "slash_slack_summary",
        message: "4 messages in #incidents mentioning Atlas billing.",
        sections: { topics: [{ topic: "Atlas billing spike", mentions: 3 }] },
        context: { channel_label: "#incidents" },
      },
    });
    });

    await waitFor(() => {
      expect(screen.getByTestId("plan-status").textContent).toBe("completed");
      expect(screen.getByTestId("last-message").textContent).toContain("#incidents");
    });
  });

  it("renders slash thread recap payloads", async () => {
    render(<WebSocketHarness />);
    const ws = MockWebSocket.instances[0];
    await act(async () => {
      ws.simulateMessage({
        type: "plan",
        goal: "/slack summarize the thread <link>",
        steps: [{ id: 1, action: "interpret" }],
        timestamp: "2025-01-02T00:00:00.000Z",
      });
    });
    await act(async () => {
      ws.simulateMessage({
        type: "plan_finalize",
        status: "completed",
        timestamp: "2025-01-02T00:00:01.000Z",
      });
    });
    await act(async () => {
      ws.simulateMessage({
        type: "assistant",
        timestamp: "2025-01-02T00:00:02.000Z",
        result: {
          type: "slash_slack_summary",
          message: "Thread recap highlights vat_code fallout in #incidents.",
          sections: { topics: [{ topic: "vat_code fallout", mentions: 4 }] },
          context: { channel_label: "#incidents", thread_ts: "1764147600.00000" },
        },
      });
    });
    await waitFor(() => {
      expect(screen.getByTestId("plan-status").textContent).toBe("completed");
      expect(screen.getByTestId("last-message").textContent).toContain("Thread recap");
    });
  });

  it("renders slash decision payloads with task summaries", async () => {
    render(<WebSocketHarness />);
    const ws = MockWebSocket.instances[0];
    await act(async () => {
      ws.simulateMessage({
        type: "plan",
        goal: "/slack list action items",
        steps: [{ id: 1, action: "interpret" }],
        timestamp: "2025-01-03T00:00:00.000Z",
      });
    });
    await act(async () => {
      ws.simulateMessage({
        type: "plan_finalize",
        status: "completed",
        timestamp: "2025-01-03T00:00:01.000Z",
      });
    });
    await act(async () => {
      ws.simulateMessage({
        type: "assistant",
        timestamp: "2025-01-03T00:00:02.000Z",
        result: {
          type: "slash_slack_summary",
          message: "Found 2 follow-up items for Atlas billing.",
          sections: { tasks: [{ description: "Update docs" }, { description: "Notify support" }] },
          context: { mode: "task", channel_label: "Slack" },
        },
      });
    });
    await waitFor(() => {
      expect(screen.getByTestId("plan-status").textContent).toBe("completed");
      expect(screen.getByTestId("last-message").textContent).toContain("follow-up");
    });
  });

  it("renders slack quota drift payloads with quota numbers", async () => {
    render(<WebSocketHarness />);
    const ws = MockWebSocket.instances[0];
    await act(async () => {
      ws.simulateMessage({
        type: "plan",
        goal: "/slack summarize free tier quota complaints in #support",
        steps: [{ id: 1, action: "interpret" }],
        timestamp: "2025-01-03T12:00:00.000Z",
      });
    });
    await act(async () => {
      ws.simulateMessage({
        type: "plan_finalize",
        status: "completed",
        timestamp: "2025-01-03T12:00:01.000Z",
      });
    });
    await act(async () => {
      ws.simulateMessage({
        type: "assistant",
        timestamp: "2025-01-03T12:00:02.000Z",
        result: {
          type: "slash_slack_summary",
          message: "#support highlighted that customers hit throttling at 300 calls while docs still cite 1,000.",
          sections: {
            topics: [{ topic: "Quota drift", mentions: 5 }],
          },
          context: { channel_label: "#support" },
        },
      });
    });
    await waitFor(() => {
      const text = screen.getByTestId("last-message").textContent ?? "";
      expect(text).toContain("#support");
      expect(text.replace(/,/g, "")).toMatch(/300/);
      expect(text.replace(/,/g, "")).toMatch(/1000/);
    });
  });

  it("renders git doc drift payloads", async () => {
    render(<WebSocketHarness />);
    const ws = MockWebSocket.instances[0];
    await act(async () => {
      ws.simulateMessage({
        type: "plan",
        goal: "/git doc drift around billing docs",
        steps: [{ id: 1, action: "interpret" }],
        timestamp: "2025-01-04T00:00:00.000Z",
      });
    });
    await act(async () => {
      ws.simulateMessage({
        type: "plan_finalize",
        status: "completed",
        timestamp: "2025-01-04T00:00:01.000Z",
      });
    });
    await act(async () => {
      ws.simulateMessage({
        type: "assistant",
        timestamp: "2025-01-04T00:00:02.000Z",
        result: {
          type: "git_response",
          message: "Doc drift detected between core-api and docs portal.",
          data: {
            doc_drift: [
              {
                summary: "billing docs still say vat optional",
                component: "web-dashboard",
              },
            ],
          },
        },
      });
    });
    await waitFor(() => {
      expect(screen.getByTestId("plan-status").textContent).toBe("completed");
      expect(screen.getByTestId("last-message").textContent).toContain("Doc drift");
    });
  });

  it("renders git PR summaries", async () => {
    render(<WebSocketHarness />);
    const ws = MockWebSocket.instances[0];
    await act(async () => {
      ws.simulateMessage({
        type: "plan",
        goal: "/git list closed PRs targeting main",
        steps: [
          { id: 1, action: "interpret" },
          { id: 2, action: "execute slash assistant" },
        ],
        timestamp: "2025-01-05T00:00:00.000Z",
      });
    });
    await act(async () => {
      ws.simulateMessage({
        type: "plan_update",
        step_id: 2,
        status: "running",
        sequence_number: 1,
        timestamp: "2025-01-05T00:00:01.000Z",
      });
    });
    await act(async () => {
      ws.simulateMessage({
        type: "plan_finalize",
        status: "completed",
        timestamp: "2025-01-05T00:00:02.000Z",
      });
    });
    await act(async () => {
      ws.simulateMessage({
        type: "assistant",
        timestamp: "2025-01-05T00:00:03.000Z",
        result: {
          type: "git_response",
          message: "1 closed PR targeting main.",
          data: {
            prs: [
              { number: 118, author: "bob", title: "Fix vat_code errors", head_branch: "feature/vat-code" },
            ],
          },
        },
      });
    });
    await waitFor(() => {
      expect(screen.getByTestId("plan-status").textContent).toBe("completed");
      expect(screen.getByTestId("last-message").textContent).toContain("closed PR");
    });
  });

  it("updates processing status message when plan finalize arrives", async () => {
    render(<WebSocketHarness />);
    const ws = MockWebSocket.instances[0];

    await act(async () => {
      ws.simulateMessage({
        type: "status",
        status: "processing",
        message: "Working...",
        timestamp: "2025-01-06T00:00:00.000Z",
      });
    });
    await waitFor(() => expect(screen.getByTestId("last-message").textContent).toContain("Working"));

    await act(async () => {
      ws.simulateMessage({
        type: "plan_finalize",
        status: "completed",
        timestamp: "2025-01-06T00:00:01.000Z",
      });
    });

    await waitFor(() => expect(screen.getByTestId("last-message").textContent).toContain("Task completed"));
  });
});

