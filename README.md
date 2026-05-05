# Adhahi Booking Monitor 🐑

A robust Python-based monitoring system for tracking sheep booking availability on [Adhahi.dz](https://adhahi.dz). Specifically designed to monitor Algiers (Alger) and surrounding wilayas, providing instant alerts and interactive control via Telegram.

## 🚀 Features

- **Real-time Monitoring**: Polls the Adhahi.dz API at configurable intervals (default: 15 minutes).
- **Instant Telegram Alerts**: Sends triple-ping notifications the moment a tracked wilaya becomes available.
- **Interactive Commands**: Control the bot directly from Telegram:
  - `/check` — Force an immediate availability check.
  - `/status` — View the last known status of all tracked wilayas.
  - `/help` — List available commands and current tracking configuration.
- **Periodic Summaries**: Receive a comprehensive status report every 2 hours (nationwide availability + check frequency).
- **Multi-Wilaya Tracking**: Pre-configured for Algiers and 9 neighboring regions:
  - Alger (16), Blida (09), Tizi Ouzou (15), Boumerdès (35), Tipaza (42), Aïn Defla (44), Médéa (26), Bouira (10), Chlef (02).

## 🛠️ Setup & Installation

### 1. Prerequisites
- Python 3.8 or higher.
- A Telegram Bot (Create one via [@BotFather](https://t.me/botfather)).
- Your Telegram Chat ID (Get it via [@userinfobot](https://t.me/userinfobot)).

### 2. Installation
Clone the repository and install dependencies:
```bash
git clone https://github.com/harrysof/Adhahi_monitor.git
cd Adhahi_monitor
pip install -r requirements.txt
```

### 3. Configuration
Copy the example config and fill in your details:
```bash
cp config.json.example config.json
```
Edit `config.json`:
```json
{
    "telegram_bot_token": "your_bot_token_here",
    "telegram_chat_id": "your_chat_id_here",
    "check_interval_minutes": 15,
    "summary_interval_hours": 2,
    "target_wilayas": ["16", "09", "15", "35", "42", "44", "26", "10", "02"],
    "api_url": "https://adhahi.dz/api/v1/public/wilaya-quotas",
    "register_url": "https://adhahi.dz/register"
}
```

## 🏃 Running the Monitor

Start the main monitoring loop:
```bash
python monitor.py
```

The bot will send a "Started" message to your Telegram chat and begin monitoring immediately.

## 🐳 Docker (Optional)
You can also run the monitor using Docker:
```bash
docker build -t adhahi-monitor .
docker run -d --name adhahi-bot adhahi-monitor
```

## 📊 Project Structure
- `monitor.py`: Core monitoring logic and Telegram command handler.
- `monitor_cron.py`: Lightweight version for running via system crontabs.
- `config.json`: Your private configuration (ignored by git).
- `config.json.example`: Template for configuration.
- `simulate_alert.py`: Utility to test Telegram notifications.
- `test_api.py`: Simple script to verify API connectivity.

## ⚖️ License
Distributed under the MIT License. See `LICENSE` for more information.
