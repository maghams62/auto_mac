# Oqoqo Dashboard – Simple Runbook

Copy-paste friendly steps to bring up the Cerebros stack plus the Oqoqo dashboard, and to try the slash commands.

## 0) Install deps (once)
```bash
# from repo root
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd frontend && npm install && cd ..
cd desktop && npm install && cd ..
cd oqoqo-dashboard && npm install && cd ..
```

## 1) Minimal env
- In repo root: copy `.env.sample` to `.env` and set **`OPENAI_API_KEY`**, **`SLACK_BOT_TOKEN`** (or `SLACK_TOKEN`), **`GITHUB_TOKEN`**. Spotify keys optional.
- In `oqoqo-dashboard/.env.local` set:
  - `NEXT_PUBLIC_CEREBROS_API_BASE=http://127.0.0.1:8000`
  - `NEXT_PUBLIC_CEREBROS_APP_BASE=http://localhost:3300`

## 2) Start the stack
Terminal 1 (repo root):
```bash
bash master_start.sh
```

Terminal 2:
```bash
cd oqoqo-dashboard
./oq_start.sh
```

## 3) Where to view
- Cerebros UI: http://localhost:3300
- Backend health: http://127.0.0.1:8000/health
- Oqoqo dashboard: http://localhost:3100/projects

## 4) Example queries (grounded in the seeded data)
- Cerebros ask (quota drift storyline):  
  ```bash
  curl "http://127.0.0.1:8000/api/cerebros/ask?question=summarize%20the%20quota%20drift%20between%20core-api%20and%20billing-service%20docs"
  ```
- Cerebros ask (doc issues snapshot):  
  ```bash
  curl "http://127.0.0.1:8000/api/cerebros/ask?question=list%20doc%20issues%20for%20web-dashboard%20and%20docs-portal"
  ```
- Slash Git (billing summary fixture):  
  ```bash
  python scripts/run_slash_smoke_tests.py --base-url http://127.0.0.1:8000 --only git_billing_summary
  ```
- Slash Git (doc drift fixture):  
  ```bash
  python scripts/run_slash_smoke_tests.py --base-url http://127.0.0.1:8000 --only git_doc_drift
  ```
- Slash Slack (status check):  
  ```bash
  python scripts/run_slash_smoke_tests.py --base-url http://127.0.0.1:8000 --only slack_status
  ```
- Health ping:  
  ```bash
  curl http://127.0.0.1:8000/health
  ```

That’s it: set env, run `master_start.sh`, run `./oq_start.sh`, then open ports 3300 (Cerebros) and 3100 (Oqoqo).
