"""
Single-run version of the monitor for GitHub Actions / cron hosting.
Run this every 15 minutes via your scheduler.
It checks once, sends alerts if needed, and exits.
The 2-hour summary is handled via a separate GitHub Actions schedule.

State (previous availability) is stored in state.json so alerts
only fire when a wilaya *changes* from unavailable -> available.
"""

import io
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

# ─── Fix Windows console encoding ────────────────────────────────────────────
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("monitor.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("adhahi_monitor")

WILAYA_NAME_MAP = {
    "16": {"fr": "Alger",      "ar": "الجزائر",    "region": "Primary"},
    "09": {"fr": "Blida",      "ar": "البليدة",    "region": "Near Alger"},
    "15": {"fr": "Tizi Ouzou", "ar": "تيزي وزو",   "region": "Primary"},
    "35": {"fr": "Boumerdès",  "ar": "بومرداس",    "region": "Near Alger"},
    "42": {"fr": "Tipaza",     "ar": "تيبازة",     "region": "Near Alger"},
    "44": {"fr": "Aïn Defla",  "ar": "عين الدفلى", "region": "Near Alger"},
    "26": {"fr": "Médéa",      "ar": "المدية",     "region": "Near Alger"},
    "10": {"fr": "Bouira",     "ar": "البويرة",    "region": "Near Alger"},
    "02": {"fr": "Chlef",      "ar": "الشلف",      "region": "Near Alger"},
}

STATE_FILE = Path("state.json")


def load_config() -> dict:
    with open("config.json", "r", encoding="utf-8") as f:
        return json.load(f)


def load_state() -> dict:
    """Load previous availability state from file."""
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"availability": {}, "last_summary": None, "check_count": 0}


def save_state(state: dict):
    """Persist availability state to file."""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def fetch_wilayas(api_url: str) -> Optional[list]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://adhahi.dz/register",
        "Origin": "https://adhahi.dz",
    }
    try:
        resp = requests.get(api_url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else data.get("data")
    except Exception as e:
        logger.error(f"Fetch error: {e}")
        return None


def send_telegram(token: str, chat_id: str, text: str) -> bool:
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                  "disable_web_page_preview": False},
            timeout=15,
        )
        ok = resp.status_code == 200
        logger.info(f"Telegram: {'OK' if ok else 'FAILED'}")
        return ok
    except Exception as e:
        logger.error(f"Telegram error: {e}")
        return False


def main():
    config = load_config()
    token        = config["telegram_bot_token"]
    chat_id      = config["telegram_chat_id"]
    target_codes = config["target_wilayas"]
    api_url      = config["api_url"]
    register_url = config["register_url"]
    summary_hrs  = config.get("summary_interval_hours", 2)

    state = load_state()
    prev  = state.get("availability", {})
    state["check_count"] = state.get("check_count", 0) + 1

    now = datetime.utcnow()
    logger.info(f"Check #{state['check_count']} at {now.strftime('%Y-%m-%d %H:%M:%S')} UTC")

    wilayas = fetch_wilayas(api_url)
    if wilayas is None:
        logger.error("Could not fetch data — aborting this run")
        sys.exit(1)

    logger.info(f"Received {len(wilayas)} wilayas")

    # ── Check for newly available target wilayas ──────────────────────────────
    newly_available = []
    new_availability = {}

    for w in wilayas:
        code     = w.get("wilayaCode", "")
        is_avail = w.get("available", False)
        new_availability[code] = is_avail

        if code not in target_codes:
            continue

        was_avail = prev.get(code, False)
        name      = w.get("wilayaNameFr", WILAYA_NAME_MAP.get(code, {}).get("fr", code))

        if is_avail:
            logger.info(f"  AVAILABLE: {name} ({code})")
            if not was_avail:
                newly_available.append((code, w))
                logger.info(f"  >> {name} just became available — alerting!")
        else:
            logger.info(f"  unavailable: {name} ({code})")

    # ── Send instant alerts ───────────────────────────────────────────────────
    for code, w in newly_available:
        fr  = w.get("wilayaNameFr", WILAYA_NAME_MAP.get(code, {}).get("fr", "?"))
        ar  = w.get("wilayaNameAr", WILAYA_NAME_MAP.get(code, {}).get("ar", "?"))
        rgn = WILAYA_NAME_MAP.get(code, {}).get("region", "")
        alert = (
            f"🚨🚨🚨 <b>BOOKING AVAILABLE!</b> 🚨🚨🚨\n\n"
            f"🐑 <b>{fr}</b> — {ar}\n"
            f"📍 Wilaya: {code} ({rgn})\n\n"
            f"⚡ <b>Register NOW before slots fill up!</b>\n\n"
            f"👉 <a href=\"{register_url}\">CLICK HERE TO REGISTER</a>\n\n"
            f"⏰ {now.strftime('%Y-%m-%d %H:%M')} UTC"
        )
        for _ in range(3):
            send_telegram(token, chat_id, alert)
            time.sleep(1)

    # ── 2-hour summary ────────────────────────────────────────────────────────
    last_summary = state.get("last_summary")
    summary_due  = True
    if last_summary:
        from datetime import timezone
        try:
            last_dt    = datetime.fromisoformat(last_summary)
            elapsed_h  = (now - last_dt).total_seconds() / 3600
            summary_due = elapsed_h >= summary_hrs
        except Exception:
            summary_due = True

    if summary_due:
        logger.info("Sending 2-hour summary...")
        target_lines = []
        for w in wilayas:
            code = w.get("wilayaCode", "")
            if code not in target_codes:
                continue
            fr     = w.get("wilayaNameFr", WILAYA_NAME_MAP.get(code, {}).get("fr", "?"))
            rgn    = WILAYA_NAME_MAP.get(code, {}).get("region", "")
            status = "✅ AVAILABLE" if w.get("available") else "❌ Unavailable"
            target_lines.append(f"  • <b>{fr}</b> [{rgn}]: {status}")

        total_avail = sum(1 for w in wilayas if w.get("available"))
        global_avail = [w for w in wilayas if w.get("available")]
        global_note = ""
        if global_avail:
            names = ", ".join(w.get("wilayaNameFr", "?") for w in global_avail)
            global_note = f"\n\n📗 <b>Other available wilayas:</b>\n{names}"

        summary_msg = (
            f"📊 <b>ADHAHI 2-HOUR SUMMARY</b>\n"
            f"{'━' * 28}\n"
            f"⏰ {now.strftime('%Y-%m-%d %H:%M')} UTC\n\n"
            f"🎯 <b>Your Tracked Wilayas:</b>\n"
            + "\n".join(target_lines) +
            f"\n\n📈 Nationwide: {total_avail}/{len(wilayas)} available"
            f"{global_note}\n\n"
            f"👉 <a href=\"{register_url}\">Register here</a>\n"
            f"🔄 Next summary in {summary_hrs}h"
        )
        send_telegram(token, chat_id, summary_msg)
        state["last_summary"] = now.isoformat()

    # Save updated state
    state["availability"] = new_availability
    save_state(state)
    logger.info("Done.")


if __name__ == "__main__":
    main()
