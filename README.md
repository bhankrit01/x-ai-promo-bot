# X AI Promo Watcher

This bot checks X every hour for **new posts about AI subscription promotions** (Claude Code, Codex/GPT, GLM, Kimi, Hermes, OpenClaw, Qwen, etc.).

It supports:

- `api` mode (X API bearer token)
- `cookies` mode (browser session cookie/state file, auto-refreshed each run)
  - Browser engine: `playwright` (default) or `cloak` (CloakBrowser)

It stores seen post IDs and only alerts on fresh matches.

## 1) Setup

```powershell
cd "C:\Users\Net\Documents\New project"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
Copy-Item .env.example .env
```

## 2) Configure auth

Edit `.env`:

### Option A: API mode

- `AUTH_MODE=api`
- `X_BEARER_TOKEN=...`

### Option B: Cookies mode

- `AUTH_MODE=cookies`
- `COOKIE_FILE=x_storage_state.json` (or your cookie file path)
- `BROWSER_ENGINE=playwright` (default)

If you want stealth mode with CloakBrowser:

```powershell
pip install cloakbrowser
```

Then set:

- `BROWSER_ENGINE=cloak`
- `CLOAK_HUMANIZE=true`

Supported cookie file formats:

- Playwright storage state JSON (`{"cookies":[...],"origins":[...]}`)
- JSON array of cookies (`[{...}, {...}]`)
- Netscape `cookies.txt`

In cookies mode, the script writes refreshed browser state back to `COOKIE_FILE` every run.

## 3) Test once

```powershell
.\.venv\Scripts\Activate.ps1
python .\x_promo_bot.py --once
```

## 4) Run continuously (every hour)

```powershell
.\.venv\Scripts\Activate.ps1
python .\x_promo_bot.py
```

Default interval is `RUN_EVERY_MINUTES=60`.

## 5) Run every hour via Task Scheduler

```powershell
$python = "C:\Users\Net\Documents\New project\.venv\Scripts\python.exe"
$script = "C:\Users\Net\Documents\New project\x_promo_bot.py"
schtasks /Create /F /SC HOURLY /MO 1 /TN "X-AI-Promo-Watcher" /TR "`"$python`" `"$script`" --once" /ST 00:00
```

Manage it:

```powershell
schtasks /Query /TN "X-AI-Promo-Watcher"
schtasks /Delete /TN "X-AI-Promo-Watcher" /F
```

## Files

- `x_promo_bot.py`: main bot
- `.env`: configuration
- `state.json`: checkpoint (`since_id`, seen IDs)
- `alerts.jsonl`: fresh alerts (JSON lines)

## Notes

- API mode uses X recent search (about last 7 days).
- Cookies mode depends on your active X web session; if it expires, export cookies/state again.
