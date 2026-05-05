# 🐑 Adhahi Booking Monitor + Auto-Register

Monitors **adhahi.dz** for sheep booking availability in Alger and nearby wilayas.
Sends instant Telegram alerts the moment a booking opens, and can automatically
fill the registration form for multiple people simultaneously.

> ⚠️ **Must run locally on an Algerian internet connection.**
> adhahi.dz geo-blocks all cloud providers (GitHub Actions, Railway, Heroku, etc.)

---

## Features

| Feature | Details |
|---|---|
| 🔍 **Monitors 9 wilayas** | Alger, Blida, Tizi Ouzou, Boumerdès, Tipaza, Aïn Defla, Médéa, Bouira, Chlef |
| 🚨 **Instant triple alert** | Telegram ping ×3 the moment a booking opens |
| 📊 **2-hour summaries** | Full status report every 2 hours |
| 🤖 **Auto-register** | Opens Chrome and fills the form automatically |
| 👥 **Multi-person** | Register multiple people simultaneously (one Chrome window each) |
| 💬 **Telegram commands** | `/check` `/status` `/help` + replies to any message |

---

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure `config.json`

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

**Getting your Telegram credentials:**
1. Message **@BotFather** → `/newbot` → copy the token
2. Send any message to your bot, then open:
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
   and find `chat.id`

### 3. Run
```bash
python monitor.py
```

---

## Telegram Commands

| Command | Action |
|---|---|
| `/check` | Force an immediate check right now |
| `/status` | Show last known status (no re-check) |
| `/help` | List commands + tracked wilayas |
| *Any message* | Bot replies with current status + command list |

---

## Auto-Register

Set `"auto_register": true` in `config.json` and fill in `registrants`.

When a target wilaya becomes available:
1. Bot sends **3 urgent Telegram alerts**
2. Opens **one Chrome window per person** (staggered 2 seconds apart)
3. Auto-fills: NIN, CNI, phone, email, password, wilaya, commune, payment
4. **Pauses** → sends you a Telegram ping to solve the CAPTCHA
5. **Pauses again** → sends you a ping to enter the SMS OTP
6. Confirms submission

You can add as many people as needed to the `registrants` list.

---

## Wilaya Codes Reference

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

---

## Hosting 24/7 on Your PC (Windows)

See the **[Windows 24/7 Hosting Guide](#)** below.
