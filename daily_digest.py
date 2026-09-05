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

sys.stdout.reconfigure(encoding='utf-8')

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
LEADS_JSON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leads.json")

# Strict Filters for Real Client Demand in Sofia
EXCLUDE_WORDS = [
    # 1. Competitor electrician service ads (خدمات‌دهندگان و همکاران)
    'електроуслуги', 'електро услуги', 'ел. услуги', 'ел услуги', 'електромонтажни',
    'предлагам', 'предлагаме', 'извършвам', 'извършваме', 'услуги по',
    'електротехник предлага', 'ел техник предлага', 'майстор предлага', 'бригада предлага', 'фирма предлага',
    'професионален електротехник', 'квалифициран електротехник', 'опитен електротехник', 'майстор електротехник',
    'направа и ремонт на ел', 'ремонт и направа на ел', 'изграждане и ремонт на ел',
    'денонощен', 'денонощни', 'авариен', 'аварийни', '24/7',
    'цени по договаряне', 'ниски цени', 'конкурентни цени', 'гарантирано качество',
    'всички видове ел', 'всякакви ел', 'всички видове електро',
    
    # 2. Hardware / E-commerce sales (فروش کالا، دوربین و وسایل دست‌دوم)
    'продавам', 'продава се', 'продава', 'чисто нов', 'чисто нови', 'не монтирани',
    'неразпечатан', 'комплект за видеонаблюдение', 'в кутия', 'доставка с',
    'еконт', 'спиди', 'на склад', 'гаранция 24', 'гаранция 12', 'конектор', 'тестер', 'вакуум', 'стойка за камера',
    
    # 3. Job seekers / Salaried employment (کارجویان و آگهی‌های استخدام شرکتی)
    'търся работа', 'търси работа', 'търсим работа', 'търси служител',
    'търси електротехник, промишлен', 'търси електротехник, строителен',
    'набира персонал', 'набира работници', 'желана длъжност',
    'автобиография', 'cv', 'за германия', 'чужбина', 'холандия', 'англия',
    'курс', 'курсове', 'обучение', 'училище', 'книга', 'учебник', 'дистанционно',
    
    # 4. General non-electrical exclusions
    'покрив', 'покриви', 'керемиди', 'улуци', 'хидроизолация',
    'до ключ', 'от основи до ключ', 'парапет', 'решетка', 'ограда', 'заваряване',
    'парцел', 'парцели', 'под наем', 'дава под наем', 'наем',
    'плочки', 'лепене на плочки', 'отпушване', 'дограма', 'кърти чисти',
    'хладилник', 'фризер', 'готварска печка', 'пералня',
    'бушонно табло опел', 'части', 'ремарке', 'трабант', 'кемпер', 'мултиметър', 'микрометър',
    'honda', 'opel', 'bmw', 'mercedes', 'toyota', 'audi', 'лампа за кола', 'протектор', 'фолио', 'ит експерт',
    'хладилни камери', 'задно виждане', 'авто камери', 'екшън камери', 'gopro',
    'имот', 'имоти', 'двор', 'кв.м', 'рзп', 'табела',
    
    # 5. Stale date indicators in classified titles
    '2024', '2025', ' януари', ' февруари', ' март', ' април', ' май', ' юни', ' юли'
]

SOFIA_AREAS = [
    'софия', 'sofia', 'младост', 'люлин', 'лозенец', 'витоша', 'бояна', 'драгалевци',
    'надежда', 'център', 'манастирски ливади', 'овча купеل', 'гео милев', 'изток',
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
    'домофон', 'соларни панели', 'фотоволтаиц', 'слаботоков', 'вентилатор', 'бойлер'
]

# Blacklisted phone numbers (e.g. platform customer support lines, NOT clients!)
BLACKLISTED_PHONES = ['0879590810', '359879590810', '+359879590810']

def is_strictly_electrical_sofia(l):
    title = l.get('title', '').lower()
    loc = l.get('location', '').lower()
    source = l.get('source', '')
    full = f"{title} {loc}".lower()
    
    # 0. Clean support phone numbers
    phone = l.get('phone', '')
    if any(bp in phone for bp in BLACKLISTED_PHONES):
        l['phone'] = ''
        phone = ''
        
    # 1. Reject competitor ads, sellers, job seekers
    if any(ex in title or ex in full for ex in EXCLUDE_WORDS):
        return False
        
    # 2. Exclude other cities
    if any(city in full for city in OTHER_CITIES) and 'софия' not in title:
        return False

    # 3. Check Sofia location strictly
    if not any(area in full for area in SOFIA_AREAS):
        return False
        
    # 4. Source specific intent verification:
    if source == 'MaistorPlus':
        # In MaistorPlus, all jobs are real clients! Must have electrical relevance
        mp_electrical = ['контакт', 'вентилатор', 'ел', 'електро', 'осветление', 'табло', 'бойлер', 'кабел', 'ключ']
        return any(w in title for w in mp_electrical)

    # For Classifieds (Bazar / Alo): Must have explicit client demand intent!
    # Real clients ask "Търся майстор за...", "Търси се ел...", "Търсим подизпълнител..."
    client_intent_words = [
        'търся', 'търси се', 'търсим', 'нуждая се', 'нужен е', 'трябва ми',
        'смяна на', 'монтаж на', 'подмяна на', 'ремонт на ел', 'изграждане на'
    ]
    if not any(w in title for w in client_intent_words):
        return False
        
    # 5. Must have electrical core
    has_electrical = any(el in title for el in ELECTRICAL_MUST_HAVE)
    return has_electrical

def is_fresh_lead(l, max_days=3):
    """Checks if lead was found within the last N days (defaults to 3 days = 72 hours)"""
    found_at = l.get('found_at', '')
    if not found_at:
        return True
    try:
        lead_time = datetime.datetime.strptime(found_at, "%Y-%m-%d %H:%M")
        now = datetime.datetime.now()
        diff_days = (now - lead_time).total_seconds() / 86400
        return diff_days <= max_days
    except Exception:
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
    
    # Apply strict electrical Sofia filtering & freshness check (last 3 days)
    valid_leads = [l for l in leads_list if is_strictly_electrical_sofia(l) and is_fresh_lead(l, max_days=4)]
    
    # Sort strictly by newest first
    valid_leads.sort(key=lambda x: (1 if x.get('phone') else 0, x.get('found_at', '')), reverse=True)

    now_str = datetime.datetime.now().strftime("%d.%m.%Y | %H:%M") + " ч."
    header_icon = "🌅" if "сутрин" in period_name.lower() or "утрин" in period_name.lower() else "🌆"

    msg = f"{header_icon} <b>ZVB Електро Радар: {period_name}</b>\n"
    msg += f"📅 <i>{now_str} (Само гр. София)</i>\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━\n\n"

    if not valid_leads:
        msg += "✅ <b>Няма нови необработени клиентски заявки в София за последните 48 часа.</b>\n"
        msg += "Всички актуални обекти са прегледани. Радарът сканира денонощно на всеки 15 минути за нови запитвания!\n\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n"
        msg += "🌐 <b>ZVB Sofia</b> | <a href='https://zvb.bg'>zvb.bg</a>"
        return msg

    # Group into Categories
    urgent_leads = [l for l in valid_leads if l.get('source') == 'MaistorPlus' or any(w in l.get('title', '').lower() for w in ['търся', 'търси', 'търсим', 'спешно', 'вентилатор', 'монтаж', 'смяна', 'контакт', 'бойлер'])]
    cctv_smart_leads = [l for l in valid_leads if l not in urgent_leads and any(w in l.get('title', '').lower() for w in ['камери', 'видеонаблюдение', 'умен дом', 'смарт', 'домофон'])]
    contractor_leads = [l for l in valid_leads if l not in urgent_leads and l not in cctv_smart_leads]

    # 1. Urgent direct requests (Clients looking for electrician)
    if urgent_leads:
        msg += "⚡ <b>ДИРЕКТНИ ЗАПИТВАНИЯ ЗА ЕЛЕКТРОТЕХНИК:</b>\n"
        for idx, l in enumerate(urgent_leads[:5], 1):
            phone = l.get('phone')
            phone_part = ""
            action_links = []
            if phone and phone.startswith("08") and len(phone) == 10:
                phone_part = f"\n   📞 Телефон: <b>{phone}</b>"
                intl = "359" + phone[1:]
                wa_txt = urllib.parse.quote("Здравейте! Пиша Ви от ZVB (Електроуслуги, София) относно Вашия проект. https://zvb.bg")
                action_links.append(f"<a href='https://wa.me/{intl}?text={wa_txt}'>💬 WhatsApp</a>")
                action_links.append(f"<a href='tel:+{intl}'>📞 Обади се</a>")
            
            link_label = "📋 Кандидатствай в MaistorPlus" if l.get('source') == 'MaistorPlus' else "🔗 Виж обявата"
            action_links.append(f"<a href='{l.get('url')}'>{link_label}</a>")
            actions_str = " | ".join(action_links)
            msg += f"{idx}. <b>{l.get('title')[:65]}</b>{phone_part}\n   👉 {actions_str}\n\n"

    # 2. CCTV & Smart home
    if cctv_smart_leads:
        msg += "📹 <b>ВИДЕОНАБЛЮДЕНИЕ И УМЕН ДОМ:</b>\n"
        for idx, l in enumerate(cctv_smart_leads[:3], 1):
            phone = l.get('phone')
            phone_part = ""
            action_links = []
            if phone and phone.startswith("08") and len(phone) == 10:
                phone_part = f"\n   📞 Телефон: <b>{phone}</b>"
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
            if phone and phone.startswith("08") and len(phone) == 10:
                phone_part = f"\n   📞 Телефон: <b>{phone}</b>"
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
    import lead_scraper
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
