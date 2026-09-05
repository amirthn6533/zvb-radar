"""
ZVB Daily Digest & Scheduler (Twice a Day Publisher)
Generates and sends strictly filtered electrical, CCTV, and smart home leads in Sofia.
"""

import os
import sys
import json
import time
import datetime
import urllib.parse
import requests
import lead_scraper

sys.stdout.reconfigure(encoding='utf-8')

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
LEADS_JSON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leads.json")

# Strict Filters
EXCLUDE_WORDS = [
    'покрив', 'покриви', 'керемиди', 'улуци', 'хидроизолация',
    'парцел', 'парцели', 'продава', 'под наем', 'дава под наем', 'наем',
    'плочки', 'лепене на плочки', 'отпушване', 'дограма', 'кърти чисти',
    'фризер', 'хладилник', 'готварска печка', 'пералня',
    'курс', 'курсове', 'обучение', 'учебен център', 'училище', 'дистанционно',
    'диплом', 'сертификат', 'книга', 'литература', 'учебник', 'задачи', 'сборник', 'речник', 'записки', 'теоретична', 'ръководство',
    'германия', 'чужбина', 'холандия', 'англия', 'франция', 'австрия', 'белгия',
    'търся работа', 'търси работа', 'търсим работа', 'работа като', 'желана длъжност', 'секретарка', 'шофьор', 'кофражист',
    'генератор за ток', 'агрегат за ток', 'бушонно табло опел', 'части', 'ремарке', 'трабант', 'кемпер', 'мултиметър', 'микрометър',
    'honda', 'opel', 'bmw', 'mercedes', 'toyota', 'audi', 'лампа', 'протектор', 'фолио', 'ит експерт', 'хладилни камери',
    'задно виждане', 'авто камери', 'екшън камери', 'gopro', 'до ключ', 'от основи до ключ',
    'имот', 'имоти', 'двор', 'кв.м', 'рзп', 'табела'
]

SOFIA_AREAS = [
    'софия', 'sofia', 'младост', 'люлин', 'лозенец', 'витоша', 'бояна', 'драгалевци',
    'надежда', 'център', 'манастирски ливади', 'овча купел', 'гео милев', 'изток',
    'дианабад', 'белите брези', 'стрелбище', 'красно село', 'хиподрума', 'симеоново',
    'банишора', 'хаджи димитър', 'дружба', 'редута', 'илинден', 'красна поляна', 'павлово',
    'банкя', 'обеля', 'света троица', 'разсадника', 'борово', 'гоце делчев', 'слатина', 'славия', 'връбница'
]

OTHER_CITIES = [
    'бургас', 'варна', 'пловдив', 'русе', 'стара загора', 'плевен', 'търговище', 
    'видин', 'разград', 'свищов', 'пазарджик', 'кърджали', 'велико търново',
    'перник', 'благоевград', 'шумен', 'сливен', 'хасково', 'враца', 'габрово',
    'пещера', 'дупница', 'сандански', 'асеновград', 'казанлък', 'червен бряг',
    'несебър', 'слънчев бряг', 'кюстендил', 'елин пелин', 'сливница', 'ботевград', 'мездра', 'разлог', 'банско'
]

ELECTRICAL_MUST_HAVE = [
    'ел.', 'ел ', 'електро', 'инсталация', 'инсталации', 'ел табло', 'ел. табло', 'табла', 'окабеляване', 'кабели',
    'контакт', 'контакти', 'ел ключ', 'ел. ключ', 'ключове и контакти', 'осветление', 'led', 'лунички',
    'видеонаблюдение', 'охранителни камери', 'камери за видеонаблюдение', 'cctv', 'умен дом', 'smart home',
    'домофон', 'соларни панели', 'фотоволтаиц', 'слаботоков', 'вентилатор'
]

def is_strictly_electrical_sofia(l):
    title = l.get('title', '').lower()
    loc = l.get('location', '').lower()
    source = l.get('source', '')
    full = (title + ' ' + loc).lower()
    
    # 1. Blacklist
    if any(ex in title or ex in full for ex in EXCLUDE_WORDS):
        return False
        
    # 2. Exclude other cities
    if any(city in full for city in OTHER_CITIES) and 'софия' not in title:
        return False

    # Check Sofia strictly
    if source == 'Alo.bg' and loc == 'българия / софия':
        if not any(area in title for area in SOFIA_AREAS):
            return False
    elif not any(area in full for area in SOFIA_AREAS):
        return False
        
    # 3. Must have electrical core
    has_electrical = any(el in title for el in ELECTRICAL_MUST_HAVE)
    if not has_electrical:
        # MaistorPlus check
        if source == 'MaistorPlus' and any(w in title for w in ['контакт', 'вентилатор', 'ел', 'електро', 'осветление']):
            has_electrical = True
            
    if not has_electrical:
        return False

    return True

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
    if not os.path.exists(LEADS_JSON_PATH):
        return None
    
    with open(LEADS_JSON_PATH, "r", encoding="utf-8") as f:
        leads = json.load(f)
    
    leads_list = list(leads.values())
    
    # Apply strict electrical Sofia filtering
    valid_leads = [l for l in leads_list if is_strictly_electrical_sofia(l)]
    
    # Group into Categories and sort (with phone first)
    urgent_leads = [l for l in valid_leads if any(w in l.get('title', '').lower() for w in ['търся', 'търси', 'търсим', 'спешно', 'вентилатор', 'монтаж', 'смяна', 'подмяна', 'контакт'])]
    urgent_leads.sort(key=lambda x: (1 if x.get('phone') else 0, x.get('found_at', '')), reverse=True)

    cctv_smart_leads = [l for l in valid_leads if any(w in l.get('title', '').lower() for w in ['камери', 'видеонаблюдение', 'умен дом', 'смарт', 'домофон'])]
    cctv_smart_leads.sort(key=lambda x: (1 if x.get('phone') else 0, x.get('found_at', '')), reverse=True)

    contractor_leads = [l for l in valid_leads if l not in urgent_leads and l not in cctv_smart_leads]
    contractor_leads.sort(key=lambda x: (1 if x.get('phone') else 0, x.get('found_at', '')), reverse=True)

    now_str = datetime.datetime.now().strftime("%d.%m.%Y | %H:%M") + " ч."
    header_icon = "🌅" if "сутрин" in period_name.lower() or "утрин" in period_name.lower() else "🌆"

    msg = f"{header_icon} <b>ZVB Електро Радар: {period_name}</b>\n"
    msg += f"📅 <i>{now_str} (Само гр. София)</i>\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━\n\n"

    # 1. Urgent direct requests (Clients looking for electrician)
    if urgent_leads:
        msg += "⚡ <b>ДИРЕКТНИ ЗАПИТВАНИЯ ЗА ЕЛЕКТРОТЕХНИК:</b>\n"
        for idx, l in enumerate(urgent_leads[:4], 1):
            phone = l.get('phone')
            phone_part = ""
            action_links = []
            if phone:
                phone_part = f"\n   📞 Телефон: <b>{phone}</b>"
                if phone.startswith("08") and len(phone) == 10:
                    intl = "359" + phone[1:]
                    wa_txt = urllib.parse.quote("Здравейте! Пиша Ви от ZVB (Електроуслуги, София) относно Вашия проект. https://zvb.bg")
                    action_links.append(f"<a href='https://wa.me/{intl}?text={wa_txt}'>💬 WhatsApp</a>")
                    action_links.append(f"<a href='tel:+{intl}'>📞 Обади се</a>")
            action_links.append(f"<a href='{l.get('url')}'>🔗 Виж обявата</a>")
            actions_str = " | ".join(action_links)
            msg += f"{idx}. <b>{l.get('title')[:65]}</b>{phone_part}\n   👉 {actions_str}\n\n"

    # 2. CCTV & Smart home
    if cctv_smart_leads:
        msg += "📹 <b>ВИДЕОНАБЛЮДЕНИЕ И УМЕН ДОМ:</b>\n"
        for idx, l in enumerate(cctv_smart_leads[:2], 1):
            phone = l.get('phone')
            phone_part = ""
            action_links = []
            if phone:
                phone_part = f"\n   📞 Телефон: <b>{phone}</b>"
                if phone.startswith("08") and len(phone) == 10:
                    intl = "359" + phone[1:]
                    wa_txt = urllib.parse.quote("Здравейте! Пиша Ви от ZVB (Видеонаблюдение & Умен дом, София). https://zvb.bg")
                    action_links.append(f"<a href='https://wa.me/{intl}?text={wa_txt}'>💬 WhatsApp</a>")
                    action_links.append(f"<a href='tel:+{intl}'>📞 Обади се</a>")
            action_links.append(f"<a href='{l.get('url')}'>🔗 Виж проекта</a>")
            actions_str = " | ".join(action_links)
            msg += f"• <b>{l.get('title')[:60]}</b>{phone_part}\n  👉 {actions_str}\n\n"

    # 3. Electrical installations & Building Subcontracting
    if contractor_leads:
        msg += "🏗️ <b>ЕЛ. ИНСТАЛАЦИИ И ОБЕКТИ В СОФИЯ:</b>\n"
        for idx, l in enumerate(contractor_leads[:3], 1):
            phone = l.get('phone')
            phone_part = ""
            action_links = []
            if phone:
                phone_part = f"\n   📞 Телефон: <b>{phone}</b>"
                if phone.startswith("08") and len(phone) == 10:
                    intl = "359" + phone[1:]
                    wa_txt = urllib.parse.quote("Здравейте! Пиша Ви от ZVB (Ел. инсталации подизпълнител, София). https://zvb.bg")
                    action_links.append(f"<a href='https://wa.me/{intl}?text={wa_txt}'>💬 WhatsApp</a>")
                    action_links.append(f"<a href='tel:+{intl}'>📞 Обади се</a>")
            action_links.append(f"<a href='{l.get('url')}'>🔗 Виж офертата</a>")
            actions_str = " | ".join(action_links)
            msg += f"• <b>{l.get('title')[:60]}</b>{phone_part}\n  👉 {actions_str}\n\n"

    msg += "━━━━━━━━━━━━━━━━━━━━\n"
    msg += "💡 <i>Прецизно филтрирано за ZVB: Само електроуслуги, камери и умен дом в София.</i>\n"
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
    print("=" * 60)
    print("      ZVB Daily Digest Scheduler (Strict Electrical & Sofia)")
    print("=" * 60)

    # First run a fresh scan
    lead_scraper.run_scan()
    send_digest_now("Първоначален електро преглед")

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
            send_digest_now("Сутрешен електро бюлетин")
            sent_today.add(morning_key)

        # Evening Digest at 18:00
        evening_key = f"{current_date_str}_evening"
        if now.hour == 18 and evening_key not in sent_today:
            print(f"[{current_time_str}] Стартиране на вечерен радар...")
            lead_scraper.run_scan()
            send_digest_now("Вечерен електро бюлетин")
            sent_today.add(evening_key)

        # Every 15 minutes, run background scan
        if now.minute % 15 == 0 and now.second < 30:
            print(f"[{current_time_str}] Автоматичен радар (на всеки 15 минути)...")
            lead_scraper.run_scan()

        time.sleep(30)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--now", action="store_true", help="Send digest immediately to test")
    args = parser.parse_args()

    if args.now:
        send_digest_now("Електро бюлетин (Прецизно филтриран)")
    else:
        run_schedule()
