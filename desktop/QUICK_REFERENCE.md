# Cerebros Launcher - Quick Reference

## 🚀 Start

```bash
./quick-start.sh
```

## ⌨️ Shortcuts

| Key | Action |
|-----|--------|
| `⌥⌘Space` | Show/Hide Launcher |
| `Esc` | Hide Launcher |
| `↑` `↓` | Navigate |
| `Enter` | Execute/Open |
| `⌘Enter` | Reveal in Finder |
| `Space` | Preview (files) |

## 🎯 Examples

### Execute Actions
- Type: `email` → Email agent
- Type: `spotify` → Spotify control
- Type: `calendar` → Calendar
- Type: `weather` → Weather info

### Search Files
- Type filename or content
- Press `Enter` to open
- Press `⌘Enter` to reveal

## 🐛 Troubleshoot

### Hotkey Not Working
```bash
cd desktop
# Edit src/main.ts line 260
# Change hotkey, then:
npx tsc
npm run dev
```

### Backend Not Starting
```bash
cd ..
source venv/bin/activate
python api_server.py
```

### Frontend Not Starting
```bash
cd ../frontend
npm run dev
```

## 📚 Full Docs

- [START_LAUNCHER.md](../START_LAUNCHER.md)
- [TEST_LAUNCHER.md](../TEST_LAUNCHER.md)
- [COMPLETE_IMPLEMENTATION_SUMMARY.md](../COMPLETE_IMPLEMENTATION_SUMMARY.md)
