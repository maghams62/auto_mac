import { describe, it, expect } from "vitest";
import {
  SLASH_COMMANDS,
  filterSlashCommands,
  getSlashQueryMetadata,
  normalizeSlashCommandInput,
  canonicalizeSlashCommandId,
} from "@/lib/slashCommands";

describe("slash command registry", () => {
  const commandNames = SLASH_COMMANDS.map((entry) => entry.command);

  it("includes the critical Cerebros commands", () => {
    expect(commandNames).toContain("/setup");
    expect(commandNames).toContain("/index");
    expect(commandNames).toContain("/cerebros");
    expect(commandNames).toContain("/youtube");
  });
});

describe("slash command helpers", () => {
  it("extracts slash command tokens even with punctuation and quotes", () => {
    const meta = getSlashQueryMetadata(`/slack “Explain core-api status” last 6h`);
    expect(meta.commandToken).toBe("slack");
    expect(meta.tokens).toContain("explain");
    expect(meta.tokens).toContain("core-api");
  });

  it("keeps canonical commands visible when query includes phrases", () => {
    const matches = filterSlashCommands("slack incidents last 6h", "all");
    const hasSlack = matches.some((cmd) => cmd.command === "/slack");
    expect(hasSlack).toBe(true);
  });

  it("normalizes /oq submissions before sending to the backend", () => {
    expect(normalizeSlashCommandInput("/oq what shipped?")).toBe("/cerebros what shipped?");
    expect(normalizeSlashCommandInput("/cerebros audit alerts")).toBe("/cerebros audit alerts");
  });

  it("canonicalizes slash command identifiers for telemetry + palette", () => {
    expect(canonicalizeSlashCommandId("oq")).toBe("cerebros");
    expect(canonicalizeSlashCommandId("cerebros")).toBe("cerebros");
  });
});

