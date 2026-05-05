"""
Adhahi Monitor + Auto-Register (Integrated)
- Monitors 9 wilayas near Alger every 15 min
- On detection: sends Telegram alert + auto-fills Chrome form
- Telegram commands: /check, /status, /help
- Must run locally (adhahi.dz geo-blocks cloud IPs)
"""

import io, json, logging, sys, threading, time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import requests

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
logger = logging.getLogger("adhahi")

WILAYA_MAP = {
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


def load_config() -> dict:
    with open("config.json", "r", encoding="utf-8") as f:
        return json.load(f)


# ─── Selenium Auto-Register ──────────────────────────────────────────────────

def auto_fill_form(personal_info: dict, register_url: str, telegram_fn):
    """Open Chrome and auto-fill the registration form. Pauses for CAPTCHA/OTP."""
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager
    except ImportError:
        logger.error("Missing selenium/webdriver-manager. Run: pip install -r requirements.txt")
        return

    p = personal_info
    logger.info("Opening Chrome for auto-registration...")

    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options,
    )
    wait = WebDriverWait(driver, 30)

    def fill(selector, value):
        el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
        el.clear()
        el.send_keys(value)

    def click(selector):
        el = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
        driver.execute_script("arguments[0].scrollIntoView(true);", el)
        el.click()

    try:
        driver.get(register_url)
        logger.info("Page loaded")

        fill("#reg-nin",              p["nin"])
        fill("#reg-cni",              p["cni"])
        fill("#reg-phone",            p["phone"])
        if p.get("email"):
            fill("#reg-email",        p["email"])
        fill("#reg-password",         p["password"])
        fill("#reg-confirm-password", p["password"])
        logger.info("Personal fields filled")

        # Wilaya
        wi = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#reg-wilaya")))
        wi.click(); time.sleep(0.5)
        wi.send_keys(p["wilaya"]); time.sleep(1.5)
        wi.send_keys(Keys.ARROW_DOWN); wi.send_keys(Keys.RETURN)
        logger.info(f"Wilaya selected: {p['wilaya']}")

        # Commune
        time.sleep(2)
        co = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#reg-commune")))
        co.click(); time.sleep(0.5)
        co.send_keys(p["commune"]); time.sleep(1.5)
        co.send_keys(Keys.ARROW_DOWN); co.send_keys(Keys.RETURN)
        logger.info(f"Commune selected: {p['commune']}")

        # Payment
        time.sleep(1)
        payment_map = {"cash": 0, "tpe": 1, "online": 2}
        idx = payment_map.get(p.get("payment", "cash").lower(), 0)
        radios = driver.find_elements(By.CSS_SELECTOR, "[role='radio']")
        if radios and idx < len(radios):
            driver.execute_script("arguments[0].click();", radios[idx])

        # Agreement
        time.sleep(0.5)
        click("#reg-law-1807-checkbox")
        logger.info("Form filled — waiting for CAPTCHA")

        # Notify CAPTCHA needed
        telegram_fn(
            "🔒 <b>CAPTCHA needed!</b>\n\n"
            "Chrome is open and the form is filled.\n"
            "👉 Solve the CAPTCHA then click SUBMIT.\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}"
        )
        input("\n  ⚠ Solve the CAPTCHA in Chrome, then press Enter here...\n")

        # OTP step
        telegram_fn(
            "📱 <b>OTP sent to your phone!</b>\n\n"
            "Enter the 6-digit SMS code in Chrome.\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}"
        )
        input("  ⚠ Enter the OTP in Chrome, then press Enter here...\n")

        logger.info("Registration submitted!")
        telegram_fn(
            "✅ <b>Registration submitted!</b>\n"
            "Check adhahi.dz to confirm your booking.\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}"
        )

    except Exception as e:
        logger.error(f"Browser error: {e}")
        telegram_fn(f"❌ Auto-fill error: {e}")
    finally:
        input("\n  Press Enter to close the browser...\n")
        driver.quit()


# ─── Telegram Client ─────────────────────────────────────────────────────────

class TelegramClient:
    def __init__(self, token: str, chat_id: str):
        self.token   = token
        self.chat_id = str(chat_id)
        self.base    = f"https://api.telegram.org/bot{token}"
        self._last_update_id = 0

    def send(self, text: str) -> bool:
        try:
            r = requests.post(f"{self.base}/sendMessage", json={
                "chat_id": self.chat_id, "text": text,
                "parse_mode": "HTML", "disable_web_page_preview": False,
            }, timeout=15)
            ok = r.status_code == 200
            logger.info(f"Telegram: {'OK' if ok else 'FAIL'}")
            return ok
        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            return False

    def send_alert(self, code: str, w: dict, url: str):
        fr  = w.get("wilayaNameFr", WILAYA_MAP.get(code, {}).get("fr", "?"))
        ar  = w.get("wilayaNameAr", WILAYA_MAP.get(code, {}).get("ar", "?"))
        rgn = WILAYA_MAP.get(code, {}).get("region", "")
        msg = (
            f"🚨🚨🚨 <b>BOOKING AVAILABLE!</b> 🚨🚨🚨\n\n"
            f"🐑 <b>{fr}</b> — {ar}\n"
            f"📍 Wilaya {code} ({rgn})\n\n"
            f"⚡ <b>Register NOW!</b>\n\n"
            f"👉 <a href=\"{url}\">CLICK HERE TO REGISTER</a>\n\n"
            f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        for _ in range(3):
            self.send(msg)
            time.sleep(1)

    def send_check_result(self, wilayas: list, targets: list, url: str):
        avail, unavail = [], []
        for w in wilayas:
            code = w.get("wilayaCode", "")
            if code not in targets:
                continue
            fr  = w.get("wilayaNameFr", WILAYA_MAP.get(code, {}).get("fr", "?"))
            rgn = WILAYA_MAP.get(code, {}).get("region", "")
            if w.get("available"):
                avail.append(f"  ✅ <b>{fr}</b> [{rgn}]")
            else:
                unavail.append(f"  ❌ {fr} [{rgn}]")

        global_avail = [w for w in wilayas if w.get("available")]
        extra = ""
        if global_avail:
            names = ", ".join(w.get("wilayaNameFr", "?") for w in global_avail)
            extra = f"\n\n🌍 <b>Nationally available:</b> {names}"

        self.send(
            f"🔘 <b>Check Result</b> — {datetime.now().strftime('%H:%M:%S')}\n"
            f"{'━'*28}\n\n"
            f"🟢 <b>Available:</b>\n" + ("\n".join(avail) or "  None") + "\n\n"
            f"🔴 <b>Unavailable:</b>\n" + ("\n".join(unavail) or "  None") +
            extra + f"\n\n👉 <a href=\"{url}\">Register</a>"
        )

    def send_summary(self, wilayas: list, targets: list, url: str, checks: int, hrs: int):
        lines = []
        for w in wilayas:
            code = w.get("wilayaCode", "")
            if code not in targets:
                continue
            fr  = w.get("wilayaNameFr", WILAYA_MAP.get(code, {}).get("fr", "?"))
            rgn = WILAYA_MAP.get(code, {}).get("region", "")
            icon = "✅" if w.get("available") else "❌"
            lines.append(f"  • {icon} <b>{fr}</b> [{rgn}]")

        total_avail = sum(1 for w in wilayas if w.get("available"))
        global_avail = [w for w in wilayas if w.get("available")]
        global_sec = ""
        if global_avail:
            names = "\n".join(f"  • {w.get('wilayaNameFr','?')} ({w.get('wilayaCode','?')})" for w in global_avail)
            global_sec = f"\n\n📗 <b>All available:</b>\n{names}"
        else:
            global_sec = "\n\n📕 No wilayas available nationwide"

        self.send(
            f"📊 <b>ADHAHI {hrs}H SUMMARY</b>\n{'━'*28}\n"
            f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"🎯 <b>Your Tracked Wilayas:</b>\n" + "\n".join(lines) +
            f"\n\n📈 Nationwide: {total_avail}/{len(wilayas)} available\n"
            f"🔍 Checks: {checks}{global_sec}\n\n"
            f"👉 <a href=\"{url}\">Register</a>\n"
            f"💡 /check to force check anytime"
        )

    def get_updates(self, timeout: int = 30) -> list:
        try:
            r = requests.get(f"{self.base}/getUpdates", params={
                "offset": self._last_update_id + 1,
                "timeout": timeout,
                "allowed_updates": ["message"],
            }, timeout=timeout + 5)
            if r.status_code == 200:
                updates = r.json().get("result", [])
                if updates:
                    self._last_update_id = updates[-1]["update_id"]
                return updates
        except Exception:
            pass
        return []


# ─── Monitor ─────────────────────────────────────────────────────────────────

class Monitor:
    def __init__(self, config: dict):
        self.cfg          = config
        self.tg           = TelegramClient(config["telegram_bot_token"], config["telegram_chat_id"])
        self.targets      = config["target_wilayas"]
        self.url          = config["register_url"]
        self.api          = config["api_url"]
        self.interval     = config.get("check_interval_minutes", 15) * 60
        self.summary_secs = config.get("summary_interval_hours", 2) * 3600
        self.registrants  = config.get("registrants", [])
        self.auto_reg     = config.get("auto_register", False)

        self._lock            = threading.Lock()
        self._prev            : dict[str, bool] = {}
        self._last_wilayas    : Optional[list]  = None
        self._last_check_time : Optional[datetime] = None
        self._last_summary    : datetime = datetime.min
        self._history         : list = []
        self._checks          : int = 0
        self._force           = threading.Event()

    def run(self):
        logger.info("=" * 55)
        logger.info("ADHAHI MONITOR + AUTO-REGISTER — STARTING")
        logger.info(f"  Targets: {', '.join(self.targets)}")
        logger.info(f"  Auto-register: {'ON' if self.auto_reg else 'OFF'}")
        logger.info("=" * 55)

        names = ", ".join(WILAYA_MAP.get(c, {}).get("fr", c) for c in self.targets)
        self.tg.send(
            f"🟢 <b>Adhahi Monitor Started</b>\n\n"
            f"📍 Tracking ({len(self.targets)}):\n{names}\n\n"
            f"🤖 Auto-register: {'<b>ON</b> (' + str(len(self.registrants)) + ' people)' if self.auto_reg else 'OFF'}\n"
            f"⏱ Every {self.cfg.get('check_interval_minutes',15)} min\n"
            f"💡 /check · /status · /help\n"
            f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        threading.Thread(target=self._cmd_listener, daemon=True).start()

        while True:
            try:
                self._check("schedule")
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Main loop error: {e}", exc_info=True)
                time.sleep(60)
                continue

            deadline = time.time() + self.interval
            try:
                while time.time() < deadline:
                    if self._force.is_set():
                        self._force.clear()
                        self._check("command")
                        deadline = time.time() + self.interval
                    time.sleep(1)
            except KeyboardInterrupt:
                break

        self.tg.send("🔴 <b>Adhahi Monitor Stopped</b>")

    def _fetch(self) -> Optional[list]:
        try:
            r = requests.get(self.api, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
                "Referer": "https://adhahi.dz/register",
                "Origin": "https://adhahi.dz",
            }, timeout=30)
            r.raise_for_status()
            d = r.json()
            return d if isinstance(d, list) else d.get("data")
        except Exception as e:
            logger.error(f"Fetch error: {e}")
            return None

    def _check(self, trigger: str = "schedule"):
        with self._lock:
            self._checks += 1
            n = self._checks
        now = datetime.now()
        logger.info(f"Check #{n} [{trigger}] at {now.strftime('%H:%M:%S')}")

        wilayas = self._fetch()
        if wilayas is None:
            logger.warning("Skipping — no data")
            return

        logger.info(f"Got {len(wilayas)} wilayas")
        newly_available = []

        with self._lock:
            for w in wilayas:
                code    = w.get("wilayaCode", "")
                is_avail = w.get("available", False)
                if code not in self.targets:
                    continue
                was_avail = self._prev.get(code, False)
                name      = w.get("wilayaNameFr", code)
                logger.info(f"  {'AVAILABLE' if is_avail else 'unavailable'}: {name} ({code})")
                if is_avail and not was_avail:
                    newly_available.append((code, w))
                self._prev[code] = is_avail

            self._last_wilayas    = wilayas
            self._last_check_time = now
            self._history.append({"time": now.isoformat()})
            cutoff = now - timedelta(hours=2, minutes=5)
            self._history = [h for h in self._history if datetime.fromisoformat(h["time"]) > cutoff]
            checks = len(self._history)
            due    = (now - self._last_summary).total_seconds() >= self.summary_secs
            if due:
                self._last_summary = now

        # Alerts for newly available
        for code, w in newly_available:
            self.tg.send_alert(code, w, self.url)
            # Launch one Chrome window per registrant in parallel
            if self.auto_reg and self.registrants:
                wilaya_name = w.get('wilayaNameFr', code)
                logger.info(f"Launching {len(self.registrants)} Chrome windows for {wilaya_name}...")
                self.tg.send(
                    f"🤖 Opening <b>{len(self.registrants)} Chrome windows</b> to auto-fill...\n"
                    f"Each person will need to solve their own CAPTCHA + OTP."
                )
                for i, person in enumerate(self.registrants):
                    name = person.get('name', f'Person {i+1}')
                    if not person.get('nin'):
                        logger.warning(f"Skipping {name} — NIN not set")
                        continue
                    logger.info(f"  Starting Chrome for: {name}")
                    threading.Thread(
                        target=auto_fill_form,
                        args=(person, self.url, self.tg.send),
                        daemon=True,
                    ).start()
                    time.sleep(2)  # stagger launches slightly

        if trigger == "command":
            self.tg.send_check_result(wilayas, self.targets, self.url)

        if due:
            hrs = self.cfg.get("summary_interval_hours", 2)
            self.tg.send_summary(wilayas, self.targets, self.url, checks, hrs)

        all_avail = [w for w in wilayas if w.get("available")]
        logger.info(f"  Nationally available: {', '.join(w.get('wilayaNameFr','?') for w in all_avail) or 'none'}")

    # ── Command listener ─────────────────────────────────────────────

    def _cmd_listener(self):
        logger.info("Command listener active (/check /status /help)")
        while True:
            try:
                for upd in self.tg.get_updates(30):
                    self._handle(upd)
            except Exception as e:
                logger.error(f"Cmd listener error: {e}")
                time.sleep(5)

    def _handle(self, upd: dict):
        msg     = upd.get("message", {})
        chat_id = str(msg.get("chat", {}).get("id", ""))
        text    = msg.get("text", "").strip().lower()
        if not text or chat_id != self.tg.chat_id:
            return
        logger.info(f"Command: '{text}'")

        if text.startswith("/check"):
            self.tg.send("🔍 <b>Forcing check...</b>")
            self._force.set()
        elif text.startswith("/status"):
            with self._lock:
                wilayas = self._last_wilayas
                t       = self._last_check_time
            if not wilayas:
                self.tg.send("⚠️ No data yet. Send /check to force one.")
                return
            lines = []
            for w in wilayas:
                code = w.get("wilayaCode", "")
                if code not in self.targets:
                    continue
                fr  = w.get("wilayaNameFr", WILAYA_MAP.get(code, {}).get("fr", "?"))
                rgn = WILAYA_MAP.get(code, {}).get("region", "")
                lines.append(f"  {'✅' if w.get('available') else '❌'} {fr} [{rgn}]")
            age = (datetime.now() - t).seconds // 60 if t else "?"
            self.tg.send(
                f"📋 <b>Last Status</b> ({age} min ago)\n{'━'*28}\n"
                + "\n".join(lines) + "\n\n💡 /check to refresh"
            )
        elif text.startswith("/help"):
            names = "\n".join(
                f"  • {WILAYA_MAP.get(c,{}).get('fr',c)} ({c})" for c in self.targets
            )
            self.tg.send(
                f"🤖 <b>Adhahi Monitor Commands</b>\n{'━'*28}\n\n"
                f"/check — Force immediate check\n"
                f"/status — Last known status\n"
                f"/help — This message\n\n"
                f"📍 <b>Tracking ({len(self.targets)}):</b>\n{names}\n\n"
                f"🤖 Auto-register: {'ON (' + str(len(self.registrants)) + ' people)' if self.auto_reg else 'OFF'}"
            )
        else:
            # Auto-reply to any message with current status + tips
            with self._lock:
                wilayas = self._last_wilayas
                t       = self._last_check_time
            age = f"{(datetime.now() - t).seconds // 60} min ago" if t else "not yet"

            if wilayas:
                target_lines = []
                for w in wilayas:
                    code = w.get("wilayaCode", "")
                    if code not in self.targets:
                        continue
                    fr   = w.get("wilayaNameFr", WILAYA_MAP.get(code, {}).get("fr", "?"))
                    icon = "✅" if w.get("available") else "❌"
                    target_lines.append(f"  {icon} {fr}")
                status_block = "\n".join(target_lines)
            else:
                status_block = "  No data yet"

            self.tg.send(
                f"👋 <b>Adhahi Monitor</b> is active!\n"
                f"{'━'*28}\n\n"
                f"📋 <b>Last check:</b> {age}\n"
                f"{status_block}\n\n"
                f"📟 <b>Commands:</b>\n"
                f"  /check — Force immediate check\n"
                f"  /status — Full status\n"
                f"  /help — All commands\n\n"
                f"⏱ Next auto-check in ~{self.cfg.get('check_interval_minutes', 15)} min"
            )


# ─── Entry point ─────────────────────────────────────────────────────────────

def main():
    print("""
    ╔══════════════════════════════════════════════════╗
    ║   ADHAHI MONITOR + AUTO-REGISTER                ║
    ║   /check · /status · /help                      ║
    ╚══════════════════════════════════════════════════╝
    """)
    config = load_config()
    Monitor(config).run()

if __name__ == "__main__":
    main()
