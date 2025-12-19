import { describe, expect, it } from "vitest";

import { isValidUrl } from "@/lib/utils/url-validation";

describe("isValidUrl", () => {
  it("accepts https URLs", () => {
    expect(isValidUrl("https://example.com/docs")).toBe(true);
  });

  it("accepts http URLs", () => {
    expect(isValidUrl("http://localhost:3100/projects")).toBe(true);
  });

  it("accepts relative paths", () => {
    expect(isValidUrl("/projects/project_atlas")).toBe(true);
  });

  it("trims whitespace before validation", () => {
    expect(isValidUrl("   https://example.com/slack ")).toBe(true);
  });

  it("rejects empty or whitespace-only strings", () => {
    expect(isValidUrl("")).toBe(false);
    expect(isValidUrl("   ")).toBe(false);
  });

  it("rejects nullish values", () => {
    expect(isValidUrl(null)).toBe(false);
    expect(isValidUrl(undefined)).toBe(false);
  });

  it("rejects unsupported protocols", () => {
    expect(isValidUrl("ftp://example.com/file.txt")).toBe(false);
    expect(isValidUrl("javascript:alert('xss')")).toBe(false);
  });
});


