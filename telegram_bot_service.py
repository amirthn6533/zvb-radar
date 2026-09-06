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
import pdf_offer_generator
import candidate_manager

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
                {"text": "💰 Калкулатор за оферти", "callback_data": "cmd_calc"},
                {"text": "🧠 Загрос AI Експерт", "callback_data": "cmd_ai"}
            ],
            [
                {"text": "📋 Готови оферти (B2B)", "callback_data": "cmd_pitches"},
                {"text": "📊 Статистика на базата", "callback_data": "cmd_stats"}
            ],
            [
                {"text": "🏗️ Строителни фирми (КСБ)", "callback_data": "cmd_builders"},
                {"text": "💎 Интериорни дизайнери", "callback_data": "cmd_designers"}
            ],
            [
                {"text": "📱 شکار پروژه‌های فیسبوک", "callback_data": "cmd_fb"},
                {"text": "📑 صدور پیش‌فاکتور رسمی (PDF)", "callback_data": "cmd_pdf"}
            ],
            [
                {"text": "👥 مدیریت برق‌کارها (کاندیداها)", "callback_data": "cmd_candidates"}
            ]
        ]
    }

def get_ai_keyboard():
    return {
        "inline_keyboard": [
            [
                {"text": "⚡ سایز کابل و فیوزها", "callback_data": "ai_cables"},
                {"text": "🏢 پیام به بسازبفروش", "callback_data": "ai_builder"}
            ],
            [
                {"text": "📹 دوربین و شبکه", "callback_data": "ai_cctv"},
                {"text": "🎨 پیام به دیزاینر", "callback_data": "ai_designer"}
            ],
            [
                {"text": "🏠 خانه هوشمند (Shelly)", "callback_data": "ai_smarthome"},
                {"text": "📩 پیام پیگیری کارفرما", "callback_data": "ai_followup"}
            ],
            [
                {"text": "🔙 بازگشت به منوی اصلی", "callback_data": "cmd_main_menu"}
            ]
        ]
    }

def get_welcome_text():
    return (
        "⚡ <b>ZVB Интерактивен Асистент (София)</b> ⚡\n\n"
        "درود! من زاگرس، دستیار هوشمند و مشاور مهندسی <b>ZVB</b> هستم.\n"
        "برای گفتگو با من کافیست نام <b>«زاگرس»</b> را در ابتدای پیامتان بیاورید، یا از دکمه‌های زیر استفاده کنید.\n\n"
        "👇 <b>امکانات کلیدی:</b>\n"
        "• 🧠 <b>هوش مصنوعی مهندسی:</b> 'زاگرس کابل مناسب برای کولر چیه؟' یا 'زاگرس پیام پیگیری مشتری'\n"
        "• 📑 <b>صدور پیش‌فاکتور رسمی PDF:</b> 'زاگرس فاکتور: آپارتمان ۸۰ متری، تعویض تابلو، ۳۰ پریز'\n"
        "• 👥 <b>بانک کاندیداهای برق‌کار:</b> 'زاگرس اضافه کن: ایوان، 0888123456، مهارت تابلو'\n"
        "• 📱 <b>شکار پروژه‌های فیسبوک:</b> ارسال متن پست با دکمه یا /fb برای آفر انفجاری بلغاری\n"
        "• ⚡ <b>پروژه‌های فوری (MaistorPlus & Daibau):</b> آخرین مناقصه‌ها و پروژه‌های برق در صوفیه\n"
        "• 🔍 <b>جستجوی محله/تجهیزات:</b> 'زاگرس младост' یا 'زاگرس камери'"
    )

def handle_urgent_cmd():
    if not os.path.exists(LEADS_JSON_PATH):
        return "Няма заредени данни."
    with open(LEADS_JSON_PATH, "r", encoding="utf-8") as f:
        leads = json.load(f)
    
    valid = [l for l in leads.values() if daily_digest.is_strictly_electrical_sofia(l) and daily_digest.is_fresh_lead(l, max_days=4)]
    
    # Sort leads: phone numbers first, then newest
    valid.sort(key=lambda x: (1 if x.get('phone') else 0, x.get('found_at', '')), reverse=True)
    
    if not valid:
        return "✅ <b>Няма нови необработени клиентски запитвания в София за последните 48 часа.</b>\nВсички обяви са прегледани. Натиснете <i>'🔍 Сканирай сега'</i> за сканиране на живо!"
    
    msg = "🎯 <b>ТОП ЕЛЕКТРО ПРОЕКТИ И ЗАПИТВАНИЯ (София):</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
    for idx, l in enumerate(valid[:5], 1):
        phone = l.get('phone')
        phone_block = ""
        action_links = []
        if phone and phone.startswith("08") and len(phone) == 10:
            phone_block = f"\n📞 Телефон: <b>{phone}</b>"
            intl = "359" + phone[1:]
            wa_txt = urllib.parse.quote("Здравейте! Пиша Ви от ZVB (Електроуслуги & Умен дом, София) относно Вашия проект. https://zvb.bg")
            action_links.append(f"<a href='https://wa.me/{intl}?text={wa_txt}'>💬 WhatsApp</a>")
            action_links.append(f"<a href='tel:+{intl}'>📞 Обади се</a>")
            
        link_label = "📋 Кандидатствай в MaistorPlus" if l.get('source') == 'MaistorPlus' else "🔗 Виж обявата"
        action_links.append(f"<a href='{l.get('url')}'>{link_label}</a>")
        actions_str = " | ".join(action_links)
        
        msg += f"{idx}. <b>{l.get('title')[:65]}</b>{phone_block}\n🌐 {l.get('source')} ➔ {actions_str}\n\n"
    msg += "💡 <i>Прецизно филтрирани клиентски проекти за ZVB Sofia (zvb.bg)</i>"
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
        "📋 <b>ГОТОВИ ТЕКСТОВЕ ЗА БЪРЗ КОНТАКТ (ZVB):</b>\n\n"
        "<b>1️⃣ За Строителни фирми (КСБ):</b>\n"
        "<code>Здравейте! Пишем Ви от ZVB (Електрически и умни системи, София). Предлагаме професионално подизпълнение на ел. инсталации, табла и видеонаблюдение с 15г. опит. Работим стриктно по проект и в срок. Тел: +359 87 7944353 | https://zvb.bg</code>\n\n"
        "<b>2️⃣ За Интериорни дизайнери:</b>\n"
        "<code>Здравейте! От ZVB (София) предлагаме прецизна техническа реализация на дизайнерско осветление, скрито LED и Умен Дом (Smart Home). Перфектна естетика без компромиси. Контакт: +359 87 7944353 | https://zvb.bg</code>\n\n"
        "<b>3️⃣ За Клиент след направен оглед:</b>\n"
        "<code>Здравейте! Беше удоволствие да се запознаем при огледа на обекта. Вече подготвяме детайлната оферта за Вашата ел. инсталация. Оставам на Ваше разположение за въпроси. Поздрави, ZVB София | +359 87 7944353</code>\n\n"
        "<i>(Кликнете върху текста за автоматично копиране!)</i>"
    )

def handle_ai_menu():
    return (
        "🧠 <b>МЕНЮ ЗАГРОС AI (ИНЖЕНЕРЕН ЕКСПЕРТ ZVB):</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "درود! من زاگرس، مغز متفکر و مشاور هوشمند مهندسی ZVB هستم.\n"
        "می‌توانید هر سوال فنی، محاسباتی یا متن پیشنهادی را مستقیماً از من بپرسید:\n\n"
        "💡 <b>چند نمونه سوالاتی که می‌توانید در گروه بنویسید:</b>\n"
        "• <code>زاگرس کابل مناسب برای کولر گازی چیه؟</code>\n"
        "• <code>زاگرس برای دوربین مداربسته چه تجهیزاتی پیشنهاد میدی؟</code>\n"
        "• <code>زاگرس متن پیام بعد از بازدید برای کارفرما</code>\n"
        "• <code>زاگرس تجهیزات خانه هوشمند بلغارستان چیه؟</code>\n"
        "• <code>زاگرس استاندارد فیوز و محافظ جان در صوفیه</code>\n\n"
        "👇 یا از موضوعات آماده زیر یکی را انتخاب کنید:"
    )

def get_cables_info():
    return (
        "🧠 <b>Загрос AI: راهنمای فنی کابل‌ها و فیوزها (استاندارد صوفیه / БДС EN 60364):</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🔌 <b>۱. پریزهای عمومی (Контакти):</b>\n"
        "• کابل: <b>ПВВ-МБ1 3x2.5 мм²</b> (یا СВТ / NYM داخل لوله گچی)\n"
        "• کلید مینیاتوری: <b>16A (منحنی B یا C)</b>\n"
        "• استاندارد: حداکثر تا ۸ پریز در یک خط مجزا\n\n"
        "💡 <b>۲. روشنایی (Осветление):</b>\n"
        "• کابل: <b>ПВВ-МБ1 2x1.5 мм²</b> (یا 3x1.5 мм² جهت ارت بدنه لوستر)\n"
        "• کلید مینیاتوری: <b>10A (منحنی B)</b>\n\n"
        "❄️ <b>۳. کولر گازی اسپلیت (Климатик):</b>\n"
        "• کابل: خط کاملاً مستقل <b>3x2.5 мм²</b>\n"
        "• کلید مینیاتوری: <b>16A منحنی C</b> (جهت تحمل جریان هجومی استارت کمپرسور)\n\n"
        "🍳 <b>۴. اجاق و فر برقی (Плот / Фурна):</b>\n"
        "• کابل: خط مستقل <b>3x4.0 мм²</b> (فیوز 25A) یا برای مدل‌های پرمصرف <b>3x6.0 мм²</b> (فیوز 32A)\n\n"
        "🚿 <b>۵. آبگرمکن برقی (Бойлер):</b>\n"
        "• کابل: <b>3x2.5 мм²</b> با فیوز 16A و کلید دوقطبی حفاظت (Двуполюсен ключ)\n\n"
        "⚡ <b>۶. محافظ جان (Дефектнотокова защита - ДТЗ / RCD):</b>\n"
        "• حساسیت <b>30mA تیپ A</b> برای مدار پریزها، حمام و آشپزخانه الزامی است.\n\n"
        "📞 <i>مشاوره تکمیلی و بازدید مهندسی: ZVB София (+359 87 7944353)</i>"
    )

def get_cctv_info():
    return (
        "🧠 <b>Загрос AI: راهنمای سیستم‌های نظارت تصویری و شبکه (ZVB Sofia):</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📹 <b>۱. دوربین‌های پیشنهادی بازار بلغارستان:</b>\n"
        "• برندهای اصلی: <b>Dahua</b> یا <b>Hikvision</b> (حداقل کیفیت 4MP / 5MP با دید در شب رنگی ColorVu/Full-color)\n\n"
        "🌐 <b>۲. بستر شبکه و کابل‌کشی:</b>\n"
        "• داخل ساختمان: کابل تمام مس <b>Cat6 UTP LSZH</b>\n"
        "• محیط بیرونی: کابل ضدآب و شیلددار <b>Cat6 FTP Outdoor</b>\n\n"
        "⚡ <b>۳. تغذیه برق (PoE):</b>\n"
        "• سوئیچ شبکه <b>PoE (استاندارد IEEE 802.3af/at)</b>، امکان ارسال برق و تصویر روی یک کابل تا ۱۰۰ متر بدون افت ولتاژ\n\n"
        "💾 <b>۴. دستگاه ضبط و هارد (NVR):</b>\n"
        "• ضبط‌کننده NVR با پشتیبانی از کدک کم‌حجم <b>H.265+</b>\n"
        "• هارد اختصاصی بنفش نظارتی (WD Purple یا Seagate SkyHawk) — هر ۲ دوربین 4MP حدود ۱ ترابایت برای ۲۰ روز ذخیره‌سازی نیاز دارد\n\n"
        "📱 <b>۵. انتقال تصویر و امنیت:</b>\n"
        "• تنظیم P2P ابری روی اپلیکیشن DMSS (داهوا) یا Hik-Connect با تایید دومرحله‌ای"
    )

def get_smarthome_info():
    return (
        "🧠 <b>Загрос AI: راهنمای سیستم‌های هوشمند (Smart Home Sofia):</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🇧🇬 <b>۱. برند محلی برتر بلغارستان: Shelly (Allterco):</b>\n"
        "شرکت شلی یک برند بین‌المللی بلغاری با مرکزیت صوفیه است و در بلغارستان فوق‌العاده محبوب و قابل اعتماد است:\n"
        "• <b>Shelly Plus 1 / 1PM:</b> ماژول مینیاتوری پشت کلید برای کنترل هوشمند روشنایی و پایش مصرف برق\n"
        "• <b>Shelly Pro 4PM:</b> رله ریلی صنعتی مخصوص نصب داخل جعبه فیوز / تابلو برق با صفحه نمایشگر\n"
        "• <b>Shelly EM:</b> اندازه‌گیری مصرف کل برق خانه با ترانس جریان کلمپی\n\n"
        "⚠️ <b>۲. نکته طلایی در سیم‌کشی برق:</b>\n"
        "حتماً هنگام بازسازی یا سیم‌کشی جدید، <b>سیم نول (Нулев проводник)</b> را به داخل تمام قوطی کلیدها ببرید تا همه مدل کلیدها و ماژول‌های هوشمند بدون مقاومت موازی کار کنند.\n\n"
        "🏛️ <b>۳. پروژه‌های لوکس ویلایی:</b>\n"
        "برای ویلاهای لوکس حومه صوفیه (Boyana, Dragalevtsi, Bistritsa) اجرای سیستم کابلی <b>KNX</b> با پنل‌های لمسی دیواری پیشنهاد می‌شود."
    )

def get_followup_info():
    return (
        "🧠 <b>Загрос AI: متن پیام پیگیری کارفرما پس از بازدید (София):</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "این متن آماده را پس از بازدید محل پروژه در واتساپ یا وایبر برای کارفرما بفرستید:\n\n"
        "<code>Здравейте! Беше удоволствие да се запознаем при огледа на обекта. "
        "Вече подготвяме детайлната оферта и количествено-стойностна сметка за Вашата електроинсталация. "
        "Ако междувременно имате допълнителни въпроси или промени по разпределението на контактите и осветлението, оставам на разположение. "
        "Поздрави, ZVB София | +359 87 7944353 | https://zvb.bg</code>\n\n"
        "<i>(روی کادر بالا ضربه بزنید تا متن خودکار کپی شود)</i>"
    )

def get_builder_pitch():
    return (
        "🧠 <b>Загрос AI: پیشنهاد همکاری رسمی به شرکت ساختمانی (B2B):</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<code>Здравейте! Обръщаме се към Вас от ZVB (Електроинженеринг & Слаботокови инсталации, гр. София). "
        "Предлагаме коректно и качествено подизпълнение за Вашите жилищни и обществени обекти: "
        "цялостно изграждане на електроинсталации, асемблиране на ГРТ и етажни ел. табла, видеонаблюдение, пожароизвестяване и контрол на достъпа. "
        "Разполагаме с квалифициран екип с над 15 години опит, спазваме стриктно строителните графици и предоставяме 5 години пълна гаранция с протокол. "
        "Ще се радваме да изготвим конкурентна оферта по Ваша количествена сметка. "
        "Контакт: +359 87 7944353 | https://zvb.bg</code>\n\n"
        "<i>(روی کادر بالا ضربه بزنید تا متن کپی شود)</i>"
    )

def get_designer_pitch():
    return (
        "🧠 <b>Загрос AI: پیشنهاد همکاری به استودیوهای طراحی و معماران:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<code>Здравейте! От инженерен екип ZVB (София) предлагаме прецизна техническа реализация на дизайнерски интериорни проекти: "
        "безшевно скрито LED осветление с алуминиеви профили, магнитни шини, димиране (DALI, 0-10V, Triac) и цялостна Smart Home автоматизация. "
        "Гарантираме естетика, скрити захранвания без видими дефекти и изпълнение точно по чертеж. "
        "Свържете се с нас за съвместни обекти: +359 87 7944353 | https://zvb.bg</code>\n\n"
        "<i>(روی کادر بالا ضربه بزنید تا متن کپی شود)</i>"
    )

def get_fb_menu():
    return (
        "📱 <b>Загрос AI: رادار شکار پروژه‌های فیسبوک صوفیه</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "در بلغارستان، بیش از ۴۰٪ پروژه‌های برق و بازسازی مستقیماً در گروه‌های فیسبوک صوفیه ثبت می‌شوند!\n\n"
        "🔗 <b>سه گروه طلایی صوفیه برای شکار کار:</b>\n"
        "1. <a href='https://www.facebook.com/groups/remontisofia'>Ремонти София - майстори и клиенти</a>\n"
        "2. <a href='https://www.facebook.com/groups/stroitelstvoiremontisofia'>Строителство и ремонти София</a>\n"
        "3. <a href='https://www.facebook.com/groups/forumremontisofia'>ФОРУМ ЗА СТРОИТЕЛСТВО И РЕМОНТИ СОФИЯ</a>\n\n"
        "🎯 <b>نحوه کار با زاگرس (سرعت ۱۰۰٪ برنده):</b>\n"
        "• هر زمان کارفرمایی در فیسبوک درخواست برق‌کار داد (مثلاً: <i>'Търся електротехник за смяна на табло...'</i>)، متن یا لینک پستش رو کپی کن و اینجا برام بفرست (یا بنویس <code>/fb [متن]</code> یا <code>زاگرس فیسبوک: [متن]</code>).\n"
        "• زاگرس زیر ۲ ثانیه:\n"
        "  ۱. بهترین <b>کامنت رسمی و ترغیب‌کننده</b> با معرفی ZVB را آماده می‌کند.\n"
        "  ۲. یک <b>پیام خصوصی مسنجر (DM)</b> شخصی‌سازی‌شده می‌نویسد.\n"
        "  ۳. <b>تحلیل فنی و برآورد قیمت منصفانه</b> را به فارسی برایت آماده می‌کند!\n\n"
        "💡 <i>در فیسبوک، اولین کامنت حرفه‌ای برنده پروژه است!</i>"
    )

AI_CONVERSATION_HISTORY = {}

ZAGROS_SYSTEM_PROMPT = (
    "تو «زاگرس» (Zagros) هستی؛ مهندس ارشد برق، اتوماسیون خانه هوشمند، سیستم‌های نظارتی و مدیر فنی شرکت ZVB در صوفیه، بلغارستان (https://zvb.bg | +359 87 7944353).\n"
    "شرکت ZVB با بیش از ۱۵ سال سابقه، مجری تخصصی پروژه‌های الکتریکی، تابلو برق، دوربین مداربسته (CCTV)، سیستم‌های هوشمند (Shelly/KNX) و نورپردازی مدرن در صوفیه با ۵ سال گارانتی کتبی و بازدید رایگان است.\n\n"
    "🎯 هویت، لحن و شیوه ارتباط تو:\n"
    "۱. رابطه تو با کاربر:\n"
    "- تو دقیقاً مانند یک دستیار هوش مصنوعی برنامه‌نویسی و مهندسی پیشرفته، باهوش، بسیار مسلط، دلسوز و پرانرژی هستی (دقیقاً مثل یک رفیق، همکار و مهندس ارشد کارکشته).\n"
    "- وقتی کاربر به زبان فارسی با تو صحبت می‌کند: مثل دو تا همکار و رفیق صمیمی در یک کارگاه یا دفتر فنی، با احترام، انرژی مثبت، تسلط کامل و صمیمیت صحبت کن. از جملات خشک اداری، کلیشه‌های ماشینی و تعارفات طولانی خودداری کن و مستقیماً وارد تحلیل مهندسی، گزینه‌های اجرایی، مزایا/معایب و فرمول‌های کاربردی شو.\n"
    "- پاسخ‌هایت باید با ساختار تمیز، تیترها و بولت‌پوینت‌های خوانا و ایموجی‌های مناسب مهندسی باشد تا خواندنش لذت‌بخش و سریع باشد.\n\n"
    "۲. وقتی کاربر از تو متن بلغاری می‌خواهد (برای کارفرما، بسازبفروش، طراح، یا پیش‌فاکتور):\n"
    "- متنی فوق‌العاده روان، اصیل، محترمانه و به زبان بلغاری استاندارد مهندسی (Български) با تمام فوت‌وفن‌های جلب اعتماد بنویس.\n"
    "- اطلاعات شرکت ZVB را همیشه در قالب رسمی زیر درج کن:\n"
    "  ZVB София | Тел: +359 87 7944353 | https://zvb.bg | 15+ г. опит | 5 г. гаранция | Безплатен оглед\n\n"
    "۳. استانداردهای فنی برق که همیشه به آن مسلطی (طبق استاندارد بلغارستان БДС EN 60364):\n"
    "• کابل روشنایی: 3x1.5 mm² با فیوز اتوماتیک 10A تیپ B/C\n"
    "• کابل پریزها: 3x2.5 mm² با فیوز اتوماتیک 16A تیپ B/C\n"
    "• کابل کولرهای گازی / بویلر: 3x4 mm² با فیوز 20A یا 25A\n"
    "• کابل اجاق برقی و فر اصلی: 3x6 mm² تک‌فاز با فیوز 32A یا 5x2.5 mm² سه‌فاز\n"
    "• محافظ جان (ДТЗ / RCD): جریان نشتی 30mA تیپ A برای حمام، بویلر و پریزها\n"
    "• برندهای استاندارد بازار بلغارستان: فیوزهای اشنایدر (Schneider Resi9/Acti9)، نوآرک (Noark)، کابل‌های ПВВ-МБ1 و СВТ مس خالص\n"
    "• خانه هوشمند: ماژول‌های Shelly (Shelly Plus 1PM, Pro 4PM) و الزام آوردن سیم نول به قوطی کلیدها\n"
    "• دوربین مداربسته: Dahua و Hikvision با کابل شبکه Cat6 FTP مس و سوئیچ PoE\n\n"
    "۴. پیوستگی مکالمه:\n"
    "تو سابقه پیام‌های قبلی همین کاربر را می‌دانی، بنابراین اگر سوال تکمیلی پرسید (مثلاً 'خب فیوزش چند باشه؟' یا 'هزینه‌ش چقدر می‌شه؟')، به پروژه و موضوعات قبلی که با هم صحبت کردید ارجاع بده."
)

def ask_zagros_ai(user_query, chat_id="default", context_ref=None):
    """
    Zagros AI Senior Engineer & Commercial Director:
    Conversational AI assistant powered by Gemini with full multi-turn memory.
    """
    cfg = load_config()
    gemini_key = cfg.get("gemini_api_key", "").strip() or os.environ.get("GEMINI_API_KEY", "").strip()
    
    if gemini_key:
        str_chat_id = str(chat_id)
        history = AI_CONVERSATION_HISTORY.get(str_chat_id, [])
        
        turn_text = user_query
        if context_ref:
            turn_text = f"پروژه یا پیامی که کاربر به آن ریپلای زده است:\n«««\n{context_ref[:800]}\n»»»\n\nپیام/سوال کاربر:\n{user_query}"
            
        history.append({"role": "user", "parts": [{"text": turn_text}]})
        
        # Keep last 16 turns in active memory
        if len(history) > 16:
            history = history[-16:]
            
        candidate_models = ["gemini-2.5-flash", "gemini-2.5-flash-lite"]
        for model_name in candidate_models:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={gemini_key}"
                payload = {
                    "contents": history,
                    "systemInstruction": {
                        "parts": [{"text": ZAGROS_SYSTEM_PROMPT}]
                    },
                    "generationConfig": {
                        "temperature": 0.7,
                        "maxOutputTokens": 1500,
                        "thinkingConfig": {
                            "thinkingBudget": 0
                        }
                    }
                }
                r = requests.post(url, json=payload, timeout=10)
                if r.status_code == 200:
                    res = r.json()
                    candidates = res.get("candidates", [])
                    if candidates and "content" in candidates[0]:
                        parts = candidates[0]["content"].get("parts", [])
                        if parts and "text" in parts[0]:
                            answer = parts[0]["text"].strip()
                            # Save model response in conversation history
                            history.append({"role": "model", "parts": [{"text": answer}]})
                            AI_CONVERSATION_HISTORY[str_chat_id] = history
                            return f"🧠 <b>Загрос AI (مهندس ارشد ZVB):</b>\n\n{answer}"
            except Exception as e:
                print(f"Gemini {model_name} error: {e}")

    uq = user_query.lower()
    
    # Technical: Cables & Breakers
    if any(w in uq for w in ['кабел', 'сечение', 'светло', 'светлина', 'святло', 'предпазител', 'автоматичен', 'سیم', 'کابل', 'کولر', 'климатик', 'مقطع', 'فیوز', 'آمپر', 'پریز']):
        return get_cables_info()
    
    # Technical: CCTV & Security
    if any(w in uq for w in ['камер', 'видеонаблюдение', 'nvr', 'dvr', 'دوربین', 'مداربسته', 'شبکه', 'هایک', 'داهوا', 'cctv']):
        return get_cctv_info()

    # Technical: Smart Home & Automation
    if any(w in uq for w in ['умен', 'смарт', 'shelly', 'шли', 'зигби', 'هوشمند', 'شلی', 'خانه هوشمند', 'خانه_هوشمند', 'اتوماسیون']):
        return get_smarthome_info()

    # Technical: Electrical Panels & RCD
    if any(w in uq for w in ['табло', 'дтз', 'дефектнотокова', 'заземяване', 'تابلو', 'جعبه فیوز', 'محافظ جان', 'ارت', 'ارتینگ']):
        return (
            "🧠 <b>Загрос AI: راهنمای فنی تابلو برق و محافظ جان (ZVB Sofia):</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "⚡ <b>۱. ساختار استاندارد تابلو برق خانگی (Ел. Табло):</b>\n"
            "• کلید اتوماتیک اصلی ورودی (Главен прекъсвач): معمولاً 40A یا 50A یا 63A بسته به توان قراردادی با چه‌ز (ЧЕЗ / Electrohold).\n"
            "• رله محافظ جان (ДТЗ / RCD): جریان خطای 30mA تیپ A برای حفاظت از جان و جلوگیری از برق‌گرفتگی در حمام و پریزها.\n"
            "• شینه ارت و نول تفکیک‌شده (سیستم TN-S / TN-C-S) مطابق استاندارد БДС.\n\n"
            "💡 <i>تعویض و سیم‌بندی اصولی تابلو برق با برچسب‌گذاری خطوط و گارانتی ۵ ساله: ZVB Sofia (+359 87 7944353)</i>"
        )

    # Commercial: Follow-up after visit
    if any(w in uq for w in ['оглед', 'клиент', 'след оглед', 'بازدید', 'پیگیری', 'مشتری', 'کارفرما', 'بعد از بازدید']):
        return get_followup_info()

    # Commercial: B2B Pitch to Builder
    if any(w in uq for w in ['строител', 'инвеститор', 'строеж', 'سازنده', 'شرکت ساختمانی', 'پیمانکار', 'بسازبفروش']):
        return get_builder_pitch()

    # Commercial: Pitch to Designer
    if any(w in uq for w in ['дизайнер', 'архитект', 'осветление', 'طراح', 'دیزاینر', 'معمار', 'دکور']):
        return get_designer_pitch()

    # General technical advice fallback
    return (
        f"🧠 <b>Загрос AI (همکار مهندسی ZVB):</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"سلام مهندس جان! در خدمتتم. پیامت رو دیدم:\n<i>'{user_query}'</i>\n\n"
        "در هر زمینه‌ای از پروژه‌های صوفیه سوالی داری با هم بررسیش کنیم:\n"
        "• ⚡ <b>محاسبات فنی:</b> سایز کابل، فیوزها، تابلو برق، خانه هوشمند و دوربین\n"
        "• 💰 <b>پیش‌فاکتور رسمی:</b> بنویس <i>'زاگرس قیمت: آپارتمان ۸۰ متری، تابلو، ۳۰ پریز'</i>\n"
        "• 📝 <b>متن‌های رسمی بلغاری:</b> برای ارسال به کارفرما، شرکت ساختمانی یا دیزاینر\n"
        "• 🔍 <b>استعلام پروژه‌ها:</b> بنویس <i>'زاگرس فوری'</i> یا <i>'زاگرس младост'</i>\n\n"
        "هر سوال یا ایده‌ای داری راحت بگو تا گام‌به‌گام با هم بچینیمش! 🚀"
    )

def handle_facebook_pitch(post_text):
    """
    Zagros Facebook Fast-Pitch Engine:
    Generates high-converting public comment + private DM in Bulgarian + Persian engineering estimate.
    """
    cfg = load_config()
    gemini_key = cfg.get("gemini_api_key", "").strip() or os.environ.get("GEMINI_API_KEY", "").strip()
    if gemini_key:
        prompt = (
            f"این یک پست/درخواست کارفرما در گروه فیسبوک صوفیه برای خدمات الکتریکی است:\n"
            f"«««\n{post_text}\n»»»\n\n"
            "به عنوان زاگرس (مدیر ارشد فنی ZVB София | +359 87 7944353 | https://zvb.bg | 15+ г. опит | 5 г. гаранция | Безплатен оглед):\n"
            "۱. یک کامنت فوق‌العاده جذاب، اصیل، محترمانه و به زبان بلغاری استاندارد (Български) برای درج زیر پست فیسبوک بنویس (با ذکر بازدید رایگان، ۵ سال گارانتی، تجربه ۱۵ ساله و شماره تماس). داخل تگ <code> قرار بده تا با یک لمس کپی شود.\n"
            "۲. یک پیام خصوصی (Лично съобщение в Messenger) به زبان بلغاری برای ارسال مستقیم به کارفرما بنویس داخل تگ <code>.\n"
            "۳. یک تحلیل کوتاه مهندسی و برآورد قیمت تقریبی بازار صوفیه به فارسی برای مجری توضیح بده.\n"
            "پاسخ را با ایموجی‌های مناسب مهندسی، ساختار زیبا و خوانا آماده کن."
        )
        for model_name in ["gemini-2.5-flash", "gemini-2.5-flash-lite"]:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={gemini_key}"
                r = requests.post(url, json={
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "systemInstruction": {"parts": [{"text": ZAGROS_SYSTEM_PROMPT}]},
                    "generationConfig": {
                        "temperature": 0.7,
                        "maxOutputTokens": 1200,
                        "thinkingConfig": {"thinkingBudget": 0}
                    }
                }, timeout=15)
                if r.status_code == 200:
                    ans = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                    return f"📱 <b>Загрос AI: بسته واکنش سریع فیسبوک (Facebook Fast-Pitch):</b>\n━━━━━━━━━━━━━━━━━━━━\n\n{ans}"
            except Exception as e:
                print(f"FB pitch error: {e}")

    # Fallback template
    clean = (
        "Здравейте! От инженерен екип ZVB (София) с удоволствие можем да съдействаме качествено за Вашия електро обект. "
        "Разполагаме с над 15 години опит, работим по БДС стандарти, предлагаме 5 години пълна гаранция и безплатен оглед на място в София. "
        "Моля свържете се с нас: +359 87 7944353 | https://zvb.bg"
    )
    return (
        "📱 <b>Загрос AI: متن آماده پاسخ سریع فیسبوک (Facebook Fast-Pitch):</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📌 <b>متن کامنت برای ارسال زیر پست:</b>\n"
        f"<code>{clean}</code>\n\n"
        "<i>(روی کادر بالا ضربه بزنید تا متن کپی شود)</i>"
    )

def generate_lead_pitch(lead):
    """
    Zagros 1-Click Lead Proposal Generator:
    Creates an irresistible, tailored Bulgarian bid proposal and engineering cost analysis.
    """
    cfg = load_config()
    gemini_key = cfg.get("gemini_api_key", "").strip() or os.environ.get("GEMINI_API_KEY", "").strip()
    title = lead.get("title", "")
    src = lead.get("source", "")
    loc = lead.get("location", "София")
    url = lead.get("url", "")
    
    if gemini_key:
        prompt = (
            f"یک پروژه برقی جدید کشف شده است:\n"
            f"عنوان: {title}\n"
            f"منبع: {src}\n"
            f"مکان: {loc}\n"
            f"لینک: {url}\n\n"
            "به عنوان زاگرس، مدیر فنی و تجاری ZVB София (+359 87 7944353 | https://zvb.bg | 15+ г. опит | 5 г. гаранция | Безплатен оглед):\n"
            "۱. یک پیشنهاد و پیام رسمی، اختصاصی و بسیار قانع‌کننده به زبان بلغاری (Български) بنویس که دقیقاً به نیازهای این پروژه پاسخ دهد و داخل تگ <code> باشد تا کاربر با یک لمس کپی کند.\n"
            "۲. به فارسی برای مجری توضیح بده چه مواردی (سایز کابل، فیوز، نوع تابلو یا دوربین) نیاز است و محدوده قیمت منصفانه و پرسود در بازار صوفیه چقدر است."
        )
        for model_name in ["gemini-2.5-flash", "gemini-2.5-flash-lite"]:
            try:
                r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={gemini_key}", json={
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "systemInstruction": {"parts": [{"text": ZAGROS_SYSTEM_PROMPT}]},
                    "generationConfig": {
                        "temperature": 0.7,
                        "maxOutputTokens": 1200,
                        "thinkingConfig": {"thinkingBudget": 0}
                    }
                }, timeout=15)
                if r.status_code == 200:
                    ans = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                    return f"🧠 <b>Загрос AI: پیشنهاد اختصاصی برای این پروژه:</b>\n━━━━━━━━━━━━━━━━━━━━\n📌 <b>{title[:60]}</b>\n\n{ans}"
            except Exception as e:
                print(f"Lead pitch error: {e}")

    # Fallback
    clean_pitch = (
        f"Здравейте! Пиша Ви от ZVB (Електроинсталации и слаботокови системи, гр. София) относно Вашия проект '{title[:40]}'. "
        "Предлагаме професионално и чисто изпълнение с висококачествени материали, безплатен оглед и 5 години гаранция с протокол. "
        "Оставам на разположение: +359 87 7944353 | https://zvb.bg"
    )
    return (
        f"🧠 <b>Загрос AI: پیشنهاد اختصاصی برای پروژه:</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>{title[:60]}</b>\n\n"
        f"<code>{clean_pitch}</code>\n\n"
        "<i>(روی کادر بالا ضربه بزنید تا متن خودکار کپی شود)</i>"
    )

def handle_search_text(query):
    if not os.path.exists(LEADS_JSON_PATH):
        return None
    with open(LEADS_JSON_PATH, "r", encoding="utf-8") as f:
        leads = json.load(f)
    
    q = query.lower().strip()
    if len(q) < 2:
        return None
        
    matches = []
    for l in leads.values():
        if not daily_digest.is_strictly_electrical_sofia(l):
            continue
        text = (l.get('title', '') + ' ' + l.get('keyword', '') + ' ' + l.get('location', '')).lower()
        if q in text:
            matches.append(l)
    
    if not matches:
        return None
    
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

def realtime_fast_radar(token, group_chat_id):
    """
    ⚡ Ultra-fast 60-second real-time monitor for new electrical client projects in Sofia.
    Ensures ZVB receives instant Telegram ping within <60 seconds of client posting.
    """
    print("⚡ [REAL-TIME RADAR] Active! Scanning for new client projects every 60s...")
    s = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    }
    
    mp_cfg = load_config().get("maistorplus", {})
    username = mp_cfg.get("username")
    password = mp_cfg.get("password")
    
    if not (username and password):
        return

    def do_login():
        try:
            r1 = s.get('https://maistorplus.com/login', headers=headers, timeout=10)
            soup = BeautifulSoup(r1.text, 'html.parser')
            tok = soup.find('input', {'name': '_csrf_token'})
            if not tok:
                return False
            csrf = tok.get('value')
            r2 = s.post('https://maistorplus.com/login_check', data={
                '_csrf_token': csrf,
                '_username': username,
                '_password': password,
                '_remember_me': 'on'
            }, headers=headers, timeout=10)
            return r2.status_code == 200 or '/craftsman' in r2.url
        except Exception:
            return False

    do_login()
    mp_keywords = ['контакт', 'вентилатор', 'ел', 'електро', 'осветлен', 'табло', 'бойлер', 'кабел', 'ключ', 'лед', 'камер', 'умен дом']

    while True:
        try:
            time.sleep(60)
            
            # Check hot open jobs where no phones have been exchanged yet
            r_jobs = s.get('https://maistorplus.com/craftsman/jobs/no-exchanged-phones', headers=headers, timeout=10)
            if r_jobs.status_code != 200 or 'login' in r_jobs.url:
                do_login()
                continue
                
            soup = BeautifulSoup(r_jobs.text, 'html.parser')
            rows = soup.select('table tr')
            
            existing_leads = lead_scraper.load_existing_leads()
            new_discovered = []
            
            for tr in rows:
                tds = tr.find_all('td')
                if len(tds) >= 3:
                    title_td = tds[0]
                    city_td = tds[1] if len(tds) > 1 else None
                    budget_td = tds[2] if len(tds) > 2 else None
                    
                    link_tag = title_td.find('a', href=True) or tr.find('a', href=True)
                    if not link_tag:
                        continue
                        
                    href = link_tag['href'].split('?')[0]
                    full_url = urllib.parse.urljoin('https://maistorplus.com', href)
                    title = title_td.get_text(' ', strip=True)
                    city = city_td.get_text(' ', strip=True) if city_td else 'София'
                    budget = budget_td.get_text(' ', strip=True) if budget_td else ''
                    
                    m = re.search(r'/job/(\d+)', href)
                    job_id = f"mp_{m.group(1)}" if m else f"mp_{hash(href)}"
                    
                    # Verify Sofia and electrical
                    if 'софия' not in city.lower():
                        continue
                    if not any(k in title.lower() for k in mp_keywords):
                        continue
                        
                    if job_id not in existing_leads:
                        new_item = {
                            "id": job_id,
                            "title": f"[MaistorPlus] {title} ({budget})",
                            "url": full_url,
                            "source": "MaistorPlus",
                            "keyword": "Спешна клиентска заявка",
                            "category": "urgent_client",
                            "category_label": "🎯 Директна клиентска заявка (MaistorPlus)",
                            "location": "София",
                            "phone": "",
                            "found_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                        }
                        existing_leads[job_id] = new_item
                        new_discovered.append(new_item)
                        
            # Check Daibau.bg for brand new Sofia electrical projects
            try:
                r_db = requests.get('https://www.daibau.bg/proekti/elektrotehnik_elektroinstalatsii', headers=headers, timeout=10)
                if r_db.status_code == 200:
                    soup_db = BeautifulSoup(r_db.text, 'html.parser')
                    db_items = soup_db.find_all('a', href=lambda h: h and '/proekti/elektrotehnik_elektroinstalatsii/' in h and h.count('/') >= 5)
                    for a in db_items[:10]:
                        href = a['href'].split('?')[0]
                        full_url = urllib.parse.urljoin('https://www.daibau.bg', href)
                        m = re.search(r'/(\d+)$', href)
                        job_id = f"daibau_{m.group(1)}" if m else f"daibau_{hash(href)}"
                        if job_id not in existing_leads:
                            card = a
                            for _ in range(4):
                                if card.parent:
                                    card = card.parent
                            card_text = card.get_text(separator=' | ', strip=True)
                            parts = [p.strip() for p in card_text.split('|') if p.strip()]
                            if any('софия' in p.lower() for p in parts):
                                urgency = ""
                                for p in parts:
                                    if any(u in p.lower() for u in ['веднага', 'спешно', 'месец', 'дни']):
                                        urgency = f" ({p})"
                                        break
                                title = a.get_text(' ', strip=True)
                                new_item = {
                                    "id": job_id,
                                    "title": f"[Daibau] {title}{urgency}",
                                    "url": full_url,
                                    "source": "Daibau",
                                    "keyword": "Спешна клиентска заявка (Daibau)",
                                    "category": "urgent_client",
                                    "category_label": "🎯 Директна клиентска заявка (Daibau.bg)",
                                    "location": "София",
                                    "phone": "",
                                    "found_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                                }
                                existing_leads[job_id] = new_item
                                new_discovered.append(new_item)
            except Exception as e_db:
                print(f"Daibau fast radar check error: {e_db}")

            if new_discovered:
                lead_scraper.save_leads(existing_leads)
                for item in new_discovered:
                    print(f"🚨 [REAL-TIME ALERT] New electrical lead discovered: {item['title']}")
                    lead_scraper.send_telegram_alert(item, token, group_chat_id)
                    time.sleep(0.5)

        except Exception as e:
            print(f"Real-time fast radar error: {e}")

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

    # Start background scheduler threads (Digest + Ultra-Fast 60s Radar)
    if group_chat_id:
        t_sched = threading.Thread(target=background_scheduler, args=(token, group_chat_id), daemon=True)
        t_sched.start()
        t_fast = threading.Thread(target=realtime_fast_radar, args=(token, group_chat_id), daemon=True)
        t_fast.start()

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
                    elif cb_data == "cmd_ai":
                        text = handle_ai_menu()
                        send_msg(token, sender_chat_id, text, get_ai_keyboard())
                    elif cb_data == "cmd_main_menu":
                        send_msg(token, sender_chat_id, get_welcome_text(), get_main_keyboard())
                    elif cb_data == "ai_cables":
                        text = get_cables_info()
                        send_msg(token, sender_chat_id, text, get_ai_keyboard())
                    elif cb_data == "ai_cctv":
                        text = get_cctv_info()
                        send_msg(token, sender_chat_id, text, get_ai_keyboard())
                    elif cb_data == "ai_smarthome":
                        text = get_smarthome_info()
                        send_msg(token, sender_chat_id, text, get_ai_keyboard())
                    elif cb_data == "ai_followup":
                        text = get_followup_info()
                        send_msg(token, sender_chat_id, text, get_ai_keyboard())
                    elif cb_data == "ai_builder":
                        text = get_builder_pitch()
                        send_msg(token, sender_chat_id, text, get_ai_keyboard())
                    elif cb_data == "ai_designer":
                        text = get_designer_pitch()
                        send_msg(token, sender_chat_id, text, get_ai_keyboard())
                    elif cb_data == "cmd_fb":
                        send_msg(token, sender_chat_id, get_fb_menu(), get_main_keyboard())
                    elif cb_data == "cmd_candidates":
                        text, kbd = candidate_manager.get_candidate_list_view()
                        send_msg(token, sender_chat_id, text, kbd)
                    elif cb_data == "cmd_add_cand_help":
                        send_msg(token, sender_chat_id, (
                            "➕ <b>راهنمای افزودن کاندیدای برق‌کار:</b>\n"
                            "━━━━━━━━━━━━━━━━━━━━\n\n"
                            "کافیست در گروه یا چت خصوصی نام، شماره و مهارت‌های فرد را بنویسید:\n\n"
                            "<code>زاگرس اضافه کن: ایوان، 0888123456، مهارت تابلوسازی و لوله‌گذاری، روزمزد ۱۲۰ لوا</code>\n"
                            "یا\n"
                            "<code>/add_cand Георги 0877998811, инсталации, 130 лв/ден</code>\n\n"
                            "زاگرس هوشمندانه اطلاعات را دسته‌بندی و در بانک اطلاعاتی ذخیره می‌کند."
                        ), get_main_keyboard())
                    elif cb_data.startswith("delcand_"):
                        target_id = cb_data[8:]
                        answer_callback(token, cb_id, "در حال حذف کاندید...")
                        ok, name = candidate_manager.delete_candidate_by_query(target_id)
                        if ok:
                            send_msg(token, sender_chat_id, f"🗑 کاندید <b>{name}</b> با موفقیت حذف شد.")
                        text, kbd = candidate_manager.get_candidate_list_view()
                        send_msg(token, sender_chat_id, text, kbd)
                    elif cb_data == "cmd_pdf":
                        send_msg(token, sender_chat_id, (
                            "📑 <b>Загрос AI: صدور پیش‌فاکتور رسمی PDF (ZVB София)</b>\n"
                            "━━━━━━━━━━━━━━━━━━━━\n\n"
                            "برای صدور فوری پیش‌فاکتور رسمی PDF با سربرگ ZVB، لوگو، جدول هزینه‌ها به لِوا (BGN) و ۵ سال گارانتی کتبی، کافی است بنویسید:\n\n"
                            "<code>/pdf آپارتمان ۸۰ متری در ملادوست: تعویض تابلو، ۳۰ پریز، متریال اشنایدر</code>\n"
                            "یا\n"
                            "<code>زاگرس فاکتور: سیم‌کشی کامل ۲ خوابه و نصب آیفون تصویری</code>\n\n"
                            "<i>(روی نمونه‌های بالا ضربه بزنید تا کپی شوند)</i>"
                        ), get_main_keyboard())
                    elif cb_data.startswith("pdf_"):
                        target_id = cb_data[4:]
                        answer_callback(token, cb_id)
                        existing = lead_scraper.load_existing_leads()
                        matched_lead = existing.get(target_id)
                        if not matched_lead:
                            for k, v in existing.items():
                                if target_id in k or k in target_id:
                                    matched_lead = v
                                    break
                        if matched_lead:
                            send_msg(token, sender_chat_id, "⏳ <i>Загрос генерира официална брандирана PDF оферта...</i>")
                            pdf_offer_generator.create_and_send_pdf_offer(
                                token=token,
                                chat_id=sender_chat_id,
                                description=matched_lead.get("title", ""),
                                client_name="Клиент",
                                location=matched_lead.get("location", "гр. София")
                            )
                        else:
                            send_msg(token, sender_chat_id, "❌ Проектът не беше намерен в базата данни.", get_main_keyboard())
                    elif cb_data.startswith("p_"):
                        target_id = cb_data[2:]
                        answer_callback(token, cb_id)
                        existing = lead_scraper.load_existing_leads()
                        matched_lead = existing.get(target_id)
                        if not matched_lead:
                            for k, v in existing.items():
                                if target_id in k or k in target_id:
                                    matched_lead = v
                                    break
                        if matched_lead:
                            send_msg(token, sender_chat_id, "⏳ <i>Загрос анализира проекта и съставя оферта...</i>")
                            pitch_res = generate_lead_pitch(matched_lead)
                            send_msg(token, sender_chat_id, pitch_res, get_main_keyboard())
                        else:
                            send_msg(token, sender_chat_id, "❌ Проектът не беше намерен в базата данни.", get_main_keyboard())

                # 2. Handle Text Messages & Commands
                elif "message" in update:
                    msg = update["message"]
                    sender_chat_id = msg["chat"]["id"]
                    raw_text = msg.get("text", "").strip()
                    
                    if not raw_text:
                        continue
                    
                    lower_text = raw_text.lower()
                    
                    # Check if addressed as "زاگرس" (Zagros), mention @zvbradar_bot, or starts with / command
                    is_command = raw_text.startswith("/")
                    mention_triggers = ["@zvbradar_bot", "@zvbradar", "زاگرس", "zagros"]
                    is_zagros = any(lower_text.startswith(w) or lower_text.startswith(f"{w} ") or lower_text.startswith(f"{w}،") or lower_text.startswith(f"{w}:") for w in mention_triggers)
                    
                    # Detect if user replied to any message from this bot
                    reply_msg = msg.get("reply_to_message", {})
                    is_reply_to_bot = bool(reply_msg.get("from", {}).get("is_bot"))
                    reply_context = reply_msg.get("text", "") if is_reply_to_bot else None
                    
                    # If it's a private chat (DM with bot), respond directly.
                    # In groups, respond if called "زاگرس", mentioned, replied to bot, or command
                    is_private = msg.get("chat", {}).get("type") == "private"
                    
                    # Also trigger directly on candidate actions even without saying "زاگرس"
                    candidate_triggers = [
                        "حذف ", "حذف:", "پاک کن", "پاک:", "اضافه کن", "ثبت کاندید", "کاندیداها", "کاندیدها", "لیست کاندید", "/del_cand", "/add_cand"
                    ]
                    is_candidate_action = any(lower_text.startswith(t) or t in lower_text for t in candidate_triggers)
                    
                    if not (is_command or is_zagros or is_reply_to_bot or is_private or is_candidate_action):
                        # Ignore normal chatter between group members
                        continue
                    
                    # Clean the query if it started with trigger words
                    clean_query = raw_text
                    for w in mention_triggers:
                        if lower_text.startswith(w):
                            clean_query = raw_text[len(w):].strip().lstrip("،,:! ")
                            break
                    
                    if not clean_query or clean_query in ["منو", "menu", "help", "کمک"]:
                        send_msg(token, sender_chat_id, "درود مهندس جان! در خدمتم. می‌توانید بفرمایید چه کاری انجام دهم:\n\n" + get_welcome_text(), get_main_keyboard())
                    elif any(clean_query.lower().startswith(p) for p in ["/pdf", "pdf", "پی دی اف", "فاکتور:", "پیش فاکتور:", "پیش‌فاکتور:", "صدور فاکتور"]) or any(k in clean_query.lower() for k in ["فاکتور رسمی", "pdf رسمی", "پیش فاکتور رسمی", "پیش‌فاکتور رسمی"]):
                        spec = clean_query
                        for w in ["/pdf", "pdf:", "pdf", "پی دی اف:", "پی دی اف", "فاکتور رسمی:", "فاکتور رسمی", "صدور فاکتور:", "صدور فاکتور", "پیش فاکتور رسمی:", "پیش فاکتور رسمی", "پیش‌فاکتور رسمی:", "پیش‌فاکتور رسمی", "فاکتور:", "فاکتور", "پیش فاکتور:", "پیش فاکتور", "پیش‌فاکتور:", "پیش‌فاکتور"]:
                            if clean_query.lower().startswith(w):
                                spec = clean_query[len(w):].strip().lstrip(":, ")
                                break
                        if spec and len(spec) > 5:
                            send_msg(token, sender_chat_id, "⏳ <i>Загрос генерира официална брандирана PDF оферта на ZVB...</i>")
                            pdf_offer_generator.create_and_send_pdf_offer(
                                token=token,
                                chat_id=sender_chat_id,
                                description=spec,
                                client_name="Клиент",
                                location="гр. София"
                            )
                        else:
                            send_msg(token, sender_chat_id, (
                                "📑 <b>Загрос AI: صدور پیش‌فاکتور رسمی PDF (ZVB София)</b>\n"
                                "━━━━━━━━━━━━━━━━━━━━\n\n"
                                "برای صدور فوری پیش‌فاکتور رسمی PDF با سربرگ ZVB، لوگو، جدول هزینه‌ها به لِوا (BGN) و ۵ سال گارانتی کتبی، مشخصات پروژه را بنویسید:\n\n"
                                "<code>/pdf آپارتمان ۸۰ متری در ملادوست: تعویض تابلو، ۳۰ پریز، متریال اشنایدر</code>\n"
                                "یا\n"
                                "<code>زاگرس فاکتور رسمی: سیم‌کشی کامل ۲ خوابه و نصب آیفون تصویری</code>\n\n"
                                "<i>(روی نمونه‌های بالا ضربه بزنید تا کپی شوند)</i>"
                            ), get_main_keyboard())
                    elif any(clean_query.lower().startswith(p) for p in ["اضافه کن", "ثبت کاندید", "کاندید جدید", "افزودن کاندید", "/add_cand", "add_cand"]) or ("اضافه کن" in clean_query.lower() and any(x in clean_query.lower() for x in ["کاندید", "برقکار", "برق‌کار", "شماره"])):
                        cand_text = clean_query
                        for w in ["/add_cand", "add_cand", "اضافه کن به کاندیداها:", "اضافه کن به کاندیداها", "اضافه کن به لیست:", "اضافه کن به لیست", "اضافه کن:", "اضافه کن", "ثبت کاندید:", "ثبت کاندید", "کاندید جدید:", "کاندید جدید", "افزودن کاندید:", "افزودن کاندید"]:
                            if clean_query.lower().startswith(w):
                                cand_text = clean_query[len(w):].strip().lstrip(":, ")
                                break
                        if cand_text and len(cand_text) > 3:
                            send_msg(token, sender_chat_id, "⏳ <i>در حال ثبت و دسته‌بندی مشخصات کاندید...</i>")
                            cands = candidate_manager.add_candidates_from_text(cand_text)
                            if len(cands) > 1:
                                reply = f"✅ <b>تعداد {len(cands)} کاندید برق‌کار به سیستم اضافه شدند:</b>\n━━━━━━━━━━━━━━━━━━━━\n"
                                for c in cands:
                                    reply += f"• <b>{c.get('name')}</b>: <code>{c.get('phone')}</code>\n"
                                reply += "\n💡 برای مشاهده کامل یا حذف هر کدام، از دکمه‌های زیر استفاده کنید:"
                            elif cands:
                                c = cands[0]
                                reply = (
                                    f"✅ <b>کاندید برق‌کار با موفقیت به سیستم اضافه شد!</b>\n"
                                    f"━━━━━━━━━━━━━━━━━━━━\n"
                                    f"👤 <b>نام:</b> {c.get('name')}\n"
                                )
                                if c.get('phone'):
                                    reply += f"📞 <b>شماره:</b> <code>{c.get('phone')}</code>\n"
                                if c.get('skills'):
                                    reply += f"⚡ <b>مهارت‌ها:</b> {c.get('skills')}\n"
                                if c.get('rate'):
                                    reply += f"💰 <b>دستمزد:</b> {c.get('rate')}\n"
                                if c.get('notes'):
                                    reply += f"📝 <b>یادداشت:</b> {c.get('notes')}\n"
                                reply += "\n💡 برای مدیریت یا حذف، روی دکمه‌های زیر بزنید:"
                            else:
                                reply = "❌ خطا در ثبت کاندید."
                            text_list, kbd_list = candidate_manager.get_candidate_list_view()
                            send_msg(token, sender_chat_id, reply, kbd_list)
                        else:
                            send_msg(token, sender_chat_id, "➕ لطفاً مشخصات فرد را بنویسید:\n<code>زاگرس اضافه کن: ایوان، 0888123456، مهارت تابلو و لوله‌گذاری، ۱۲۰ لوا</code>", get_main_keyboard())
                    elif any(clean_query.lower().startswith(p) for p in ["پاک کن", "حذف کن", "حذف ", "حذف:", "پاک ", "پاک:", "/del_cand", "del_cand", "حذف کاندید", "پاک کردن کاندید"]):
                        target_q = clean_query
                        for w in ["/del_cand", "del_cand", "حذف کاندید:", "حذف کاندید", "پاک کن کاندید:", "پاک کن کاندید", "حذف کن:", "حذف کن", "پاک کن:", "پاک کن", "حذف:", "حذف ", "حذف", "پاک:", "پاک ", "پاک"]:
                            if clean_query.lower().startswith(w):
                                target_q = clean_query[len(w):].strip().lstrip(":, ")
                                break
                        if target_q:
                            ok, res_name = candidate_manager.delete_candidate_by_query(target_q)
                            if ok:
                                send_msg(token, sender_chat_id, f"🗑 <b>کاندید «{res_name}» با موفقیت از سیستم حذف شد.</b>")
                                text_list, kbd_list = candidate_manager.get_candidate_list_view()
                                send_msg(token, sender_chat_id, text_list, kbd_list)
                            else:
                                send_msg(token, sender_chat_id, f"❌ {res_name}\nبرای مشاهده لیست بنویسید: <code>زاگرس لیست کاندیداها</code>", get_main_keyboard())
                        else:
                            send_msg(token, sender_chat_id, "🗑 نام یا شماره فردی که می‌خواهید حذف شود را بنویسید:\n<code>حذف بهزاد</code>", get_main_keyboard())
                    elif any(k in clean_query.lower() for k in ["کاندیداها", "کاندیدها", "لیست کاندید", "برقکارها", "برق‌کارها", "candidates", "/candidates"]):
                        text_list, kbd_list = candidate_manager.get_candidate_list_view()
                        send_msg(token, sender_chat_id, text_list, kbd_list)
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
                    elif any(k in clean_query.lower() for k in ["فیسبوک", "facebook", "fb"]):
                        post_body = ""
                        for w in ["/fb", "فیسبوک:", "فیسبوک", "facebook:", "facebook", "fb:", "fb"]:
                            if clean_query.lower().startswith(w):
                                post_body = clean_query[len(w):].strip().lstrip(":, ")
                                break
                        if post_body and len(post_body) > 15:
                            send_msg(token, sender_chat_id, "⏳ <i>Загрос анализира поста от Facebook и подготвя оферта...</i>")
                            send_msg(token, sender_chat_id, handle_facebook_pitch(post_body), get_main_keyboard())
                        else:
                            send_msg(token, sender_chat_id, get_fb_menu(), get_main_keyboard())
                    elif clean_query.startswith("/start") or clean_query.startswith("/help"):
                        send_msg(token, sender_chat_id, get_welcome_text(), get_main_keyboard())
                    elif clean_query.startswith("/calc"):
                        send_msg(token, sender_chat_id, handle_calc_cmd(clean_query), get_main_keyboard())
                    elif clean_query.startswith("/ai"):
                        send_msg(token, sender_chat_id, handle_ai_menu(), get_ai_keyboard())
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
                        # First try keyword search in Sofia electrical database
                        res = handle_search_text(clean_query)
                        if res:
                            send_msg(token, sender_chat_id, res, get_main_keyboard())
                        else:
                            # If no specific database lead matches, route directly to Zagros AI Expert Brain!
                            ai_res = ask_zagros_ai(clean_query, chat_id=sender_chat_id, context_ref=reply_context)
                            send_msg(token, sender_chat_id, ai_res, get_main_keyboard())

        except Exception as e:
            print(f"Bot polling error: {e}")
            time.sleep(3)

if __name__ == "__main__":
    run_telegram_bot()
