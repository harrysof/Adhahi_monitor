# 🐑 Adhahi Booking Monitor + Auto-Register

Monitors **adhahi.dz** for sheep booking availability in Alger and nearby wilayas.
Sends instant Telegram alerts the moment a booking opens, and can automatically
fill the registration form for multiple people simultaneously.

> ⚠️ **Must run locally on an Algerian internet connection.**
> adhahi.dz geo-blocks all cloud providers (GitHub Actions, Railway, Heroku, etc.)

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure `config.json`
Create a `config.json` file in the root directory (use the template below).

```json
{
    "telegram_bot_token": "YOUR_BOT_TOKEN",
    "telegram_chat_id":   "YOUR_CHAT_ID",

    "check_interval_minutes": 15,
    "summary_interval_hours": 2,

    "target_wilayas": ["16","09","15","35","42","44","26","10","02"],
    "api_url":        "https://adhahi.dz/api/v1/public/wilaya-quotas",
    "register_url":   "https://adhahi.dz/register",

    "auto_register": false,
    "registrants": [
        {
            "name":     "Person 1",
            "nin":      "18-digit national ID",
            "cni":      "9-digit card number",
            "phone":    "05xxxxxxxx",
            "email":    "email@example.com",
            "password": "YourPassword1@",
            "wilaya":   "الجزائر",
            "commune":  "الجزائر الوسطى",
            "payment":  "cash"
        }
    ]
}
```

### 3. Telegram Setup (Important!)
1.  **Get Token:** Message **@BotFather** on Telegram, create a new bot, and copy the token.
2.  **Get Chat ID:**
    *   For personal: Message your bot, then check `https://api.telegram.org/bot<TOKEN>/getUpdates`.
    *   For groups: Add the bot to the group, then use a bot like `@userinfobot` to get the group's **negative ID** (e.g., `-100...`).
3.  **Group Privacy (CRITICAL):** By default, bots cannot see group messages.
    *   Go to **@BotFather** → `/mybots` → Select your bot.
    *   **Bot Settings** → **Group Privacy** → **Turn OFF**.

### 4. Run the Monitor
```bash
python monitor.py
```

---

## 🛠 Features

| Feature | Details |
|---|---|
| 🔍 **Monitors 9 wilayas** | Alger, Blida, Tizi Ouzou, Boumerdès, Tipaza, Aïn Defla, Médéa, Bouira, Chlef |
| 🚨 **Instant Alerts** | Triple Telegram ping the moment a booking opens |
| 📊 **Periodic Summaries** | Full status report every 2 hours |
| 🤖 **Auto-Register** | Fills Chrome form automatically for multiple people |
| 💬 **Bot Commands** | `/check`, `/status`, `/ping`, `/help` |

---

## 📟 Telegram Commands

| Command | Action |
|---|---|
| `/check` | Force an immediate check right now |
| `/status` | Show last known status (cached) |
| `/ping` | Check if the bot is alive and responding |
| `/help` | List all commands and tracked wilayas |

---

## 🤖 Auto-Register Details

Set `"auto_register": true` in `config.json` and add your info to the `registrants` list.

1.  **Alert:** Bot sends 3 urgent Telegram notifications.
2.  **Browser:** Opens one Chrome window per registrant (staggered).
3.  **Form:** Auto-fills NIN, CNI, phone, wilaya, etc.
4.  **CAPTCHA:** Bot pings you on Telegram to solve the CAPTCHA manually.
5.  **OTP:** Bot pings you to enter the SMS OTP in the browser.
6.  **Done:** Once you enter OTP, registration is complete.

---

## 📍 Tracked Wilayas

| Code | Wilaya | Arabic |
|---|---|---|
| 16 | Alger | الجزائر |
| 09 | Blida | البليدة |
| 15 | Tizi Ouzou | تيزي وزو |
| 35 | Boumerdès | بومرداس |
| 42 | Tipaza | تيبازة |
| 44 | Aïn Defla | عين الدفلى |
| 26 | Médéa | المدية |
| 10 | Bouira | البويرة |
| 02 | Chlef | الشلف |
