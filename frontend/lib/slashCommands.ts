export interface SlashCommandDefinition {
  command: string;
  label: string;
  description: string;
  category?: string;
  emoji?: string;
  icon?: string;
  kind?: "chat" | "palette-only" | "special-ui";
  priority?: number;
  telemetryKey?: string;
  placeholder?: string;
  keywords?: string[];
  commandType?: "immediate" | "with_input";
}

/**
 * Canonical list of supported slash commands.
 * Only commands listed here should appear in the dropdown and command palette.
 * 
 * Priority order (lower number = higher priority):
 * 1. /email - Most commonly used
 * 2. /explain - Frequently used for document queries
 * 3. /files - Special UI command (opens palette, not chat)
 * 3.5. /folder - Folder management operations
 * 4. /bluesky - Social media integration
 * 4.5. /index - Document indexing
 * 5. /report - Content generation
 * 6. /help - Meta command
 * 7. /agents - Meta command
 * 8. /clear - Meta command
 * 9. /confetti - Fun command
 */
export const SLASH_COMMANDS: SlashCommandDefinition[] = [
  // Communication
  {
    command: "/email",
    label: "Email",
    description: "Compose, read, and send emails through Mail.app",
    category: "Communication",
    emoji: "📧",
    kind: "chat",
    priority: 1,
    telemetryKey: "email",
    placeholder: "e.g. follow up with Sarah about the onboarding deck...",
    keywords: ["email", "mail", "send", "inbox"],
    commandType: "with_input",
  },
  {
    command: "/message",
    label: "iMessage",
    description: "Send iMessages or read recent threads",
    category: "Communication",
    emoji: "💬",
    kind: "chat",
    priority: 1.05,
    telemetryKey: "message",
    placeholder: "e.g. send a note to Alex wishing them happy birthday",
    keywords: ["imessage", "text", "sms", "message"],
    commandType: "with_input",
  },
  {
    command: "/slack",
    label: "Slack",
    description: "Summarize channels, threads, or DM history",
    category: "Communication",
    emoji: "💬",
    kind: "chat",
    priority: 1.1,
    telemetryKey: "slack",
    placeholder: "e.g. summarize #incidents last 24h",
    keywords: ["slack", "channel", "chat", "thread", "search"],
    commandType: "with_input",
  },
  {
    command: "/whatsapp",
    label: "WhatsApp",
    description: "Analyze or respond to WhatsApp conversations",
    category: "Communication",
    emoji: "💬",
    kind: "chat",
    priority: 1.15,
    telemetryKey: "whatsapp",
    placeholder: "e.g. summarize WhatsApp chat with design team",
    keywords: ["whatsapp", "wa", "chat"],
    commandType: "with_input",
  },
  {
    command: "/wa",
    label: "WA",
    description: "Alias for WhatsApp workflows",
    category: "Communication",
    emoji: "💬",
    kind: "chat",
    priority: 1.16,
    telemetryKey: "whatsapp",
    placeholder: "e.g. wa summarize chat with operations",
    keywords: ["wa", "whatsapp", "chat"],
    commandType: "with_input",
  },
  {
    command: "/discord",
    label: "Discord",
    description: "Read or send Discord updates",
    category: "Communication",
    emoji: "💬",
    kind: "chat",
    priority: 1.18,
    telemetryKey: "discord",
    placeholder: "e.g. summarize #product-announcements on Discord",
    keywords: ["discord", "server", "chat", "channel"],
    commandType: "with_input",
  },
  {
    command: "/notify",
    label: "Notify",
    description: "Send macOS notifications or reminders",
    category: "System",
    emoji: "🔔",
    kind: "chat",
    priority: 1.2,
    telemetryKey: "notify",
    placeholder: "e.g. notify me to stretch in 30 minutes",
    keywords: ["notify", "notification", "alert"],
    commandType: "with_input",
  },

  // Files & knowledge
  {
    command: "/files",
    label: "Files",
    description: "Search documents and files (opens search palette)",
    category: "Knowledge",
    emoji: "📁",
    kind: "special-ui",
    priority: 2,
    telemetryKey: "files",
    placeholder: "Type a file query...",
    keywords: ["files", "documents", "search", "lookup"],
    commandType: "with_input",
  },
  {
    command: "/folder",
    label: "Folder",
    description: "List, organize, and manage folders",
    category: "Knowledge",
    emoji: "📂",
    kind: "chat",
    priority: 2.1,
    telemetryKey: "folder",
    placeholder: "e.g. list research docs or normalize folder names",
    keywords: ["folder", "directory", "browse", "organize"],
    commandType: "with_input",
  },
  {
    command: "/browse",
    label: "Browse",
    description: "Open the Browser Agent for live web workflows",
    category: "Web",
    emoji: "🌐",
    kind: "chat",
    priority: 2.2,
    telemetryKey: "browse",
    placeholder: "e.g. browse for the latest AI safety report",
    keywords: ["browse", "web", "search", "internet"],
    commandType: "with_input",
  },
  {
    command: "/explain",
    label: "Explain",
    description: "Run explain workflows for documents or topics",
    category: "Knowledge",
    emoji: "🧠",
    kind: "chat",
    priority: 2.3,
    telemetryKey: "explain",
    placeholder: "e.g. explain the attached spec and highlight risks",
    keywords: ["explain", "how", "docs"],
    commandType: "with_input",
  },
  {
    command: "/index",
    label: "Index",
    description: "Reindex documents from configured folders",
    category: "Knowledge",
    emoji: "📚",
    kind: "chat",
    priority: 2.4,
    telemetryKey: "index",
    placeholder: "Optional: specify folders or leave blank for config defaults",
    keywords: ["index", "reindex", "documents"],
    commandType: "with_input",
  },

  // Productivity & planning
  {
    command: "/present",
    label: "Present",
    description: "Generate Keynote / PPT presentations",
    category: "Productivity",
    emoji: "📊",
    kind: "chat",
    priority: 3,
    telemetryKey: "present",
    placeholder: "e.g. create a 5-slide deck about Q4 roadmap",
    keywords: ["present", "presentation", "slides", "deck", "keynote"],
    commandType: "with_input",
  },
  {
    command: "/write",
    label: "Write",
    description: "Draft documents, briefs, and memos",
    category: "Productivity",
    emoji: "✍️",
    kind: "chat",
    priority: 3.1,
    telemetryKey: "write",
    placeholder: "e.g. write a hiring brief for frontend lead",
    keywords: ["write", "document", "memo", "pages"],
    commandType: "with_input",
  },
  {
    command: "/calendar",
    label: "Calendar",
    description: "Summarize events or prep meeting briefs",
    category: "Productivity",
    emoji: "📅",
    kind: "chat",
    priority: 3.2,
    telemetryKey: "calendar",
    placeholder: "e.g. prep me for tomorrow's design review",
    keywords: ["calendar", "event", "meeting", "schedule"],
    commandType: "with_input",
  },
  {
    command: "/day",
    label: "Day Briefing",
    description: "Generate daily overviews and action plans",
    category: "Productivity",
    emoji: "📅",
    kind: "chat",
    priority: 3.3,
    telemetryKey: "day",
    placeholder: "e.g. summarize my day across Slack, Git, and email",
    keywords: ["day", "daily", "brief", "overview"],
    commandType: "with_input",
  },
  {
    command: "/report",
    label: "Reports",
    description: "Generate PDF/Keynote summaries from files",
    category: "Productivity",
    emoji: "📋",
    kind: "chat",
    priority: 3.4,
    telemetryKey: "report",
    placeholder: "e.g. create a PDF summary of investor updates",
    keywords: ["report", "pdf", "summary"],
    commandType: "with_input",
  },
  {
    command: "/recurring",
    label: "Recurring Tasks",
    description: "Schedule recurring automations",
    category: "Productivity",
    emoji: "🔄",
    kind: "chat",
    priority: 3.5,
    telemetryKey: "recurring",
    placeholder: "e.g. summarize #incidents every weekday at 5pm",
    keywords: ["recurring", "schedule", "repeat", "automation"],
    commandType: "with_input",
  },

  // Development & intelligence
  {
    command: "/git",
    label: "GitHub PRs",
    description: "Summarize or inspect GitHub pull requests",
    category: "Development",
    emoji: "🐙",
    kind: "chat",
    priority: 4,
    telemetryKey: "git",
    placeholder: "e.g. summarize open PRs on main",
    keywords: ["git", "github", "pr", "review"],
    commandType: "with_input",
  },
  {
    command: "/pr",
    label: "PR Lookup",
    description: "Alias for focusing on a specific pull request",
    category: "Development",
    emoji: "🐙",
    kind: "chat",
    priority: 4.1,
    telemetryKey: "pr",
    placeholder: "e.g. PR #4821 or PR https://github.com/org/repo/pull/42",
    keywords: ["pr", "pull request", "github"],
    commandType: "with_input",
  },
  {
    command: "/oq",
    label: "Activity Intelligence",
    description: "Blend Slack + Git signals for status updates",
    category: "Intelligence",
    emoji: "🧭",
    kind: "chat",
    priority: 4.2,
    telemetryKey: "oq",
    placeholder: "e.g. what's happening with onboarding revamp?",
    keywords: ["activity", "status", "oqoqo", "recent work"],
    commandType: "with_input",
  },
  {
    command: "/activity",
    label: "Activity Query",
    description: "Alias for Oqoqo intelligence queries",
    category: "Intelligence",
    emoji: "🧭",
    kind: "chat",
    priority: 4.3,
    telemetryKey: "activity",
    placeholder: "e.g. activity updates for billing service",
    keywords: ["activity", "status", "report"],
    commandType: "with_input",
  },

  // Media & navigation
  {
    command: "/spotify",
    label: "Spotify",
    description: "Control Spotify playback with rich context",
    category: "Media",
    emoji: "🎵",
    kind: "chat",
    priority: 5,
    telemetryKey: "spotify",
    placeholder: "e.g. play Pyro by Rezz, or summarize current song",
    keywords: ["spotify", "music", "play", "song"],
    commandType: "with_input",
  },
  {
    command: "/music",
    label: "Music",
    description: "Alias for advanced Spotify workflows",
    category: "Media",
    emoji: "🎵",
    kind: "chat",
    priority: 5.1,
    telemetryKey: "spotify",
    placeholder: "e.g. music queue chill playlist",
    keywords: ["music", "spotify", "playlist"],
    commandType: "with_input",
  },
  {
    command: "/maps",
    label: "Maps",
    description: "Plan routes, trips, and local errands",
    category: "Navigation",
    emoji: "🗺️",
    kind: "chat",
    priority: 5.2,
    telemetryKey: "maps",
    placeholder: "e.g. plan a route from SF to Palo Alto with stops",
    keywords: ["maps", "directions", "route", "travel"],
    commandType: "with_input",
  },
  {
    command: "/stock",
    label: "Stocks",
    description: "Run finance workflows for tickers or sectors",
    category: "Finance",
    emoji: "📈",
    kind: "chat",
    priority: 5.3,
    telemetryKey: "stock",
    placeholder: "e.g. stock breakdown for NVDA vs AMD last month",
    keywords: ["stock", "finance", "ticker", "market"],
    commandType: "with_input",
  },

  // Social
  {
    command: "/bluesky",
    label: "Bluesky",
    description: "Read, summarize, or draft Bluesky posts",
    category: "Social",
    emoji: "🦋",
    kind: "chat",
    priority: 5.4,
    telemetryKey: "bluesky",
    placeholder: "e.g. summarize latest Bluesky mentions",
    keywords: ["bluesky", "post", "social"],
    commandType: "with_input",
  },
  {
    command: "/twitter",
    label: "Twitter",
    description: "Analyze or draft posts for X/Twitter",
    category: "Social",
    emoji: "🐦",
    kind: "chat",
    priority: 5.45,
    telemetryKey: "twitter",
    placeholder: "e.g. write a playful launch tweet",
    keywords: ["twitter", "tweet", "x", "social"],
    commandType: "with_input",
  },
  {
    command: "/reddit",
    label: "Reddit",
    description: "Browse or summarize Reddit discussions",
    category: "Social",
    emoji: "🤖",
    kind: "chat",
    priority: 5.5,
    telemetryKey: "reddit",
    placeholder: "e.g. summarize top posts in r/startups",
    keywords: ["reddit", "browse", "thread"],
    commandType: "with_input",
  },

  // Meta / utilities
  {
    command: "/help",
    label: "Help",
    description: "List commands and usage examples",
    category: "Meta",
    emoji: "❓",
    kind: "chat",
    priority: 6,
    telemetryKey: "help",
    placeholder: "e.g. help with /slack format",
    keywords: ["help", "docs", "commands"],
    commandType: "with_input",
  },
  {
    command: "/agents",
    label: "Agent Directory",
    description: "List every available agent",
    category: "Meta",
    emoji: "🤖",
    kind: "chat",
    priority: 6.1,
    telemetryKey: "agents",
    keywords: ["agents", "list", "available"],
    commandType: "immediate",
  },
  {
    command: "/clear",
    label: "Clear Session",
    description: "Reset memory and start a fresh chat",
    category: "Meta",
    emoji: "🗑️",
    kind: "chat",
    priority: 6.2,
    telemetryKey: "clear",
    keywords: ["clear", "reset", "restart"],
    commandType: "immediate",
  },
  {
    command: "/confetti",
    label: "Confetti",
    description: "Trigger celebratory confetti effects",
    category: "Fun",
    emoji: "🎉",
    kind: "chat",
    priority: 6.3,
    telemetryKey: "confetti",
    keywords: ["confetti", "celebrate", "party"],
    commandType: "immediate",
  },
];

const SORTED_COMMANDS: SlashCommandDefinition[] = [...SLASH_COMMANDS].sort(
  (a, b) => (a.priority || 999) - (b.priority || 999)
);

const CHAT_COMMANDS: SlashCommandDefinition[] = SORTED_COMMANDS.filter(
  (cmd) => cmd.kind === "chat" || cmd.kind === undefined
);

type SlashCommandScope = "chat" | "all";

const SCOPE_MAP: Record<SlashCommandScope, SlashCommandDefinition[]> = {
  chat: CHAT_COMMANDS,
  all: SORTED_COMMANDS,
};

const cloneCommands = (list: SlashCommandDefinition[]) =>
  list.map((cmd) => ({ ...cmd }));

/**
 * Get commands sorted by priority for display in dropdown/palette
 */
export function getSortedCommands(): SlashCommandDefinition[] {
  return cloneCommands(SORTED_COMMANDS);
}

/**
 * Get commands that should appear in chat input dropdown
 */
export function getChatCommands(): SlashCommandDefinition[] {
  return cloneCommands(CHAT_COMMANDS);
}

/**
 * Get commands that should appear in command palette
 */
export function getPaletteCommands(): SlashCommandDefinition[] {
  return cloneCommands(SORTED_COMMANDS);
}

export function getCommandsByScope(scope: SlashCommandScope = "all"): SlashCommandDefinition[] {
  return cloneCommands(SCOPE_MAP[scope]);
}

export function filterSlashCommands(
  query: string,
  scope: SlashCommandScope = "all"
): SlashCommandDefinition[] {
  const commands = getCommandsByScope(scope);
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return commands;
  }

  return commands.filter((cmd) => {
    const searchable = [
      cmd.command.replace(/^\//, ""),
      cmd.command,
      cmd.label,
      cmd.description,
      cmd.category || "",
      ...(cmd.keywords || []),
    ]
      .join(" ")
      .toLowerCase();

    return searchable.includes(normalized);
  });
}
