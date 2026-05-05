"""
Simulation: pretend Alger (code 16) just became available.
Sends the exact same triple-alert that the monitor would send.
Run this while monitor.py is NOT running to avoid conflicts.
"""
import json, sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import requests
from datetime import datetime

with open("config.json", "r") as f:
    config = json.load(f)

BOT_TOKEN  = config["telegram_bot_token"]
CHAT_ID    = config["telegram_chat_id"]
REGISTER   = config["register_url"]
BASE_URL   = f"https://api.telegram.org/bot{BOT_TOKEN}"

SIMULATED_WILAYA = {
    "wilayaCode":   "16",
    "wilayaNameFr": "Alger",
    "wilayaNameAr": "الجزائر",
    "available":    True,   # <-- simulated
}

def send(text):
    r = requests.post(f"{BASE_URL}/sendMessage", json={
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }, timeout=15)
    ok = r.status_code == 200
    print(f"  Sent: {'OK' if ok else 'FAILED — ' + r.text[:100]}")
    return ok

w = SIMULATED_WILAYA
fr  = w["wilayaNameFr"]
ar  = w["wilayaNameAr"]
code = w["wilayaCode"]
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

alert_msg = (
    f"🚨🚨🚨 <b>BOOKING AVAILABLE!</b> 🚨🚨🚨\n"
    f"\n"
    f"🐑 <b>{fr}</b> — {ar}\n"
    f"📍 Wilaya: {code} (Primary)\n"
    f"\n"
    f"⚡ <b>Register NOW before slots fill up!</b>\n"
    f"\n"
    f"👉 <a href=\"{REGISTER}\">CLICK HERE TO REGISTER</a>\n"
    f"\n"
    f"⏰ {now}\n"
    f"\n"
    f"⚠️ <i>[THIS IS A TEST SIMULATION]</i>"
)

print(f"\n🧪 Simulating availability alert for: {fr} ({ar})")
print("Sending triple alert...\n")
for i in range(1, 4):
    print(f"  Alert {i}/3...")
    send(alert_msg)
    if i < 3:
        time.sleep(1)

print("\n✅ Simulation done! Check your Telegram.")
