## Spotlight vs. Raycast – UX Audit

### Scope
- `frontend/components/CommandPalette.tsx`
- `frontend/components/LauncherHistoryPanel.tsx`
- `frontend/components/SpotifyMiniPlayer.tsx`
- `frontend/components/DesktopExpandAnimation.tsx`
- `frontend/components/ReasoningTrace.tsx`

### Key Raycast Expectations
1. **Instant affordances** – inputs stay idle until the user confirms (no auto-search), and empty states are informative but quiet.
2. **Paired chat turns** – history is grouped by request/response with subtle timestamps, max 2-3 rows in spotlight.
3. **Deterministic slash UX** – `/` commands surface hints inline, file search stays dormant unless explicitly chosen.
4. **Live media tiles** – Spotify mini-players mirror the expanded view, with clear transport state and cached metadata.
5. **Featherweight transitions** – launch/expand animations are short, glassy, and avoid full-screen dimming.

### Current Gaps

#### 1. Command Input & Search (`CommandPalette.tsx`)
- Triggers file search as the user types, so spotlight often replies “no results” before Enter.
- Slash hints disappear when reconnect banner shows; `/help` and Spotify commands sometimes queue silently.
- Error/empty states are verbose paragraphs instead of Raycast-style inline pills.

#### 2. Conversation History (`LauncherHistoryPanel.tsx`)
- Displays every message including verbose assistant streams, so spotlight scrolls instead of staying contextual.
- Lacks user/assistant pairing, timestamps, or plan badges; status updates intermingle with replies.
- No config-driven max turns, so spotlight view can show dozens of rows, unlike Raycast’s 2-3 bubble preview.

#### 3. Spotify Mini Player (`SpotifyMiniPlayer.tsx`)
- `launcher-mini` variant drifts from expanded UI (missing scrubber, device badge is hidden when `status.item` is null).
- Cached track handling only stores album art; when playback resumes we still render “No song available”.
- Slash Spotify commands acknowledge success even if `/api/spotify/*` responds 4xx, so UI shows success but state stays paused.

#### 4. Animation & Theming (`DesktopExpandAnimation.tsx`, `ReasoningTrace.tsx`)
- Desktop expand overlay dims the entire screen with a heavy blur and large card, unlike Raycast’s subtle corner growth.
- Reasoning trace shares the same dense panel in spotlight and full view, overwhelming the mini launcher.
- Iconography mixes emojis and inline SVGs with inconsistent sizing, clashing with the Raycast-like monochrome glyphs.

### Recommended Directions
1. Introduce `frontend/config/ui.ts` with spotlight limits (e.g., `miniConversationTurns = 3`, `animation = { duration: 180ms }`).
2. Defer file search until Enter (unless `/files`) and show hint rows (“Press Enter to ask Cerebros”) for empty states.
3. Rebuild `LauncherHistoryPanel` to group user + assistant pairs, show status badges, clamp to config turns, and add expand CTA.
4. Mirror expanded Spotify controls inside `launcher-mini` (play/pause/prev/next, progress, device badge) and keep last-known metadata for skeleton states; pipe actual API failures through connection banner.
5. Replace the full-screen expand overlay with a translucent corner card animation, reuse a `.motionPreset` shared across spotlight surfaces, and lighten reasoning trace visuals (accordion or sparkline instead of full panel).

### 2025-11-30 Follow-up Findings

1. **Status chip never clears** – Launcher shows “Processing your request…” indefinitely because the backend never emits a `status=complete`. Fixing the websocket payload plus trimming empty status bubbles keeps spotlight calm.
2. **Plan animation duplication** – The floating Plan rail and the in-chat plan bubble animate the same steps, creating two competing focal points. Removing the floating rail and gating the reasoning trace behind a single button reduces noise.
3. **Expand CTA overload** – Header, history panel, and sometimes response blocks all expose “Expand” at once. We now keep the global expand action (keyboard muscle memory) and removed the redundant history-panel button; future work should attach contextual `↗ Expand View` links per assistant reply instead of scattering generic buttons.
4. **Trace access** – With the rail gone, plan trace is now reachable via a small header icon that also indicates when orchestration is running. This mirrors Raycast’s lightweight “show steps” affordance instead of occupying prime chat real estate.

These updates keep the spotlight surface closer to Raycast’s “one action, one hint” model while we continue hardening the mini conversation flow.

### 2025-11-30 Evening Polish

- **Slash registry parity** – `CommandPalette` now bootstraps from the shared `SLASH_COMMANDS` registry so `/slack`, `/git`, `/files`, etc. remain discoverable even if `/api/commands` is slow. API results are merged (not replaced) so backend-only agents still appear, but spotlight never loses deterministic slash affordances.
- **Aligned hint row** – The `/help` chip and “Ask Cerebros” pill share a 24px baseline with consistent pill styles. Secondary hints (calculator, queued submission, reconnect) render as compact tags instead of full-width banners.
- **History spacing rhythm** – `LauncherHistoryPanel` clamps to the new `historyPanel.maxHeight = 192px`, uses 16px/24px padding multiples, sticky headers, and paired bubbles with timestamps so mini conversations mirror Raycast’s “last 2-3 turns” presentation.
- **Integrated trace drawer** – The full-screen reasoning overlay was dropped. Toggling “Show Steps” now expands an in-flow panel inside the desktop chat column, keeping orchestration context co-located with the conversation.
- **Footer cues trimmed** – Spotlight only advertises the two core shortcuts (`↵ Submit`, `Esc Close`), reducing CTA clutter while still matching Raycast’s muscle-memory cues.
