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
                {"text": "⚡ Спешни електро запитвания", "callback_data": "cmd_urgent"},
                {"text": "🔍 Сканирай сега (Live)", "callback_data": "cmd_scan"}
            ],
            [
                {"text": "🏗️ Строителни компании (КСБ)", "callback_data": "cmd_builders"},
                {"text": "💎 Интериорни дизайнери", "callback_data": "cmd_designers"}
            ],
            [
                {"text": "📊 Статистика на базата", "callback_data": "cmd_stats"},
                {"text": "📋 Готови оферти", "callback_data": "cmd_pitches"}
            ]
        ]
    }

def get_welcome_text():
    return (
        "⚡ <b>ZVB Интерактивен Радар (София)</b> ⚡\n\n"
        "Здравейте! Аз съм Вашият денонощен асистент за намиране на проекти за електроуслуги, камери и умен дом.\n\n"
        "👇 <b>Изберете действие от бутоните по-долу или напишете ключова дума</b> (напр. <i>'младост', 'табло', 'камери', 'лозенец'</i>):"
    )

def handle_urgent_cmd():
    if not os.path.exists(LEADS_JSON_PATH):
        return "Няма заредени данни."
    with open(LEADS_JSON_PATH, "r", encoding="utf-8") as f:
        leads = json.load(f)
    
    valid = [l for l in leads.values() if daily_digest.is_strictly_electrical_sofia(l)]
    urgent = [l for l in valid if any(w in l.get('title', '').lower() for w in ['търся', 'търси', 'търсим', 'спешно', 'вентилатор'])]
    
    if not urgent:
        return "В момента няма спешни запитвания в София. Всичко е прегледано!"
    
    msg = "🎯 <b>ТОП СПЕШНИ ЗАПИТВАНИЯ ЗА ЕЛЕКТРОТЕХНИК (София):</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
    for idx, l in enumerate(urgent[:5], 1):
        phone = f"\n📞 Телефон: <b>{l.get('phone')}</b>" if l.get('phone') else ""
        msg += f"{idx}. <b>{l.get('title')[:65]}</b>{phone}\n🌐 Източник: {l.get('source')}\n🔗 <a href='{l.get('url')}'>Отвори обявата</a>\n\n"
    msg += "💡 <i>Позвънете бързо преди конкуренцията!</i>"
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
                    elif cb_data == "cmd_pitches":
                        text = handle_pitches_cmd()
                        send_msg(token, sender_chat_id, text, get_main_keyboard())

                # 2. Handle Text Messages & Commands
                elif "message" in update:
                    msg = update["message"]
                    sender_chat_id = msg["chat"]["id"]
                    text = msg.get("text", "").strip()
                    
                    if not text:
                        continue
                    
                    if text.startswith("/start") or text.startswith("/help") or text.lower() in ["menu", "меню", "سلام", "hi", "help"]:
                        send_msg(token, sender_chat_id, get_welcome_text(), get_main_keyboard())
                    elif text.startswith("/scan"):
                        send_msg(token, sender_chat_id, "⏳ <i>Стартирано е сканиране на живо...</i>")
                        lead_scraper.run_scan()
                        send_msg(token, sender_chat_id, "✅ <b>Сканирането завърши!</b>", get_main_keyboard())
                    elif text.startswith("/urgent") or text.startswith("/спешно"):
                        send_msg(token, sender_chat_id, handle_urgent_cmd(), get_main_keyboard())
                    elif text.startswith("/builders") or text.startswith("/строители"):
                        send_msg(token, sender_chat_id, handle_builders_cmd(), get_main_keyboard())
                    elif text.startswith("/designers") or text.startswith("/дизайнери"):
                        send_msg(token, sender_chat_id, handle_designers_cmd(), get_main_keyboard())
                    elif text.startswith("/stats") or text.startswith("/статистика"):
                        send_msg(token, sender_chat_id, handle_stats_cmd(), get_main_keyboard())
                    else:
                        # Perform live keyword search in database
                        res = handle_search_text(text)
                        send_msg(token, sender_chat_id, res, get_main_keyboard())

        except Exception as e:
            print(f"Bot polling error: {e}")
            time.sleep(3)

if __name__ == "__main__":
    run_telegram_bot()
