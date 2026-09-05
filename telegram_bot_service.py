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
        "• 💰 <b>پیش‌فاکتور رسمی بلغاری:</b> 'زاگرس قیمت: آپارتمان ۸۰ متری، تابلو برق، ۳۰ پریز، ۴ دوربین'\n"
        "• ⚡ <b>پروژه‌های فوری:</b> مشاهده آخرین تماس‌ها و درخواست‌های کارفرمایان برق در صوفیه\n"
        "• 🔍 <b>جستجوی محله/تجهیزات:</b> 'زاگرس младост' یا 'زاگرس камери'"
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

def ask_zagros_ai(user_query):
    """
    Zagros AI Expert Assistant:
    Acts as Senior Electrical Engineer & Commercial Director for ZVB in Sofia.
    Handles technical calculations, drafting Bulgarian client pitches, and consultations.
    """
    cfg = load_config()
    gemini_key = cfg.get("gemini_api_key", "").strip() or os.environ.get("GEMINI_API_KEY", "").strip()
    
    system_prompt = (
        "Ти си Загрос (Zagros) - виртуален старши електроинженер и търговски директор на ZVB "
        "(Електрически системи, видеонаблюдение, LED осветление и Smart Home в гр. София, България | https://zvb.bg | Тел: +359 87 7944353). "
        "Фирмата има над 15 години доказан опит, предлага 5 години гаранция и безплатен оглед в София. "
        "Отговаряй учтиво, професионално, конкретно и ясно на езика, на който ти пишат (български или персийски). "
        "Ако те питаت за технически въпроси по ел. инсталации, кабели, предпазители или камери - дай точен инженерен съвет. "
        "Ако искат оферта или съобщение за клиент/строител - напиши перфектен текст за изпращане с данните на ZVB."
    )

    if gemini_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
            payload = {
                "contents": [
                    {"role": "user", "parts": [{"text": f"System Context:\n{system_prompt}\n\nUser Question:\n{user_query}"}]}
                ]
            }
            r = requests.post(url, json=payload, timeout=12)
            if r.status_code == 200:
                res = r.json()
                answer = res["candidates"][0]["content"]["parts"][0]["text"]
                return f"🧠 <b>Загрос AI (Инженерен асистент ZVB):</b>\n\n{answer}"
        except Exception as e:
            print(f"AI API error: {e}")

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
        f"🧠 <b>Загрос AI (ZVB Електро Експерт):</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"درود! پیام شما دریافت شد: <i>'{user_query}'</i>\n\n"
        "من به عنوان دستیار هوشمند مهندسی <b>ZVB در صوفیه</b> می‌توانم در این موارد به شما کمک کنم:\n"
        "1. ⚡ <b>مشاوره مهندسی:</b> کابل‌ها، فیوزها، تابلو برق، خانه هوشمند و دوربین مداربسته\n"
        "2. 💰 <b>پیش‌فاکتور رسمی:</b> بنویسید <i>'زاگرس قیمت: آپارتمان ۸۰ متری، تابلو، ۳۰ پریز'</i>\n"
        "3. 📝 <b>متن‌های رسمی بلغاری:</b> برای بسازبفروش‌ها، دیزاینرها، یا پیگیری مشتری بعد از بازدید\n"
        "4. 🔍 <b>جستجوی پروژه‌ها:</b> بنویسید <i>'زاگرس младост'</i> یا <i>'زاگرس فوری'</i>\n\n"
        "🌐 <i>ZVB Sofia - Професионални електрически и умни решения | zvb.bg</i>"
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
                    elif any(k in clean_query.lower() for k in ["هوش", "ai", "مشاوره", "بپرس", "سوال"]):
                        send_msg(token, sender_chat_id, ask_zagros_ai(clean_query), get_main_keyboard())
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
                            ai_res = ask_zagros_ai(clean_query)
                            send_msg(token, sender_chat_id, ai_res, get_main_keyboard())

        except Exception as e:
            print(f"Bot polling error: {e}")
            time.sleep(3)

if __name__ == "__main__":
    run_telegram_bot()
