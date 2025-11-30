import { afterEach, describe, expect, it, vi } from "vitest";

const MOCK_EPOCH_KEY = "NEXT_PUBLIC_MOCK_SNAPSHOT_EPOCH";
const originalMockEpoch = process.env[MOCK_EPOCH_KEY];

async function loadProjects() {
  const mod = await import("@/lib/mock-data");
  return mod.projects;
}

describe("mock data clock", () => {
  afterEach(() => {
    vi.resetModules();
    if (typeof originalMockEpoch === "undefined") {
      delete process.env[MOCK_EPOCH_KEY];
    } else {
      process.env[MOCK_EPOCH_KEY] = originalMockEpoch;
    }
  });

  it("produces stable project snapshots across module reloads", async () => {
    delete process.env[MOCK_EPOCH_KEY];
    const first = await loadProjects();
    await new Promise((resolve) => setTimeout(resolve, 5));
    vi.resetModules();
    const second = await loadProjects();
    expect(second).toEqual(first);
  });

  it("respects env override when provided", async () => {
    process.env[MOCK_EPOCH_KEY] = "2030-01-01T00:00:00.000Z";
    vi.resetModules();
    const { mockSnapshotTimestamp } = await import("@/lib/mock-data");
    expect(mockSnapshotTimestamp).toBe("2030-01-01T00:00:00.000Z");
  });
});


