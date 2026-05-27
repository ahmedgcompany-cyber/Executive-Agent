# MegaV — Setup Guide

## What You Need

| Requirement | Where to get it |
|---|---|
| Windows 10 or 11 | Already have it |
| Python 3.9 or newer | https://www.python.org/downloads/ — tick "Add Python to PATH" |
| An AI model (choose one below) | See options |

### AI Model Options (choose one)

**Option A — Free, runs locally (no internet needed)**
Install Ollama from https://ollama.com, then open a terminal and run:
```
ollama pull dolphin-mistral
```

**Option B — Claude API (best quality, costs per use)**
Get an API key from https://console.anthropic.com, then set it as an environment variable:
- Press Win+R, type `sysdm.cpl`, press Enter
- Advanced → Environment Variables → New (under "User variables")
- Name: `ANTHROPIC_API_KEY`   Value: `sk-ant-...your key...`

**Option C — DeepSeek API (cheap and powerful)**
Get a key from https://platform.deepseek.com, set environment variable:
- Name: `DEEPSEEK_API_KEY`   Value: `sk-...your key...`

---

## Installation Steps

1. **Extract** the ZIP file to any folder on your computer (not inside OneDrive)
2. **Double-click** `Install Dependencies.bat` — wait for it to finish (takes 1–3 minutes)
3. **Double-click** `Launch MegaV.bat` to start the app
4. On first launch, a setup wizard will guide you through connecting your AI model

---

## First Launch

- The app opens a setup wizard the first time only
- Choose your AI model (Ollama for free/local, or enter your API key)
- After setup, type any goal in plain English and press Send

---

## Connecting Email / Social / GitHub (Optional)

These are optional. The app works for AI tasks without them.

- **Email**: Settings → Email Accounts → Add Account (needs Gmail/Outlook app password)
- **GitHub**: Settings → GitHub → Paste your personal access token
- **Social Media**: Settings → Social → Connect button for each platform

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Window doesn't open | Check `logs\startup.log` for error details |
| "AI: Offline" in status bar | Install Ollama or set your API key (see above) |
| Agents do nothing | Check `logs\app_debug.log` for error messages |
| Email not connecting | Use an App Password, not your regular password |
| Import errors on start | Re-run `Install Dependencies.bat` |

---

## What MegaV Can Do

- **AI Chat**: Ask questions, get help with any task
- **Code Generation**: Describe what you want built, get working code
- **Job Search**: Browse job listings, generate cover letters
- **Sales / Lead Generation**: Research companies, generate outreach lists
- **Email Automation**: Read, classify, and draft replies to emails
- **Social Media**: Post to LinkedIn, Twitter, Facebook, Instagram
- **Browser Automation**: Control a browser to complete web tasks

---

## Your Data Stays Local

- No data is sent to any server except the AI provider you choose
- API keys are stored encrypted on your computer only
- All profiles and credentials are local to your machine
