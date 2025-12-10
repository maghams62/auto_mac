## Spotlight Launcher vs. Desktop Chat – Architectural Notes

These notes capture how the two primary UI surfaces wire into the shared orchestration stack. They summarize the relevant files so future parity work can reference a single map instead of re-tracing the component tree.

### Entry Points & Providers
- **Spotlight launcher** (`frontend/app/launcher/page.tsx`) mounts `CommandPalette` directly. The Electron shell controls visibility and relies on `window.electronAPI` helpers for lock/unlock events.
- **Expanded desktop** (`frontend/app/desktop/page.tsx`) renders `DesktopContent`, which wraps `ChatInterface` inside `BootProvider` and optionally shows `DesktopExpandAnimation`.
- Both screens ultimately live inside the Next.js app, but only the desktop view hydrates full chat chrome (header, footer, plan trace toggles).

### Input & Command Pipeline
| Layer | Spotlight (`CommandPalette.tsx`) | Desktop (`ChatInterface.tsx`) |
| --- | --- | --- |
| Keyboard capture | Inlined inside palette with hint pills and calculator checks. | Delegated to `InputArea.tsx`, which exposes slash dropdown + shortcut helpers. |
| Voice | `useVoiceRecorder` + `RecordingIndicator` rendered inline, locks window while recording. | Same hook rendered near footer; plan rail handles additional CTA state. |
| Deterministic routing | Shared `useCommandRouter` hook invoked before WebSocket send to handle Spotify, stop, clear, etc. | Same hook (via `InputArea` + `ChatInterface`) handles identical actions. |
| Slash metadata | Palette bootstraps from `frontend/lib/slashCommands.ts` but currently slices to the top 5 entries and doesn’t emit telemetry. | `InputArea` consumes `getSortedCommands`/`getChatCommands`, emits `slash-command-used` events, and always shows `/slack`, `/git`, etc. |

### WebSocket & History
- Both surfaces connect through `useWebSocket.ts`, but the launcher only instantiates the hook in `"launcher"` mode (`ws://<api>/ws/chat`). The desktop view uses the same hook plus plan telemetry.
- `CommandPalette` renders conversation state via `LauncherHistoryPanel` (limited to `spotlightUi.miniConversation.defaultTurns`). It currently strips advanced widgets (Slack sections, completion artifacts) before displaying.
- `ChatInterface` renders each message through `MessageBubble`, which handles `SlashSlackSummaryCard`, completion events, file lists, and plan updates.

### Visual Treatment & Help Surfaces
- Desktop view lazy-loads `HelpOverlay` and `KeyboardShortcutsOverlay`; the launcher only shows a `/help` hint pill and writes deterministic router output into the response surface.
- Animation tokens for expand/collapse live in `frontend/config/ui.ts` (`spotlightUi`) but the launcher embeds bespoke easing literals in multiple places.

### Known Divergences (to fix in this remediation)
1. **Help parity:** `HelpOverlay` is absent from the launcher despite sharing the slash registry.
2. **Slash discoverability:** Launcher slices the slash list and lacks telemetry, so `/slack` and `/git` disappear under certain states.
3. **History richness:** `LauncherHistoryPanel` hides Slack sections, completion cards, and plan progress; desktop view shows them inside `MessageBubble`.
4. **Telemetry surfacing:** Desktop view shows connection, plan trace, and slash usage banners; launcher needs the same error affordances so users understand backend failures.

Use this map as the canonical reference when updating spotlight behavior. Keep new constants inside `frontend/config/ui.ts` so Electron, docs, and future surfaces can consume the same tokens without hardcoding values.

