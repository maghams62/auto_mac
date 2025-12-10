# Electron Launcher Diagnostics (2025‑11‑28)

## Command

```
cd /Users/siddharthsuresh/Downloads/auto_mac/desktop
npm run dev
```

## Key Observations

1. **Backend readiness is the pacing item**  
   - When the Python server is spawned by `desktop/src/main.ts`, it spends ~10 s initializing schedulers (Bluesky, GitHub PR watcher, branch watcher).  
   - During that window the Electron log prints `Health check in progress … connect ECONNREFUSED 127.0.0.1:8000`. This is expected until Uvicorn finishes booting—`waitForServer` keeps retrying for 30 s.

2. **Successful run**  
   - After the backend responds (≈500 ms when already running), frontend health also passes immediately and the launcher window is created.  
   - The self-test locks/unlocks the window, confirms blur grace and focus telemetry, and leaves the command palette visible for manual testing.

3. **Dependencies on background services**  
   - The buffered backend output (captured in `/tmp/electron-dev*.log` and `logs/electron/*`) shows the GitHub PR monitor issuing dozens of API calls on boot. These are benign but explain why the backend might look “stuck” even though it is just processing the watcher queue.

4. **Tray/icon fallback**  
   - When `/desktop/assets/icon.png` is missing or incompatible, Electron logs `Tray] Could not load icon, using default` but otherwise continues normally.

5. **Port hygiene**  
   - For consistent results, clear ports `8000` and `3000` (`lsof -ti :8000 -ti :3000 | xargs kill -9`) before launching. Otherwise the orchestrator assumes services are already up and might skip respawning them.

Overall, Electron is healthy once backend and frontend ports are free. Most “launcher won’t show” reports stem from the backend still warming up or Next.js dev servers occupying port 3000.

