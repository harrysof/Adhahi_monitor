"""
╔══════════════════════════════════════════════════════════════════╗
║          ADHAHI.DZ — Booking Availability Monitor               ║
║   Monitors Alger + nearby wilayas for open sheep bookings      ║
║   Sends instant Telegram alerts + periodic 2-hour summaries    ║
║   Supports /check and /status Telegram commands                ║
╚══════════════════════════════════════════════════════════════════╝

Usage:
    1. Fill in config.json with your Telegram bot token & chat ID
    2. pip install -r requirements.txt
    3. python monitor.py

Telegram Commands:
    /check   — Force an immediate availability check right now
    /status  — Show current known status without re-checking
    /help    — List available commands
"""

import io
import json
import logging
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import requests

# ─── Fix Windows console encoding for Arabic/emoji text ──────────────────────
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ─── Logging Setup ────────────────────────────────────────────────────────────

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

# ─── Wilaya Reference Map ─────────────────────────────────────────────────────
# All wilayas near Alger + the 3 primary targets

WILAYA_NAME_MAP = {
    # Primary targets
    "16": {"fr": "Alger",      "ar": "الجزائر",    "en": "Algiers",    "region": "Primary"},
    "09": {"fr": "Blida",      "ar": "البليدة",    "en": "Blida",      "region": "Near Alger"},
    "15": {"fr": "Tizi Ouzou", "ar": "تيزي وزو",   "en": "Tizi Ouzou", "region": "Primary"},
    # Near Alger
    "35": {"fr": "Boumerdès",  "ar": "بومرداس",    "en": "Boumerdas",  "region": "Near Alger"},
    "42": {"fr": "Tipaza",     "ar": "تيبازة",     "en": "Tipaza",     "region": "Near Alger"},
    "44": {"fr": "Aïn Defla",  "ar": "عين الدفلى", "en": "Ain Defla",  "region": "Near Alger"},
    "26": {"fr": "Médéa",      "ar": "المدية",     "en": "Medea",      "region": "Near Alger"},
    "10": {"fr": "Bouira",     "ar": "البويرة",    "en": "Bouira",     "region": "Near Alger"},
    "02": {"fr": "Chlef",      "ar": "الشلف",      "en": "Chlef",      "region": "Near Alger"},
}

# ─── Config Loading ──────────────────────────────────────────────────────────

def load_config(path: str = "config.json") -> dict:
    """Load and validate configuration from JSON file."""
    config_path = Path(path)
    if not config_path.exists():
        logger.error(f"Config file not found: {path}")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    if config.get("telegram_bot_token", "").startswith("YOUR_"):
        logger.error("Please set your Telegram bot token in config.json!")
        sys.exit(1)
    if config.get("telegram_chat_id", "").startswith("YOUR_"):
        logger.error("Please set your Telegram chat ID in config.json!")
        sys.exit(1)

    return config


# ─── Telegram Client ─────────────────────────────────────────────────────────

class TelegramClient:
    """Handles all Telegram bot messaging and update polling."""

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = str(chat_id)
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self._last_update_id: int = 0

    # ── Sending ──────────────────────────────────────────────────────────────

    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send a message. Returns True on success."""
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": False,
        }
        try:
            resp = requests.post(url, json=payload, timeout=15)
            if resp.status_code == 200:
                logger.info("Telegram message sent OK")
                return True
            else:
                logger.error(f"Telegram API error {resp.status_code}: {resp.text[:200]}")
                return False
        except requests.RequestException as e:
            logger.error(f"Telegram send failed: {e}")
            return False

    def send_availability_alert(self, wilaya_code: str, wilaya_data: dict, register_url: str):
        """Urgent alert when a target wilaya becomes available."""
        names = WILAYA_NAME_MAP.get(wilaya_code, {})
        fr_name = wilaya_data.get("wilayaNameFr", names.get("fr", "Unknown"))
        ar_name = wilaya_data.get("wilayaNameAr", names.get("ar", ""))
        region = names.get("region", "")

        msg = (
            f"🚨🚨🚨 <b>BOOKING AVAILABLE!</b> 🚨🚨🚨\n"
            f"\n"
            f"🐑 <b>{fr_name}</b> — {ar_name}\n"
            f"📍 Wilaya: {wilaya_code} ({region})\n"
            f"\n"
            f"⚡ <b>Register NOW before slots fill up!</b>\n"
            f"\n"
            f"👉 <a href=\"{register_url}\">CLICK HERE TO REGISTER</a>\n"
            f"\n"
            f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        # Triple-send for urgency
        for _ in range(3):
            self.send_message(msg)
            time.sleep(1)

    def send_check_result(self, all_wilayas: list, target_codes: list, register_url: str, triggered_by: str = "schedule"):
        """Send immediate check results (used for /check command and scheduled checks)."""
        now = datetime.now()

        # Split into available vs not
        target_available = []
        target_unavailable = []

        for w in all_wilayas:
            code = w.get("wilayaCode", "")
            if code not in target_codes:
                continue
            name_fr = w.get("wilayaNameFr", WILAYA_NAME_MAP.get(code, {}).get("fr", "?"))
            region = WILAYA_NAME_MAP.get(code, {}).get("region", "")
            if w.get("available"):
                target_available.append(f"  ✅ <b>{name_fr}</b> [{region}] — code {code}")
            else:
                target_unavailable.append(f"  ❌ {name_fr} [{region}] — code {code}")

        trigger_icon = "🔘" if triggered_by == "schedule" else "👤"
        trigger_label = "Scheduled check" if triggered_by == "schedule" else "Manual /check"

        avail_section = (
            "\n".join(target_available) if target_available
            else "  ❌ None of your wilayas are available"
        )
        unavail_section = "\n".join(target_unavailable) if target_unavailable else "  (none)"

        global_avail = [w for w in all_wilayas if w.get("available")]
        global_note = ""
        if global_avail:
            names = ", ".join(w.get("wilayaNameFr", "?") for w in global_avail)
            global_note = f"\n\n🌍 <b>Other available wilayas:</b> {names}"

        msg = (
            f"{trigger_icon} <b>Booking Check — {trigger_label}</b>\n"
            f"⏰ {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"{'━' * 28}\n"
            f"\n"
            f"🟢 <b>Available:</b>\n{avail_section}\n"
            f"\n"
            f"🔴 <b>Unavailable:</b>\n{unavail_section}"
            f"{global_note}\n"
            f"\n"
            f"👉 <a href=\"{register_url}\">Register here</a>"
        )
        self.send_message(msg)

    def send_summary(self, all_wilayas: list, target_codes: list, register_url: str, checks_count: int):
        """Send a periodic 2-hour summary."""
        now = datetime.now()

        target_lines = []
        for w in all_wilayas:
            code = w.get("wilayaCode", "")
            if code not in target_codes:
                continue
            status = "✅ AVAILABLE" if w.get("available") else "❌ Unavailable"
            name_fr = w.get("wilayaNameFr", WILAYA_NAME_MAP.get(code, {}).get("fr", "?"))
            region = WILAYA_NAME_MAP.get(code, {}).get("region", "")
            target_lines.append(f"  • <b>{name_fr}</b> [{region}]: {status}")

        total = len(all_wilayas)
        available_count = sum(1 for w in all_wilayas if w.get("available"))

        global_avail = [w for w in all_wilayas if w.get("available")]
        if global_avail:
            avail_names = "\n".join(
                f"  • {w.get('wilayaNameFr', '?')} (code {w.get('wilayaCode', '?')})"
                for w in global_avail
            )
            global_section = f"\n📗 <b>All Available Wilayas:</b>\n{avail_names}\n"
        else:
            global_section = "\n📕 <b>No wilayas available nationwide right now.</b>\n"

        msg = (
            f"📊 <b>ADHAHI 2-HOUR SUMMARY</b>\n"
            f"{'━' * 28}\n"
            f"⏰ {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"\n"
            f"🎯 <b>Your Tracked Wilayas:</b>\n"
            + "\n".join(target_lines) +
            f"\n\n"
            f"📈 <b>Nationwide:</b> {available_count}/{total} available\n"
            f"🔍 Checks in last 2h: {checks_count}"
            f"{global_section}\n"
            f"👉 <a href=\"{register_url}\">Register here</a>\n"
            f"🔄 Next summary in 2 hours\n"
            f"\n"
            f"💡 Send /check to force a check anytime"
        )
        self.send_message(msg)

    # ── Command Polling ───────────────────────────────────────────────────────

    def get_updates(self, timeout: int = 30) -> list:
        """Long-poll for new Telegram updates. Returns list of update dicts."""
        url = f"{self.base_url}/getUpdates"
        params = {
            "offset": self._last_update_id + 1,
            "timeout": timeout,
            "allowed_updates": ["message"],
        }
        try:
            resp = requests.get(url, params=params, timeout=timeout + 5)
            if resp.status_code == 200:
                data = resp.json()
                updates = data.get("result", [])
                if updates:
                    self._last_update_id = updates[-1]["update_id"]
                return updates
            return []
        except requests.RequestException:
            return []


# ─── API Client ───────────────────────────────────────────────────────────────

class AdhahiClient:
    """Fetches wilaya booking data from the Adhahi public API."""

    def __init__(self, api_url: str):
        self.api_url = api_url
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7,ar;q=0.6",
            "Referer": "https://adhahi.dz/register",
            "Origin": "https://adhahi.dz",
        })

    def fetch_wilaya_quotas(self) -> Optional[list]:
        """Returns list of wilaya dicts or None on error."""
        try:
            resp = self.session.get(self.api_url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "data" in data:
                return data["data"]
            return None
        except requests.exceptions.ConnectionError:
            logger.error("Connection error — network issue or site down")
            return None
        except requests.exceptions.Timeout:
            logger.error("Request timed out (30s)")
            return None
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error: {e}")
            return None
        except json.JSONDecodeError:
            logger.error("Failed to parse API response as JSON")
            return None
        except Exception as e:
            logger.error(f"Unexpected fetch error: {e}")
            return None


# ─── Monitor Core ─────────────────────────────────────────────────────────────

class BookingMonitor:
    """
    Main monitor with:
    - Scheduled checks every N minutes
    - Instant Telegram alerts on availability change
    - 2-hour periodic summaries
    - Telegram command listener (/check, /status, /help)
    """

    def __init__(self, config: dict):
        self.config = config
        self.telegram = TelegramClient(
            config["telegram_bot_token"],
            config["telegram_chat_id"],
        )
        self.client = AdhahiClient(config["api_url"])
        self.target_codes = config["target_wilayas"]
        self.register_url = config["register_url"]
        self.check_interval = config.get("check_interval_minutes", 15) * 60
        self.summary_interval = config.get("summary_interval_hours", 2) * 3600

        # Shared state (accessed from both threads)
        self._lock = threading.Lock()
        self._previous_availability: dict[str, bool] = {}
        self._last_wilayas: Optional[list] = None       # cached last result
        self._last_check_time: Optional[datetime] = None
        self._last_summary_time: datetime = datetime.min
        self._check_history: list[dict] = []
        self._total_checks: int = 0
        self._force_check_event = threading.Event()     # set by command thread

    # ── Main Loop ────────────────────────────────────────────────────────────

    def run(self):
        logger.info("=" * 60)
        logger.info("ADHAHI BOOKING MONITOR — STARTING")
        logger.info(f"  Tracking {len(self.target_codes)} wilayas: {', '.join(self.target_codes)}")
        logger.info(f"  Check every {self.config.get('check_interval_minutes', 15)} min | "
                    f"Summary every {self.config.get('summary_interval_hours', 2)} hrs")
        logger.info("=" * 60)

        # Startup message
        names = ", ".join(
            WILAYA_NAME_MAP.get(c, {}).get("fr", c) for c in self.target_codes
        )
        self.telegram.send_message(
            f"🟢 <b>Adhahi Monitor Started</b>\n\n"
            f"📍 Tracking ({len(self.target_codes)} wilayas):\n{names}\n\n"
            f"⏱ Check every {self.config.get('check_interval_minutes', 15)} min\n"
            f"📊 Summary every {self.config.get('summary_interval_hours', 2)} hrs\n\n"
            f"💡 Commands: /check · /status · /help\n"
            f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        # Start Telegram command listener in background thread
        cmd_thread = threading.Thread(target=self._command_listener, daemon=True)
        cmd_thread.start()

        # Main scheduler loop
        while True:
            try:
                self._perform_check(triggered_by="schedule")
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                time.sleep(60)
                continue

            logger.info(f"Sleeping {self.config.get('check_interval_minutes', 15)} min...")
            # Sleep in 1-second increments so we can react to force-check events
            deadline = time.time() + self.check_interval
            try:
                while time.time() < deadline:
                    if self._force_check_event.is_set():
                        self._force_check_event.clear()
                        logger.info("Force check triggered by Telegram command!")
                        self._perform_check(triggered_by="command")
                        # Reset deadline after forced check
                        deadline = time.time() + self.check_interval
                    time.sleep(1)
            except KeyboardInterrupt:
                break

        logger.info("Monitor stopped.")
        self.telegram.send_message("🔴 <b>Adhahi Monitor Stopped</b>")

    # ── Check Logic ──────────────────────────────────────────────────────────

    def _perform_check(self, triggered_by: str = "schedule"):
        with self._lock:
            self._total_checks += 1
            check_num = self._total_checks

        now = datetime.now()
        logger.info(f"Check #{check_num} [{triggered_by}] at {now.strftime('%H:%M:%S')}")

        wilayas = self.client.fetch_wilaya_quotas()
        if wilayas is None:
            logger.warning("Skipping — could not fetch data")
            return

        logger.info(f"Got data for {len(wilayas)} wilayas")

        # Detect newly available wilayas
        newly_available = []
        with self._lock:
            for w in wilayas:
                code = w.get("wilayaCode", "")
                if code not in self.target_codes:
                    continue
                is_avail = w.get("available", False)
                was_avail = self._previous_availability.get(code, False)
                name = w.get("wilayaNameFr", code)

                if is_avail:
                    logger.info(f"  AVAILABLE: {name} (code {code})")
                    if not was_avail:
                        newly_available.append((code, w))
                        logger.info(f"  >> {name} just became available — ALERTING!")
                else:
                    logger.info(f"  unavailable: {name} (code {code})")

                self._previous_availability[code] = is_avail

            # Cache last result
            self._last_wilayas = wilayas
            self._last_check_time = now

            # Record check history
            record = {
                "time": now.isoformat(),
                "available_count": sum(1 for w in wilayas if w.get("available")),
                "target_status": {
                    w.get("wilayaCode", ""): w.get("available", False)
                    for w in wilayas if w.get("wilayaCode", "") in self.target_codes
                },
            }
            self._check_history.append(record)
            cutoff = now - timedelta(hours=2, minutes=5)
            self._check_history = [
                c for c in self._check_history
                if datetime.fromisoformat(c["time"]) > cutoff
            ]
            checks_count = len(self._check_history)

        # Send instant alerts for newly available wilayas
        for code, w_data in newly_available:
            self.telegram.send_availability_alert(code, w_data, self.register_url)

        # For /check commands, always send full result
        if triggered_by == "command":
            self.telegram.send_check_result(wilayas, self.target_codes, self.register_url, triggered_by="command")

        # 2-hour summary
        with self._lock:
            due_summary = (now - self._last_summary_time).total_seconds() >= self.summary_interval
            if due_summary:
                self._last_summary_time = now

        if due_summary:
            logger.info("Sending 2-hour summary...")
            self.telegram.send_summary(wilayas, self.target_codes, self.register_url, checks_count)

        # Log all available
        all_avail = [w for w in wilayas if w.get("available")]
        if all_avail:
            logger.info(f"  Nationally available: {', '.join(w.get('wilayaNameFr','?') for w in all_avail)}")
        else:
            logger.info("  No wilayas available nationwide")

    # ── Telegram Command Listener ─────────────────────────────────────────────

    def _command_listener(self):
        """Background thread: long-polls Telegram for commands."""
        logger.info("Command listener started (listening for /check, /status, /help)")
        while True:
            try:
                updates = self.telegram.get_updates(timeout=30)
                for update in updates:
                    self._handle_update(update)
            except Exception as e:
                logger.error(f"Command listener error: {e}")
                time.sleep(5)

    def _handle_update(self, update: dict):
        """Process a single Telegram update."""
        message = update.get("message", {})
        chat_id = str(message.get("chat", {}).get("id", ""))
        text = message.get("text", "").strip().lower()

        if not text:
            return

        # Security: only respond to the configured chat
        if chat_id != self.telegram.chat_id:
            logger.warning(f"Ignoring message from unknown chat_id: {chat_id}")
            return

        logger.info(f"Received command: '{text}' from chat {chat_id}")

        if text.startswith("/check"):
            self._cmd_check()
        elif text.startswith("/status"):
            self._cmd_status()
        elif text.startswith("/help"):
            self._cmd_help()
        else:
            self.telegram.send_message(
                f"❓ Unknown command: <code>{text}</code>\n\nSend /help for available commands."
            )

    def _cmd_check(self):
        """Handle /check command — trigger an immediate check."""
        self.telegram.send_message(
            "🔍 <b>Forcing immediate check...</b>\nResults will appear shortly!"
        )
        # Signal the main loop to run a check ASAP
        self._force_check_event.set()

    def _cmd_status(self):
        """Handle /status — show cached last known status without re-checking."""
        with self._lock:
            wilayas = self._last_wilayas
            last_time = self._last_check_time
            checks = len(self._check_history)

        if wilayas is None:
            self.telegram.send_message(
                "⚠️ No data yet — first check hasn't completed. Try again in a moment, "
                "or send /check to force one."
            )
            return

        lines = []
        for w in wilayas:
            code = w.get("wilayaCode", "")
            if code not in self.target_codes:
                continue
            name_fr = w.get("wilayaNameFr", WILAYA_NAME_MAP.get(code, {}).get("fr", "?"))
            region = WILAYA_NAME_MAP.get(code, {}).get("region", "")
            icon = "✅" if w.get("available") else "❌"
            lines.append(f"  {icon} {name_fr} [{region}]")

        age = (datetime.now() - last_time).seconds // 60 if last_time else "?"
        msg = (
            f"📋 <b>Last Known Status</b> (from {age} min ago)\n"
            f"⏰ {last_time.strftime('%H:%M:%S') if last_time else '?'}\n"
            f"{'━' * 28}\n"
            + "\n".join(lines) +
            f"\n\n💡 Send /check to refresh now."
        )
        self.telegram.send_message(msg)

    def _cmd_help(self):
        """Handle /help command."""
        names = "\n".join(
            f"  • {WILAYA_NAME_MAP.get(c, {}).get('fr', c)} (code {c}) — "
            f"{WILAYA_NAME_MAP.get(c, {}).get('region', '')}"
            for c in self.target_codes
        )
        self.telegram.send_message(
            f"🤖 <b>Adhahi Monitor — Commands</b>\n"
            f"{'━' * 28}\n\n"
            f"/check — Force an immediate availability check\n"
            f"/status — Show last known status (no re-check)\n"
            f"/help — Show this help message\n\n"
            f"📍 <b>Tracked Wilayas ({len(self.target_codes)}):</b>\n{names}\n\n"
            f"⏱ Auto-checks every {self.config.get('check_interval_minutes', 15)} min\n"
            f"📊 Summary every {self.config.get('summary_interval_hours', 2)} hrs"
        )


# ─── Entry Point ──────────────────────────────────────────────────────────────

def main():
    print("""
    ╔══════════════════════════════════════════════════╗
    ║     ADHAHI.DZ BOOKING MONITOR                   ║
    ║     Alger + nearby wilayas                      ║
    ║     Commands: /check  /status  /help            ║
    ╚══════════════════════════════════════════════════╝
    """)
    config = load_config()
    monitor = BookingMonitor(config)
    monitor.run()


if __name__ == "__main__":
    main()
