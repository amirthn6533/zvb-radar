"""
ZVB Interactive Telegram Bot Service (24/7)
Handles:
1. User commands & Interactive Inline Buttons (/scan, /urgent, /builders, /designers, /stats)
2. Real-time search for keywords in Sofia (e.g. "младост", "табло", "камери")
3. Background 15-minute auto-scan across Bazar, Alo, and MaistorPlus
4. 09:00 & 18:00 Executive Daily Digests sent to the ZVB Group
"""

import os
import sys
import time
import json
import threading
import datetime
import requests
import urllib.parse
import re

import lead_scraper
import daily_digest
import sofia_b2b_extractor

sys.stdout.reconfigure(encoding='utf-8')

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
LEADS_JSON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leads.json")
B2B_CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sofia_b2b_partners.csv")

def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def send_msg(token, chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        r = requests.post(url, json=payload, timeout=12)
        return r.json()
    except Exception as e:
        print(f"Error sending msg: {e}")
        return None

def answer_callback(token, callback_query_id):
    try:
        requests.post(f"https://api.telegram.org/bot{token}/answerCallbackQuery", json={"callback_query_id": callback_query_id}, timeout=6)
    except Exception:
        pass

def get_main_keyboard():
    return {
        "inline_keyboard": [
            [
                {"text": "⚡ Спешни електро проекти", "callback_data": "cmd_urgent"},
                {"text": "🔍 Сканирай сега (Live)", "callback_data": "cmd_scan"}
            ],
            [
                {"text": "💰 Калкулатор за цени & оферти", "callback_data": "cmd_calc"},
                {"text": "📋 Готови оферти (B2B)", "callback_data": "cmd_pitches"}
            ],
            [
                {"text": "🏗️ Строителни компании (КСБ)", "callback_data": "cmd_builders"},
                {"text": "💎 Интериорни дизайнери", "callback_data": "cmd_designers"}
            ],
            [
                {"text": "📊 Статистика на базата", "callback_data": "cmd_stats"}
            ]
        ]
    }

def get_welcome_text():
    return (
        "⚡ <b>ZVB Интерактивен Асистент (София)</b> ⚡\n\n"
        "درود! من زاگرس، دستیار هوشمند تیم مهندسی <b>ZVB</b> هستم.\n"
        "برای صحبت با من کافیست کلمه <b>«زاگرس»</b> را در پیام خود بیاورید، یا از دکمه‌های زیر استفاده کنید.\n\n"
        "👇 <b>امکانات ویژه:</b>\n"
        "• ⚡ مشاهده پروژه‌های فوری کارفرمایان برق\n"
        "• 💰 <b>محاسبه پیش‌فاکتور رسمی:</b> بنویسید <i>'زاگرس قیمت: آپارتمان ۸۰ متری، تابلو برق، ۳۰ پریز، ۴ دوربین'</i>\n"
        "• 🔍 جستجوی محله یا زمینه (مثلاً <i>'زاگرس младост'</i> или <i>'زاگرس табло'</i>)"
    )

def handle_urgent_cmd():
    if not os.path.exists(LEADS_JSON_PATH):
        return "Няма заредени данни."
    with open(LEADS_JSON_PATH, "r", encoding="utf-8") as f:
        leads = json.load(f)
    
    valid = [l for l in leads.values() if daily_digest.is_strictly_electrical_sofia(l)]
    urgent = [l for l in valid if any(w in l.get('title', '').lower() for w in ['търся', 'търси', 'търсим', 'спешно', 'вентилатор', 'монтаж', 'смяна', 'подмяна', 'контакт'])]
    
    # Sort leads: phone numbers first, then newest
    urgent.sort(key=lambda x: (1 if x.get('phone') else 0, x.get('found_at', '')), reverse=True)
    
    if not urgent:
        return "В момента няма спешни запитвания в София. Всичко е прегледано!"
    
    msg = "🎯 <b>ТОП ЕЛЕКТРО ПРОЕКТИ И ЗАПИТВАНИЯ (София):</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
    for idx, l in enumerate(urgent[:5], 1):
        phone = l.get('phone')
        phone_block = ""
        action_links = []
        if phone:
            phone_block = f"\n📞 Телефон: <b>{phone}</b>"
            if phone.startswith("08") and len(phone) == 10:
                intl = "359" + phone[1:]
                wa_txt = urllib.parse.quote("Здравейте! Пиша Ви от ZVB (Електроуслуги & Умен дом, София) относно Вашия проект. https://zvb.bg")
                action_links.append(f"<a href='https://wa.me/{intl}?text={wa_txt}'>💬 WhatsApp</a>")
                action_links.append(f"<a href='tel:+{intl}'>📞 Обади се</a>")
        action_links.append(f"<a href='{l.get('url')}'>🔗 Виж обявата</a>")
        actions_str = " | ".join(action_links)
        
        msg += f"{idx}. <b>{l.get('title')[:65]}</b>{phone_block}\n🌐 {l.get('source')} ➔ {actions_str}\n\n"
    msg += "💡 <i>Кликнете върху WhatsApp или Обади се за директна връзка!</i>"
    return msg

def handle_builders_cmd():
    builders = [p for p in sofia_b2b_extractor.fetch_ksb_builders(max_count=6)]
    if not builders:
        return "Не можаха да се заредят строителни фирми от КСБ."
    
    msg = "🏗️ <b>ВОДЕЩИ СТРОИТЕЛНИ КОМПАНИИ В СОФИЯ (КСБ):</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
    for idx, b in enumerate(builders[:5], 1):
        msg += (
            f"{idx}. <b>{b.get('name')}</b>\n"
            f"📍 {b.get('location')} | {b.get('specialty')}\n"
            f"🔗 <a href='{b.get('website')}'>Виж профила в КСБ</a>\n\n"
        )
    msg += "💡 <i>Копирайте офертата за строител и се свържете с техния технически ръководител!</i>"
    return msg

def handle_designers_cmd():
    studios = sofia_b2b_extractor.TOP_INTERIOR_STUDIOS[:5]
    msg = "💎 <b>ТОП ИНТЕРИОРНИ СТУДИА В СОФИЯ (За осветление & Smart Home):</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
    for idx, s in enumerate(studios, 1):
        msg += (
            f"{idx}. <b>{s.get('name')}</b>\n"
            f"📍 {s.get('location')} | Управител: {s.get('manager')}\n"
            f"📞 {s.get('phone')} | ✉️ {s.get('email')}\n"
            f"💡 {s.get('specialty')}\n"
            f"🌐 <a href='{s.get('website')}'>Уебсайт</a>\n\n"
        )
    msg += "💡 <i>Изпратете им портфолиото на ZVB за дизайнерско LED осветление и умен дом!</i>"
    return msg

def handle_stats_cmd():
    if not os.path.exists(LEADS_JSON_PATH):
        return "Няма данни."
    with open(LEADS_JSON_PATH, "r", encoding="utf-8") as f:
        leads = json.load(f)
    total = len(leads)
    sofia_valid = sum(1 for l in leads.values() if daily_digest.is_strictly_electrical_sofia(l))
    with_phone = sum(1 for l in leads.values() if l.get('phone'))
    
    return (
        f"📊 <b>СТАТИСТИКА НА ZVB РАДАРА:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"• Общо регистрирани обяви: <b>{total}</b>\n"
        f"• Прецизни електро обекти в София: <b>{sofia_valid}</b>\n"
        f"• Обяви с директен телефон: <b>{with_phone}</b>\n"
        f"• Източници: <b>Bazar.bg, Alo.bg, MaistorPlus.com, KSB.bg</b>\n"
        f"• Период на авто-сканиране: <b>на всеки 15 минути</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🌐 <i>ZVB | Електрически и умни системи</i>"
    )

def handle_calc_cmd(query=""):
    """
    Smart Electrical Quotation & Price Calculator for Sofia market.
    Calculates labor and estimated materials based on input parameters.
    """
    q = query.lower()
    # Normalize Persian / Arabic digits to English digits
    persian_digits = {'۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4', '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9'}
    for p_d, e_d in persian_digits.items():
        q = q.replace(p_d, e_d)
    
    # If user just asks for calculator guide/price list
    trigger_words = ['метър', 'кв.м', 'кв', 'm2', 'табло', 'контакт', 'камер', 'точка', 'апартамент', 'бойлер', 'متر', 'تابلو', 'پریز', 'کلید', 'دوربین', 'آپارتمان']
    if not any(k in q for k in trigger_words):
        return (
            "💰 <b>ZVB СМАРТ КАЛКУЛАТОР ЗА ОФЕРТИ (Ценоразпис София):</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "📌 <b>Ориентировъчни цени за труд (ZVB Sofia):</b>\n"
            "• Изграждане на ел. инсталация: <b>25 - 35 лв./кв.м</b> (€13 - €18)\n"
            "• Смяна/монтаж на апартаментно ел. табло (до 12 предпазителя): <b>140 - 180 лв.</b> (€70 - €90)\n"
            "• Изтегляне на нов токов кръг (кабел): <b>4 - 6 лв./л.м.</b> (€2 - €3)\n"
            "• Монтаж на контакт / ключ / розетка: <b>8 - 12 лв./бр.</b> (€4 - €6)\n"
            "• Монтаж на осветително тяло / плафон / полилей: <b>20 - 35 лв./бр.</b> (€10 - €18)\n"
            "• Монтаж на скрито LED осветление с профил: <b>18 - 25 лв./л.м.</b> (€9 - €13)\n"
            "• Монтаж и настройка на охранителна IP камера: <b>60 - 90 лв./бр.</b> (€30 - €45)\n"
            "• Свързване на бойлер / електроуред: <b>50 - 70 лв./бр.</b> (€25 - €35)\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💡 <b>نحوه استعلام قیمت هوشمند:</b>\n"
            "کافیست در گروه بنویسید:\n"
            "<code>زاگرس قیمت: آپارتمان ۸۰ متری، تابلو برق، ۳۰ پریز، ۴ دوربین</code>\n"
            "تا پیش‌فاکتور رسمی تفکیک‌شده به زبان بلغاری برای مشتری تولید شود!"
        )

    # Parse parameters
    area = 0
    m_area = re.search(r'(\d+)\s*(?:кв|кв\.м|мет|m2|متر)', q)
    if m_area:
        area = int(m_area.group(1))

    sockets = 0
    m_sock = re.search(r'(\d+)\s*(?:контакт|прериз|پریز|کلید|ключ)', q)
    if m_sock:
        sockets = int(m_sock.group(1))

    cameras = 0
    m_cam = re.search(r'(\d+)\s*(?:камер|دوربین)', q)
    if m_cam:
        cameras = int(m_cam.group(1))

    has_board = any(w in q for w in ['табло', 'تابلو'])
    has_led = any(w in q for w in ['led', 'лед', 'осветлен', 'نور'])

    # Calculation
    labor_bgn = 0
    breakdown = []

    if area > 0:
        area_labor = area * 30
        labor_bgn += area_labor
        breakdown.append(f"• Цялостна ел. инсталация ({area} кв.м): <b>{area_labor} лв.</b> (€{round(area_labor/1.95583)})")
    
    if has_board:
        labor_bgn += 160
        breakdown.append("• Асемблиране и монтаж на ново ел. табло: <b>160 лв.</b> (€82)")
        
    if sockets > 0:
        sock_labor = sockets * 10
        labor_bgn += sock_labor
        breakdown.append(f"• Монтаж на ключове и контакти ({sockets} бр.): <b>{sock_labor} лв.</b> (€{round(sock_labor/1.95583)})")
        
    if cameras > 0:
        cam_labor = cameras * 70
        labor_bgn += cam_labor
        breakdown.append(f"• Монтаж и конфигурация на камери ({cameras} бр.): <b>{cam_labor} лв.</b> (€{round(cam_labor/1.95583)})")

    if has_led:
        labor_bgn += 180
        breakdown.append("• Монтаж на дизайнерско LED осветление: <b>180 лв.</b> (€92)")

    if labor_bgn == 0:
        labor_bgn = 150
        breakdown.append("• Стандартен електро монтаж и диагностика: <b>150 лв.</b> (€77)")

    materials_bgn = round(labor_bgn * 0.45)
    total_bgn = labor_bgn + materials_bgn
    total_eur = round(total_bgn / 1.95583)

    quote_msg = (
        "📑 <b>ОФИЦИАЛНА ОФЕРТА / ZVB ELECTRICAL SYSTEMS (София)</b>\n"
        f"📅 <i>Дата: {datetime.datetime.now().strftime('%d.%m.%Y')} г. | Валидност: 14 дни</i>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📋 <b>ОПИСАНИЕ НА ДЕЙНОСТИТЕ:</b>\n"
        + "\n".join(breakdown) + "\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🛠️ Труд: <b>{labor_bgn} лв.</b>\n"
        f"📦 Ориентировъчни материали: <b>~{materials_bgn} лв.</b>\n"
        f"💎 <b>ОБЩА СТОЙНОСТ: ~{total_bgn} лв. (~€{total_eur})</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "✅ <i>Включва: БЕЗПЛАТЕН оглед на място в София, издаване на протокол и гаранция 5 години.</i>\n\n"
        "📞 <b>Контакт за потвърждение:</b>\n"
        "Инж. екип ZVB: <b>+359 87 7944353</b> | 🌐 <a href='https://zvb.bg'>zvb.bg</a>\n"
        "<i>(Можете директно да копирате и препратите този текст на клиента!)</i>"
    )
    return quote_msg

def handle_pitches_cmd():
    return (
        "📋 <b>ГОТОВИ ТЕКСТОВЕ ЗА БЪРЗ КОНТАКТ:</b>\n\n"
        "<b>1️⃣ За Строителни фирми:</b>\n"
        "<code>Здравейте! Пишем Ви от ZVB (Електрически и умни системи, София). Предлагаме професионално подизпълнение на ел. инсталации, табла и видеонаблюдение с 15г. опит. Работим стриктно по проект и в срок. Тел: +359 87 7944353 | https://zvb.bg</code>\n\n"
        "<b>2️⃣ За Интериорни дизайнери:</b>\n"
        "<code>Здравейте! От ZVB (София) предлагаме прецизна техническа реализация на дизайнерско осветление, скрито LED и Умен Дом (Smart Home). Перфектна естетика без компромиси. Контакт: +359 87 7944353 | https://zvb.bg</code>\n\n"
        "<i>(Кликнете върху текста за автоматично копиране!)</i>"
    )

def handle_search_text(query):
    if not os.path.exists(LEADS_JSON_PATH):
        return "Няма данни за търсене."
    with open(LEADS_JSON_PATH, "r", encoding="utf-8") as f:
        leads = json.load(f)
    
    q = query.lower()
    matches = []
    for l in leads.values():
        if not daily_digest.is_strictly_electrical_sofia(l):
            continue
        text = (l.get('title', '') + ' ' + l.get('keyword', '') + ' ' + l.get('location', '')).lower()
        if q in text:
            matches.append(l)
    
    if not matches:
        return f"🔍 Не бяха намерени електро обекти за: '<b>{query}</b>' в София."
    
    msg = f"🔍 <b>Резултати за '{query}' в София ({len(matches)} намерени):</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
    for idx, l in enumerate(matches[:5], 1):
        phone = f"\n📞 Телефон: <b>{l.get('phone')}</b>" if l.get('phone') else ""
        msg += f"{idx}. <b>{l.get('title')[:65]}</b>{phone}\n🔗 <a href='{l.get('url')}'>Отвори обявата</a>\n\n"
    return msg

def background_scheduler(token, chat_id):
    """Runs in background: auto-scans every 15 minutes and sends 09:00/18:00 digests"""
    print("⏰ Background scheduler started: 15-min scans & 09:00 / 18:00 digests...")
    sent_today = set()
    
    while True:
        try:
            now = datetime.datetime.now()
            current_date_str = now.strftime("%Y-%m-%d")
            
            # Morning Digest at 09:00
            morning_key = f"{current_date_str}_morning"
            if now.hour == 9 and morning_key not in sent_today:
                lead_scraper.run_scan()
                daily_digest.send_digest_now("Сутрешен електро бюлетин")
                sent_today.add(morning_key)

            # Evening Digest at 18:00
            evening_key = f"{current_date_str}_evening"
            if now.hour == 18 and evening_key not in sent_today:
                lead_scraper.run_scan()
                daily_digest.send_digest_now("Вечерен електро бюлетин")
                sent_today.add(evening_key)

            # Every 15 minutes, auto-scan
            if now.minute % 15 == 0 and now.second < 30:
                print(f"[{now.strftime('%H:%M')}] Автоматичен 15-минутен скан...")
                lead_scraper.run_scan()

        except Exception as e:
            print(f"Scheduler error: {e}")
            
        time.sleep(30)

def run_telegram_bot():
    cfg = load_config()
    token = cfg.get("telegram", {}).get("bot_token")
    group_chat_id = cfg.get("telegram", {}).get("chat_id")
    
    if not token:
        print("❌ Bot token missing!")
        return

    print("=" * 60)
    print("🚀 ZVB Interactive Telegram Bot Service Running...")
    print(f"Connected to Group ID: {group_chat_id}")
    print("Listening for messages & commands 24/7...")
    print("=" * 60)

    # Start background scheduler thread
    if group_chat_id:
        t = threading.Thread(target=background_scheduler, args=(token, group_chat_id), daemon=True)
        t.start()

    offset = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{token}/getUpdates?offset={offset}&timeout=25"
            r = requests.get(url, timeout=30)
            data = r.json()
            
            if not data.get("ok"):
                time.sleep(2)
                continue

            for update in data.get("result", []):
                offset = update["update_id"] + 1
                
                # 1. Handle Callback Query (Buttons)
                if "callback_query" in update:
                    cb = update["callback_query"]
                    cb_id = cb["id"]
                    cb_data = cb.get("data", "")
                    sender_chat_id = cb["message"]["chat"]["id"]
                    
                    answer_callback(token, cb_id)
                    
                    if cb_data == "cmd_urgent":
                        text = handle_urgent_cmd()
                        send_msg(token, sender_chat_id, text, get_main_keyboard())
                    elif cb_data == "cmd_scan":
                        send_msg(token, sender_chat_id, "⏳ <i>Стартирано е сканиране на живо в Bazar.bg, Alo.bg и MaistorPlus... Моля, изчакайте چند ثانیه...</i>")
                        lead_scraper.run_scan()
                        text = handle_urgent_cmd()
                        send_msg(token, sender_chat_id, f"✅ <b>Сканирането завърши успешно!</b>\n\n{text}", get_main_keyboard())
                    elif cb_data == "cmd_builders":
                        text = handle_builders_cmd()
                        send_msg(token, sender_chat_id, text, get_main_keyboard())
                    elif cb_data == "cmd_designers":
                        text = handle_designers_cmd()
                        send_msg(token, sender_chat_id, text, get_main_keyboard())
                    elif cb_data == "cmd_stats":
                        text = handle_stats_cmd()
                        send_msg(token, sender_chat_id, text, get_main_keyboard())
                    elif cb_data == "cmd_calc":
                        text = handle_calc_cmd()
                        send_msg(token, sender_chat_id, text, get_main_keyboard())
                    elif cb_data == "cmd_pitches":
                        text = handle_pitches_cmd()
                        send_msg(token, sender_chat_id, text, get_main_keyboard())

                # 2. Handle Text Messages & Commands
                elif "message" in update:
                    msg = update["message"]
                    sender_chat_id = msg["chat"]["id"]
                    raw_text = msg.get("text", "").strip()
                    
                    if not raw_text:
                        continue
                    
                    lower_text = raw_text.lower()
                    
                    # Check if addressed as "زاگرس" (Zagros) or starts with / command
                    is_command = raw_text.startswith("/")
                    is_zagros = any(lower_text.startswith(w) or lower_text.startswith(f"{w} ") or lower_text.startswith(f"{w}،") or lower_text.startswith(f"{w}:") for w in ["زاگرس", "zagros"])
                    
                    # If it's a private chat (DM with bot), respond directly.
                    # In groups, ONLY respond if called "زاگرس" or if it's a slash command!
                    is_private = msg.get("chat", {}).get("type") == "private"
                    
                    if not (is_command or is_zagros or is_private):
                        # Ignore normal chat messages in group
                        continue
                    
                    # Clean the query if it started with "زاگرس"
                    clean_query = raw_text
                    if is_zagros:
                        for w in ["زاگرس", "zagros"]:
                            if lower_text.startswith(w):
                                clean_query = raw_text[len(w):].strip().lstrip("،,:! ")
                                break
                    
                    if not clean_query or clean_query in ["سلام", "درود", "منو", "menu", "help", "کمک"]:
                        send_msg(token, sender_chat_id, "درود! در خدمتم. می‌توانید بفرمایید چه کاری انجام دهم:\n\n" + get_welcome_text(), get_main_keyboard())
                    elif any(k in clean_query.lower() for k in ["قیمت", "پیش فاکتور", "پیش‌فاکتور", "فاکتور", "محاسبه", "کالکولاتور", "ценоразпис", "оферта", "цена"]):
                        send_msg(token, sender_chat_id, handle_calc_cmd(clean_query), get_main_keyboard())
                    elif any(k in clean_query.lower() for k in ["اسکن", "scan", "بروزرسانی", "جستجو کن", "بگرد", "اسکن کن"]):
                        send_msg(token, sender_chat_id, "⏳ <i>در حال اسکن زنده سایت‌ها برای پروژه‌های جدید برقی...</i>")
                        lead_scraper.run_scan()
                        text = handle_urgent_cmd()
                        send_msg(token, sender_chat_id, f"✅ <b>اسکن انجام شد!</b>\n\n{text}", get_main_keyboard())
                    elif any(k in clean_query.lower() for k in ["فوری", "urgent", "پروژه", "پروژه‌ها", "مشتری", "کارفرما"]):
                        send_msg(token, sender_chat_id, handle_urgent_cmd(), get_main_keyboard())
                    elif any(k in clean_query.lower() for k in ["سازنده", "سازندگان", "شرکت ساختمانی", "builders", "ксб"]):
                        send_msg(token, sender_chat_id, handle_builders_cmd(), get_main_keyboard())
                    elif any(k in clean_query.lower() for k in ["طراح", "دیزاینر", "معمار", "طراحان", "designers"]):
                        send_msg(token, sender_chat_id, handle_designers_cmd(), get_main_keyboard())
                    elif any(k in clean_query.lower() for k in ["آمار", "وضعیت", "stats"]):
                        send_msg(token, sender_chat_id, handle_stats_cmd(), get_main_keyboard())
                    elif any(k in clean_query.lower() for k in ["پیشنهاد", "متن پیام", "پیچ", "pitches", "آفر"]):
                        send_msg(token, sender_chat_id, handle_pitches_cmd(), get_main_keyboard())
                    elif clean_query.startswith("/start") or clean_query.startswith("/help"):
                        send_msg(token, sender_chat_id, get_welcome_text(), get_main_keyboard())
                    elif clean_query.startswith("/calc"):
                        send_msg(token, sender_chat_id, handle_calc_cmd(clean_query), get_main_keyboard())
                    elif clean_query.startswith("/scan"):
                        send_msg(token, sender_chat_id, "⏳ <i>Стартирано е сканиране на живо...</i>")
                        lead_scraper.run_scan()
                        send_msg(token, sender_chat_id, "✅ <b>Сканирането завърши!</b>", get_main_keyboard())
                    elif clean_query.startswith("/urgent"):
                        send_msg(token, sender_chat_id, handle_urgent_cmd(), get_main_keyboard())
                    elif clean_query.startswith("/builders"):
                        send_msg(token, sender_chat_id, handle_builders_cmd(), get_main_keyboard())
                    elif clean_query.startswith("/designers"):
                        send_msg(token, sender_chat_id, handle_designers_cmd(), get_main_keyboard())
                    elif clean_query.startswith("/stats"):
                        send_msg(token, sender_chat_id, handle_stats_cmd(), get_main_keyboard())
                    else:
                        # Perform keyword search in Sofia electrical database
                        res = handle_search_text(clean_query)
                        send_msg(token, sender_chat_id, res, get_main_keyboard())

        except Exception as e:
            print(f"Bot polling error: {e}")
            time.sleep(3)

if __name__ == "__main__":
    run_telegram_bot()
