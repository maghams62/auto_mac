# Frontend Dev Server Check (2025‑11‑28)

## Steps

```
cd /Users/siddharthsuresh/Downloads/auto_mac/frontend
npm run dev
curl -Ls http://localhost:3000/launcher > /tmp/launcher.html
```

## Observations

1. **Port collisions**  
   - Initial run showed “Port 3000 is in use” and Next.js fell back to `3002`.  
   - `lsof -i :3000` revealed an orphaned `next-server` (PID 81269) still listening from an older session. Killing it freed the canonical port.

2. **Launcher route**  
   - Once port 3000 was available, the dev server booted cleanly in ~1.1 s.  
   - Fetching `/launcher` returned valid HTML (saved in `/tmp/launcher.html`), confirming that the route renders correctly outside Electron.

3. **Redirect note**  
   - `/launcher` issues an expected `308` redirect to `/launcher/` (Next.js app router behavior). Following the redirect returns the full SPA shell with command palette markup.

## Implications

- If Electron still points at `http://localhost:3000/launcher` while another Next dev instance is listening, you’ll get either a blank window or a connection refusal.  
- Running `lsof -ti :3000 | xargs kill -9` (or `start_ui.sh`) before `desktop/npm run dev` guarantees the launcher window sees the right server.

