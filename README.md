# 🐑 Adhahi Monitor

Monitors **adhahi.dz** for sheep booking availability in Alger and nearby wilayas.
Sends instant Telegram alerts the moment a quota opens, and keeps you updated with periodic summaries.

> ⚠️ **Must run on an Algerian internet connection.** adhahi.dz geo-blocks all cloud providers (GitHub Actions, Railway, Heroku, etc.)

---

## How it works

The bot polls the adhahi.dz public API every 15 minutes. It tracks availability per wilaya and only fires an alert when a wilaya **changes** from unavailable → available (no spam on every check). When a slot opens, it sends 3 back-to-back Telegram messages so you actually notice.

Every 2 hours it also sends a full status summary of all tracked wilayas regardless of changes.

---

## 📟 Telegram Commands

| Command | What it does |
|---------|--------------|
| `/check` | Force an immediate check right now |
| `/status` | Show last known status (no re-check, uses cache) |
| `/ping` | Confirm the bot is alive and show last check time |
| `/help` | List all commands and currently tracked wilayas |

---

## 📍 Tracked Wilayas

| Code | Wilaya | Arabic |
|------|--------|--------|
| 16 | Alger | الجزائر |
| 09 | Blida | البليدة |
| 15 | Tizi Ouzou | تيزي وزو |
| 35 | Boumerdès | بومرداس |
| 42 | Tipaza | تيبازة |
| 44 | Aïn Defla | عين الدفلى |
| 26 | Médéa | المدية |
| 10 | Bouira | البويرة |
| 02 | Chlef | الشلف |

You can change which wilayas are tracked via `target_wilayas` in `config.json`.

---

## 🚀 Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Create `config.json`

```json
{
    "telegram_bot_token": "YOUR_BOT_TOKEN",
    "telegram_chat_id":   "YOUR_CHAT_ID",

    "check_interval_minutes": 15,
    "summary_interval_hours": 2,

    "target_wilayas": ["16","09","15","35","42","44","26","10","02"],
    "api_url":        "https://adhahi.dz/api/v1/public/wilaya-quotas",
    "register_url":   "https://adhahi.dz/register"
}
```

### 3. Set up Telegram

1. Message **@BotFather**, create a new bot, copy the token.
2. Get your chat ID:
   - **Personal:** Message your bot, then open `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser.
   - **Group:** Add the bot to the group, use `@userinfobot` to get the group's negative ID (e.g. `-100...`).
3. **If using a group** — go to @BotFather → `/mybots` → your bot → Bot Settings → Group Privacy → **Turn OFF**. Otherwise the bot can't read commands.

### 4. Run

**Long-running (recommended):**
```bash
python monitor.py
```
Stays running, listens for Telegram commands, checks on schedule.

**Single-run / cron mode:**
```bash
python monitor_cron.py
```
Checks once and exits. Persists state in `state.json` between runs so alerts only fire on changes. Suitable for task schedulers.

---

## 🛠 Files

| File | Purpose |
|------|---------|
| `monitor.py` | Long-running bot with Telegram command listener |
| `monitor_cron.py` | Single-run version for cron/task scheduler |
| `check_names.py` | Utility — prints wilaya names (FR + AR) from the API, useful for debugging |
| `config.json` | Your config (not committed) |
| `state.json` | Persisted availability state between cron runs (auto-created) |
| `monitor.log` | Log file (auto-created) |

---

## Notes

- Alerts only fire on **state changes** (unavailable → available), not on every check.
- The 2-hour summary runs regardless and shows the full picture including wilayas available nationwide outside your tracked list.
- Logs are written to both console and `monitor.log`.
- Windows users: UTF-8 console encoding is handled automatically.
