"""
ZVB Daily Digest & Scheduler (Twice a Day Publisher)
Generates and sends Morning & Evening project summaries to the ZVB Telegram Group.
"""

import os
import sys
import json
import time
import datetime
import requests
import lead_scraper

sys.stdout.reconfigure(encoding='utf-8')

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
LEADS_JSON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leads.json")

def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def send_telegram(text, bot_token, chat_id):
    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        r = requests.post(api_url, json=payload, timeout=12)
        return r.status_code == 200
    except Exception as e:
        print(f"Telegram error: {e}")
        return False

def build_daily_digest(period_name="Дневен бюлетин"):
    """Compiles top leads in Sofia into an executive Telegram briefing"""
    if not os.path.exists(LEADS_JSON_PATH):
        return None
    
    with open(LEADS_JSON_PATH, "r", encoding="utf-8") as f:
        leads = json.load(f)
    
    leads_list = list(leads.values())
    
    # Prioritize Sofia and Urgent / Construction leads
    sofia_leads = [l for l in leads_list if "софия" in l.get("location", "").lower() or "софия" in l.get("title", "").lower()]
    urgent_leads = [l for l in sofia_leads if l.get("category") == "urgent_client"]
    contractor_leads = [l for l in sofia_leads if l.get("category") == "contractor"]
    renovation_leads = [l for l in sofia_leads if l.get("category") == "renovation"]

    now_str = datetime.datetime.now().strftime("%d.%m.%Y | %H:%M") + " ч."

    header_icon = "🌅" if "сутрин" in period_name.lower() or "утрин" in period_name.lower() else "🌆"

    msg = f"{header_icon} <b>ZVB Радар: {period_name}</b>\n"
    msg += f"📅 <i>{now_str} (Град София)</i>\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━\n\n"

    # 1. Urgent direct requests
    if urgent_leads:
        msg += "🎯 <b>ТОП ДИРЕКТНИ ЗАПИТВАНИЯ (Спешно):</b>\n"
        for idx, l in enumerate(urgent_leads[:3], 1):
            phone_part = f"\n   📞 Телефон: <b>{l.get('phone')}</b>" if l.get('phone') else ""
            msg += f"{idx}. <b>{l.get('title')[:60]}</b>{phone_part}\n   🔗 <a href='{l.get('url')}'>Отвори обявата</a>\n\n"

    # 2. Construction firms / Developers
    if contractor_leads:
        msg += "🏗️ <b>СТРОИТЕЛНИ ФИРМИ И ПАРТНЬОРИ:</b>\n"
        for idx, l in enumerate(contractor_leads[:3], 1):
            phone_part = f"\n   📞 Телефон: <b>{l.get('phone')}</b>" if l.get('phone') else ""
            msg += f"{idx}. <b>{l.get('title')[:60]}</b>{phone_part}\n   🔗 <a href='{l.get('url')}'>Виж офертата</a>\n\n"

    # 3. Renovations
    if renovation_leads:
        msg += "🔨 <b>ОБЕКТИ ЗА РЕМОНТ / ЕЛ. ИНСТАЛАЦИИ:</b>\n"
        for idx, l in enumerate(renovation_leads[:2], 1):
            msg += f"• <b>{l.get('title')[:55]}</b>\n  🔗 <a href='{l.get('url')}'>Детайли за обекта</a>\n\n"

    msg += "━━━━━━━━━━━━━━━━━━━━\n"
    msg += "💡 <i>Съвет: Свържете се първи! Използвайте готовото партньорско съобщение от ZVB Таблото.</i>\n"
    msg += "🌐 <b>ZVB Sofia</b> | <a href='https://zvb.bg'>zvb.bg</a>"

    return msg

def send_digest_now(period="Бюлетин за нови обекти"):
    cfg = load_config()
    telegram_cfg = cfg.get("telegram", {})
    token = telegram_cfg.get("bot_token")
    chat_id = telegram_cfg.get("chat_id")
    
    if not token or not chat_id:
        print("❌ Telegram credentials not configured in config.json")
        return False
    
    print(f"Generating and sending {period}...")
    digest_text = build_daily_digest(period)
    if digest_text:
        ok = send_telegram(digest_text, token, chat_id)
        if ok:
            print("✅ Digest successfully sent to Telegram group!")
            return True
        else:
            print("❌ Failed to send digest.")
            return False
    return False

def run_schedule():
    """Runs 24/7 and sends briefings at 09:00 (Morning) and 18:00 (Evening)"""
    print("=" * 60)
    print("      ZVB Daily Digest Scheduler (2 пъти на ден)")
    print("      График: 09:00 ч. (Сутрешен) и 18:00 ч. (Вечерен)")
    print("=" * 60)

    # First run a fresh scan
    lead_scraper.run_scan()
    send_digest_now("Първоначален преглед на проектите")

    sent_today = set()

    while True:
        now = datetime.datetime.now()
        current_date_str = now.strftime("%Y-%m-%d")
        current_time_str = now.strftime("%H:%M")

        # Morning Digest at 09:00
        morning_key = f"{current_date_str}_morning"
        if now.hour == 9 and morning_key not in sent_today:
            print(f"[{current_time_str}] Стартиране на сутрешен радар...")
            lead_scraper.run_scan()
            send_digest_now("Сутрешен бюлетин за проекти")
            sent_today.add(morning_key)

        # Evening Digest at 18:00
        evening_key = f"{current_date_str}_evening"
        if now.hour == 18 and evening_key not in sent_today:
            print(f"[{current_time_str}] Стартиране на вечерен радар...")
            lead_scraper.run_scan()
            send_digest_now("Вечерен бюлетин за проекти")
            sent_today.add(evening_key)

        # Also every 30 minutes, run background scan for urgent leads
        if now.minute % 30 == 0 and now.second < 30:
            lead_scraper.run_scan()

        time.sleep(30)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--now", action="store_true", help="Send digest immediately to test")
    args = parser.parse_args()

    if args.now:
        send_digest_now("Извънреден бюлетин (Тест)")
    else:
        run_schedule()
