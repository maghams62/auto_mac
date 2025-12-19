import { describe, expect, it, beforeEach, afterEach, vi } from "vitest";

const ORIGINAL_ENV = process.env.NEXT_PUBLIC_BRAIN_UNIVERSE_URL;

describe("workspaceNavItems", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  afterEach(() => {
    if (ORIGINAL_ENV === undefined) {
      delete process.env.NEXT_PUBLIC_BRAIN_UNIVERSE_URL;
    } else {
      process.env.NEXT_PUBLIC_BRAIN_UNIVERSE_URL = ORIGINAL_ENV;
    }
  });

  it("includes the Brain nav entry with default href", async () => {
    delete process.env.NEXT_PUBLIC_BRAIN_UNIVERSE_URL;
    const { workspaceNavItems } = await import("@/components/layout/nav-data");
    const brainLink = workspaceNavItems.find((item) => item.label === "Brain");
    expect(brainLink?.href).toBe("/brain/universe");
  });

  it("uses NEXT_PUBLIC_BRAIN_UNIVERSE_URL when provided", async () => {
    process.env.NEXT_PUBLIC_BRAIN_UNIVERSE_URL = "https://example.com/brain";
    const { workspaceNavItems } = await import("@/components/layout/nav-data");
    const brainLink = workspaceNavItems.find((item) => item.label === "Brain");
    expect(brainLink?.href).toBe("https://example.com/brain");
  });
});

